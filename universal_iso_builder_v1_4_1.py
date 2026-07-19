#!/usr/bin/env python3
"""
Universal ISO Builder - Safe setup folder to ISO creator

Goal:
- Build a non-bootable ISO from any setup/software folder without modifying source files.
- Use the best local ISO backend available for speed and compatibility.
- Fall back between installed tools where possible.
- Use only Python standard library for the GUI and orchestration.

Important:
- Python standard library does NOT include a reliable UDF/ISO writer.
- Actual ISO creation uses the best local backend available:
  Windows: oscdimg.exe from Windows ADK (recommended)
  Windows fallback: built-in PowerShell + IMAPI COM
  macOS: hdiutil (built-in)
  Linux/macOS/Windows if installed: xorriso / genisoimage / mkisofs

This app does NOT bypass antivirus and does NOT modify, hide, encrypt, or pack executables.
"""

from __future__ import annotations

import hashlib
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Universal ISO Builder"
APP_VERSION = "1.4.1"

PROFILE_AUTO = "Auto - Best Compatible"
PROFILE_MODERN = "Modern Windows - UDF + ISO"
PROFILE_LEGACY = "Old PC - ISO9660 + Joliet"
PROFILE_UDF_ONLY = "UDF Only - Modern"

PROFILES = [PROFILE_AUTO, PROFILE_MODERN, PROFILE_LEGACY, PROFILE_UDF_ONLY]

WINDOWS_OSCDIMG_PATHS = [
    r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\x86\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\11\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\11\Assessment and Deployment Kit\Deployment Tools\x86\Oscdimg\oscdimg.exe",
]

WINDOWS_POWERSHELL_PATHS = [
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Program Files\PowerShell\7\pwsh.exe",
    r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
]


@dataclass
class Backend:
    name: str
    executable: str
    priority: int
    description: str
    supports_udf: bool
    supports_joliet: bool
    supports_iso_level3: bool
    source: str


@dataclass
class ScanResult:
    files: int = 0
    dirs: int = 0
    total_bytes: int = 0
    largest_file_bytes: int = 0
    largest_file_path: str = ""
    max_rel_path_len: int = 0
    max_name_len: int = 0
    non_ascii_names: int = 0
    hidden_items: int = 0
    symlinks: int = 0
    unreadable: int = 0
    empty_dirs: int = 0
    files_over_4gb: int = 0
    warnings: List[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


@dataclass(frozen=True)
class BuildOptions:
    """Immutable snapshot of user-selected settings for one build."""

    profile: str
    include_hidden: bool
    generate_hash: bool
    optimize_duplicates: bool
    auto_package: bool
    dry_run: bool


@dataclass
class BuildPlan:
    """Structured build data passed between preparation and execution layers."""

    source: Path
    output_iso: Path
    label: str
    backend: Backend
    scan: ScanResult
    command: List[str]
    warnings: List[str]
    options: BuildOptions


def human_size(num: int) -> str:
    value = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if value < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num} B"


def quote_cmd(parts: Sequence[str]) -> str:
    def q(item: str) -> str:
        item = str(item)
        if not item:
            return '""'
        if any(ch.isspace() for ch in item) or any(ch in item for ch in ['"', "'", "&", "(", ")"]):
            return '"' + item.replace('"', '\\"') + '"'
        return item

    return " ".join(q(p) for p in parts)


def clean_volume_label(label: str) -> str:
    """Safe label for common ISO/UDF tools. Keep it simple for old systems."""
    label = (label or "SOFTWARE_SETUP").strip().upper()
    label = re.sub(r"[^A-Z0-9_]", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    if not label:
        label = "SOFTWARE_SETUP"
    return label[:32]


def normalize_iso_name(name: str) -> str:
    name = (name or "Software_Setup.iso").strip()
    name = re.sub(r"[<>:\"/\\|?*]", "_", name)
    if not name.lower().endswith(".iso"):
        name += ".iso"
    return name


def safe_path_component(name: str, fallback: str = "Software_Setup") -> str:
    """Create a safe Windows/macOS/Linux folder/file base name while keeping it readable."""
    name = (name or fallback).strip()
    name = re.sub(r"[<>:\"/\\|?*]", "_", name)
    name = re.sub(r"[\x00-\x1f]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(" .")
    if not name:
        name = fallback

    # Avoid reserved Windows device names.
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if name.upper() in reserved:
        name = f"{name}_SETUP"

    # Keep room for suffixes like _ISO and .iso on older paths.
    return name[:120]


def auto_names_from_source(source: Path) -> Tuple[str, str, str]:
    """Return (safe_base_name, iso_file_name, volume_label) from original source folder name."""
    safe_base = safe_path_component(source.name, "Software_Setup")
    iso_name = normalize_iso_name(safe_base)
    label = clean_volume_label(source.name)
    return safe_base, iso_name, label


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

    # Windows recommended backend.
    oscdimg = shutil.which("oscdimg") or shutil.which("oscdimg.exe")
    if not oscdimg and system == "windows":
        for p in WINDOWS_OSCDIMG_PATHS:
            if Path(p).exists():
                oscdimg = p
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

    # Windows built-in fallback through IMAPI COM, driven by PowerShell.
    # Slower/less controllable than oscdimg, but requires no ADK install.
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

    # xorriso is usually the best open-source cross-platform backend if installed.
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

    # macOS built-in backend.
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

    # Deduplicate by executable path/name.
    seen = set()
    unique: List[Backend] = []
    for b in sorted(backends, key=lambda x: x.priority):
        key = (b.name, str(Path(b.executable).resolve()) if Path(b.executable).exists() else b.executable)
        if key not in seen:
            unique.append(b)
            seen.add(key)
    return unique


def select_backend(backends: List[Backend], profile: str) -> Optional[Backend]:
    if not backends:
        return None

    if profile in (PROFILE_AUTO, PROFILE_MODERN, PROFILE_UDF_ONLY):
        udf_backends = [b for b in backends if b.supports_udf]
        if udf_backends:
            return udf_backends[0]
        return backends[0]

    if profile == PROFILE_LEGACY:
        joliet_backends = [b for b in backends if b.supports_joliet]
        if joliet_backends:
            return joliet_backends[0]
        return backends[0]

    return backends[0]


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


def make_windows_imapi_script() -> Path:
    # Create a temporary PowerShell script that uses Windows IMAPI COM to create a data ISO.
    script = r"""
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$OutputIso,
    [Parameter(Mandatory=$true)][string]$Label
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $Source -PathType Container)) {
    throw "Source folder not found: $Source"
}
$outDir = Split-Path -LiteralPath $OutputIso -Parent
if (!(Test-Path -LiteralPath $outDir -PathType Container)) {
    throw "Output folder not found: $outDir"
}
if (Test-Path -LiteralPath $OutputIso) {
    throw "Output ISO already exists: $OutputIso"
}

$cs = @"
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class IsoStreamWriter
{
    public static void Save(object streamObject, string fileName)
    {
        IStream stream = (IStream)streamObject;
        stream.Seek(0, 0, IntPtr.Zero);

        byte[] buffer = new byte[1024 * 1024];
        IntPtr bytesReadPtr = Marshal.AllocHGlobal(4);
        try
        {
            using (FileStream file = new FileStream(fileName, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                while (true)
                {
                    Marshal.WriteInt32(bytesReadPtr, 0);
                    stream.Read(buffer, buffer.Length, bytesReadPtr);
                    int bytesRead = Marshal.ReadInt32(bytesReadPtr);
                    if (bytesRead <= 0)
                    {
                        break;
                    }
                    file.Write(buffer, 0, bytesRead);
                }
            }
        }
        finally
        {
            Marshal.FreeHGlobal(bytesReadPtr);
        }
    }
}
"@

Add-Type -TypeDefinition $cs -Language CSharp

Write-Host "Using Windows IMAPI fallback..."
Write-Host "Source: $Source"
Write-Host "Output: $OutputIso"
Write-Host "Label: $Label"

$fsi = New-Object -ComObject IMAPI2FS.MsftFileSystemImage
# 1=ISO9660, 2=Joliet, 4=UDF. 7 creates all three for broad Windows compatibility.
$fsi.FileSystemsToCreate = 7
$fsi.VolumeName = $Label
try {
    # 2,147,483,647 blocks * 2048 bytes gives a very high virtual media size ceiling.
    $fsi.FreeMediaBlocks = 2147483647
} catch {
    Write-Host "FreeMediaBlocks tune skipped: $($_.Exception.Message)"
}

Write-Host "Adding source tree to ISO image..."
$fsi.Root.AddTree($Source, $false)

Write-Host "Creating ISO image stream..."
$result = $fsi.CreateResultImage()

Write-Host "Writing ISO file. This can take time for big setup folders..."
[IsoStreamWriter]::Save($result.ImageStream, $OutputIso)

Write-Host "ISO created successfully."
"""
    temp_dir = Path(tempfile.gettempdir())
    script_path = temp_dir / f"universal_iso_builder_imapi_{os.getpid()}_{int(time.time() * 1000)}.ps1"
    script_path.write_text(script, encoding="utf-8")
    return script_path


def cleanup_temp_script_from_command(cmd: Sequence[str]) -> None:
    try:
        if "-File" not in cmd:
            return
        idx = list(cmd).index("-File") + 1
        script_path = Path(cmd[idx])
        if script_path.name.startswith("universal_iso_builder_imapi_") and script_path.suffix.lower() == ".ps1":
            script_path.unlink(missing_ok=True)
    except Exception:
        pass


def build_command(
    backend: Backend,
    source: Path,
    output_iso: Path,
    label: str,
    profile: str,
    include_hidden: bool,
    optimize_duplicates: bool,
) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    exe = backend.executable
    source_s = str(source)
    output_s = str(output_iso)

    if backend.name == "oscdimg":
        cmd = [exe, "-m", f"-l{label}"]
        if include_hidden:
            cmd.append("-h")
        if optimize_duplicates:
            cmd.append("-o")

        if profile == PROFILE_UDF_ONLY:
            cmd.extend(["-u2", "-udfver102"])
        elif profile == PROFILE_LEGACY:
            # Joliet + DOS-compatible ISO namespace. Good old-PC fallback.
            cmd.append("-j1")
        else:
            # Best default: UDF Unicode names + ISO 9660 8.3 fallback namespace.
            cmd.extend(["-u1", "-udfver102"])

        cmd.extend([source_s, output_s])
        return cmd, warnings

    if backend.name == "xorriso":
        cmd = [exe, "-as", "mkisofs", "-V", label, "-o", output_s]

        if optimize_duplicates:
            # xorriso supports duplicate file detection via hard-link-ish behavior in some modes,
            # but options vary. Keep compatibility over risky optimization.
            warnings.append("Duplicate optimization xorriso ke liye skip kiya gaya for compatibility.")

        if profile == PROFILE_LEGACY:
            cmd.extend(["-iso-level", "3", "-J", "-joliet-long", "-R"])
        else:
            # ISO Level 3 for large files, Joliet for Windows names, Rock Ridge for POSIX names,
            # UDF for modern Windows compatibility.
            cmd.extend(["-iso-level", "3", "-J", "-joliet-long", "-R", "-udf"])
        cmd.append(source_s)
        return cmd, warnings

    if backend.name in ("genisoimage", "mkisofs"):
        if profile in (PROFILE_AUTO, PROFILE_MODERN, PROFILE_UDF_ONLY):
            warnings.append(
                f"{backend.name} generally UDF nahi banata. ISO9660+Joliet fallback use hoga."
            )
        cmd = [
            exe,
            "-iso-level",
            "3",
            "-J",
            "-joliet-long",
            "-R",
            "-V",
            label,
            "-o",
            output_s,
            source_s,
        ]
        return cmd, warnings

    if backend.name == "powershell_imapi":
        script_path = make_windows_imapi_script()
        cmd = [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-File",
            str(script_path),
            "-Source",
            source_s,
            "-OutputIso",
            output_s,
            "-Label",
            label,
        ]
        if optimize_duplicates:
            warnings.append("Duplicate optimization Windows IMAPI fallback me available nahi hai; skip kiya gaya.")
        if profile == PROFILE_UDF_ONLY:
            warnings.append("Windows IMAPI fallback ISO9660+Joliet+UDF create karta hai; UDF-only control available nahi hai.")
        warnings.append("Windows IMAPI fallback built-in hai, lekin complex/very large installer folders ke liye oscdimg zyada reliable hai.")
        return cmd, warnings

    if backend.name == "hdiutil":
        cmd = [exe, "makehybrid", "-iso", "-joliet", "-default-volume-name", label]
        if profile != PROFILE_LEGACY:
            cmd.append("-udf")
        cmd.extend(["-o", output_s, source_s])
        if optimize_duplicates:
            warnings.append("Duplicate optimization hdiutil ke liye available nahi hai; skip kiya gaya.")
        return cmd, warnings

    raise ValueError(f"Unsupported backend: {backend.name}")


def calculate_sha256(file_path: Path, progress: Optional[Callable[[int], None]] = None) -> str:
    hasher = hashlib.sha256()
    total_read = 0
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
            total_read += len(chunk)
            if progress:
                progress(total_read)
    return hasher.hexdigest()


def run_process(cmd: List[str], log: Callable[[str], None]) -> int:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    process.wait()
    return int(process.returncode)



class IsoBuilderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1180x820")
        self.minsize(1040, 720)

        self.ui_queue: "queue.Queue[Tuple[str, str, str]]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.detected_backends: List[Backend] = []

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.iso_name_var = tk.StringVar(value="Software_Setup.iso")
        self.label_var = tk.StringVar(value="SOFTWARE_SETUP")
        self.profile_var = tk.StringVar(value=PROFILE_AUTO)
        self.backend_var = tk.StringVar(value="Auto")
        self.include_hidden_var = tk.BooleanVar(value=True)
        self.hash_var = tk.BooleanVar(value=True)
        self.optimize_var = tk.BooleanVar(value=False)
        self.auto_package_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="Select a source folder to begin")

        self._configure_styles()
        self._build_ui()
        self.refresh_backends()
        self.after(150, self._process_ui_queue)

    def _configure_styles(self) -> None:
        self.colors = {
            "bg": "#0f172a",
            "surface": "#111827",
            "surface_2": "#162033",
            "card": "#182233",
            "card_2": "#1f2937",
            "border": "#2b3648",
            "text": "#e5e7eb",
            "muted": "#94a3b8",
            "accent": "#22c55e",
            "accent_2": "#38bdf8",
            "warning": "#f59e0b",
            "danger": "#ef4444",
        }

        self.configure(bg=self.colors["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("App.TFrame", background=self.colors["bg"])
        style.configure("Surface.TFrame", background=self.colors["surface"])
        style.configure("Card.TFrame", background=self.colors["card"], relief="flat")
        style.configure("Inner.TFrame", background=self.colors["card_2"], relief="flat")
        style.configure("Header.TFrame", background=self.colors["surface"])
        style.configure("Status.TFrame", background=self.colors["surface_2"])

        style.configure("Title.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Segoe UI", 24, "bold"))
        style.configure("Subtitle.TLabel", background=self.colors["surface"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        style.configure("SectionTitle.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("Body.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("Badge.TLabel", background=self.colors["surface_2"], foreground=self.colors["accent_2"], font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillGood.TLabel", background="#0b2a1b", foreground="#86efac", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillInfo.TLabel", background="#082f49", foreground="#7dd3fc", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillWarn.TLabel", background="#3a2405", foreground="#fcd34d", font=("Segoe UI", 9, "bold"), padding=(10, 4))

        style.configure("Section.TLabelframe", background=self.colors["card"], borderwidth=1, relief="solid", bordercolor=self.colors["border"])
        style.configure("Section.TLabelframe.Label", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 11, "bold"))

        style.configure("App.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("StatusLabel.TLabel", background=self.colors["surface_2"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
        style.configure("StatusHint.TLabel", background=self.colors["surface_2"], foreground=self.colors["muted"], font=("Segoe UI", 9))

        style.configure("App.TButton", font=("Segoe UI", 10), padding=(14, 10), background=self.colors["card_2"], foreground=self.colors["text"], borderwidth=0)
        style.map("App.TButton", background=[("active", "#273447")])
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 11), background="#16a34a", foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#15803d")])

        style.configure("App.TCheckbutton", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 9))
        style.map("App.TCheckbutton", background=[("active", self.colors["card"])], foreground=[("disabled", self.colors["muted"])])

        style.configure("App.TEntry", fieldbackground="#0b1220", background="#0b1220", foreground=self.colors["text"], insertcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=8)
        style.map(
            "App.TEntry",
            fieldbackground=[("!disabled", "#0b1220")],
            foreground=[("!disabled", self.colors["text"])],
        )

        style.configure("App.TCombobox", fieldbackground="#0b1220", background="#0b1220", foreground=self.colors["text"], arrowcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=6)
        style.map(
            "App.TCombobox",
            fieldbackground=[("readonly", "#0b1220"), ("!disabled", "#0b1220")],
            foreground=[("readonly", self.colors["text"]), ("!disabled", self.colors["text"])],
            selectbackground=[("readonly", "#0b1220")],
            selectforeground=[("readonly", self.colors["text"])],
            background=[("readonly", "#0b1220"), ("active", "#0b1220")],
            arrowcolor=[("readonly", self.colors["text"]), ("active", self.colors["text"])],
        )

        style.configure("Vertical.TScrollbar", background=self.colors["card_2"], troughcolor="#0b1220", bordercolor=self.colors["border"], arrowcolor=self.colors["text"])

        self.option_add("*TCombobox*Listbox.background", "#0b1220")
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", "#1d4ed8")
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        header = ttk.Frame(outer, style="Header.TFrame", padding=18)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        logo_wrap = tk.Frame(header, bg=self.colors["surface"], highlightthickness=0)
        logo_wrap.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        logo = tk.Canvas(logo_wrap, width=68, height=68, bg=self.colors["surface"], highlightthickness=0, bd=0)
        logo.pack()
        self._draw_logo(logo)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="Modern folder-to-ISO builder with backend auto-detect, compatibility fallback, and clean package output.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        badge_bar = ttk.Frame(header, style="Header.TFrame")
        badge_bar.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Label(badge_bar, text="SAFE PACKAGING", style="PillGood.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(badge_bar, text="AUTO BACKEND", style="PillInfo.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(badge_bar, text="SHA256 READY", style="PillWarn.TLabel").pack(side="left")

        summary = ttk.Frame(outer, style="Status.TFrame", padding=(14, 10))
        summary.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, textvariable=self.status_var, style="StatusLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.summary_var, style="StatusHint.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        body = ttk.Frame(outer, style="App.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        # Input / Output card
        form = ttk.LabelFrame(left, text="Input / Output", style="Section.TLabelframe", padding=14)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self._add_labeled_row(form, 0, "Source folder", self.source_var, self.pick_source, "Browse")
        self._add_labeled_row(form, 1, "Output folder", self.output_var, self.pick_output, "Browse")
        self._add_labeled_row(form, 2, "ISO file name", self.iso_name_var)
        self._add_labeled_row(form, 3, "Volume label", self.label_var)

        # Settings card
        settings = ttk.LabelFrame(left, text="ISO Settings", style="Section.TLabelframe", padding=14)
        settings.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="Compatibility profile", style="App.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Combobox(settings, textvariable=self.profile_var, values=PROFILES, state="readonly", style="App.TCombobox").grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(settings, text="Backend", style="App.TLabel").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=6)
        self.backend_combo = ttk.Combobox(settings, textvariable=self.backend_var, values=["Auto"], state="readonly", style="App.TCombobox")
        self.backend_combo.grid(row=0, column=3, sticky="ew", pady=6)

        checks_frame = ttk.Frame(settings, style="Card.TFrame")
        checks_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        checks_frame.columnconfigure(0, weight=1)
        checks_frame.columnconfigure(1, weight=1)

        left_checks = ttk.Frame(checks_frame, style="Card.TFrame")
        left_checks.grid(row=0, column=0, sticky="w")
        right_checks = ttk.Frame(checks_frame, style="Card.TFrame")
        right_checks.grid(row=0, column=1, sticky="w")

        ttk.Checkbutton(left_checks, text="Include hidden files", variable=self.include_hidden_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(left_checks, text="Generate SHA256 hash", variable=self.hash_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(right_checks, text="Auto name + package folder", variable=self.auto_package_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(right_checks, text="Optimize duplicate files (when supported)", variable=self.optimize_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(right_checks, text="Dry run only", variable=self.dry_run_var, style="App.TCheckbutton").pack(anchor="w", pady=2)

        # Quick action card
        actions = ttk.LabelFrame(right, text="Quick Actions", style="Section.TLabelframe", padding=14)
        actions.grid(row=0, column=0, sticky="ew")
        actions.columnconfigure((0,1), weight=1)
        ttk.Button(actions, text="Refresh Backends", style="App.TButton", command=self.refresh_backends).grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=6)
        ttk.Button(actions, text="Scan Folder", style="App.TButton", command=self.scan_only).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(actions, text="Show Command", style="App.TButton", command=self.show_command).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=6)
        ttk.Button(actions, text="Clear Logs", style="App.TButton", command=self.clear_logs).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(actions, text="Build ISO", style="Primary.TButton", command=self.start_build).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        info = ttk.LabelFrame(right, text="Best Practice", style="Section.TLabelframe", padding=14)
        info.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        info.columnconfigure(0, weight=1)
        ttk.Label(info, text="• Source folder ko original state me rakha jata hai.", style="Body.TLabel").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Auto mode source folder ke name se ISO aur label banata hai.", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Package folder me ISO + SHA256 hash dono save hote hain.", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Windows par oscdimg best backend hai; PowerShell IMAPI fallback available hai.", style="Body.TLabel").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Ye app non-bootable data ISO banata hai.", style="Body.TLabel").grid(row=4, column=0, sticky="w", pady=2)

        tips = ttk.Frame(right, style="Card.TFrame", padding=(2, 12, 2, 0))
        tips.grid(row=2, column=0, sticky="ew")
        ttk.Label(tips, text="UI refreshed with a modern layout and custom in-app branding.", style="Muted.TLabel").pack(anchor="w")

        log_frame = ttk.LabelFrame(outer, text="Logs", style="Section.TLabelframe", padding=12)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=18,
            font=("Cascadia Mono", 10),
            bg="#0b1220",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            selectbackground="#1d4ed8",
            selectforeground="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        footer = ttk.Frame(outer, style="App.TFrame", padding=(2, 10, 2, 0))
        footer.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="Note: This app creates non-bootable data ISOs. It does not bypass antivirus or run installers.",
            style="Muted.TLabel",
        ).pack(anchor="w")

    def _draw_logo(self, canvas: tk.Canvas) -> None:
        canvas.create_oval(6, 6, 62, 62, fill="#0b1220", outline="#2b3648", width=2)
        canvas.create_arc(12, 12, 56, 56, start=30, extent=280, style="arc", outline="#38bdf8", width=5)
        canvas.create_oval(22, 22, 46, 46, fill="#16a34a", outline="")
        canvas.create_rectangle(32, 15, 36, 53, fill="#e5e7eb", outline="")
        canvas.create_rectangle(20, 31, 48, 35, fill="#e5e7eb", outline="")
        canvas.create_text(34, 58, text="ISO", fill="#94a3b8", font=("Segoe UI", 8, "bold"))

    def _add_labeled_row(self, parent: ttk.LabelFrame, row: int, label: str, var: tk.StringVar, command: Optional[Callable[[], None]] = None, button_text: str = "") -> None:
        ttk.Label(parent, text=label, style="App.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(parent, textvariable=var, style="App.TEntry").grid(row=row, column=1, sticky="ew", pady=6)
        if command:
            ttk.Button(parent, text=button_text or "Browse", style="App.TButton", command=command).grid(row=row, column=2, padx=(8, 0), pady=6)

    def _set_status(self, title: str, hint: str = "") -> None:
        self.status_var.set(title)
        if hint:
            self.summary_var.set(hint)

    def pick_source(self) -> None:
        folder = filedialog.askdirectory(title="Select source setup folder")
        if folder:
            source = Path(folder)
            self.source_var.set(folder)
            if not self.output_var.get().strip():
                self.output_var.set(str(source.parent))
            if self.auto_package_var.get():
                safe_base, iso_name, label = auto_names_from_source(source)
                self.iso_name_var.set(iso_name)
                self.label_var.set(label)
                self.log(f"Auto naming set from source: {safe_base}")
                self.log(f"Package folder will be: {safe_base}_ISO")
            self._set_status("Source selected", f"Ready to package: {source.name}")
            self.log(f"Source selected: {folder}")

    def pick_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)
            self._set_status("Output folder selected", folder)
            self.log(f"Output selected: {folder}")

    def log(self, msg: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
        self.update_idletasks()

    def thread_log(self, msg: str) -> None:
        self.ui_queue.put(("log", msg, ""))

    def thread_status(self, title: str, hint: str = "") -> None:
        self.ui_queue.put(("status", title, hint))

    def _process_ui_queue(self) -> None:
        try:
            while True:
                event_type, value, detail = self.ui_queue.get_nowait()
                if event_type == "log":
                    self.log(value)
                elif event_type == "status":
                    self._set_status(value, detail)
        except queue.Empty:
            pass
        self.after(150, self._process_ui_queue)

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", "end")
        self._set_status("Logs cleared", self.summary_var.get())

    def refresh_backends(self) -> None:
        self.detected_backends = detect_backends()
        values = ["Auto"] + [f"{b.name} | {b.executable}" for b in self.detected_backends]
        self.backend_combo.configure(values=values)
        self.backend_var.set("Auto")
        self.log("Backend scan complete.")
        if not self.detected_backends:
            self._set_status("No backend detected", "Install Windows ADK oscdimg or use the built-in fallback where available")
            self.log("WARNING: Koi ISO backend nahi mila.")
            self.log("Windows: oscdimg best hai; PowerShell IMAPI fallback bhi auto-detect hona chahiye.")
            self.log("Agar PowerShell bhi detect nahi ho raha, Windows PATH/system issue hai.")
            self.log("macOS: hdiutil usually built-in hota hai. Linux: xorriso/genisoimage install karo.")
            self.log("Python standard library alone reliable UDF/ISO image create nahi karti.")
        else:
            self._set_status("Backends detected", f"{len(self.detected_backends)} backend(s) available. Auto mode best option choose karega.")
            for b in self.detected_backends:
                self.log(f"Found: {b.name} -> {b.executable} ({b.description})")

    def get_selected_backend(self) -> Backend:
        if not self.detected_backends:
            raise RuntimeError("No ISO backend found. Windows par oscdimg install karo ya PowerShell PATH check karo; Linux/macOS par xorriso/genisoimage/mkisofs/hdiutil use karo.")

        chosen = self.backend_var.get()
        profile = self.profile_var.get()
        if chosen == "Auto":
            backend = select_backend(self.detected_backends, profile)
            if not backend:
                raise RuntimeError("No compatible backend selected.")
            return backend

        selected_name = chosen.split(" | ", 1)[0].strip()
        for b in self.detected_backends:
            if b.name == selected_name and b.executable in chosen:
                return b
        for b in self.detected_backends:
            if b.name == selected_name:
                return b
        raise RuntimeError("Selected backend not found. Refresh backends and try again.")

    def validate_paths(self) -> Tuple[Path, Path, str, str]:
        source_text = self.source_var.get().strip()
        output_text = self.output_var.get().strip()

        if not source_text:
            raise ValueError("Source folder select karo.")
        if not output_text:
            raise ValueError("Output folder select karo.")

        source = Path(source_text).expanduser()
        output_folder = Path(output_text).expanduser()

        if not source.exists() or not source.is_dir():
            raise ValueError("Source folder valid nahi hai.")
        if not output_folder.exists() or not output_folder.is_dir():
            raise ValueError("Output folder valid nahi hai.")

        if self.auto_package_var.get():
            safe_base, iso_name, label = auto_names_from_source(source)
            package_folder = output_folder / f"{safe_base}_ISO"
            output_iso = package_folder / iso_name
            self.iso_name_var.set(iso_name)
            self.label_var.set(label)
        else:
            iso_name = normalize_iso_name(self.iso_name_var.get())
            label = clean_volume_label(self.label_var.get())
            output_iso = output_folder / iso_name

        source_resolved = source.resolve()
        output_iso_resolved = output_iso.resolve()

        try:
            output_iso_resolved.relative_to(source_resolved)
        except ValueError:
            pass
        else:
            raise ValueError(
                "Output ISO source folder ke andar nahi ho sakta. Alag output folder select karo."
            )

        if output_iso_resolved.exists():
            raise FileExistsError(f"Output ISO already exists: {output_iso_resolved}")

        return source_resolved, output_iso_resolved, label, iso_name

    def prepare(self) -> Tuple[Path, Path, str, Backend, ScanResult, List[str]]:
        source, output_iso, label, _ = self.validate_paths()
        profile = self.profile_var.get()
        include_hidden = bool(self.include_hidden_var.get())
        backend = self.get_selected_backend()

        scan = scan_source_folder(source, profile, include_hidden)
        cmd, command_warnings = build_command(
            backend=backend,
            source=source,
            output_iso=output_iso,
            label=label,
            profile=profile,
            include_hidden=include_hidden,
            optimize_duplicates=bool(self.optimize_var.get()),
        )
        return source, output_iso, label, backend, scan, cmd + ["__WARNINGS_SPLIT__"] + command_warnings

    def print_scan(self, scan: ScanResult) -> None:
        self.log("Scan summary:")
        self.log(f"  Files: {scan.files}")
        self.log(f"  Folders: {scan.dirs}")
        self.log(f"  Empty folders: {scan.empty_dirs}")
        self.log(f"  Total size: {human_size(scan.total_bytes)}")
        self.log(f"  Largest file: {human_size(scan.largest_file_bytes)} | {scan.largest_file_path}")
        self.log(f"  Max relative path length: {scan.max_rel_path_len}")
        self.log(f"  Max single name length: {scan.max_name_len}")
        self.log(f"  Unicode/non-ASCII paths: {scan.non_ascii_names}")
        self.log(f"  Hidden items: {scan.hidden_items}")
        self.log(f"  Symlinks: {scan.symlinks}")
        self.log(f"  Files over 4GB: {scan.files_over_4gb}")
        if scan.warnings:
            self.log("Warnings:")
            for w in scan.warnings:
                self.log(f"  - {w}")
        else:
            self.log("Warnings: none")

    def scan_only(self) -> None:
        try:
            source_text = self.source_var.get().strip()
            if not source_text:
                raise ValueError("Source folder select karo.")

            source = Path(source_text).expanduser()
            if not source.exists() or not source.is_dir():
                raise ValueError("Source folder valid nahi hai.")
            scan = scan_source_folder(source, self.profile_var.get(), bool(self.include_hidden_var.get()))
            self._set_status("Scan complete", f"{scan.files} files | {human_size(scan.total_bytes)} total size")
            self.print_scan(scan)
        except Exception as e:
            messagebox.showerror("Scan Error", str(e))
            self._set_status("Scan failed", str(e))
            self.log(f"ERROR: {e}")

    def show_command(self) -> None:
        try:
            source, output_iso, label, backend, scan, cmd_and_warnings = self.prepare()
            split_index = cmd_and_warnings.index("__WARNINGS_SPLIT__")
            cmd = cmd_and_warnings[:split_index]
            warnings = cmd_and_warnings[split_index + 1:]

            self._set_status("Command prepared", f"Backend: {backend.name} | Output: {output_iso.name}")
            self.log("Prepared command:")
            self.log(f"  Backend: {backend.name} ({backend.description})")
            self.log(f"  Source: {source}")
            self.log(f"  Output: {output_iso}")
            self.log(f"  Output package folder: {output_iso.parent}")
            self.log(f"  Label: {label}")
            self.log(f"  Profile: {self.profile_var.get()}")
            self.log(quote_cmd(cmd))
            self.print_scan(scan)
            for w in warnings:
                self.log(f"Command warning: {w}")
        except Exception as e:
            messagebox.showerror("Command Error", str(e))
            self._set_status("Command failed", str(e))
            self.log(f"ERROR: {e}")

    def start_build(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Busy", "Build already running.")
            return

        try:
            profile = self.profile_var.get()
            dry_run = bool(self.dry_run_var.get())
            generate_hash = bool(self.hash_var.get())
            source, output_iso, label, backend, scan, cmd_and_warnings = self.prepare()
            split_index = cmd_and_warnings.index("__WARNINGS_SPLIT__")
            cmd = cmd_and_warnings[:split_index]
            warnings = cmd_and_warnings[split_index + 1:]
        except Exception as e:
            messagebox.showerror("Build Error", str(e))
            self._set_status("Build cannot start", str(e))
            self.log(f"ERROR: {e}")
            return

        if scan.warnings:
            warn_text = "\n".join(f"- {w}" for w in scan.warnings[:8])
            if len(scan.warnings) > 8:
                warn_text += f"\n- ...and {len(scan.warnings) - 8} more"
            proceed = messagebox.askyesno("Warnings Found", f"Scan warnings mile:\n\n{warn_text}\n\nContinue?")
            if not proceed:
                self._set_status("Build cancelled", "User cancelled after reviewing scan warnings")
                self.log("Build cancelled by user after warnings.")
                return

        self._set_status("Building ISO...", f"Source: {source.name}")
        self.worker = threading.Thread(
            target=self._build_worker,
            args=(
                source,
                output_iso,
                label,
                backend,
                scan,
                cmd,
                warnings,
                profile,
                dry_run,
                generate_hash,
            ),
            daemon=True,
        )
        self.worker.start()

    def _build_worker(
        self,
        source: Path,
        output_iso: Path,
        label: str,
        backend: Backend,
        scan: ScanResult,
        cmd: List[str],
        warnings: List[str],
        profile: str,
        dry_run: bool,
        generate_hash: bool,
    ) -> None:
        try:
            self.thread_status("Build started", f"Using backend: {backend.name}")
            self.thread_log("=" * 72)
            self.thread_log("Build started")
            self.thread_log(f"Backend: {backend.name} -> {backend.executable}")
            self.thread_log(f"Profile: {profile}")
            self.thread_log(f"Dry run: {'ON' if dry_run else 'OFF'}")
            self.thread_log(f"Generate SHA256: {'ON' if generate_hash else 'OFF'}")
            self.thread_log(f"Source: {source}")
            self.thread_log(f"Output: {output_iso}")
            self.thread_log(f"Output package folder: {output_iso.parent}")
            self.thread_log(f"Volume label: {label}")
            self.thread_log(f"Files: {scan.files} | Size: {human_size(scan.total_bytes)}")
            for w in warnings:
                self.thread_log(f"Command warning: {w}")
            self.thread_log("Command:")
            self.thread_log(quote_cmd(cmd))

            if dry_run:
                self.thread_log("Dry run ON: actual ISO create nahi kiya gaya.")
                self.thread_log("Build finished: DRY RUN")
                self.thread_status("Dry run finished", f"Output preview: {output_iso.name}")
                return

            output_iso.parent.mkdir(parents=True, exist_ok=True)
            rc = run_process(cmd, self.thread_log)
            if rc != 0:
                raise RuntimeError(f"ISO backend failed with exit code {rc}")

            if not output_iso.exists():
                candidates = [
                    output_iso.with_suffix(output_iso.suffix + ".iso"),
                    output_iso.with_suffix(".cdr"),
                    Path(str(output_iso) + ".iso"),
                ]
                found = next((p for p in candidates if p.exists()), None)
                if found:
                    self.thread_log(f"Backend created file at {found}; renaming to {output_iso}")
                    found.rename(output_iso)

            if not output_iso.exists() or output_iso.stat().st_size == 0:
                raise RuntimeError("ISO output file create nahi hua ya empty hai.")

            self.thread_log(f"ISO created: {output_iso}")
            self.thread_log(f"ISO size: {human_size(output_iso.stat().st_size)}")

            if generate_hash:
                self.thread_log("Generating SHA256...")
                sha = calculate_sha256(output_iso)
                hash_path = output_iso.with_suffix(output_iso.suffix + ".sha256.txt")
                hash_path.write_text(f"{sha}  {output_iso.name}\n", encoding="utf-8")
                self.thread_log(f"SHA256: {sha}")
                self.thread_log(f"Hash saved: {hash_path}")

            self.thread_log(f"Package folder ready: {output_iso.parent}")
            self.thread_log("Build finished: PASS")
            self.thread_status("Build finished: PASS", f"Package folder ready: {output_iso.parent}")
        except Exception as e:
            self.thread_log(f"ERROR: {e}")
            self.thread_log("Build finished: FAIL")
            self.thread_status("Build finished: FAIL", str(e))
        finally:
            cleanup_temp_script_from_command(cmd)


def main() -> None:
    app = IsoBuilderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
