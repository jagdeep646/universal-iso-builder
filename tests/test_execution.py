import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import iso_builder.execution as execution
    from iso_builder.constants import PROFILE_AUTO
    from iso_builder.models import Backend, BuildOptions, BuildPlan, ScanResult
except ModuleNotFoundError:
    import universal_iso_builder_v1_4_1 as execution
    from universal_iso_builder_v1_4_1 import (
        PROFILE_AUTO,
        Backend,
        BuildOptions,
        BuildPlan,
        ScanResult,
    )


def make_plan(output_iso: Path, *, dry_run: bool, generate_hash: bool) -> BuildPlan:
    backend = Backend(
        name="fake",
        executable="fake.exe",
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
        generate_hash=generate_hash,
        optimize_duplicates=False,
        auto_package=False,
        dry_run=dry_run,
    )
    return BuildPlan(
        source=output_iso.parent / "source",
        output_iso=output_iso,
        label="TEST",
        backend=backend,
        scan=ScanResult(files=1, total_bytes=3),
        command=["fake.exe"],
        warnings=[],
        options=options,
    )


class ExecutionTests(unittest.TestCase):
    def test_calculate_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            file_path = Path(root_dir) / "payload.bin"
            file_path.write_bytes(b"abc")
            progress = []

            digest = execution.calculate_sha256(file_path, progress.append)

            self.assertEqual(
                digest,
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )
            self.assertEqual(progress, [3])

    def test_dry_run_produces_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "dry.iso"
            plan = make_plan(output_iso, dry_run=True, generate_hash=True)
            logs = []

            result = execution.execute_build_plan(plan, logs.append)

            self.assertEqual(result.outcome, "DRY RUN")
            self.assertFalse(output_iso.exists())
            self.assertFalse(output_iso.with_suffix(".iso.sha256.txt").exists())
            self.assertEqual(logs[-1], "Build finished: DRY RUN")

    def test_execute_success_and_hash_output(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "success.iso"
            plan = make_plan(output_iso, dry_run=False, generate_hash=True)
            logs = []

            def fake_run_process(command, log) -> int:
                self.assertEqual(command, ["fake.exe"])
                output_iso.write_bytes(b"abc")
                return 0

            with patch.object(execution, "run_process", side_effect=fake_run_process):
                result = execution.execute_build_plan(plan, logs.append)

            expected_hash = hashlib.sha256(b"abc").hexdigest()
            expected_hash_path = output_iso.with_suffix(".iso.sha256.txt")
            self.assertEqual(result.outcome, "PASS")
            self.assertEqual(result.sha256, expected_hash)
            self.assertEqual(result.hash_path, expected_hash_path)
            self.assertEqual(
                expected_hash_path.read_text(encoding="utf-8"),
                f"{expected_hash}  success.iso\n",
            )
            self.assertEqual(logs[-1], "Build finished: PASS")

    def test_execute_backend_failure(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "failed.iso"
            plan = make_plan(output_iso, dry_run=False, generate_hash=False)
            logs = []

            with patch.object(execution, "run_process", return_value=7):
                result = execution.execute_build_plan(plan, logs.append)

            self.assertEqual(result.outcome, "FAIL")
            self.assertEqual(result.error, "ISO backend failed with exit code 7")
            self.assertFalse(output_iso.exists())
            self.assertEqual(logs[-1], "Build finished: FAIL")

    def test_storage_preflight_failure_stops_backend_execution(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "blocked.iso"
            plan = make_plan(output_iso, dry_run=False, generate_hash=False)
            logs = []

            with (
                patch.object(
                    execution,
                    "validate_output_storage",
                    side_effect=RuntimeError("Insufficient free space for ISO output."),
                ),
                patch.object(execution, "run_process") as run_process,
            ):
                result = execution.execute_build_plan(plan, logs.append)

            self.assertEqual(result.outcome, "FAIL")
            self.assertIn("Insufficient free space", result.error or "")
            run_process.assert_not_called()
            self.assertFalse(output_iso.exists())

    def test_execute_detects_missing_output(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "missing.iso"
            plan = make_plan(output_iso, dry_run=False, generate_hash=False)

            with patch.object(execution, "run_process", return_value=0):
                result = execution.execute_build_plan(plan, lambda message: None)

            self.assertEqual(result.outcome, "FAIL")
            self.assertIn("output file create nahi hua", result.error or "")


if __name__ == "__main__":
    unittest.main()
