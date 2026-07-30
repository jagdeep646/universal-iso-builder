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
    BuildOptions,
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
    output_iso = (
        Path(request.output_text)
        / "Setup_ISO"
        / "Setup.iso"
    )
    return BuildPlan(
        source=Path(request.source_text),
        output_iso=output_iso,
        label="SETUP",
        backend=backend,
        scan=ScanResult(files=3, total_bytes=4096),
        command=[
            backend.executable,
            "-lSETUP",
            request.source_text,
            str(output_iso),
        ],
        warnings=["controlled warning"],
        options=request.options,
    )


@unittest.skipIf(QCoreApplication is None, "PySide6 GUI dependency is not installed")
class QtDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def wait_until(self, predicate, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.application.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt dry-run state")

    def test_dry_run_uses_snapshot_and_executor_off_ui_thread(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        planner_requests = []
        executor_threads = []
        executor_plans = []
        cleaned_commands = []

        def planner(request, backends):
            planner_requests.append(request)
            self.assertEqual(backends, [backend])
            return make_plan(request, backend)

        def executor(plan, log):
            executor_threads.append(threading.get_ident())
            executor_plans.append(plan)
            log("Build started")
            log("Dry run ON: actual ISO create nahi kiya gaya.")
            log("Build finished: DRY RUN")
            return BuildExecutionResult(
                outcome="DRY RUN",
                output_iso=plan.output_iso,
            )

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=3, total_bytes=4096),
                planner=planner,
                executor=executor,
                command_cleanup=lambda command: cleaned_commands.append(list(command)),
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)

            calling_thread = threading.get_ident()
            self.assertTrue(bridge.canRunDryRun)
            bridge.runDryRun()
            self.assertTrue(bridge.isDryRunning)
            self.assertEqual(bridge.buildOutcome, "RUNNING")
            self.wait_until(lambda: not bridge.isDryRunning)

            self.assertEqual(len(planner_requests), 1)
            self.assertTrue(planner_requests[0].options.dry_run)
            self.assertEqual(len(executor_plans), 1)
            self.assertTrue(executor_plans[0].options.dry_run)
            self.assertNotEqual(executor_threads[0], calling_thread)
            self.assertEqual(bridge.buildOutcome, "DRY RUN")
            self.assertEqual(bridge.buildStatusText, "Dry run complete")
            self.assertEqual(bridge.buildProgressPercent, 100)
            self.assertIn("Build finished: DRY RUN", bridge.buildLogText)
            self.assertEqual(bridge.buildError, "")
            self.assertEqual(
                bridge.lastExecutionOutput,
                str(source.parent / "Setup_ISO" / "Setup.iso"),
            )
            self.assertEqual(len(cleaned_commands), 1)

    def test_real_executor_dry_run_creates_no_iso_or_hash(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            output_iso = source.parent / "Setup_ISO" / "Setup.iso"
            hash_path = output_iso.with_suffix(output_iso.suffix + ".sha256.txt")

            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=1, total_bytes=32),
                planner=lambda request, _backends: make_plan(request, backend),
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)
            bridge.runDryRun()
            self.wait_until(lambda: not bridge.isDryRunning)

            self.assertEqual(bridge.buildOutcome, "DRY RUN")
            self.assertFalse(output_iso.exists())
            self.assertFalse(hash_path.exists())
            self.assertIn(
                "Dry run ON: actual ISO create nahi kiya gaya.",
                bridge.buildLogText,
            )

    def test_planning_failure_never_calls_executor(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        executor_called = False

        def planner(_request, _backends):
            raise ValueError("controlled dry-run planning failure")

        def executor(_plan, _log):
            nonlocal executor_called
            executor_called = True
            raise AssertionError("executor must not run after planning failure")

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=1),
                planner=planner,
                executor=executor,
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)
            bridge.runDryRun()
            self.wait_until(lambda: not bridge.isDryRunning)

        self.assertFalse(executor_called)
        self.assertEqual(bridge.buildOutcome, "FAIL")
        self.assertEqual(bridge.buildStatusText, "Dry run failed")
        self.assertEqual(bridge.buildProgressPercent, 0)
        self.assertIn("controlled dry-run planning failure", bridge.buildError)

    def test_non_dry_plan_is_rejected_before_executor(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        executor_called = False

        def planner(request, _backends):
            plan = make_plan(request, backend)
            plan.options = BuildOptions(
                profile=plan.options.profile,
                include_hidden=plan.options.include_hidden,
                generate_hash=plan.options.generate_hash,
                optimize_duplicates=plan.options.optimize_duplicates,
                auto_package=plan.options.auto_package,
                dry_run=False,
            )
            return plan

        def executor(_plan, _log):
            nonlocal executor_called
            executor_called = True
            raise AssertionError("non-dry plan must never be executed")

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=1),
                planner=planner,
                executor=executor,
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)
            bridge.runDryRun()
            self.wait_until(lambda: not bridge.isDryRunning)

        self.assertFalse(executor_called)
        self.assertEqual(bridge.buildOutcome, "FAIL")
        self.assertIn("non-dry-run plan", bridge.buildError)


class QtDryRunQmlContractTests(unittest.TestCase):
    def test_qml_exposes_dry_run_without_real_build_entrypoint(self) -> None:
        root = Path(__file__).resolve().parents[1]
        qml = (
            root / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("bridge.runDryRun()", qml)
        self.assertIn("bridge.canRunDryRun", qml)
        self.assertIn("bridge.buildProgress", qml)
        self.assertIn("bridge.buildLogText", qml)
        self.assertIn("dryRunDialog", qml)
        self.assertIn('"Dry Test"', qml)
        self.assertIn("bridge.startBuild()", qml)
        self.assertNotIn("execute_build_plan", qml)


if __name__ == "__main__":
    unittest.main()
