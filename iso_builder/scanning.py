import os
from pathlib import Path

from .constants import PROFILE_LEGACY
from .models import ScanResult


def is_hidden_path(path: Path) -> bool:
    # Cross-platform approximation. On Windows, dot files are not always hidden,
    # but this is only for scan warnings/logging.
    try:
        if any(part.startswith(".") for part in path.parts if part not in (".", "..")):
            return True
        if os.name == "nt":
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1 and attrs & 2:
                return True
    except Exception:
        pass
    return False


def scan_source_folder(source: Path, profile: str, include_hidden: bool) -> ScanResult:
    result = ScanResult()
    source = source.resolve()

    for root, dirnames, filenames in os.walk(source, topdown=True, followlinks=False):
        root_path = Path(root)
        result.dirs += len(dirnames)

        if not dirnames and not filenames:
            result.empty_dirs += 1

        for dirname in dirnames:
            item = root_path / dirname
            rel = item.relative_to(source)
            result.max_rel_path_len = max(result.max_rel_path_len, len(str(rel)))
            result.max_name_len = max(result.max_name_len, len(dirname))
            if any(ord(ch) > 127 for ch in str(rel)):
                result.non_ascii_names += 1
            if is_hidden_path(item):
                result.hidden_items += 1
            if item.is_symlink():
                result.symlinks += 1

        for filename in filenames:
            item = root_path / filename
            try:
                rel = item.relative_to(source)
            except ValueError:
                rel = item

            result.max_rel_path_len = max(result.max_rel_path_len, len(str(rel)))
            result.max_name_len = max(result.max_name_len, len(filename))
            if any(ord(ch) > 127 for ch in str(rel)):
                result.non_ascii_names += 1
            if is_hidden_path(item):
                result.hidden_items += 1
            if item.is_symlink():
                result.symlinks += 1
                continue

            try:
                st = item.stat()
                size = st.st_size
            except OSError:
                result.unreadable += 1
                continue

            result.files += 1
            result.total_bytes += size
            if size > result.largest_file_bytes:
                result.largest_file_bytes = size
                result.largest_file_path = str(rel)
            if size > 4 * 1024 * 1024 * 1024:
                result.files_over_4gb += 1

    if result.files == 0:
        result.warnings.append("Source folder empty lag raha hai. ISO banega, lekin useful nahi hoga.")

    if result.unreadable:
        result.warnings.append(f"{result.unreadable} file(s) readable nahi hain. Build fail ho sakta hai.")

    if result.symlinks:
        result.warnings.append(
            f"{result.symlinks} symbolic link(s) mile. Backends symlinks ko different tarah handle kar sakte hain."
        )

    if result.hidden_items and not include_hidden:
        result.warnings.append(
            f"{result.hidden_items} hidden item(s) mile. Hidden include OFF hai, installer dependency miss ho sakti hai."
        )

    if result.files_over_4gb:
        result.warnings.append(
            f"{result.files_over_4gb} file(s) 4GB se badi hain. UDF/ISO-level-3 mode use karo; pure old ISO mode avoid karo."
        )

    if result.max_rel_path_len > 240:
        result.warnings.append(
            f"Long paths detected: max relative path {result.max_rel_path_len} chars. Old Windows/tools par issue aa sakta hai."
        )

    if result.max_name_len > 100:
        result.warnings.append(
            f"Very long file/folder names detected: max name {result.max_name_len} chars. UDF mode safest hai."
        )

    if result.non_ascii_names:
        result.warnings.append(
            f"{result.non_ascii_names} Unicode/non-English path(s) mile. UDF/Joliet mode use karo."
        )

    if profile == PROFILE_LEGACY:
        if result.files_over_4gb:
            result.warnings.append("Legacy profile + 4GB+ files risky hai. Auto/Modern UDF profile better hai.")
        if result.max_name_len > 64 or result.non_ascii_names:
            result.warnings.append("Legacy profile me long/Unicode names rename/truncate ho sakte hain. Auto/Modern profile better hai.")

    return result
