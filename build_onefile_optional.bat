@echo off
setlocal

REM Optional single-file build.
REM Use only if you specifically need one EXE file.
REM ONEDIR is recommended for this app.

set "APP_SCRIPT=universal_iso_builder_v1_4_1.py"
set "APP_NAME=Universal ISO Builder"

python -m pip install --upgrade pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name "%APP_NAME%" ^
  "%APP_SCRIPT%"

pause
endlocal
