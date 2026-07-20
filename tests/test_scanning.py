import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from iso_builder.constants import PROFILE_AUTO, PROFILE_LEGACY
    from iso_builder.scanning import is_hidden_path, scan_source_folder
except ModuleNotFoundError:
    from universal_iso_builder_v1_4_1 import (
        PROFILE_AUTO,
        PROFILE_LEGACY,
        is_hidden_path,
        scan_source_folder,
    )


class ScanningTests(unittest.TestCase):
    def test_dot_name_is_hidden(self) -> None:
        self.assertTrue(is_hidden_path(Path(".secret")))
        self.assertFalse(is_hidden_path(Path("visible")))

    def test_scan_collects_counts_sizes_and_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir)
            (source / "empty").mkdir()
            (source / "visible.bin").write_bytes(b"abc")
            (source / ".hidden.txt").write_bytes(b"x")
            (source / "unicodé.txt").write_bytes(b"yz")

            result = scan_source_folder(source, PROFILE_AUTO, include_hidden=False)

            self.assertEqual(result.files, 3)
            self.assertEqual(result.dirs, 1)
            self.assertEqual(result.empty_dirs, 1)
            self.assertEqual(result.total_bytes, 6)
            self.assertEqual(result.largest_file_bytes, 3)
            self.assertEqual(result.largest_file_path, "visible.bin")
            self.assertEqual(result.hidden_items, 1)
            self.assertEqual(result.non_ascii_names, 1)
            self.assertTrue(any("Hidden include OFF" in warning for warning in result.warnings))
            self.assertTrue(any("Unicode/non-English" in warning for warning in result.warnings))

    def test_empty_source_warning(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            result = scan_source_folder(Path(source_dir), PROFILE_AUTO, include_hidden=True)
            self.assertEqual(result.files, 0)
            self.assertEqual(result.empty_dirs, 1)
            self.assertTrue(any("Source folder empty" in warning for warning in result.warnings))

    def test_directory_walk_error_is_counted_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir)

            def fake_walk(
                _source,
                *,
                topdown,
                onerror=None,
                followlinks,
            ):
                self.assertTrue(topdown)
                self.assertFalse(followlinks)
                self.assertIsNotNone(onerror)
                onerror(PermissionError(13, "Access denied", str(source / "blocked")))
                return []

            with patch("iso_builder.scanning.os.walk", side_effect=fake_walk):
                result = scan_source_folder(source, PROFILE_AUTO, include_hidden=True)

            self.assertEqual(result.unreadable, 1)
            self.assertTrue(
                any("file/folder item(s)" in warning for warning in result.warnings)
            )

    def test_absolute_long_path_is_measured_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir).resolve()
            long_dirname = "x" * 230

            with patch(
                "iso_builder.scanning.os.walk",
                return_value=[(str(source), [long_dirname], [])],
            ):
                result = scan_source_folder(source, PROFILE_AUTO, include_hidden=True)

            expected_length = len(str(source / long_dirname))
            self.assertEqual(result.max_abs_path_len, expected_length)
            self.assertGreater(result.max_abs_path_len, 240)
            self.assertTrue(
                any("absolute path" in warning for warning in result.warnings)
            )

    def test_legacy_profile_adds_unicode_risk_warning(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source = Path(source_dir)
            (source / "unicodé.txt").write_text("x", encoding="utf-8")

            result = scan_source_folder(source, PROFILE_LEGACY, include_hidden=True)

            self.assertTrue(any("Legacy profile" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
