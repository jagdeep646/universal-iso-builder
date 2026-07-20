import ctypes
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .utils import human_size


FAT32_MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024 - 1
MIN_ISO_OVERHEAD_BYTES = 64 * 1024 * 1024
ISO_OVERHEAD_DIVISOR = 50


@dataclass(frozen=True)
class OutputStorageStatus:
    probe_path: Path
    filesystem: Optional[str]
    required_bytes: int
    free_bytes: int


def estimate_iso_output_bytes(source_bytes: int) -> int:
    payload_bytes = max(0, int(source_bytes))
    proportional_overhead = (
        payload_bytes + ISO_OVERHEAD_DIVISOR - 1
    ) // ISO_OVERHEAD_DIVISOR
    overhead_bytes = max(MIN_ISO_OVERHEAD_BYTES, proportional_overhead)
    return payload_bytes + overhead_bytes


def find_existing_output_ancestor(output_iso: Path) -> Path:
    candidate = output_iso.parent
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise RuntimeError(
                f"Output filesystem inspect nahi ho saka: {output_iso.parent}"
            )
        candidate = parent
    if not candidate.is_dir():
        raise RuntimeError(f"Output parent directory valid nahi hai: {candidate}")
    return candidate


def detect_filesystem_type(path: Path) -> Optional[str]:
    if os.name != "nt":
        return None

    try:
        volume_path = ctypes.create_unicode_buffer(261)
        if not ctypes.windll.kernel32.GetVolumePathNameW(
            str(path),
            volume_path,
            len(volume_path),
        ):
            return None

        filesystem_name = ctypes.create_unicode_buffer(261)
        if not ctypes.windll.kernel32.GetVolumeInformationW(
            volume_path.value,
            None,
            0,
            None,
            None,
            None,
            filesystem_name,
            len(filesystem_name),
        ):
            return None
        return filesystem_name.value.upper() or None
    except Exception:
        return None


def validate_output_storage(
    output_iso: Path,
    source_bytes: int,
    *,
    disk_usage_func: Optional[Callable[[Path], object]] = None,
    filesystem_func: Optional[Callable[[Path], Optional[str]]] = None,
) -> OutputStorageStatus:
    probe_path = find_existing_output_ancestor(output_iso)
    disk_usage = (disk_usage_func or shutil.disk_usage)(probe_path)
    filesystem = (filesystem_func or detect_filesystem_type)(probe_path)
    if filesystem:
        filesystem = filesystem.upper()

    required_bytes = estimate_iso_output_bytes(source_bytes)
    free_bytes = int(disk_usage.free)

    if filesystem in {"FAT", "FAT32"} and required_bytes > FAT32_MAX_FILE_BYTES:
        raise RuntimeError(
            f"Output filesystem {filesystem} single ISO file ko 4GB se bada store nahi kar sakta. "
            f"Estimated ISO requirement: {human_size(required_bytes)}. NTFS/exFAT/APFS/ext filesystem use karo."
        )

    if free_bytes < required_bytes:
        raise RuntimeError(
            "Insufficient free space for ISO output. "
            f"Estimated required: {human_size(required_bytes)} | "
            f"Available: {human_size(free_bytes)}."
        )

    return OutputStorageStatus(
        probe_path=probe_path,
        filesystem=filesystem,
        required_bytes=required_bytes,
        free_bytes=free_bytes,
    )
