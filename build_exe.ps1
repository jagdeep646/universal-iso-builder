# Universal ISO Builder - PowerShell EXE build script
# Recommended build: ONEDIR. Faster startup and fewer antivirus false-positive issues than onefile.

$ErrorActionPreference = "Stop"

$AppScript = "universal_iso_builder_v1_4_1.py"
$AppName = "Universal ISO Builder"

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
python -m pip install --upgrade pyinstaller

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

Write-Host ""
Write-Host "============================================================"
Write-Host "BUILD PASS"
Write-Host "EXE folder:"
Write-Host "dist\$AppName\"
Write-Host ""
Write-Host "Main EXE:"
Write-Host "dist\$AppName\$AppName.exe"
Write-Host "============================================================"
Write-Host ""
