# Universal ISO Builder - PowerShell EXE build script
# Recommended build: ONEDIR. Share the complete output folder, not only the EXE.

$ErrorActionPreference = "Stop"

$AppName = "Universal ISO Builder"
$AppVersion = "2.0"
$PyInstallerVersion = "6.21.0"
$ScriptRoot = $PSScriptRoot
$AppScript = Join-Path $ScriptRoot "universal_iso_builder_v1_4_1.py"
$VersionFile = Join-Path $ScriptRoot "windows_version_info.txt"
$BuildBase = Join-Path $ScriptRoot "build"
$BuildRoot = Join-Path $BuildBase $AppName
$WorkPath = Join-Path $BuildRoot "work"
$SpecPath = Join-Path $BuildRoot "spec"
$DistRoot = Join-Path $ScriptRoot "dist"
$OutputFolder = Join-Path $DistRoot $AppName
$ExpectedExe = Join-Path $OutputFolder "$AppName.exe"
$LegacySpec = Join-Path $ScriptRoot "$AppName.spec"
$WarnFile = Join-Path $WorkPath "$AppName\warn-$AppName.txt"

function Assert-NativeCommandSucceeded {
    param(
        [Parameter(Mandatory=$true)][string]$Step,
        [Parameter(Mandatory=$true)][int]$ExitCode
    )

    if ($ExitCode -ne 0) {
        throw "$Step failed with exit code $ExitCode."
    }
}

function Remove-ScopedDirectory {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$AllowedRoot
    )

    $targetPath = [System.IO.Path]::GetFullPath($Path)
    $rootPath = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar

    if (!$targetPath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing cleanup outside expected build root: $targetPath"
    }
    if (Test-Path -LiteralPath $targetPath) {
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Building $AppName v$AppVersion"
Write-Host "PyInstaller: $PyInstallerVersion"
Write-Host "Project root: $ScriptRoot"
Write-Host "============================================================"
Write-Host ""

if (!(Test-Path -LiteralPath $AppScript -PathType Leaf)) {
    throw "Application entrypoint not found: $AppScript"
}
if (!(Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
    throw "Windows version metadata file not found: $VersionFile"
}

$VenvPython = Join-Path $ScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $PythonExe = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (!$PythonCommand) {
        throw "Python not found. Create .venv beside this script or add Python to PATH."
    }
    $PythonExe = $PythonCommand.Source
}

& $PythonExe -m pip install --disable-pip-version-check "pyinstaller==$PyInstallerVersion"
Assert-NativeCommandSucceeded -Step "Pinned PyInstaller install" -ExitCode $LASTEXITCODE

& $PythonExe -c "import tkinter; root = tkinter.Tcl(); print('Tk preflight:', root.call('info', 'patchlevel'))"
Assert-NativeCommandSucceeded -Step "Tkinter/Tcl preflight" -ExitCode $LASTEXITCODE

Remove-ScopedDirectory -Path $BuildRoot -AllowedRoot $BuildBase
Remove-ScopedDirectory -Path $OutputFolder -AllowedRoot $DistRoot
if (Test-Path -LiteralPath $LegacySpec -PathType Leaf) {
    Remove-Item -LiteralPath $LegacySpec -Force
}
New-Item -ItemType Directory -Path $SpecPath -Force | Out-Null

& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --distpath "$DistRoot" `
  --workpath "$WorkPath" `
  --specpath "$SpecPath" `
  --version-file "$VersionFile" `
  --name "$AppName" `
  "$AppScript"
Assert-NativeCommandSucceeded -Step "PyInstaller EXE build" -ExitCode $LASTEXITCODE

if (
    (Test-Path -LiteralPath $WarnFile -PathType Leaf) -and
    (Select-String -LiteralPath $WarnFile -SimpleMatch "missing module named tkinter" -Quiet)
) {
    throw "PyInstaller excluded tkinter. EXE GUI would not start. See: $WarnFile"
}
if (!(Test-Path -LiteralPath $ExpectedExe -PathType Leaf)) {
    throw "PyInstaller reported success but expected EXE was not found: $ExpectedExe"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "BUILD PASS"
Write-Host "EXE folder:"
Write-Host $OutputFolder
Write-Host ""
Write-Host "Main EXE:"
Write-Host $ExpectedExe
Write-Host ""
Write-Host "Share the complete '$AppName' folder, including _internal."
Write-Host "============================================================"
Write-Host ""

exit 0
