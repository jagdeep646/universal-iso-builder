import tempfile
import unittest
from pathlib import Path

try:
    from iso_builder.constants import PROFILE_AUTO
    from iso_builder.models import Backend, BuildOptions, BuildRequest
    from iso_builder.planner import prepare_build_plan
except ModuleNotFoundError:
    from universal_iso_builder_v1_4_1 import (
        PROFILE_AUTO,
        Backend,
        BuildOptions,
        BuildRequest,
        prepare_build_plan,
    )


class PlannerTests(unittest.TestCase):
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
