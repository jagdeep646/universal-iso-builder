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

    def test_qml_shell_exposes_only_verified_product_claims(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("ApplicationWindow", qml)
        self.assertIn("bridge.refreshBackends()", qml)
        self.assertIn("Qt.FramelessWindowHint", qml)
        self.assertIn("DragHandler", qml)
        self.assertIn("height: 150", qml)
        self.assertIn('"Show Command"', qml)
        self.assertIn("bridge.startBuild()", qml)
        self.assertIn("realBuildConfirmDialog", qml)
        self.assertNotIn("Bootable ISO", qml)
        self.assertNotIn("ISO Verified", qml)
        self.assertNotIn("72%", qml)

    def test_premium_qml_components_exist(self) -> None:
        components = ROOT / "iso_builder" / "gui" / "qml" / "components"
        expected = {
            "AccentButton.qml",
            "ClayBadge.qml",
            "DiscArt.qml",
            "GlassCard.qml",
            "GradientButton.qml",
            "NavButton.qml",
            "PremiumCheckBox.qml",
            "PremiumComboBox.qml",
            "PremiumProgressBar.qml",
            "StatusCard.qml",
            "WindowResizeHandle.qml",
        }

        self.assertEqual(
            {path.name for path in components.glob("*.qml")},
            expected,
        )

    def test_qml_theme_and_progress_use_bridge_state(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("bridge.systemDarkMode", qml)
        self.assertIn("PremiumProgressBar", qml)
        self.assertIn("value: bridge.buildProgress", qml)
        self.assertIn("bridge.buildProgressPercent", qml)
        self.assertIn("text: bridge.buildStatusText", qml)

    def test_frameless_window_has_all_native_resize_edges(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertEqual(qml.count("WindowResizeHandle {"), 8)
        self.assertIn("edges: Qt.LeftEdge", qml)
        self.assertIn("edges: Qt.RightEdge", qml)
        self.assertIn("edges: Qt.TopEdge", qml)
        self.assertIn("edges: Qt.BottomEdge", qml)
        self.assertIn("Qt.LeftEdge | Qt.TopEdge", qml)
        self.assertIn("Qt.RightEdge | Qt.BottomEdge", qml)

    def test_vector_status_assets_exist_and_are_used(self) -> None:
        icon_directory = (
            ROOT / "iso_builder" / "gui" / "qml" / "assets" / "icons"
        )
        expected = {
            "check.svg",
            "create.svg",
            "disc.svg",
            "folder.svg",
            "globe.svg",
            "help.svg",
            "history.svg",
            "home.svg",
            "settings.svg",
            "shield.svg",
            "tools.svg",
            "verify.svg",
        }
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            {path.name for path in icon_directory.glob("*.svg")},
            expected,
        )
        for icon_name in expected:
            self.assertIn(f"assets/icons/{icon_name}", qml)

    def test_complete_reference_sidebar_and_segoe_ui_font_contract(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")
        launcher = (
            ROOT / "iso_builder" / "gui" / "qt_app.py"
        ).read_text(encoding="utf-8")

        for label in (
            "Home",
            "Create ISO",
            "Verify ISO",
            "History",
            "Settings",
            "Tools",
            "Help",
        ):
            self.assertIn(f'text: "{label}"', qml)
        self.assertIn('QFont("Segoe UI")', launcher)
        self.assertIn("app.setFont(application_font)", launcher)

    def test_dark_status_cards_and_disabled_preview_controls_keep_contrast(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")
        status_card = (
            ROOT / "iso_builder" / "gui" / "qml" / "components" / "StatusCard.qml"
        ).read_text(encoding="utf-8")
        gradient_button = (
            ROOT
            / "iso_builder"
            / "gui"
            / "qml"
            / "components"
            / "GradientButton.qml"
        ).read_text(encoding="utf-8")

        self.assertGreaterEqual(qml.count("valueColor: window.ink"), 4)
        self.assertGreaterEqual(qml.count("captionColor: window.muted"), 4)
        self.assertIn("color: root.valueColor", status_card)
        self.assertIn("color: root.captionColor", status_card)
        self.assertIn("control.enabled ? 1.0 : 0.86", gradient_button)
        self.assertIn("control.glowEnabled && control.enabled", gradient_button)
        self.assertIn("focusPolicy: Qt.StrongFocus", gradient_button)
        self.assertEqual(qml.count("AccentButton {"), 2)
        self.assertEqual(qml.count("PremiumComboBox {"), 2)
        self.assertEqual(qml.count("PremiumCheckBox {"), 4)
        self.assertEqual(qml.count("activeFocus ? 2 : 1"), 2)
        self.assertEqual(qml.count("Qt.alpha(window.purple, 0.45)"), 2)

    def test_premium_controls_define_interaction_state_contracts(self) -> None:
        components = ROOT / "iso_builder" / "gui" / "qml" / "components"
        accent_button = (components / "AccentButton.qml").read_text(encoding="utf-8")
        gradient_button = (components / "GradientButton.qml").read_text(
            encoding="utf-8"
        )
        combo_box = (components / "PremiumComboBox.qml").read_text(
            encoding="utf-8"
        )
        check_box = (components / "PremiumCheckBox.qml").read_text(
            encoding="utf-8"
        )

        for control in (accent_button, gradient_button, combo_box, check_box):
            self.assertIn("focusPolicy: Qt.StrongFocus", control)
            self.assertIn("control.enabled", control)
            self.assertIn("control.hovered", control)
            self.assertIn("control.down", control)

        self.assertIn("control.glowEnabled && control.enabled", gradient_button)
        self.assertIn("control.activeFocus ? 2 : 1", accent_button)
        self.assertIn("control.activeFocus ? 2 : 1", combo_box)
        self.assertIn("control.activeFocus ? 2 : 1", check_box)

    def test_action_navigation_and_window_controls_keep_premium_color_contract(self) -> None:
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")
        nav_button = (
            ROOT
            / "iso_builder"
            / "gui"
            / "qml"
            / "components"
            / "NavButton.qml"
        ).read_text(encoding="utf-8")

        self.assertIn(': "Show Command"', qml)
        self.assertIn('startColor: "#7857f3"', qml)
        self.assertIn('endColor: "#3d8df6"', qml)
        self.assertIn(': "Dry Test"', qml)
        self.assertIn('startColor: "#32bfe8"', qml)
        self.assertIn('endColor: "#7358ee"', qml)
        self.assertIn('startColor: "#ff8b5c"', qml)
        self.assertIn('endColor: "#ef4f73"', qml)

        self.assertIn(
            "readonly property bool visualHighlight: control.hovered",
            nav_button,
        )
        self.assertNotIn("control.activeFocus", nav_button)
        self.assertNotIn("selected: true", qml)

        for color in ("#438cf2", "#7655eb", "#ed5262"):
            self.assertIn(f'baseColor: "{color}"', qml)
        self.assertIn("width: 34", qml)
        self.assertIn("height: 34", qml)
        self.assertIn("color: parent.hovered", qml)
        self.assertIn(": modelData.baseColor", qml)

    def test_reference_icon_scale_and_badge_detail_contract(self) -> None:
        components = ROOT / "iso_builder" / "gui" / "qml" / "components"
        nav_button = (components / "NavButton.qml").read_text(encoding="utf-8")
        status_card = (components / "StatusCard.qml").read_text(encoding="utf-8")
        clay_badge = (components / "ClayBadge.qml").read_text(encoding="utf-8")

        self.assertIn("spacing: 15", nav_button)
        self.assertIn("width: 24", nav_button)
        self.assertIn("height: 24", nav_button)
        self.assertIn("Layout.preferredWidth: 50", status_card)
        self.assertIn("Layout.preferredHeight: 50", status_card)
        self.assertIn("iconSize: 27", status_card)
        self.assertIn('color: "#5cffffff"', clay_badge)

    def test_reference_disc_and_vector_micro_detail_contract(self) -> None:
        components = ROOT / "iso_builder" / "gui" / "qml" / "components"
        qml = (
            ROOT / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")
        disc_art = (components / "DiscArt.qml").read_text(encoding="utf-8")
        combo_box = (components / "PremiumComboBox.qml").read_text(
            encoding="utf-8"
        )
        check_box = (components / "PremiumCheckBox.qml").read_text(
            encoding="utf-8"
        )
        gradient_button = (components / "GradientButton.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn('Qt.resolvedUrl("../assets/icons/disc.svg")', disc_art)
        self.assertIn("rotation: root.rotationAngle", disc_art)
        self.assertIn("indicator: Canvas", combo_box)
        self.assertNotIn('text: "\\u2304"', combo_box)
        self.assertIn("indicator: Rectangle", check_box)
        self.assertIn("Canvas {", check_box)
        self.assertNotIn('text: "\\u2713"', check_box)
        self.assertIn("property bool showArrow: false", gradient_button)
        self.assertIn("visible: control.showArrow", gradient_button)
        self.assertIn("showArrow: !bridge.isBuildRunning", qml)
        self.assertIn("id: heroArtwork", qml)
        self.assertIn("id: heroPedestal", qml)
        self.assertIn("width: 170", qml)
        self.assertIn("width: 270", qml)

    def test_versioned_compatibility_entrypoint_remains_tkinter(self) -> None:
        launcher = (ROOT / "universal_iso_builder_v1_4_1.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("iso_builder.gui.app", launcher)
        self.assertNotIn("qt_app", launcher)


if __name__ == "__main__":
    unittest.main()
