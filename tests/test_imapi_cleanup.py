import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iso_builder.backends.imapi import cleanup_temp_script_from_command
from iso_builder.constants import PROFILE_AUTO
from iso_builder.execution import execute_build_plan
from iso_builder.gui.app import IsoBuilderApp
from iso_builder.models import Backend, BuildOptions, BuildPlan, ScanResult


def make_temp_script(root: Path, name: str = "universal_iso_builder_imapi_test.ps1") -> Path:
    script_path = root / name
    script_path.write_text("Write-Host 'test'\n", encoding="utf-8")
    return script_path


def make_imapi_plan(
    root: Path,
    script_path: Path,
    *,
    dry_run: bool,
    scan_warnings=None,
) -> BuildPlan:
    source = root / "source"
    source.mkdir(exist_ok=True)
    output_iso = root / "output.iso"
    backend = Backend(
        name="powershell_imapi",
        executable="powershell.exe",
        priority=1,
        description="test",
        supports_udf=True,
        supports_joliet=True,
        supports_iso_level3=False,
        source="test",
    )
    options = BuildOptions(
        profile=PROFILE_AUTO,
        include_hidden=True,
        generate_hash=False,
        optimize_duplicates=False,
        auto_package=False,
        dry_run=dry_run,
    )
    return BuildPlan(
        source=source,
        output_iso=output_iso,
        label="TEST",
        backend=backend,
        scan=ScanResult(warnings=list(scan_warnings or [])),
        command=[
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(script_path),
            "-Source",
            str(source),
            "-OutputIso",
            str(output_iso),
            "-Label",
            "TEST",
        ],
        warnings=[],
        options=options,
    )


class ImapiDiscardedPlanCleanupTests(unittest.TestCase):
    def test_show_command_cleans_temp_script_after_display(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(root, script_path, dry_run=True)
            app = type("ShowCommandHarness", (), {})()
            app.displayed = []
            app._display_prepared_command = app.displayed.append

            IsoBuilderApp._handle_plan_complete(app, "command", plan)

            self.assertEqual(app.displayed, [plan])
            self.assertFalse(script_path.exists())

    def test_show_command_cleans_temp_script_when_display_raises(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(root, script_path, dry_run=True)
            app = type("ShowCommandErrorHarness", (), {})()

            def fail_display(_plan):
                raise RuntimeError("display failed")

            app._display_prepared_command = fail_display

            with self.assertRaisesRegex(RuntimeError, "display failed"):
                IsoBuilderApp._handle_plan_complete(app, "command", plan)

            self.assertFalse(script_path.exists())

    def test_warning_cancel_cleans_temp_script(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(
                root,
                script_path,
                dry_run=False,
                scan_warnings=["test warning"],
            )
            app = type("WarningCancelHarness", (), {})()
            app.active_operation = "build"
            app.statuses = []
            app.logs = []
            app._finish_operation = IsoBuilderApp._finish_operation.__get__(app)
            app._set_status = lambda title, detail: app.statuses.append((title, detail))
            app.log = app.logs.append

            with patch("iso_builder.gui.app.messagebox.askyesno", return_value=False):
                IsoBuilderApp._handle_build_plan_ready(app, plan)

            self.assertFalse(script_path.exists())
            self.assertIsNone(app.active_operation)

    def test_build_worker_start_failure_cleans_temp_script(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(root, script_path, dry_run=False)
            app = type("WorkerStartFailureHarness", (), {})()
            app.active_operation = "build"
            app.statuses = []
            app.errors = []
            app._build_worker = lambda _plan: None
            app._finish_operation = IsoBuilderApp._finish_operation.__get__(app)
            app._set_status = lambda title, detail: app.statuses.append((title, detail))
            app._handle_operation_error = lambda operation, error: app.errors.append(
                (operation, error)
            )

            with patch(
                "iso_builder.gui.app.threading.Thread.start",
                side_effect=RuntimeError("thread start failed"),
            ):
                IsoBuilderApp._handle_build_plan_ready(app, plan)

            self.assertFalse(script_path.exists())
            self.assertIsNone(app.active_operation)
            self.assertEqual(app.errors, [("build", "thread start failed")])


class ImapiExecutionCleanupTests(unittest.TestCase):
    def test_dry_run_cleans_temp_script(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(root, script_path, dry_run=True)

            result = execute_build_plan(plan, lambda _message: None)

            self.assertEqual(result.outcome, "DRY RUN")
            self.assertFalse(script_path.exists())

    def test_backend_failure_cleans_temp_script(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root)
            plan = make_imapi_plan(root, script_path, dry_run=False)

            with patch("iso_builder.execution.run_process", return_value=7):
                result = execute_build_plan(plan, lambda _message: None)

            self.assertEqual(result.outcome, "FAIL")
            self.assertFalse(script_path.exists())

    def test_cleanup_does_not_delete_unrelated_script(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            script_path = make_temp_script(root, name="unrelated.ps1")
            command = ["powershell.exe", "-File", str(script_path)]

            cleanup_temp_script_from_command(command)

            self.assertTrue(script_path.exists())


if __name__ == "__main__":
    unittest.main()
