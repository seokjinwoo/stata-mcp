@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "setup_result=%ERRORLEVEL%"
echo.
if not "%setup_result%"=="0" echo Setup did not complete. Please read the message above.
pause
exit /b %setup_result%
