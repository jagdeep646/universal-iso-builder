import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

from iso_builder.preflight import (
    FAT32_MAX_FILE_BYTES,
    estimate_iso_output_bytes,
    validate_output_storage,
)


DiskUsage = namedtuple("DiskUsage", "total used free")


class OutputStoragePreflightTests(unittest.TestCase):
    def test_insufficient_free_space_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "output.iso"
            required = estimate_iso_output_bytes(1000)

            with self.assertRaisesRegex(RuntimeError, "Insufficient free space"):
                validate_output_storage(
                    output_iso,
                    source_bytes=1000,
                    disk_usage_func=lambda _path: DiskUsage(
                        total=required * 2,
                        used=required + 1,
                        free=required - 1,
                    ),
                    filesystem_func=lambda _path: "NTFS",
                )

    def test_fat32_large_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "output.iso"

            with self.assertRaisesRegex(RuntimeError, "FAT32"):
                validate_output_storage(
                    output_iso,
                    source_bytes=FAT32_MAX_FILE_BYTES,
                    disk_usage_func=lambda _path: DiskUsage(
                        total=FAT32_MAX_FILE_BYTES * 4,
                        used=0,
                        free=FAT32_MAX_FILE_BYTES * 4,
                    ),
                    filesystem_func=lambda _path: "fat32",
                )

    def test_existing_ancestor_is_used_for_auto_package_output(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            existing_output = root / "output"
            existing_output.mkdir()
            output_iso = existing_output / "package" / "image.iso"
            probes = []

            status = validate_output_storage(
                output_iso,
                source_bytes=1024,
                disk_usage_func=lambda path: (
                    probes.append(path)
                    or DiskUsage(total=10**9, used=0, free=10**9)
                ),
                filesystem_func=lambda path: (
                    probes.append(path)
                    or "NTFS"
                ),
            )

            self.assertEqual(probes, [existing_output, existing_output])
            self.assertEqual(status.probe_path, existing_output)
            self.assertEqual(status.filesystem, "NTFS")
            self.assertGreater(status.required_bytes, 1024)

    def test_unknown_filesystem_is_not_falsely_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            output_iso = Path(root_dir) / "output.iso"

            status = validate_output_storage(
                output_iso,
                source_bytes=1024,
                disk_usage_func=lambda _path: DiskUsage(
                    total=10**9,
                    used=0,
                    free=10**9,
                ),
                filesystem_func=lambda _path: None,
            )

            self.assertIsNone(status.filesystem)


if __name__ == "__main__":
    unittest.main()
