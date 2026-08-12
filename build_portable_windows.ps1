# Build and verify a self-contained, portable Windows Qt onedir folder and ZIP.

$ErrorActionPreference = "Stop"

$AppName = "Universal ISO Builder"
$PyInstallerVersion = "6.21.0"
$PySideVersion = "6.11.1"
$ScriptRoot = $PSScriptRoot
$PythonExe = Join-Path $ScriptRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ScriptRoot "packaging\windows-portable.spec"
$DistRoot = Join-Path $ScriptRoot "dist"
$BuildRoot = Join-Path $ScriptRoot "build"

function Assert-NativeCommandSucceeded {
    param(
        [Parameter(Mandatory=$true)][string]$Step,
        [Parameter(Mandatory=$true)][int]$ExitCode
    )

    if ($ExitCode -ne 0) {
        throw "$Step failed with exit code $ExitCode."
    }
}

function Remove-ScopedPath {
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

function Invoke-SmokeTest {
    param([Parameter(Mandatory=$true)][string]$Executable)

    $previousQpaPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:QT_QPA_PLATFORM = "offscreen"
        $process = Start-Process -FilePath $Executable -ArgumentList "--smoke-test" -PassThru -Wait
    } finally {
        if ($null -eq $previousQpaPlatform) {
            Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        } else {
            $env:QT_QPA_PLATFORM = $previousQpaPlatform
        }
    }
    if ($process.ExitCode -ne 0) {
        throw "Packaged Qt smoke test failed with exit code $($process.ExitCode): $Executable"
    }
}

if (!(Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Pinned environment missing. Run 'uv sync --locked --all-groups' first."
}
if (!(Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
    throw "PyInstaller spec not found: $SpecFile"
}

$Architecture = & $PythonExe -c "import platform; print(platform.machine())"
Assert-NativeCommandSucceeded -Step "Architecture detection" -ExitCode $LASTEXITCODE
switch ($Architecture.Trim().ToUpperInvariant()) {
    "AMD64" { $TargetArch = "x86_64" }
    "X86_64" { $TargetArch = "x86_64" }
    "ARM64" { $TargetArch = "arm64" }
    default { throw "Unsupported Windows Python architecture: $Architecture" }
}

$PackageName = "$AppName-Windows-$TargetArch"
$OutputFolder = Join-Path $DistRoot $PackageName
$ExpectedExe = Join-Path $OutputFolder "$AppName.exe"
$ExpectedQml = Join-Path $OutputFolder "_internal\iso_builder\gui\qml\Main.qml"
$ZipFile = Join-Path $DistRoot "$PackageName.zip"
$ChecksumFile = "$ZipFile.sha256.txt"
$WorkPath = Join-Path $BuildRoot "portable-windows-$TargetArch"
$VerifyRoot = Join-Path $BuildRoot "portable-windows-$TargetArch-zip-verify"
$ExtractedFolder = Join-Path $VerifyRoot $PackageName
$ExtractedExe = Join-Path $ExtractedFolder "$AppName.exe"

& $PythonExe -c "import PyInstaller, PySide6; assert PyInstaller.__version__ == '$PyInstallerVersion'; assert PySide6.__version__ == '$PySideVersion'; print('Packaging dependencies:', PyInstaller.__version__, PySide6.__version__)"
Assert-NativeCommandSucceeded -Step "Pinned packaging dependency check" -ExitCode $LASTEXITCODE

$previousQpaPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    & $PythonExe -B -m iso_builder.gui.qt_app --smoke-test
    $sourceSmokeExitCode = $LASTEXITCODE
} finally {
    if ($null -eq $previousQpaPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $previousQpaPlatform
    }
}
Assert-NativeCommandSucceeded -Step "Qt source smoke test" -ExitCode $sourceSmokeExitCode

Remove-ScopedPath -Path $OutputFolder -AllowedRoot $DistRoot
Remove-ScopedPath -Path $ZipFile -AllowedRoot $DistRoot
Remove-ScopedPath -Path $ChecksumFile -AllowedRoot $DistRoot
Remove-ScopedPath -Path $WorkPath -AllowedRoot $BuildRoot
Remove-ScopedPath -Path $VerifyRoot -AllowedRoot $BuildRoot

$previousTargetArch = $env:UIB_TARGET_ARCH
try {
    $env:UIB_TARGET_ARCH = $TargetArch
    & $PythonExe -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkPath $SpecFile
    $buildExitCode = $LASTEXITCODE
} finally {
    if ($null -eq $previousTargetArch) {
        Remove-Item Env:UIB_TARGET_ARCH -ErrorAction SilentlyContinue
    } else {
        $env:UIB_TARGET_ARCH = $previousTargetArch
    }
}
Assert-NativeCommandSucceeded -Step "Windows portable PyInstaller build" -ExitCode $buildExitCode

foreach ($requiredPath in @($ExpectedExe, $ExpectedQml)) {
    if (!(Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Portable package is missing required file: $requiredPath"
    }
}
$PythonDll = @(Get-ChildItem -LiteralPath (Join-Path $OutputFolder "_internal") -Filter "python3*.dll" -File)
if ($PythonDll.Count -eq 0) {
    throw "Portable package is missing its Python runtime DLL."
}
$QtPlugins = Join-Path $OutputFolder "_internal\PySide6\plugins"
if (!(Test-Path -LiteralPath $QtPlugins -PathType Container)) {
    throw "Portable package is missing Qt plugins: $QtPlugins"
}
$TkArtifacts = @(Get-ChildItem -LiteralPath $OutputFolder -Recurse -Force -ErrorAction Stop | Where-Object {
    $_.Name -in @("_tkinter.pyd", "tcl", "tk")
})
if ($TkArtifacts.Count -ne 0) {
    throw "Qt-only package unexpectedly contains Tkinter/Tcl artifacts."
}

Invoke-SmokeTest -Executable $ExpectedExe

Compress-Archive -LiteralPath $OutputFolder -DestinationPath $ZipFile -CompressionLevel Optimal
if (!(Test-Path -LiteralPath $ZipFile -PathType Leaf)) {
    throw "Portable ZIP was not created: $ZipFile"
}

New-Item -ItemType Directory -Path $VerifyRoot -Force | Out-Null
Expand-Archive -LiteralPath $ZipFile -DestinationPath $VerifyRoot -Force
if (!(Test-Path -LiteralPath $ExtractedExe -PathType Leaf)) {
    throw "ZIP verification failed; extracted EXE is missing: $ExtractedExe"
}
Invoke-SmokeTest -Executable $ExtractedExe

$FolderFiles = @(Get-ChildItem -LiteralPath $OutputFolder -Recurse -File)
$FolderBytes = ($FolderFiles | Measure-Object -Property Length -Sum).Sum
$ExeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ExpectedExe).Hash
$ZipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipFile).Hash
$ChecksumLine = $ZipHash.ToLowerInvariant() + "  " + (Split-Path $ZipFile -Leaf) + [Environment]::NewLine
[System.IO.File]::WriteAllText($ChecksumFile, $ChecksumLine, [System.Text.UTF8Encoding]::new($false))
$ZipBytes = (Get-Item -LiteralPath $ZipFile).Length

Remove-ScopedPath -Path $VerifyRoot -AllowedRoot $BuildRoot

Write-Host ""
Write-Host "PORTABLE WINDOWS BUILD PASS"
Write-Host "Architecture: $TargetArch"
Write-Host "Folder: $OutputFolder"
Write-Host "Folder files: $($FolderFiles.Count)"
Write-Host "Folder bytes: $FolderBytes"
Write-Host "EXE SHA256: $ExeHash"
Write-Host "ZIP: $ZipFile"
Write-Host "ZIP bytes: $ZipBytes"
Write-Host "ZIP SHA256: $ZipHash"
Write-Host "Checksum: $ChecksumFile"
Write-Host "Share the complete folder or ZIP; do not move the EXE alone."

exit 0
