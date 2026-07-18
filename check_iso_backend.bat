@echo off
echo === Universal ISO Builder backend check ===
echo.
echo Python:
where python 2>nul
python --version 2>nul
echo.
echo PowerShell PATH check:
where powershell 2>nul
echo.
echo Direct PowerShell paths:
if exist C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe echo FOUND C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
if exist C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe echo FOUND C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe
if exist C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe echo FOUND C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe
echo.
echo IMAPI COM check:
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $x = New-Object -ComObject IMAPI2FS.MsftFileSystemImage; 'IMAPI OK' } catch { 'IMAPI ERROR: ' + $_.Exception.Message }"
echo.
echo OSCDIMG check:
where oscdimg 2>nul
echo.
pause
