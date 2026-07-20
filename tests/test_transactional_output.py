import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from iso_builder.backends.commands import build_command
from iso_builder.backends.imapi import cleanup_temp_script_from_command
from iso_builder.constants import PROFILE_AUTO
from iso_builder.models import Backend
from iso_builder.transaction import (
    cleanup_temporary_outputs,
    make_temporary_output_path,
    normalize_backend_output,
    publish_temporary_output,
    retarget_output_command,
    temporary_output_candidates,
)


class TransactionalOutputTests(unittest.TestCase):
    def test_all_backend_commands_retarget_exactly_one_output_argument(self) -> None:
        source = Path("C:/Source Folder")
        final_output = Path("D:/Output Folder/Setup.iso")
        temporary_output = Path("D:/Output Folder/.Setup.test.partial.iso")

        for name in (
            "oscdimg",
            "xorriso",
            "genisoimage",
            "mkisofs",
            "powershell_imapi",
            "hdiutil",
        ):
            with self.subTest(backend=name):
                backend = Backend(
                    name=name,
                    executable=f"/tools/{name}",
                    priority=1,
                    description="test",
                    supports_udf=True,
                    supports_joliet=True,
                    supports_iso_level3=True,
                    source="test",
                )
                command, _warnings = build_command(
                    backend,
                    source,
                    final_output,
                    "TEST",
                    PROFILE_AUTO,
                    True,
                    False,
                )
                try:
                    execution_command = retarget_output_command(
                        command,
                        final_output,
                        temporary_output,
                    )
                    self.assertEqual(command.count(str(final_output)), 1)
                    self.assertEqual(
                        execution_command.count(str(temporary_output)),
                        1,
                    )
                    self.assertNotIn(str(final_output), execution_command)
                finally:
                    cleanup_temp_script_from_command(command)

    def test_temporary_output_is_hidden_sibling_iso(self) -> None:
        final_output = Path("D:/Output Folder/Setup.iso")

        temporary_output = make_temporary_output_path(final_output, token="abc123")

        self.assertEqual(temporary_output.parent, final_output.parent)
        self.assertEqual(temporary_output.suffix.lower(), ".iso")
        self.assertEqual(
            temporary_output.name,
            ".Setup.abc123.partial.iso",
        )

    def test_command_output_is_retargeted_without_mutating_plan_command(self) -> None:
        final_output = Path("D:/Output/Setup.iso")
        temporary_output = Path("D:/Output/.Setup.test.partial.iso")
        planned_command = [
            "tool.exe",
            "-source",
            "C:/Source",
            "-output",
            str(final_output),
        ]

        execution_command = retarget_output_command(
            planned_command,
            final_output,
            temporary_output,
        )

        self.assertEqual(planned_command[-1], str(final_output))
        self.assertEqual(execution_command[-1], str(temporary_output))

    def test_command_retarget_rejects_missing_or_ambiguous_output(self) -> None:
        final_output = Path("D:/Output/Setup.iso")
        temporary_output = Path("D:/Output/.Setup.test.partial.iso")

        with self.assertRaisesRegex(RuntimeError, "exactly once"):
            retarget_output_command(
                ["tool.exe"],
                final_output,
                temporary_output,
            )
        with self.assertRaisesRegex(RuntimeError, "exactly once"):
            retarget_output_command(
                ["tool.exe", str(final_output), str(final_output)],
                final_output,
                temporary_output,
            )

    def test_publish_preserves_race_created_final_output(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            temporary_output = root / ".output.test.partial.iso"
            final_output = root / "output.iso"
            temporary_output.write_bytes(b"new")
            final_output.write_bytes(b"old")

            with self.assertRaisesRegex(RuntimeError, "appeared during build"):
                publish_temporary_output(temporary_output, final_output)

            self.assertEqual(final_output.read_bytes(), b"old")
            self.assertEqual(temporary_output.read_bytes(), b"new")

    def test_publish_creates_complete_final_and_removes_temporary_name(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            temporary_output = root / ".output.test.partial.iso"
            final_output = root / "output.iso"
            temporary_output.write_bytes(b"complete")

            publish_temporary_output(
                temporary_output,
                final_output,
                platform_name="nt" if os.name == "nt" else "posix",
            )

            self.assertFalse(temporary_output.exists())
            self.assertEqual(final_output.read_bytes(), b"complete")

    def test_posix_publish_remains_successful_if_temp_unlink_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            temporary_output = root / ".output.test.partial.iso"
            final_output = root / "output.iso"
            temporary_output.write_bytes(b"complete")

            publish_temporary_output(
                temporary_output,
                final_output,
                platform_name="posix",
                unlink_func=Mock(side_effect=OSError("busy")),
            )

            self.assertEqual(final_output.read_bytes(), b"complete")
            self.assertTrue(temporary_output.exists())

    def test_normalize_rejects_multiple_backend_output_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            temporary_output = Path(root_dir) / ".output.test.partial.iso"
            candidates = temporary_output_candidates(temporary_output)
            candidates[0].write_bytes(b"first")
            candidates[1].write_bytes(b"second")

            with self.assertRaisesRegex(RuntimeError, "multiple temporary"):
                normalize_backend_output(temporary_output)

    def test_cleanup_removes_only_known_temporary_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            temporary_output = root / ".output.test.partial.iso"
            unrelated = root / "keep.iso"
            unrelated.write_bytes(b"keep")
            candidates = temporary_output_candidates(temporary_output)
            for candidate in candidates:
                candidate.write_bytes(b"partial")

            cleanup_temporary_outputs(temporary_output)

            self.assertTrue(unrelated.exists())
            self.assertTrue(all(not candidate.exists() for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
