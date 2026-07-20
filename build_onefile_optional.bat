@echo off
setlocal EnableExtensions

REM Optional single-file build.
REM ONEDIR from build_exe.bat/build_exe.ps1 remains recommended.
REM Onefile starts slower and is more likely to trigger antivirus heuristics.

set "SCRIPT_ROOT=%~dp0"
set "APP_NAME=Universal ISO Builder"
set "APP_VERSION=2.0"
set "PYINSTALLER_VERSION=6.21.0"
set "APP_SCRIPT=%SCRIPT_ROOT%universal_iso_builder_v1_4_1.py"
set "VERSION_FILE=%SCRIPT_ROOT%windows_version_info.txt"
set "BUILD_BASE=%SCRIPT_ROOT%build"
set "BUILD_ROOT=%BUILD_BASE%\%APP_NAME% OneFile"
set "WORK_PATH=%BUILD_ROOT%\work"
set "SPEC_PATH=%BUILD_ROOT%\spec"
set "DIST_ROOT=%SCRIPT_ROOT%dist-onefile"
set "EXPECTED_EXE=%DIST_ROOT%\%APP_NAME%.exe"
set "WARN_FILE=%WORK_PATH%\%APP_NAME%\warn-%APP_NAME%.txt"

echo.
echo WARNING: Optional ONEFILE build. Recommended release format is ONEDIR.
echo.

if not exist "%APP_SCRIPT%" (
    echo ERROR: Application entrypoint not found: %APP_SCRIPT%
    goto :fail
)
if not exist "%VERSION_FILE%" (
    echo ERROR: Windows version metadata file not found: %VERSION_FILE%
    goto :fail
)

if exist "%SCRIPT_ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"
call "%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found. Create .venv beside this script or add Python to PATH.
    goto :fail
)

call "%PYTHON_EXE%" -m pip install --disable-pip-version-check "pyinstaller==%PYINSTALLER_VERSION%"
if errorlevel 1 (
    echo ERROR: Pinned PyInstaller install failed.
    goto :fail
)

call "%PYTHON_EXE%" -c "import tkinter; root = tkinter.Tcl(); print('Tk preflight:', root.call('info', 'patchlevel'))"
if errorlevel 1 (
    echo ERROR: Tkinter/Tcl preflight failed. Repair Python Tk support before building.
    goto :fail
)

if exist "%BUILD_ROOT%" rmdir /s /q "%BUILD_ROOT%"
if exist "%BUILD_ROOT%" (
    echo ERROR: Scoped onefile build cleanup failed: %BUILD_ROOT%
    goto :fail
)
if exist "%EXPECTED_EXE%" del /q "%EXPECTED_EXE%"
if exist "%EXPECTED_EXE%" (
    echo ERROR: Existing onefile EXE cleanup failed: %EXPECTED_EXE%
    goto :fail
)
if not exist "%SPEC_PATH%" mkdir "%SPEC_PATH%"
if errorlevel 1 (
    echo ERROR: Build directory creation failed: %SPEC_PATH%
    goto :fail
)
if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"
if errorlevel 1 (
    echo ERROR: Onefile output directory creation failed: %DIST_ROOT%
    goto :fail
)

call "%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --distpath "%DIST_ROOT%" ^
  --workpath "%WORK_PATH%" ^
  --specpath "%SPEC_PATH%" ^
  --version-file "%VERSION_FILE%" ^
  --name "%APP_NAME%" ^
  "%APP_SCRIPT%"

if errorlevel 1 (
    echo ERROR: Optional onefile build failed.
    goto :fail
)
if exist "%WARN_FILE%" (
    findstr /c:"missing module named tkinter" "%WARN_FILE%" >nul
    if not errorlevel 1 (
        echo ERROR: PyInstaller excluded tkinter. Onefile GUI would not start.
        echo Warning file: %WARN_FILE%
        goto :fail
    )
)
if not exist "%EXPECTED_EXE%" (
    echo ERROR: PyInstaller reported success but expected onefile EXE was not found:
    echo %EXPECTED_EXE%
    goto :fail
)

echo.
echo ============================================================
echo OPTIONAL ONEFILE BUILD PASS
echo Main EXE:
echo %EXPECTED_EXE%
echo ============================================================
echo.
pause
endlocal & exit /b 0

:fail
echo.
echo OPTIONAL ONEFILE BUILD FAILED
pause
endlocal & exit /b 1
