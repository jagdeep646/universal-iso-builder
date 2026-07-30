import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QtBuildScriptPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (ROOT / "build_qt_exe.ps1").read_text(
            encoding="utf-8"
        ).lower()

    def test_qt_launcher_uses_package_entrypoint(self) -> None:
        launcher = (ROOT / "universal_iso_builder_qt.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from iso_builder.gui.qt_app import main", launcher)
        self.assertIn("raise SystemExit(main())", launcher)

    def test_qt_build_is_onedir_and_isolated_from_tkinter_dist(self) -> None:
        self.assertIn('$distroot = join-path $scriptroot "dist-qt"', self.script)
        self.assertIn('"universal_iso_builder_qt.py"', self.script)
        self.assertIn("--onedir", self.script)
        self.assertNotIn("--onefile", self.script)
        self.assertNotIn('"universal_iso_builder_v1_4_1.py"', self.script)

    def test_qt_build_pins_dependencies_and_runs_source_smoke_test(self) -> None:
        requirements = (ROOT / "requirements-gui.txt").read_text(
            encoding="utf-8"
        )

        self.assertEqual(requirements.strip(), "PySide6==6.11.1")
        self.assertIn('$pyinstallerversion = "6.21.0"', self.script)
        self.assertIn('$pysideversion = "6.11.1"', self.script)
        self.assertIn('"pyinstaller==$pyinstallerversion"', self.script)
        self.assertIn("-r $guirequirements", self.script)
        self.assertIn("qt_qpa_platform", self.script)
        self.assertIn("--smoke-test", self.script)

    def test_qt_build_packages_and_gates_qml_assets(self) -> None:
        self.assertIn("--add-data", self.script)
        self.assertIn("iso_builder/gui/qml", self.script)
        self.assertIn(
            '"_internal\\iso_builder\\gui\\qml\\main.qml"',
            self.script,
        )
        self.assertIn(
            "if (!(test-path -literalpath $expectedqml -pathtype leaf))",
            self.script,
        )

    def test_qt_build_uses_version_metadata_and_expected_exe_gate(self) -> None:
        self.assertIn("windows_version_info.txt", self.script)
        self.assertIn("--version-file", self.script)
        self.assertIn(
            "if (!(test-path -literalpath $expectedexe -pathtype leaf))",
            self.script,
        )
        self.assertIn("qt onedir build pass", self.script)

    def test_qt_generated_output_is_ignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("dist-qt/", gitignore.splitlines())
        self.assertIn("dist-qt-onefile/", gitignore.splitlines())


class QtOneFileBuildScriptPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "build_qt_onefile_optional.ps1"
        ).read_text(encoding="utf-8").lower()

    def test_qt_onefile_is_isolated_and_does_not_replace_onedir(self) -> None:
        self.assertIn(
            '$distroot = join-path $scriptroot "dist-qt-onefile"',
            self.script,
        )
        self.assertIn('"universal_iso_builder_qt.py"', self.script)
        self.assertIn("--onefile", self.script)
        self.assertNotIn("--onedir", self.script)
        self.assertNotIn('"universal_iso_builder_v1_4_1.py"', self.script)

    def test_qt_onefile_pins_dependencies_and_packages_qml(self) -> None:
        self.assertIn('$pyinstallerversion = "6.21.0"', self.script)
        self.assertIn('$pysideversion = "6.11.1"', self.script)
        self.assertIn('"pyinstaller==$pyinstallerversion"', self.script)
        self.assertIn("-r $guirequirements", self.script)
        self.assertIn("--add-data", self.script)
        self.assertIn("iso_builder/gui/qml", self.script)
        self.assertIn("--smoke-test", self.script)

    def test_qt_onefile_gates_expected_exe_and_reports_tradeoffs(self) -> None:
        self.assertIn(
            "if (!(test-path -literalpath $expectedexe -pathtype leaf))",
            self.script,
        )
        self.assertIn("qt onefile build pass", self.script)
        self.assertIn("extracts to a temporary folder", self.script)
        self.assertIn("antivirus scrutiny", self.script)


if __name__ == "__main__":
    unittest.main()
