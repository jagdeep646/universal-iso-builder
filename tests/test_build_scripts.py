import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "nt", "Windows PowerShell build script test")
class PowerShellBuildScriptTests(unittest.TestCase):
    SUCCESSFUL_FAKE_PYTHON = (
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        "if /I \"%1\"==\"-c\" exit /b 0\r\n"
        "if /I not \"%2\"==\"PyInstaller\" exit /b 0\r\n"
        "set \"DISTPATH=%CD%\\dist\"\r\n"
        "set \"MODE=onedir\"\r\n"
        ":parse\r\n"
        "if \"%~1\"==\"\" goto build\r\n"
        "if /I \"%~1\"==\"--onefile\" set \"MODE=onefile\"\r\n"
        "if /I \"%~1\"==\"--distpath\" (\r\n"
        "  set \"DISTPATH=%~2\"\r\n"
        "  shift\r\n"
        ")\r\n"
        "shift\r\n"
        "goto parse\r\n"
        ":build\r\n"
        "if /I \"%MODE%\"==\"onefile\" (\r\n"
        "  if not exist \"%DISTPATH%\" mkdir \"%DISTPATH%\"\r\n"
        "  type nul > \"%DISTPATH%\\Universal ISO Builder.exe\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if not exist \"%DISTPATH%\\Universal ISO Builder\" "
        "mkdir \"%DISTPATH%\\Universal ISO Builder\"\r\n"
        "type nul > \"%DISTPATH%\\Universal ISO Builder\\Universal ISO Builder.exe\"\r\n"
        "exit /b 0\r\n"
    )

    def run_script_with_fake_python(
        self,
        fake_python_body: str,
        *,
        launch_from_other_cwd: bool = False,
    ):
        project_root = Path(__file__).resolve().parents[1]
        source_script = project_root / "build_exe.ps1"
        powershell = (
            Path(os.environ["SystemRoot"])
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            shutil.copy2(source_script, root / "build_exe.ps1")
            (root / "universal_iso_builder_v1_4_1.py").write_text(
                "print('test entrypoint')\n",
                encoding="utf-8",
            )
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            (fake_bin / "python.cmd").write_text(
                fake_python_body,
                encoding="ascii",
            )
            launch_dir = root
            if launch_from_other_cwd:
                launch_dir = root / "caller"
                launch_dir.mkdir()

            environment = os.environ.copy()
            environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]
            result = subprocess.run(
                [
                    str(powershell),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "RemoteSigned",
                    "-File",
                    str(root / "build_exe.ps1"),
                ],
                cwd=launch_dir,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            output = result.stdout + result.stderr
            expected_exe = (
                root
                / "dist"
                / "Universal ISO Builder"
                / "Universal ISO Builder.exe"
            )
            return result.returncode, output, expected_exe.exists()

    def test_native_command_failure_is_nonzero_without_build_pass(self) -> None:
        return_code, output, exe_exists = self.run_script_with_fake_python(
            "@echo off\r\nexit /b 23\r\n"
        )

        self.assertNotEqual(return_code, 0)
        self.assertNotIn("BUILD PASS", output)
        self.assertFalse(exe_exists)

    def test_missing_expected_exe_is_failure_even_after_zero_exit(self) -> None:
        return_code, output, exe_exists = self.run_script_with_fake_python(
            "@echo off\r\nexit /b 0\r\n"
        )

        self.assertNotEqual(return_code, 0)
        self.assertNotIn("BUILD PASS", output)
        self.assertFalse(exe_exists)

    def test_build_pass_requires_success_exit_and_expected_exe(self) -> None:
        return_code, output, exe_exists = self.run_script_with_fake_python(
            self.SUCCESSFUL_FAKE_PYTHON
        )

        self.assertEqual(return_code, 0, output)
        self.assertIn("BUILD PASS", output)
        self.assertTrue(exe_exists)

    def test_build_uses_script_root_from_different_current_directory(self) -> None:
        return_code, output, exe_exists = self.run_script_with_fake_python(
            self.SUCCESSFUL_FAKE_PYTHON,
            launch_from_other_cwd=True,
        )

        self.assertEqual(return_code, 0, output)
        self.assertIn("BUILD PASS", output)
        self.assertTrue(exe_exists)


@unittest.skipUnless(os.name == "nt", "Windows batch build script test")
class BatchBuildScriptTests(unittest.TestCase):
    def run_batch(
        self,
        filename: str,
        fake_python_body: str,
        expected_relative_exe: Path,
    ):
        project_root = Path(__file__).resolve().parents[1]
        cmd_exe = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            shutil.copy2(project_root / filename, root / filename)
            (root / "universal_iso_builder_v1_4_1.py").write_text(
                "print('test entrypoint')\n",
                encoding="utf-8",
            )
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            (fake_bin / "python.cmd").write_text(
                fake_python_body,
                encoding="ascii",
            )
            caller = root / "caller"
            caller.mkdir()
            environment = os.environ.copy()
            environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]

            result = subprocess.run(
                [
                    str(cmd_exe),
                    "/d",
                    "/c",
                    "call",
                    str(root / filename),
                ],
                cwd=caller,
                env=environment,
                input="\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            output = result.stdout + result.stderr
            return (
                result.returncode,
                output,
                (root / expected_relative_exe).exists(),
            )

    def test_onedir_batch_works_from_different_current_directory(self) -> None:
        return_code, output, exe_exists = self.run_batch(
            "build_exe.bat",
            PowerShellBuildScriptTests.SUCCESSFUL_FAKE_PYTHON,
            Path("dist") / "Universal ISO Builder" / "Universal ISO Builder.exe",
        )

        self.assertEqual(return_code, 0, output)
        self.assertIn("BUILD PASS", output)
        self.assertTrue(exe_exists)

    def test_onedir_batch_native_failure_is_nonzero_without_pass(self) -> None:
        return_code, output, exe_exists = self.run_batch(
            "build_exe.bat",
            "@echo off\r\nexit /b 23\r\n",
            Path("dist") / "Universal ISO Builder" / "Universal ISO Builder.exe",
        )

        self.assertNotEqual(return_code, 0)
        self.assertNotIn("BUILD PASS", output)
        self.assertFalse(exe_exists)

    def test_onefile_batch_uses_isolated_output(self) -> None:
        return_code, output, exe_exists = self.run_batch(
            "build_onefile_optional.bat",
            PowerShellBuildScriptTests.SUCCESSFUL_FAKE_PYTHON,
            Path("dist-onefile") / "Universal ISO Builder.exe",
        )

        self.assertEqual(return_code, 0, output)
        self.assertIn("OPTIONAL ONEFILE BUILD PASS", output)
        self.assertTrue(exe_exists)


class BuildScriptPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def read(self, filename: str) -> str:
        return (self.project_root / filename).read_text(encoding="utf-8")

    def test_build_scripts_pin_tested_pyinstaller_without_pip_upgrade(self) -> None:
        for filename in (
            "build_exe.ps1",
            "build_exe.bat",
            "build_onefile_optional.bat",
        ):
            with self.subTest(filename=filename):
                content = self.read(filename).lower()
                if filename.endswith(".ps1"):
                    self.assertIn('$pyinstallerversion = "6.21.0"', content)
                    self.assertIn('"pyinstaller==$pyinstallerversion"', content)
                else:
                    self.assertIn('set "pyinstaller_version=6.21.0"', content)
                    self.assertIn('"pyinstaller==%pyinstaller_version%"', content)
                self.assertNotIn("pip install --upgrade pip", content)
                self.assertNotIn("pip install --upgrade pyinstaller", content)

    def test_batch_build_scripts_anchor_paths_to_script_directory(self) -> None:
        for filename in ("build_exe.bat", "build_onefile_optional.bat"):
            with self.subTest(filename=filename):
                self.assertIn("%~dp0", self.read(filename))

    def test_onefile_output_is_isolated_from_recommended_onedir(self) -> None:
        content = self.read("build_onefile_optional.bat").lower()
        self.assertIn("dist-onefile", content)
        self.assertIn("if errorlevel 1", content)

    def test_backend_check_does_not_bypass_execution_policy(self) -> None:
        content = self.read("check_iso_backend.bat").lower()
        self.assertNotIn("executionpolicy bypass", content)

    def test_build_scripts_gate_success_on_tkinter_preflight(self) -> None:
        for filename in (
            "build_exe.ps1",
            "build_exe.bat",
            "build_onefile_optional.bat",
        ):
            with self.subTest(filename=filename):
                content = self.read(filename).lower()
                self.assertIn("import tkinter", content)
                self.assertIn("missing module named tkinter", content)


if __name__ == "__main__":
    unittest.main()
