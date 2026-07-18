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
APP_VERSION = "1.2.0"

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
        self.geometry("980x720")
        self.minsize(900, 620)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
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
        self.dry_run_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.refresh_backends()
        self.after(150, self._process_log_queue)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            if platform.system().lower() == "windows":
                style.theme_use("vista")
            else:
                style.theme_use("clam")
        except Exception:
            pass

        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text=APP_NAME, font=("Segoe UI", 22, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(
            main,
            text="Safe folder-to-ISO builder. Best backend auto-detect + compatibility fallback.",
            font=("Segoe UI", 10),
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        form = ttk.LabelFrame(main, text="Input / Output", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Source folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(form, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse", command=self.pick_source).grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(form, text="Output folder").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(form, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse", command=self.pick_output).grid(row=1, column=2, padx=(8, 0), pady=6)

        ttk.Label(form, text="ISO file name").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(form, textvariable=self.iso_name_var).grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Volume label").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(form, textvariable=self.label_var).grid(row=3, column=1, sticky="ew", pady=6)

        options = ttk.LabelFrame(main, text="ISO Settings", padding=12)
        options.pack(fill="x", pady=(12, 0))
        options.columnconfigure(1, weight=1)
        options.columnconfigure(3, weight=1)

        ttk.Label(options, text="Compatibility profile").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Combobox(options, textvariable=self.profile_var, values=PROFILES, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=6
        )

        ttk.Label(options, text="Backend").grid(row=0, column=2, sticky="w", padx=(14, 8), pady=6)
        self.backend_combo = ttk.Combobox(options, textvariable=self.backend_var, values=["Auto"], state="readonly")
        self.backend_combo.grid(row=0, column=3, sticky="ew", pady=6)

        checks = ttk.Frame(options)
        checks.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(checks, text="Include hidden files", variable=self.include_hidden_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Generate SHA256", variable=self.hash_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Optimize duplicate files when backend supports it", variable=self.optimize_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Dry run only", variable=self.dry_run_var).pack(side="left")

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Refresh Backends", command=self.refresh_backends).pack(side="left")
        ttk.Button(buttons, text="Scan Folder", command=self.scan_only).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Show Command", command=self.show_command).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Build ISO", command=self.start_build).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Clear Logs", command=self.clear_logs).pack(side="right")

        log_frame = ttk.LabelFrame(main, text="Logs", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(12, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=18, font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        footer = ttk.Label(
            main,
            text="Note: This app creates non-bootable data ISOs. It does not bypass antivirus or run installers.",
            foreground="#666666",
        )
        footer.pack(anchor="w", pady=(8, 0))

    def pick_source(self) -> None:
        folder = filedialog.askdirectory(title="Select source setup folder")
        if folder:
            self.source_var.set(folder)
            if not self.output_var.get().strip():
                self.output_var.set(str(Path(folder).parent))
            self.log(f"Source selected: {folder}")

    def pick_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)
            self.log(f"Output selected: {folder}")

    def log(self, msg: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
        self.update_idletasks()

    def thread_log(self, msg: str) -> None:
        self.log_queue.put(msg)

    def _process_log_queue(self) -> None:
        try:
            while True:
                self.log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self._process_log_queue)

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", "end")

    def refresh_backends(self) -> None:
        self.detected_backends = detect_backends()
        values = ["Auto"] + [f"{b.name} | {b.executable}" for b in self.detected_backends]
        self.backend_combo.configure(values=values)
        self.backend_var.set("Auto")
        self.log("Backend scan complete.")
        if not self.detected_backends:
            self.log("WARNING: Koi ISO backend nahi mila.")
            self.log("Windows: oscdimg best hai; PowerShell IMAPI fallback bhi auto-detect hona chahiye.")
            self.log("Agar PowerShell bhi detect nahi ho raha, Windows PATH/system issue hai.")
            self.log("macOS: hdiutil usually built-in hota hai. Linux: xorriso/genisoimage install karo.")
            self.log("Python standard library alone reliable UDF/ISO image create nahi karti.")
        else:
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
        source = Path(self.source_var.get().strip()).expanduser()
        output_folder = Path(self.output_var.get().strip()).expanduser()
        iso_name = normalize_iso_name(self.iso_name_var.get())
        label = clean_volume_label(self.label_var.get())

        if not source.exists() or not source.is_dir():
            raise ValueError("Source folder valid nahi hai.")
        if not output_folder.exists() or not output_folder.is_dir():
            raise ValueError("Output folder valid nahi hai.")

        output_iso = output_folder / iso_name
        if output_iso.exists():
            # Let the user decide; no silent overwrite.
            raise FileExistsError(f"Output ISO already exists: {output_iso}")

        return source.resolve(), output_iso.resolve(), label, iso_name

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
            source = Path(self.source_var.get().strip()).expanduser()
            if not source.exists() or not source.is_dir():
                raise ValueError("Source folder valid nahi hai.")
            scan = scan_source_folder(source, self.profile_var.get(), bool(self.include_hidden_var.get()))
            self.print_scan(scan)
        except Exception as e:
            messagebox.showerror("Scan Error", str(e))
            self.log(f"ERROR: {e}")

    def show_command(self) -> None:
        try:
            source, output_iso, label, backend, scan, cmd_and_warnings = self.prepare()
            split_index = cmd_and_warnings.index("__WARNINGS_SPLIT__")
            cmd = cmd_and_warnings[:split_index]
            warnings = cmd_and_warnings[split_index + 1:]

            self.log("Prepared command:")
            self.log(f"  Backend: {backend.name} ({backend.description})")
            self.log(f"  Source: {source}")
            self.log(f"  Output: {output_iso}")
            self.log(f"  Label: {label}")
            self.log(f"  Profile: {self.profile_var.get()}")
            self.log(quote_cmd(cmd))
            self.print_scan(scan)
            for w in warnings:
                self.log(f"Command warning: {w}")
        except Exception as e:
            messagebox.showerror("Command Error", str(e))
            self.log(f"ERROR: {e}")

    def start_build(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Busy", "Build already running.")
            return

        try:
            source, output_iso, label, backend, scan, cmd_and_warnings = self.prepare()
            split_index = cmd_and_warnings.index("__WARNINGS_SPLIT__")
            cmd = cmd_and_warnings[:split_index]
            warnings = cmd_and_warnings[split_index + 1:]
        except Exception as e:
            messagebox.showerror("Build Error", str(e))
            self.log(f"ERROR: {e}")
            return

        if scan.warnings:
            warn_text = "\n".join(f"- {w}" for w in scan.warnings[:8])
            if len(scan.warnings) > 8:
                warn_text += f"\n- ...and {len(scan.warnings) - 8} more"
            proceed = messagebox.askyesno("Warnings Found", f"Scan warnings mile:\n\n{warn_text}\n\nContinue?")
            if not proceed:
                self.log("Build cancelled by user after warnings.")
                return

        self.worker = threading.Thread(
            target=self._build_worker,
            args=(source, output_iso, label, backend, scan, cmd, warnings),
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
    ) -> None:
        try:
            self.thread_log("=" * 72)
            self.thread_log("Build started")
            self.thread_log(f"Backend: {backend.name} -> {backend.executable}")
            self.thread_log(f"Profile: {self.profile_var.get()}")
            self.thread_log(f"Source: {source}")
            self.thread_log(f"Output: {output_iso}")
            self.thread_log(f"Volume label: {label}")
            self.thread_log(f"Files: {scan.files} | Size: {human_size(scan.total_bytes)}")
            for w in warnings:
                self.thread_log(f"Command warning: {w}")
            self.thread_log("Command:")
            self.thread_log(quote_cmd(cmd))

            if self.dry_run_var.get():
                self.thread_log("Dry run ON: actual ISO create nahi kiya gaya.")
                self.thread_log("Build finished: DRY RUN")
                return

            output_iso.parent.mkdir(parents=True, exist_ok=True)
            rc = run_process(cmd, self.thread_log)
            if rc != 0:
                raise RuntimeError(f"ISO backend failed with exit code {rc}")

            # hdiutil can sometimes append a suffix depending on args; try to locate nearby output.
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

            if self.hash_var.get():
                self.thread_log("Generating SHA256...")
                sha = calculate_sha256(output_iso)
                hash_path = output_iso.with_suffix(output_iso.suffix + ".sha256.txt")
                hash_path.write_text(f"{sha}  {output_iso.name}\n", encoding="utf-8")
                self.thread_log(f"SHA256: {sha}")
                self.thread_log(f"Hash saved: {hash_path}")

            self.thread_log("Build finished: PASS")
        except Exception as e:
            self.thread_log(f"ERROR: {e}")
            self.thread_log("Build finished: FAIL")
        finally:
            cleanup_temp_script_from_command(cmd)


def main() -> None:
    app = IsoBuilderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
