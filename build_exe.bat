@echo off
setlocal

REM Universal ISO Builder - Windows EXE build script
REM Recommended build: ONEDIR. Faster startup and fewer antivirus false-positive issues than onefile.

set "APP_SCRIPT=universal_iso_builder_v1_4_1.py"
set "APP_NAME=Universal ISO Builder"

echo.
echo ============================================================
echo Building %APP_NAME%
echo ============================================================
echo.

if not exist "%APP_SCRIPT%" (
    echo ERROR: %APP_SCRIPT% not found in this folder.
    echo Put this build_exe.bat in the same folder as %APP_SCRIPT%.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: PyInstaller install/upgrade failed.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --name "%APP_NAME%" ^
  "%APP_SCRIPT%"

if errorlevel 1 (
    echo.
    echo ERROR: EXE build failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo BUILD PASS
echo EXE folder:
echo dist\%APP_NAME%\
echo.
echo Main EXE:
echo dist\%APP_NAME%\%APP_NAME%.exe
echo ============================================================
echo.

pause
endlocal
