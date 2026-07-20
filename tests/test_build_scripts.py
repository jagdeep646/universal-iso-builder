import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "nt", "Windows PowerShell build script test")
class PowerShellBuildScriptTests(unittest.TestCase):
    def run_script_with_fake_python(self, fake_python_body: str):
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
                cwd=root,
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
            "@echo off\r\n"
            "if /I \"%2\"==\"PyInstaller\" (\r\n"
            "  if not exist \"dist\\Universal ISO Builder\" "
            "mkdir \"dist\\Universal ISO Builder\"\r\n"
            "  type nul > \"dist\\Universal ISO Builder\\Universal ISO Builder.exe\"\r\n"
            ")\r\n"
            "exit /b 0\r\n"
        )

        self.assertEqual(return_code, 0, output)
        self.assertIn("BUILD PASS", output)
        self.assertTrue(exe_exists)


if __name__ == "__main__":
    unittest.main()
