# Universal ISO Builder - optional PySide6/Qt Quick ONEFILE build.
# ONEDIR from build_qt_exe.ps1 remains the recommended diagnostic build.

$ErrorActionPreference = "Stop"

$AppName = "Universal ISO Builder"
$AppVersion = "2.0"
$PyInstallerVersion = "6.21.0"
$PySideVersion = "6.11.1"
$ScriptRoot = $PSScriptRoot
$AppScript = Join-Path $ScriptRoot "universal_iso_builder_qt.py"
$GuiRequirements = Join-Path $ScriptRoot "requirements-gui.txt"
$VersionFile = Join-Path $ScriptRoot "windows_version_info.txt"
$QmlSource = Join-Path $ScriptRoot "iso_builder\gui\qml"
$BuildBase = Join-Path $ScriptRoot "build"
$BuildRoot = Join-Path $BuildBase "$AppName Qt OneFile"
$WorkPath = Join-Path $BuildRoot "work"
$SpecPath = Join-Path $BuildRoot "spec"
$DistRoot = Join-Path $ScriptRoot "dist-qt-onefile"
$ExpectedExe = Join-Path $DistRoot "$AppName.exe"
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
        throw "Refusing cleanup outside expected Qt onefile build root: $targetPath"
    }
    if (Test-Path -LiteralPath $targetPath) {
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }
}

function Remove-ScopedFile {
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
        throw "Refusing cleanup outside expected Qt onefile output root: $targetPath"
    }
    if (Test-Path -LiteralPath $targetPath -PathType Leaf) {
        Remove-Item -LiteralPath $targetPath -Force
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Building optional Qt ONEFILE: $AppName v$AppVersion"
Write-Host "PyInstaller: $PyInstallerVersion"
Write-Host "PySide6: $PySideVersion"
Write-Host "Project root: $ScriptRoot"
Write-Host "============================================================"
Write-Host ""
Write-Host "WARNING: Qt onefile starts slower because it extracts to a temporary folder."
Write-Host "Unsigned onefile executables may receive more antivirus scrutiny."
Write-Host ""

foreach ($requiredFile in @($AppScript, $GuiRequirements, $VersionFile)) {
    if (!(Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required Qt onefile build file not found: $requiredFile"
    }
}
if (!(Test-Path -LiteralPath $QmlSource -PathType Container)) {
    throw "QML source directory not found: $QmlSource"
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

& $PythonExe -m pip install --disable-pip-version-check -r $GuiRequirements
Assert-NativeCommandSucceeded -Step "Pinned PySide6 install" -ExitCode $LASTEXITCODE

& $PythonExe -c "import PySide6; from PySide6.QtQml import QQmlApplicationEngine; assert PySide6.__version__ == '$PySideVersion', PySide6.__version__; print('Qt preflight:', PySide6.__version__)"
Assert-NativeCommandSucceeded -Step "PySide6/Qt QML preflight" -ExitCode $LASTEXITCODE

$PreviousQpaPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    & $PythonExe -B -m iso_builder.gui.qt_app --smoke-test
    $SmokeExitCode = $LASTEXITCODE
} finally {
    if ($null -eq $PreviousQpaPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $PreviousQpaPlatform
    }
}
Assert-NativeCommandSucceeded -Step "Qt Quick source smoke test" -ExitCode $SmokeExitCode

Remove-ScopedDirectory -Path $BuildRoot -AllowedRoot $BuildBase
New-Item -ItemType Directory -Path $SpecPath -Force | Out-Null
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
Remove-ScopedFile -Path $ExpectedExe -AllowedRoot $DistRoot

& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --distpath "$DistRoot" `
  --workpath "$WorkPath" `
  --specpath "$SpecPath" `
  --version-file "$VersionFile" `
  --add-data "$QmlSource;iso_builder/gui/qml" `
  --name "$AppName" `
  "$AppScript"
Assert-NativeCommandSucceeded -Step "Qt onefile PyInstaller build" -ExitCode $LASTEXITCODE

if (
    (Test-Path -LiteralPath $WarnFile -PathType Leaf) -and
    (Select-String -LiteralPath $WarnFile -SimpleMatch -Quiet -Pattern @(
        "missing module named PySide6",
        "missing module named shiboken6"
    ))
) {
    throw "PyInstaller excluded a required Qt module. See: $WarnFile"
}
if (!(Test-Path -LiteralPath $ExpectedExe -PathType Leaf)) {
    throw "PyInstaller reported success but expected Qt onefile EXE was not found: $ExpectedExe"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "QT ONEFILE BUILD PASS"
Write-Host "Standalone EXE:"
Write-Host $ExpectedExe
Write-Host ""
Write-Host "Runtime launch is still a separate required verification gate."
Write-Host "============================================================"
Write-Host ""

exit 0
