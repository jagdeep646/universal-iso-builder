from pathlib import Path
from typing import List, Tuple

from ..constants import (
    PROFILE_AUTO,
    PROFILE_LEGACY,
    PROFILE_MODERN,
    PROFILE_UDF_ONLY,
)
from ..models import Backend
from .imapi import make_windows_imapi_script


def build_oscdimg_command(
    executable: str,
    source: str,
    output_iso: str,
    label: str,
    profile: str,
    include_hidden: bool,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    command = [executable, "-m", f"-l{label}"]
    if include_hidden:
        command.append("-h")
    if optimize_duplicates:
        command.append("-o")

    if profile == PROFILE_UDF_ONLY:
        command.extend(["-u2", "-udfver102"])
    elif profile == PROFILE_LEGACY:
        command.append("-j1")
    else:
        command.extend(["-u1", "-udfver102"])

    command.extend([source, output_iso])
    return command, []


def build_xorriso_command(
    executable: str,
    source: str,
    output_iso: str,
    label: str,
    profile: str,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    command = [executable, "-as", "mkisofs", "-V", label, "-o", output_iso]
    warnings: List[str] = []

    if optimize_duplicates:
        warnings.append("Duplicate optimization xorriso ke liye skip kiya gaya for compatibility.")

    if profile == PROFILE_LEGACY:
        command.extend(["-iso-level", "3", "-J", "-joliet-long", "-R"])
    else:
        command.extend(["-iso-level", "3", "-J", "-joliet-long", "-R", "-udf"])
    command.append(source)
    return command, warnings


def build_mkisofs_compatible_command(
    backend_name: str,
    executable: str,
    source: str,
    output_iso: str,
    label: str,
    profile: str,
) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    if profile in (PROFILE_AUTO, PROFILE_MODERN, PROFILE_UDF_ONLY):
        warnings.append(
            f"{backend_name} generally UDF nahi banata. ISO9660+Joliet fallback use hoga."
        )

    command = [
        executable,
        "-iso-level",
        "3",
        "-J",
        "-joliet-long",
        "-R",
        "-V",
        label,
        "-o",
        output_iso,
        source,
    ]
    return command, warnings


def build_powershell_imapi_command(
    executable: str,
    source: str,
    output_iso: str,
    label: str,
    profile: str,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    script_path = make_windows_imapi_script()
    command = [
        executable,
        "-NoProfile",
        "-ExecutionPolicy",
        "RemoteSigned",
        "-File",
        str(script_path),
        "-Source",
        source,
        "-OutputIso",
        output_iso,
        "-Label",
        label,
    ]
    warnings: List[str] = []
    if optimize_duplicates:
        warnings.append("Duplicate optimization Windows IMAPI fallback me available nahi hai; skip kiya gaya.")
    if profile == PROFILE_UDF_ONLY:
        warnings.append("Windows IMAPI fallback ISO9660+Joliet+UDF create karta hai; UDF-only control available nahi hai.")
    warnings.append("Windows IMAPI fallback built-in hai, lekin complex/very large installer folders ke liye oscdimg zyada reliable hai.")
    return command, warnings


def build_hdiutil_command(
    executable: str,
    source: str,
    output_iso: str,
    label: str,
    profile: str,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    command = [executable, "makehybrid", "-iso", "-joliet", "-default-volume-name", label]
    if profile != PROFILE_LEGACY:
        command.append("-udf")
    command.extend(["-o", output_iso, source])

    warnings: List[str] = []
    if optimize_duplicates:
        warnings.append("Duplicate optimization hdiutil ke liye available nahi hai; skip kiya gaya.")
    return command, warnings


def build_command(
    backend: Backend,
    source: Path,
    output_iso: Path,
    label: str,
    profile: str,
    include_hidden: bool,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    """Dispatch command creation to the selected backend-specific builder."""
    executable = backend.executable
    source_text = str(source)
    output_text = str(output_iso)

    if backend.name == "oscdimg":
        return build_oscdimg_command(
            executable,
            source_text,
            output_text,
            label,
            profile,
            include_hidden,
            optimize_duplicates,
        )
    if backend.name == "xorriso":
        return build_xorriso_command(
            executable,
            source_text,
            output_text,
            label,
            profile,
            optimize_duplicates,
        )
    if backend.name in ("genisoimage", "mkisofs"):
        return build_mkisofs_compatible_command(
            backend.name,
            executable,
            source_text,
            output_text,
            label,
            profile,
        )
    if backend.name == "powershell_imapi":
        return build_powershell_imapi_command(
            executable,
            source_text,
            output_text,
            label,
            profile,
            optimize_duplicates,
        )
    if backend.name == "hdiutil":
        return build_hdiutil_command(
            executable,
            source_text,
            output_text,
            label,
            profile,
            optimize_duplicates,
        )

    raise ValueError(f"Unsupported backend: {backend.name}")
