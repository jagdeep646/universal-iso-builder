import platform
import shutil
from pathlib import Path
from typing import List, Optional

from ..constants import (
    PROFILE_AUTO,
    PROFILE_LEGACY,
    PROFILE_MODERN,
    PROFILE_UDF_ONLY,
    WINDOWS_OSCDIMG_PATHS,
    WINDOWS_POWERSHELL_PATHS,
)
from ..models import Backend


def find_windows_powershell() -> Optional[str]:
    """Find Windows PowerShell even when PATH is incomplete.

    Some technician/customer PCs launch Python from environments where System32 is not
    visible in PATH. This fallback checks the normal Windows locations directly.
    """
    candidates = [
        shutil.which("powershell.exe"),
        shutil.which("powershell"),
        shutil.which("pwsh.exe"),
        shutil.which("pwsh"),
        *WINDOWS_POWERSHELL_PATHS,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = Path(candidate)
            if path.exists() and path.is_file():
                return str(path)
        except Exception:
            # shutil.which can return unusual values in rare cases; skip them safely.
            continue
    return None


def detect_backends() -> List[Backend]:
    backends: List[Backend] = []
    system = platform.system().lower()

    def add_if_found(name: str, exe: Optional[str], priority: int, description: str,
                     supports_udf: bool, supports_joliet: bool, supports_iso_level3: bool,
                     source: str) -> None:
        if exe:
            backends.append(
                Backend(
                    name=name,
                    executable=exe,
                    priority=priority,
                    description=description,
                    supports_udf=supports_udf,
                    supports_joliet=supports_joliet,
                    supports_iso_level3=supports_iso_level3,
                    source=source,
                )
            )

    oscdimg = shutil.which("oscdimg") or shutil.which("oscdimg.exe")
    if not oscdimg and system == "windows":
        for path_text in WINDOWS_OSCDIMG_PATHS:
            if Path(path_text).exists():
                oscdimg = path_text
                break
        if not oscdimg:
            kit_root = Path(r"C:\Program Files (x86)\Windows Kits")
            if kit_root.exists():
                matches = list(kit_root.glob(r"**\Oscdimg\oscdimg.exe"))
                if matches:
                    oscdimg = str(matches[0])
    add_if_found(
        "oscdimg",
        oscdimg,
        10,
        "Microsoft OSCDIMG from Windows ADK - best for Windows setup ISO",
        True,
        True,
        True,
        "PATH / Windows ADK",
    )

    if system == "windows":
        powershell = find_windows_powershell()
        add_if_found(
            "powershell_imapi",
            powershell,
            15,
            "Windows built-in PowerShell + IMAPI fallback - no ADK required",
            True,
            True,
            False,
            "Windows built-in / hardcoded path",
        )

    xorriso = shutil.which("xorriso")
    add_if_found(
        "xorriso",
        xorriso,
        20,
        "xorriso mkisofs-compatible mode - strong fallback on Linux/macOS",
        True,
        True,
        True,
        "PATH",
    )

    genisoimage = shutil.which("genisoimage")
    add_if_found(
        "genisoimage",
        genisoimage,
        30,
        "genisoimage - ISO/Joliet fallback, usually no UDF",
        False,
        True,
        True,
        "PATH",
    )

    mkisofs = shutil.which("mkisofs")
    add_if_found(
        "mkisofs",
        mkisofs,
        40,
        "mkisofs - ISO/Joliet fallback, usually no UDF",
        False,
        True,
        True,
        "PATH",
    )

    hdiutil = shutil.which("hdiutil")
    if system == "darwin":
        add_if_found(
            "hdiutil",
            hdiutil,
            50,
            "macOS hdiutil makehybrid - built-in ISO/Joliet/UDF fallback",
            True,
            True,
            False,
            "macOS built-in",
        )

    seen = set()
    unique: List[Backend] = []
    for backend in sorted(backends, key=lambda item: item.priority):
        key = (
            backend.name,
            str(Path(backend.executable).resolve())
            if Path(backend.executable).exists()
            else backend.executable,
        )
        if key not in seen:
            unique.append(backend)
            seen.add(key)
    return unique


def select_backend(backends: List[Backend], profile: str) -> Optional[Backend]:
    if not backends:
        return None

    if profile in (PROFILE_AUTO, PROFILE_MODERN, PROFILE_UDF_ONLY):
        udf_backends = [backend for backend in backends if backend.supports_udf]
        if udf_backends:
            return udf_backends[0]
        return backends[0]

    if profile == PROFILE_LEGACY:
        joliet_backends = [backend for backend in backends if backend.supports_joliet]
        if joliet_backends:
            return joliet_backends[0]
        return backends[0]

    return backends[0]


def select_requested_backend(
    backends: List[Backend],
    backend_choice: str,
    profile: str,
) -> Backend:
    """Resolve an Auto or explicit backend choice without reading GUI state."""
    if not backends:
        raise RuntimeError("No ISO backend found. Windows par oscdimg install karo ya PowerShell PATH check karo; Linux/macOS par xorriso/genisoimage/mkisofs/hdiutil use karo.")

    if backend_choice == "Auto":
        backend = select_backend(backends, profile)
        if not backend:
            raise RuntimeError("No compatible backend selected.")
        return backend

    selected_name = backend_choice.split(" | ", 1)[0].strip()
    for backend in backends:
        if backend.name == selected_name and backend.executable in backend_choice:
            return backend
    for backend in backends:
        if backend.name == selected_name:
            return backend
    raise RuntimeError("Selected backend not found. Refresh backends and try again.")
