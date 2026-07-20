import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from iso_builder.constants import PROFILE_AUTO
    from iso_builder.models import Backend, BuildOptions, BuildRequest, ScanResult
    from iso_builder.planner import prepare_build_plan
except ModuleNotFoundError:
    from universal_iso_builder_v1_4_1 import (
        PROFILE_AUTO,
        Backend,
        BuildOptions,
        BuildRequest,
        ScanResult,
        prepare_build_plan,
    )


class PlannerTests(unittest.TestCase):
    def test_prepare_warns_about_long_absolute_output_path(self) -> None:
        backend = Backend(
            name="oscdimg",
            executable="oscdimg.exe",
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
            dry_run=True,
        )
        request = BuildRequest(
            source_text="source",
            output_text="output",
            iso_name_text="Manual.iso",
            label_text="MANUAL",
            backend_choice="Auto",
            options=options,
        )
        source = Path("C:/source")
        output_iso = Path("D:/") / ("x" * 241 + ".iso")

        with (
            patch(
                "iso_builder.planner.resolve_build_paths",
                return_value=(source, output_iso, "MANUAL", output_iso.name),
            ),
            patch(
                "iso_builder.planner.scan_source_folder",
                return_value=ScanResult(files=1),
            ),
            patch(
                "iso_builder.planner.build_command",
                return_value=(["oscdimg.exe"], []),
            ),
        ):
            plan = prepare_build_plan(request, [backend])

        self.assertTrue(
            any("Output ISO absolute path" in warning for warning in plan.warnings)
        )

    def test_prepare_rejects_hidden_exclusion_for_unsupported_backend(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            output.mkdir()
            (source / ".hidden.txt").write_text("hidden", encoding="utf-8")

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
                include_hidden=False,
                generate_hash=False,
                optimize_duplicates=False,
                auto_package=False,
                dry_run=True,
            )
            request = BuildRequest(
                source_text=str(source),
                output_text=str(output),
                iso_name_text="Manual.iso",
                label_text="MANUAL",
                backend_choice="Auto",
                options=options,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "cannot reliably exclude hidden items",
            ):
                prepare_build_plan(request, [backend])

    def test_prepare_build_plan_manual_mode(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            output.mkdir()
            (source / "payload.bin").write_bytes(b"abc")

            backend = Backend(
                name="oscdimg",
                executable="oscdimg.exe",
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
                generate_hash=True,
                optimize_duplicates=False,
                auto_package=False,
                dry_run=True,
            )
            request = BuildRequest(
                source_text=str(source),
                output_text=str(output),
                iso_name_text="Manual.iso",
                label_text="MANUAL",
                backend_choice="Auto",
                options=options,
            )

            plan = prepare_build_plan(request, [backend])

            self.assertEqual(plan.source, source.resolve())
            self.assertEqual(plan.output_iso, (output / "Manual.iso").resolve())
            self.assertEqual(plan.label, "MANUAL")
            self.assertIs(plan.backend, backend)
            self.assertEqual(plan.scan.files, 1)
            self.assertEqual(plan.scan.total_bytes, 3)
            self.assertEqual(plan.options, options)
            self.assertEqual(
                plan.command,
                [
                    "oscdimg.exe",
                    "-m",
                    "-lMANUAL",
                    "-h",
                    "-u1",
                    "-udfver102",
                    str(source.resolve()),
                    str((output / "Manual.iso").resolve()),
                ],
            )
            self.assertEqual(plan.warnings, [])


if __name__ == "__main__":
    unittest.main()
