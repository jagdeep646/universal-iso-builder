import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QCoreApplication
except ImportError:  # pragma: no cover - allows the core-only environment to test cleanly
    QCoreApplication = None

from iso_builder.models import Backend


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(QCoreApplication is None, "PySide6 GUI dependency is not installed")
class QtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_bridge_reports_detected_backend(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        backend = Backend(
            name="oscdimg",
            executable=r"C:\Tools\oscdimg.exe",
            priority=10,
            description="test backend",
            supports_udf=True,
            supports_joliet=True,
            supports_iso_level3=True,
            source="test",
        )
        bridge = QtIsoBridge(detector=lambda: [backend])

        bridge.refreshBackends()

        self.assertEqual(bridge.backendCount, 1)
        self.assertEqual(bridge.backendNames, ["oscdimg"])
        self.assertEqual(bridge.preferredBackend, "oscdimg")
        self.assertEqual(bridge.statusTitle, "System ready")

    def test_bridge_reports_no_backend_without_inventing_readiness(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        bridge = QtIsoBridge(detector=lambda: [])

        bridge.refreshBackends()

        self.assertEqual(bridge.backendCount, 0)
        self.assertEqual(bridge.backendNames, [])
        self.assertEqual(bridge.preferredBackend, "Not available")
        self.assertEqual(bridge.statusTitle, "Backend required")

    def test_bridge_reports_detection_failure(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        def fail_detection():
            raise RuntimeError("controlled failure")

        bridge = QtIsoBridge(detector=fail_detection)

        bridge.refreshBackends()

        self.assertEqual(bridge.backendCount, 0)
        self.assertEqual(bridge.preferredBackend, "Detection failed")
        self.assertEqual(bridge.statusTitle, "Backend check failed")
        self.assertEqual(bridge.statusDetail, "controlled failure")


class QtGuiContractTests(unittest.TestCase):
    def test_gui_dependency_is_pinned(self) -> None:
        requirement = (ROOT / "requirements-gui.txt").read_text(encoding="utf-8")
        self.assertEqual(requirement.strip(), "PySide6==6.11.1")

    def test_qml_shell_exists_without_unimplemented_product_claims(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("ApplicationWindow", qml)
        self.assertIn("bridge.refreshBackends()", qml)
        self.assertNotIn("Bootable ISO", qml)
        self.assertNotIn("Verify ISO", qml)
        self.assertNotIn("72%", qml)

    def test_existing_production_entrypoint_remains_tkinter(self) -> None:
        launcher = (ROOT / "universal_iso_builder_v1_4_1.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("iso_builder.gui.app", launcher)
        self.assertNotIn("qt_app", launcher)


if __name__ == "__main__":
    unittest.main()
