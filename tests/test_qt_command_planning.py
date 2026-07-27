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

from iso_builder.constants import PROFILE_UDF_ONLY
from iso_builder.models import Backend, BuildPlan, ScanResult


def make_backend(name: str = "oscdimg") -> Backend:
    return Backend(
        name=name,
        executable=f"{name}.exe",
        priority=10,
        description="test backend",
        supports_udf=True,
        supports_joliet=True,
        supports_iso_level3=True,
        source="test",
    )


@unittest.skipIf(QCoreApplication is None, "PySide6 GUI dependency is not installed")
class QtCommandPlanningTests(unittest.TestCase):
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
        self.fail("Timed out waiting for Qt command planning state")

    def test_default_settings_match_verified_tk_defaults(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        bridge = QtIsoBridge(detector=lambda: [make_backend()])
        bridge.refreshBackends()

        self.assertEqual(bridge.selectedProfile, "Auto - Best Compatible")
        self.assertEqual(bridge.selectedBackend, "Auto")
        self.assertTrue(bridge.includeHidden)
        self.assertTrue(bridge.generateHash)
        self.assertFalse(bridge.optimizeDuplicates)
        self.assertTrue(bridge.autoPackage)
        self.assertEqual(bridge.backendOptions[0], "Auto")

    def test_settings_update_output_preview_and_backend_choice(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Setup"
            output = root / "Output"
            source.mkdir()
            output.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=1),
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)

            self.assertEqual(
                bridge.outputPreview,
                str(root / "Setup_ISO" / "Setup.iso"),
            )
            bridge.selectOutputFolder(QUrl.fromLocalFile(str(output)))
            bridge.setAutoPackage(False)
            bridge.setIsoName("Manual.iso")
            bridge.setVolumeLabel("MANUAL")
            bridge.setProfile(PROFILE_UDF_ONLY)
            bridge.setBackend(bridge.backendOptions[1])
            bridge.setIncludeHidden(False)
            bridge.setGenerateHash(False)
            bridge.setOptimizeDuplicates(True)

            self.assertEqual(bridge.outputPreview, str(output / "Manual.iso"))
            self.assertEqual(bridge.volumeLabel, "MANUAL")
            self.assertEqual(bridge.selectedProfile, PROFILE_UDF_ONLY)
            self.assertEqual(bridge.selectedBackend, bridge.backendOptions[1])
            self.assertEqual(bridge.preferredBackend, "oscdimg")
            self.assertFalse(bridge.includeHidden)
            self.assertFalse(bridge.generateHash)
            self.assertTrue(bridge.optimizeDuplicates)

    def test_show_command_uses_immutable_snapshot_off_ui_thread_and_cleans_plan(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()
        planner_threads = []
        requests = []
        cleaned_commands = []

        def planner(request, backends):
            planner_threads.append(threading.get_ident())
            requests.append(request)
            self.assertEqual(backends, [backend])
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
                scan=ScanResult(files=4, total_bytes=1024),
                command=[
                    backend.executable,
                    "-lSETUP",
                    request.source_text,
                    str(output_iso),
                ],
                warnings=["controlled warning"],
                options=request.options,
            )

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=4, total_bytes=1024),
                planner=planner,
                command_cleanup=lambda command: cleaned_commands.append(list(command)),
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)

            calling_thread = threading.get_ident()
            self.assertTrue(bridge.canShowCommand)
            bridge.showCommand()
            self.assertTrue(bridge.isPlanning)
            self.wait_until(lambda: not bridge.isPlanning)

            self.assertEqual(len(requests), 1)
            request = requests[0]
            self.assertEqual(request.source_text, str(source.resolve()))
            self.assertEqual(request.output_text, str(source.parent.resolve()))
            self.assertEqual(request.backend_choice, "Auto")
            self.assertTrue(request.options.dry_run)
            self.assertTrue(request.options.auto_package)
            self.assertNotEqual(planner_threads[0], calling_thread)
            self.assertIn("oscdimg.exe", bridge.commandText)
            self.assertIn("Setup_ISO", bridge.commandText)
            self.assertEqual(bridge.commandWarningsText, "controlled warning")
            self.assertEqual(
                bridge.plannedOutput,
                str(source.parent / "Setup_ISO" / "Setup.iso"),
            )
            self.assertEqual(len(cleaned_commands), 1)

    def test_planning_failure_is_exposed_without_command(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = make_backend()

        def planner(_request, _backends):
            raise ValueError("controlled planning failure")

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Setup"
            source.mkdir()
            bridge = QtIsoBridge(
                detector=lambda: [backend],
                scanner=lambda *_args: ScanResult(files=1),
                planner=planner,
            )
            bridge.refreshBackends()
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.wait_until(lambda: not bridge.isScanning)
            bridge.showCommand()
            self.wait_until(lambda: not bridge.isPlanning)

        self.assertEqual(bridge.commandText, "")
        self.assertIn("controlled planning failure", bridge.planningError)


class QtCommandQmlContractTests(unittest.TestCase):
    def test_qml_exposes_settings_and_command_without_build_execution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        qml = (
            root / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("buildSettingsDialog", qml)
        self.assertIn("outputFolderDialog", qml)
        self.assertIn("bridge.profileOptions", qml)
        self.assertIn("bridge.backendOptions", qml)
        self.assertIn("bridge.setAutoPackage", qml)
        self.assertIn("bridge.setIncludeHidden", qml)
        self.assertIn("bridge.setGenerateHash", qml)
        self.assertIn("bridge.setOptimizeDuplicates", qml)
        self.assertIn("bridge.showCommand()", qml)
        self.assertIn("bridge.commandText", qml)
        self.assertNotIn("bridge.startBuild", qml)


if __name__ == "__main__":
    unittest.main()
