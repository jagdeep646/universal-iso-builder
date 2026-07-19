import os
import tempfile
import time
from pathlib import Path
from typing import Sequence


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


def cleanup_temp_script_from_command(command: Sequence[str]) -> None:
    try:
        if "-File" not in command:
            return
        index = list(command).index("-File") + 1
        script_path = Path(command[index])
        if script_path.name.startswith("universal_iso_builder_imapi_") and script_path.suffix.lower() == ".ps1":
            script_path.unlink(missing_ok=True)
    except Exception:
        pass
