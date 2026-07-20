import queue
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from iso_builder.constants import PROFILE_AUTO
from iso_builder.gui.app import IsoBuilderApp
from iso_builder.models import (
    Backend,
    BuildExecutionResult,
    BuildOptions,
    BuildPlan,
    BuildRequest,
    ScanResult,
    UIEvent,
)


class _Value:
    def __init__(self, value):
        self.value = value
        self.get_threads = []

    def get(self):
        self.get_threads.append(threading.get_ident())
        return self.value

    def set(self, value):
        self.value = value


class _ScanHarness:
    _operation_is_active = IsoBuilderApp._operation_is_active
    _begin_operation = IsoBuilderApp._begin_operation
    _finish_operation = IsoBuilderApp._finish_operation
    _scan_worker = IsoBuilderApp._scan_worker
    thread_operation_finished = IsoBuilderApp.thread_operation_finished

    def __init__(self, source_dir):
        self.source_var = _Value(source_dir)
        self.profile_var = _Value(PROFILE_AUTO)
        self.include_hidden_var = _Value(True)
        self.ui_queue = queue.Queue()
        self.worker = None
        self.active_operation = None
        self.statuses = []
        self.scans = []
        self.logs = []

    def _set_status(self, title, detail):
        self.statuses.append((title, detail))

    def print_scan(self, scan):
        self.scans.append(scan)

    def log(self, message):
        self.logs.append(message)


class _PlanningHarness:
    _operation_is_active = IsoBuilderApp._operation_is_active
    _begin_operation = IsoBuilderApp._begin_operation
    _finish_operation = IsoBuilderApp._finish_operation
    _prepare_worker = IsoBuilderApp._prepare_worker
    thread_operation_finished = IsoBuilderApp.thread_operation_finished

    def __init__(self, request, backend):
        self.request = request
        self.detected_backends = [backend]
        self.ui_queue = queue.Queue()
        self.worker = None
        self.active_operation = None
        self.snapshot_threads = []
        self.statuses = []

    def snapshot_build_request(self):
        self.snapshot_threads.append(threading.get_ident())
        return self.request

    def _set_status(self, title, detail):
        self.statuses.append((title, detail))


class GuiThreadingTests(unittest.TestCase):
    """Capture threading behavior while Fix 4 is implemented incrementally."""

    def test_scan_only_runs_folder_scan_on_background_thread(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            app = _ScanHarness(source_dir)

            caller_thread = threading.get_ident()
            scan_threads = []
            scan_started = threading.Event()
            release_scan = threading.Event()

            def record_scan(*_args):
                scan_threads.append(threading.get_ident())
                scan_started.set()
                if not release_scan.wait(timeout=2):
                    raise RuntimeError("Test did not release scan worker.")
                return ScanResult()

            with patch("iso_builder.gui.app.scan_source_folder", side_effect=record_scan):
                IsoBuilderApp.scan_only(app)
                try:
                    self.assertTrue(scan_started.wait(timeout=1))
                    self.assertTrue(app.worker.is_alive())
                    self.assertEqual(app.active_operation, "scan")
                    self.assertNotEqual(scan_threads, [caller_thread])
                    widget_reads = (
                        app.source_var.get_threads
                        + app.profile_var.get_threads
                        + app.include_hidden_var.get_threads
                    )
                    self.assertTrue(widget_reads)
                    self.assertEqual(set(widget_reads), {caller_thread})
                finally:
                    release_scan.set()
                    app.worker.join(timeout=2)

            self.assertFalse(app.worker.is_alive())
            events = list(app.ui_queue.queue)
            self.assertEqual([event.kind for event in events], ["scan_complete", "operation_finished"])
            self.assertIsInstance(events[0].payload, ScanResult)

    def test_scan_worker_reports_error_through_queue(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            app = _ScanHarness(source_dir)

            with patch(
                "iso_builder.gui.app.scan_source_folder",
                side_effect=PermissionError("scan denied"),
            ):
                IsoBuilderApp.scan_only(app)
                app.worker.join(timeout=2)

            events = list(app.ui_queue.queue)
            self.assertEqual([event.kind for event in events], ["operation_error", "operation_finished"])
            self.assertEqual(events[0].message, "scan")
            self.assertEqual(events[0].detail, "scan denied")
            self.assertEqual(app.statuses, [("Scanning folder...", str(Path(source_dir)))])
            self.assertEqual(app.scans, [])
            self.assertEqual(app.logs, [])

    def test_prepare_helper_runs_build_planning_on_calling_thread(self) -> None:
        source = Path("source").resolve()
        output_iso = Path("output.iso").resolve()
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        request = BuildRequest(
            source_text=str(source),
            output_text=str(output_iso.parent),
            iso_name_text=output_iso.name,
            label_text="TEST",
            backend_choice="Auto",
            options=options,
        )
        plan = BuildPlan(
            source=source,
            output_iso=output_iso,
            label="TEST",
            backend=backend,
            scan=ScanResult(),
            command=["oscdimg.exe"],
            warnings=[],
            options=options,
        )

        app = type("PrepareHarness", (), {})()
        app.detected_backends = [backend]
        app.iso_name_var = _Value("")
        app.label_var = _Value("")

        caller_thread = threading.get_ident()
        planner_threads = []

        def record_planning(*_args):
            planner_threads.append(threading.get_ident())
            return plan

        with patch("iso_builder.gui.app.prepare_build_plan", side_effect=record_planning):
            actual = IsoBuilderApp.prepare(app, request)

        self.assertIs(actual, plan)
        self.assertEqual(planner_threads, [caller_thread])

    def test_show_command_runs_planning_on_background_thread(self) -> None:
        source = Path("source").resolve()
        output_iso = Path("output.iso").resolve()
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        request = BuildRequest(
            source_text=str(source),
            output_text=str(output_iso.parent),
            iso_name_text=output_iso.name,
            label_text="TEST",
            backend_choice="Auto",
            options=options,
        )
        plan = BuildPlan(
            source=source,
            output_iso=output_iso,
            label="TEST",
            backend=backend,
            scan=ScanResult(),
            command=["oscdimg.exe"],
            warnings=[],
            options=options,
        )
        app = _PlanningHarness(request, backend)

        caller_thread = threading.get_ident()
        planner_threads = []
        planning_started = threading.Event()
        release_planning = threading.Event()

        def record_planning(actual_request, actual_backends):
            self.assertIs(actual_request, request)
            self.assertEqual(actual_backends, [backend])
            planner_threads.append(threading.get_ident())
            planning_started.set()
            if not release_planning.wait(timeout=2):
                raise RuntimeError("Test did not release command planning worker.")
            return plan

        with patch("iso_builder.gui.app.prepare_build_plan", side_effect=record_planning):
            IsoBuilderApp.show_command(app)
            try:
                self.assertTrue(planning_started.wait(timeout=1))
                self.assertTrue(app.worker.is_alive())
                self.assertEqual(app.active_operation, "command")
                self.assertEqual(app.snapshot_threads, [caller_thread])
                self.assertEqual(len(planner_threads), 1)
                self.assertNotEqual(planner_threads[0], caller_thread)
            finally:
                release_planning.set()
                app.worker.join(timeout=2)

        self.assertFalse(app.worker.is_alive())
        self.assertEqual(
            app.statuses,
            [("Preparing command...", "Scanning source folder")],
        )
        events = list(app.ui_queue.queue)
        self.assertEqual([event.kind for event in events], ["plan_complete", "operation_finished"])
        self.assertEqual(events[0].message, "command")
        self.assertIs(events[0].payload, plan)

    def test_command_worker_reports_error_through_queue(self) -> None:
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        request = BuildRequest(
            source_text="source",
            output_text="output",
            iso_name_text="output.iso",
            label_text="TEST",
            backend_choice="Auto",
            options=options,
        )
        app = _PlanningHarness(request, backend)

        with patch(
            "iso_builder.gui.app.prepare_build_plan",
            side_effect=ValueError("planning failed"),
        ):
            IsoBuilderApp.show_command(app)
            app.worker.join(timeout=2)

        events = list(app.ui_queue.queue)
        self.assertEqual([event.kind for event in events], ["operation_error", "operation_finished"])
        self.assertEqual(events[0].message, "command")
        self.assertEqual(events[0].detail, "planning failed")

    def test_start_build_runs_planning_on_background_thread(self) -> None:
        source = Path("source").resolve()
        output_iso = Path("output.iso").resolve()
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        request = BuildRequest(
            source_text=str(source),
            output_text=str(output_iso.parent),
            iso_name_text=output_iso.name,
            label_text="TEST",
            backend_choice="Auto",
            options=options,
        )
        plan = BuildPlan(
            source=source,
            output_iso=output_iso,
            label="TEST",
            backend=backend,
            scan=ScanResult(),
            command=["oscdimg.exe"],
            warnings=[],
            options=options,
        )
        app = _PlanningHarness(request, backend)

        caller_thread = threading.get_ident()
        planner_threads = []
        planning_started = threading.Event()
        release_planning = threading.Event()

        def record_planning(actual_request, actual_backends):
            self.assertIs(actual_request, request)
            self.assertEqual(actual_backends, [backend])
            planner_threads.append(threading.get_ident())
            planning_started.set()
            if not release_planning.wait(timeout=2):
                raise RuntimeError("Test did not release build planning worker.")
            return plan

        with patch("iso_builder.gui.app.prepare_build_plan", side_effect=record_planning):
            IsoBuilderApp.start_build(app)
            try:
                self.assertTrue(planning_started.wait(timeout=1))
                self.assertTrue(app.worker.is_alive())
                self.assertEqual(app.active_operation, "build")
                self.assertEqual(app.snapshot_threads, [caller_thread])
                self.assertEqual(len(planner_threads), 1)
                self.assertNotEqual(planner_threads[0], caller_thread)
            finally:
                release_planning.set()
                app.worker.join(timeout=2)

        self.assertFalse(app.worker.is_alive())
        self.assertEqual(
            app.statuses,
            [("Preparing build...", "Scanning source folder")],
        )
        events = list(app.ui_queue.queue)
        self.assertEqual([event.kind for event in events], ["plan_complete"])
        self.assertEqual(events[0].message, "build")
        self.assertIs(events[0].payload, plan)
        self.assertEqual(app.active_operation, "build")

    def test_build_planning_error_releases_operation_through_queue(self) -> None:
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        request = BuildRequest(
            source_text="source",
            output_text="output",
            iso_name_text="output.iso",
            label_text="TEST",
            backend_choice="Auto",
            options=options,
        )
        app = _PlanningHarness(request, backend)

        with patch(
            "iso_builder.gui.app.prepare_build_plan",
            side_effect=ValueError("build planning failed"),
        ):
            IsoBuilderApp.start_build(app)
            app.worker.join(timeout=2)

        events = list(app.ui_queue.queue)
        self.assertEqual([event.kind for event in events], ["operation_error", "operation_finished"])
        self.assertEqual(events[0].message, "build")
        self.assertEqual(events[0].detail, "build planning failed")

    def test_build_warning_dialog_and_cancel_run_on_calling_thread(self) -> None:
        source = Path("source").resolve()
        output_iso = Path("output.iso").resolve()
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        plan = BuildPlan(
            source=source,
            output_iso=output_iso,
            label="TEST",
            backend=backend,
            scan=ScanResult(warnings=["test warning"]),
            command=["oscdimg.exe"],
            warnings=[],
            options=options,
        )
        app = type("BuildPlanHarness", (), {})()
        app.active_operation = "build"
        app.worker = None
        app.iso_name_var = _Value("")
        app.label_var = _Value("")
        app.statuses = []
        app.logs = []
        app._set_status = lambda title, detail: app.statuses.append((title, detail))
        app.log = app.logs.append
        app._finish_operation = IsoBuilderApp._finish_operation.__get__(app)
        app._handle_build_plan_ready = IsoBuilderApp._handle_build_plan_ready.__get__(app)

        caller_thread = threading.get_ident()
        dialog_threads = []

        def cancel_build(*_args, **_kwargs):
            dialog_threads.append(threading.get_ident())
            return False

        with patch("iso_builder.gui.app.messagebox.askyesno", side_effect=cancel_build):
            IsoBuilderApp._handle_plan_complete(app, "build", plan)

        self.assertEqual(dialog_threads, [caller_thread])
        self.assertIsNone(app.active_operation)
        self.assertEqual(
            app.statuses,
            [("Build cancelled", "User cancelled after reviewing scan warnings")],
        )
        self.assertEqual(app.logs, ["Build cancelled by user after warnings."])

    def test_ready_build_plan_runs_executor_and_queues_completion(self) -> None:
        source = Path("source").resolve()
        output_iso = Path("output.iso").resolve()
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
            priority=1,
            description="test",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        options = BuildOptions(
            profile=PROFILE_AUTO,
            include_hidden=True,
            generate_hash=True,
            optimize_duplicates=False,
            auto_package=False,
            dry_run=True,
        )
        plan = BuildPlan(
            source=source,
            output_iso=output_iso,
            label="TEST",
            backend=backend,
            scan=ScanResult(),
            command=["oscdimg.exe"],
            warnings=[],
            options=options,
        )
        app = type("BuildExecutionHarness", (), {})()
        app.active_operation = "build"
        app.worker = None
        app.ui_queue = queue.Queue()
        app.statuses = []
        app._set_status = lambda title, detail: app.statuses.append((title, detail))
        app._build_worker = IsoBuilderApp._build_worker.__get__(app)
        app.thread_log = IsoBuilderApp.thread_log.__get__(app)
        app.thread_status = IsoBuilderApp.thread_status.__get__(app)
        app.thread_operation_finished = IsoBuilderApp.thread_operation_finished.__get__(app)
        app._finish_operation = IsoBuilderApp._finish_operation.__get__(app)
        app._handle_operation_error = IsoBuilderApp._handle_operation_error.__get__(app)

        result = BuildExecutionResult(outcome="DRY RUN", output_iso=output_iso)
        with patch("iso_builder.gui.app.execute_build_plan", return_value=result):
            IsoBuilderApp._handle_build_plan_ready(app, plan)
            app.worker.join(timeout=2)

        self.assertFalse(app.worker.is_alive())
        self.assertEqual(app.statuses, [("Building ISO...", f"Source: {source.name}")])
        events = list(app.ui_queue.queue)
        self.assertEqual(
            [(event.kind, event.message, event.detail) for event in events],
            [
                ("status", "Build started", "Using backend: oscdimg"),
                ("status", "Dry run finished", "Output preview: output.iso"),
                ("operation_finished", "build", ""),
            ],
        )
        self.assertEqual(app.active_operation, "build")


class UiEventTests(unittest.TestCase):
    def test_ui_event_is_immutable(self) -> None:
        event = UIEvent(kind="status", message="Scanning", detail="Please wait")

        with self.assertRaises(FrozenInstanceError):
            event.message = "Changed"

    def test_worker_helpers_enqueue_typed_events(self) -> None:
        app = type("QueueHarness", (), {})()
        app.ui_queue = queue.Queue()

        IsoBuilderApp.thread_log(app, "line")
        IsoBuilderApp.thread_status(app, "Scanning", "Please wait")
        IsoBuilderApp.thread_operation_finished(app, "scan")

        self.assertEqual(
            list(app.ui_queue.queue),
            [
                UIEvent(kind="log", message="line"),
                UIEvent(kind="status", message="Scanning", detail="Please wait"),
                UIEvent(kind="operation_finished", message="scan"),
            ],
        )

    def test_main_thread_dispatches_events_and_clears_matching_operation(self) -> None:
        app = type("DispatchHarness", (), {})()
        app.ui_queue = queue.Queue()
        app.active_operation = "scan"
        app.logs = []
        app.statuses = []
        app.scans = []
        app.after_calls = []
        app.log = app.logs.append
        app._set_status = lambda title, hint: app.statuses.append((title, hint))
        app.print_scan = lambda scan: app.scans.append((scan, threading.get_ident()))
        app._finish_operation = IsoBuilderApp._finish_operation.__get__(app)
        app._handle_scan_complete = IsoBuilderApp._handle_scan_complete.__get__(app)
        app._handle_plan_complete = IsoBuilderApp._handle_plan_complete.__get__(app)
        app._handle_operation_error = IsoBuilderApp._handle_operation_error.__get__(app)
        app._process_ui_queue = IsoBuilderApp._process_ui_queue.__get__(app)
        app.after = lambda delay, callback: app.after_calls.append((delay, callback))

        scan = ScanResult(files=3, total_bytes=1024)
        app.ui_queue.put(UIEvent(kind="scan_complete", payload=scan))
        app.ui_queue.put(UIEvent(kind="log", message="line"))
        app.ui_queue.put(UIEvent(kind="status", message="Done", detail="3 files"))
        app.ui_queue.put(UIEvent(kind="operation_finished", message="scan"))

        caller_thread = threading.get_ident()
        IsoBuilderApp._process_ui_queue(app)

        self.assertEqual(app.logs, ["line"])
        self.assertEqual(
            app.statuses,
            [
                ("Scan complete", "3 files | 1.00 KB total size"),
                ("Done", "3 files"),
            ],
        )
        self.assertEqual(app.scans, [(scan, caller_thread)])
        self.assertIsNone(app.active_operation)
        self.assertEqual(app.after_calls, [(150, app._process_ui_queue)])

    def test_only_one_operation_can_be_active(self) -> None:
        app = type("OperationHarness", (), {})()
        app.active_operation = None
        app.worker = None
        app._operation_is_active = IsoBuilderApp._operation_is_active.__get__(app)

        self.assertTrue(IsoBuilderApp._begin_operation(app, "scan"))
        self.assertFalse(IsoBuilderApp._begin_operation(app, "build"))
        self.assertEqual(app.active_operation, "scan")

        IsoBuilderApp._finish_operation(app, "build")
        self.assertEqual(app.active_operation, "scan")

        IsoBuilderApp._finish_operation(app, "scan")
        self.assertIsNone(app.active_operation)


if __name__ == "__main__":
    unittest.main()
