import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from PySide6.QtCore import QCoreApplication, QUrl
except ImportError:  # pragma: no cover - core-only environments skip Qt tests
    QCoreApplication = None
    QUrl = None

from iso_builder.models import (
    Backend,
    BuildExecutionResult,
    BuildPlan,
    ScanResult,
)


def make_backend() -> Backend:
    return Backend(
        name="oscdimg",
        executable="oscdimg.exe",
        priority=10,
        description="test backend",
        supports_udf=True,
        supports_joliet=True,
        supports_iso_level3=True,
        source="test",
    )


def make_plan(request, backend: Backend) -> BuildPlan:
    output_iso = Path(request.output_text) / request.iso_name_text
    return BuildPlan(
        source=Path(request.source_text),
        output_iso=output_iso,
        label=request.label_text,
        backend=backend,
        scan=ScanResult(files=3, total_bytes=4096),
        command=[
            backend.executable,
            request.source_text,
            str(output_iso),
        ],
        warnings=[],
        options=request.options,
    )


@unittest.skipIf(QCoreApplication is None, "PySide6 GUI dependency is not installed")
class QtRealBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def wait_until(self, predicate, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.application.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt real-build state")

    def make_ready_bridge(self, root: Path, *, planner, executor, cleanup=lambda _command: None):
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        source = root / "Source"
        output = root / "Output"
        source.mkdir()
        output.mkdir()
        bridge = QtIsoBridge(
            detector=lambda: [backend],
            scanner=lambda *_args: ScanResult(files=3, total_bytes=4096),
            planner=planner,
            executor=executor,
            command_cleanup=cleanup,
        )
        bridge.refreshBackends()
        bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
        self.wait_until(lambda: not bridge.isScanning)
        bridge.selectOutputFolder(QUrl.fromLocalFile(str(output)))
        bridge.setAutoPackage(False)
        bridge.setIsoName("real.iso")
        bridge.setVolumeLabel("REAL")
        return bridge, backend, source, output

    def test_real_build_uses_non_dry_snapshot_off_ui_thread(self) -> None:
        planner_requests = []
        executor_threads = []
        cancellation_tokens = []
        cleaned_commands = []

        def planner(request, backends):
            planner_requests.append(request)
            return make_plan(request, backends[0])

        def executor(plan, log, cancellation):
            executor_threads.append(threading.get_ident())
            cancellation_tokens.append(cancellation)
            log("Build started")
            log("Storage preflight: controlled")
            log("Transactional execution command:")
            log("50% complete")
            plan.output_iso.write_bytes(b"ISO")
            hash_path = plan.output_iso.with_suffix(".iso.sha256.txt")
            hash_path.write_text("controlled", encoding="utf-8")
            log(f"ISO created: {plan.output_iso}")
            log(f"Hash saved: {hash_path}")
            log("Build finished: PASS")
            return BuildExecutionResult(
                outcome="PASS",
                output_iso=plan.output_iso,
                hash_path=hash_path,
                sha256="controlled",
            )

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
                cleanup=lambda command: cleaned_commands.append(list(command)),
            )
            calling_thread = threading.get_ident()
            self.assertTrue(bridge.canStartBuild)
            bridge.startBuild()
            self.assertTrue(bridge.isBuildRunning)
            self.wait_until(lambda: not bridge.isBuildRunning)

            self.assertEqual(len(planner_requests), 1)
            self.assertFalse(planner_requests[0].options.dry_run)
            self.assertNotEqual(executor_threads[0], calling_thread)
            self.assertEqual(len(cancellation_tokens), 1)
            self.assertEqual(bridge.executionMode, "BUILD")
            self.assertEqual(bridge.buildOutcome, "PASS")
            self.assertEqual(bridge.buildStatusText, "Build complete")
            self.assertEqual(bridge.buildProgressPercent, 100)
            self.assertFalse(bridge.buildProgressIndeterminate)
            self.assertIn("50% complete", bridge.buildLogText)
            self.assertEqual(bridge.lastExecutionOutput, str(output / "real.iso"))
            self.assertEqual(
                bridge.buildHashPath,
                str(output / "real.iso.sha256.txt"),
            )
            self.assertEqual(len(cleaned_commands), 1)

    def test_cancel_requests_shared_token_and_reports_cancelled(self) -> None:
        executor_started = threading.Event()
        received_token = []

        def planner(request, backends):
            return make_plan(request, backends[0])

        def executor(plan, log, cancellation):
            received_token.append(cancellation)
            executor_started.set()
            log("Build started")
            while not cancellation.is_cancelled():
                time.sleep(0.005)
            log("Build finished: CANCELLED")
            return BuildExecutionResult(
                outcome="CANCELLED",
                output_iso=plan.output_iso,
                error="Build cancelled by user.",
            )

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            bridge.startBuild()
            self.wait_until(executor_started.is_set)
            bridge.cancelBuild()
            self.wait_until(lambda: not bridge.isBuildRunning)

            self.assertEqual(len(received_token), 1)
            self.assertTrue(received_token[0].is_cancelled())
            self.assertEqual(bridge.buildOutcome, "CANCELLED")
            self.assertEqual(bridge.buildStatusText, "Build cancelled")
            self.assertFalse((output / "real.iso").exists())

    def test_close_request_cancels_then_emits_safe_to_close(self) -> None:
        executor_started = threading.Event()

        def planner(request, backends):
            return make_plan(request, backends[0])

        def executor(plan, _log, cancellation):
            executor_started.set()
            while not cancellation.is_cancelled():
                time.sleep(0.005)
            return BuildExecutionResult(
                outcome="CANCELLED",
                output_iso=plan.output_iso,
                error="Build cancelled by user.",
            )

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, _output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            close_notifications = []
            bridge.safeToClose.connect(lambda: close_notifications.append(True))
            bridge.startBuild()
            self.wait_until(executor_started.is_set)
            bridge.requestCloseAfterCancel()
            self.wait_until(lambda: bool(close_notifications))

            self.assertFalse(bridge.isBuildRunning)
            self.assertEqual(bridge.buildOutcome, "CANCELLED")
            self.assertEqual(close_notifications, [True])

    def test_planning_failure_never_calls_real_executor(self) -> None:
        executor_called = False

        def planner(_request, _backends):
            raise ValueError("controlled real-build planning failure")

        def executor(_plan, _log, _cancellation):
            nonlocal executor_called
            executor_called = True
            raise AssertionError("executor must not run after planning failure")

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, _output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            bridge.startBuild()
            self.wait_until(lambda: not bridge.isBuildRunning)

        self.assertFalse(executor_called)
        self.assertEqual(bridge.buildOutcome, "FAIL")
        self.assertIn("controlled real-build planning failure", bridge.buildError)

    def test_dry_plan_is_rejected_before_real_executor(self) -> None:
        executor_called = False

        def planner(request, backends):
            plan = make_plan(request, backends[0])
            plan.options = type(request.options)(
                profile=request.options.profile,
                include_hidden=request.options.include_hidden,
                generate_hash=request.options.generate_hash,
                optimize_duplicates=request.options.optimize_duplicates,
                auto_package=request.options.auto_package,
                dry_run=True,
            )
            return plan

        def executor(_plan, _log, _cancellation):
            nonlocal executor_called
            executor_called = True
            raise AssertionError("dry plan must not enter real executor")

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, _output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            bridge.startBuild()
            self.wait_until(lambda: not bridge.isBuildRunning)

        self.assertFalse(executor_called)
        self.assertEqual(bridge.buildOutcome, "FAIL")
        self.assertIn("dry-run plan", bridge.buildError)

    def test_progress_parser_only_uses_explicit_percent_output(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        self.assertEqual(
            QtIsoBridge._progress_from_log("37% complete"),
            ("Creating ISO...", 0.37, False),
        )
        self.assertEqual(
            QtIsoBridge._progress_from_log("Files: 37"),
            ("", 0.0, False),
        )
        self.assertEqual(
            QtIsoBridge._progress_from_log("Transactional execution command:"),
            ("Creating ISO...", 0.28, True),
        )

    def test_scan_warnings_pause_executor_until_user_approves(self) -> None:
        executor_called = False

        def planner(request, backends):
            plan = make_plan(request, backends[0])
            plan.scan.warnings = ["controlled source warning"]
            return plan

        def executor(plan, _log, _cancellation):
            nonlocal executor_called
            executor_called = True
            return BuildExecutionResult(
                outcome="PASS",
                output_iso=plan.output_iso,
            )

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, _output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            bridge.startBuild()
            self.wait_until(lambda: bridge.buildWarningPending)
            self.assertFalse(executor_called)
            self.assertIn("controlled source warning", bridge.buildWarningText)

            bridge.continueBuildAfterWarnings()
            self.wait_until(lambda: not bridge.isBuildRunning)

        self.assertTrue(executor_called)
        self.assertEqual(bridge.buildOutcome, "PASS")

    def test_rejecting_scan_warnings_never_starts_executor(self) -> None:
        executor_called = False

        def planner(request, backends):
            plan = make_plan(request, backends[0])
            plan.scan.warnings = ["controlled source warning"]
            return plan

        def executor(_plan, _log, _cancellation):
            nonlocal executor_called
            executor_called = True
            raise AssertionError("rejected warning must not start executor")

        with TemporaryDirectory() as temporary:
            bridge, _backend, _source, output = self.make_ready_bridge(
                Path(temporary),
                planner=planner,
                executor=executor,
            )
            bridge.startBuild()
            self.wait_until(lambda: bridge.buildWarningPending)
            bridge.rejectBuildWarnings()
            self.wait_until(lambda: not bridge.isBuildRunning)

            self.assertFalse(executor_called)
            self.assertEqual(bridge.buildOutcome, "CANCELLED")
            self.assertFalse((output / "real.iso").exists())


class QtRealBuildQmlContractTests(unittest.TestCase):
    def test_qml_exposes_confirm_build_cancel_and_close_lifecycle(self) -> None:
        root = Path(__file__).resolve().parents[1]
        qml = (
            root / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("realBuildConfirmDialog", qml)
        self.assertIn("buildLogDialog", qml)
        self.assertIn("closeBuildDialog", qml)
        self.assertIn("bridge.startBuild()", qml)
        self.assertIn("bridge.cancelBuild()", qml)
        self.assertIn("bridge.requestCloseAfterCancel()", qml)
        self.assertIn("bridge.isBuildRunning", qml)
        self.assertIn("bridge.buildProgressIndeterminate", qml)
        self.assertIn("buildWarningDialog", qml)
        self.assertIn("bridge.continueBuildAfterWarnings()", qml)
        self.assertIn("bridge.rejectBuildWarnings()", qml)
        self.assertIn('text: "View log"', qml)
        self.assertIn('text: "Close Log"', qml)
        log_section = qml[
            qml.index("id: buildLogDialog"):
            qml.index("id: closeBuildDialog")
        ]
        self.assertNotIn("PremiumProgressBar", log_section)
        self.assertNotIn("bridge.cancelBuild()", log_section)
        self.assertIn("function onSafeToClose()", qml)


if __name__ == "__main__":
    unittest.main()
