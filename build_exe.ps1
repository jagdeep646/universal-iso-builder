# Universal ISO Builder - PowerShell EXE build script
# Recommended build: ONEDIR. Faster startup and fewer antivirus false-positive issues than onefile.

$ErrorActionPreference = "Stop"

$AppScript = "universal_iso_builder_v1_4_1.py"
$AppName = "Universal ISO Builder"
$ExpectedExe = "dist\$AppName\$AppName.exe"

function Assert-NativeCommandSucceeded {
    param(
        [Parameter(Mandatory=$true)][string]$Step,
        [Parameter(Mandatory=$true)][int]$ExitCode
    )

    if ($ExitCode -ne 0) {
        throw "$Step failed with exit code $ExitCode."
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Building $AppName"
Write-Host "============================================================"
Write-Host ""

if (!(Test-Path -LiteralPath $AppScript -PathType Leaf)) {
    throw "$AppScript not found. Put this build_exe.ps1 in the same folder as $AppScript."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (!$python) {
    throw "Python not found in PATH."
}

python -m pip install --upgrade pip
Assert-NativeCommandSucceeded -Step "pip upgrade" -ExitCode $LASTEXITCODE

python -m pip install --upgrade pyinstaller
Assert-NativeCommandSucceeded -Step "PyInstaller install/upgrade" -ExitCode $LASTEXITCODE

if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}
if (Test-Path -LiteralPath "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}
if (Test-Path -LiteralPath "$AppName.spec") {
    Remove-Item -LiteralPath "$AppName.spec" -Force
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name "$AppName" `
  "$AppScript"
Assert-NativeCommandSucceeded -Step "PyInstaller EXE build" -ExitCode $LASTEXITCODE

if (!(Test-Path -LiteralPath $ExpectedExe -PathType Leaf)) {
    throw "PyInstaller reported success but expected EXE was not found: $ExpectedExe"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "BUILD PASS"
Write-Host "EXE folder:"
Write-Host "dist\$AppName\"
Write-Host ""
Write-Host "Main EXE:"
Write-Host $ExpectedExe
Write-Host "============================================================"
Write-Host ""

exit 0
