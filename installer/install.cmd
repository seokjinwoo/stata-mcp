@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "setup_result=%ERRORLEVEL%"
echo.
if not "%setup_result%"=="0" echo Setup did not complete. / 설치를 완료하지 못했습니다.
set /p "setup_close=Press Enter to close. / 종료하려면 Enter를 누르세요. "
exit /b %setup_result%
