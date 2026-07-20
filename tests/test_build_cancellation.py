import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import iso_builder.execution as execution
from iso_builder.constants import PROFILE_AUTO
from iso_builder.gui.app import IsoBuilderApp
from iso_builder.models import Backend, BuildOptions, BuildPlan, ScanResult


def make_plan(output_iso: Path) -> BuildPlan:
    backend = Backend(
        name="fake",
        executable="fake.exe",
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
        generate_hash=False,
        optimize_duplicates=False,
        auto_package=False,
        dry_run=False,
    )
    return BuildPlan(
        source=output_iso.parent / "source",
        output_iso=output_iso,
        label="TEST",
        backend=backend,
        scan=ScanResult(files=1, total_bytes=3),
        command=["fake.exe", "--output", str(output_iso)],
        warnings=[],
        options=options,
    )


class BuildCancellationTests(unittest.TestCase):
    def test_run_process_cancels_real_child_process(self) -> None:
        cancellation = execution.BuildCancellation()
        logs = []

        def request_cancel() -> None:
            time.sleep(0.2)
            cancellation.cancel()

        cancel_thread = threading.Thread(target=request_cancel)
        cancel_thread.start()
        try:
            with self.assertRaises(execution.BuildCancelled):
                execution.run_process(
                    [
                        sys.executable,
                        "-u",
                        "-c",
                        "import time; print('child started'); time.sleep(30)",
                    ],
                    logs.append,
                    cancellation,
                )
        finally:
            cancel_thread.join(timeout=2)

        self.assertFalse(cancel_thread.is_alive())
        self.assertEqual(logs, ["child started"])

    def test_cancel_terminates_registered_backend_process(self) -> None:
        cancellation = execution.BuildCancellation()
        process = Mock()
        process.poll.return_value = None
        cancellation.register_process(process)

        cancellation.cancel()

        self.assertTrue(cancellation.is_cancelled())
        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()

    def test_force_cancel_kills_registered_backend_process(self) -> None:
        cancellation = execution.BuildCancellation()
        process = Mock()
        process.poll.return_value = None
        cancellation.register_process(process)

        cancellation.cancel(force=True)

        process.kill.assert_called_once_with()

    def test_cancelled_backend_cleans_partial_and_never_publishes_final(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "cancelled.iso"
            cancellation = execution.BuildCancellation()
            plan = make_plan(output_iso)

            def fake_run_process(command, log, cancellation=None):
                Path(command[-1]).write_bytes(b"partial ISO")
                cancellation.cancel()
                cancellation.raise_if_cancelled()

            with patch.object(
                execution,
                "run_process",
                side_effect=fake_run_process,
            ):
                result = execution.execute_build_plan(
                    plan,
                    lambda _message: None,
                    cancellation,
                )

            self.assertEqual(result.outcome, "CANCELLED")
            self.assertFalse(output_iso.exists())
            self.assertEqual(list(Path(root_dir).glob(".*.partial.iso")), [])

    def test_pre_cancelled_build_never_starts_backend(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "cancelled.iso"
            cancellation = execution.BuildCancellation()
            cancellation.cancel()

            with patch.object(execution, "run_process") as run_process:
                result = execution.execute_build_plan(
                    make_plan(output_iso),
                    lambda _message: None,
                    cancellation,
                )

            self.assertEqual(result.outcome, "CANCELLED")
            run_process.assert_not_called()
            self.assertFalse(output_iso.exists())


class WindowCloseTests(unittest.TestCase):
    def make_app(self):
        app = type("CloseHarness", (), {})()
        app.active_operation = "build"
        app.worker = Mock()
        app.worker.is_alive.return_value = True
        app.build_cancellation = execution.BuildCancellation()
        app.close_requested = False
        app.close_force_deadline = None
        app.ui_queue = queue.Queue()
        app.logs = []
        app.statuses = []
        app.after_calls = []
        app.destroy_calls = 0
        app.log = app.logs.append
        app._set_status = lambda title, detail: app.statuses.append((title, detail))
        app.after = lambda delay, callback: app.after_calls.append((delay, callback))
        app.destroy = lambda: setattr(app, "destroy_calls", app.destroy_calls + 1)
        app._on_close_requested = IsoBuilderApp._on_close_requested.__get__(app)
        app._wait_for_build_close = IsoBuilderApp._wait_for_build_close.__get__(app)
        return app

    def test_close_confirmation_requests_cancel_without_destroying_early(self) -> None:
        app = self.make_app()

        with patch(
            "iso_builder.gui.app.messagebox.askyesno",
            return_value=True,
        ):
            app._on_close_requested()

        self.assertTrue(app.close_requested)
        self.assertTrue(app.build_cancellation.is_cancelled())
        self.assertEqual(app.destroy_calls, 0)
        self.assertEqual(len(app.after_calls), 1)
        self.assertEqual(app.statuses, [("Cancelling build...", "Waiting for backend to stop safely")])

    def test_close_wait_destroys_only_after_build_worker_finishes(self) -> None:
        app = self.make_app()
        app.close_requested = True
        app.worker.is_alive.side_effect = [True, False]

        app._wait_for_build_close()
        self.assertEqual(app.destroy_calls, 0)
        self.assertEqual(len(app.after_calls), 1)

        app.active_operation = None
        app.after_calls.pop()[1]()
        self.assertEqual(app.destroy_calls, 1)

    def test_close_confirmation_rejection_keeps_build_running(self) -> None:
        app = self.make_app()

        with patch(
            "iso_builder.gui.app.messagebox.askyesno",
            return_value=False,
        ):
            app._on_close_requested()

        self.assertFalse(app.close_requested)
        self.assertFalse(app.build_cancellation.is_cancelled())
        self.assertEqual(app.destroy_calls, 0)


if __name__ == "__main__":
    unittest.main()
