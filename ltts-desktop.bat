@echo off
REM Десктоп ltts: трей + окно WebView2 (без консоли serve).
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\ltts-tray.bat" (
  echo [ltts] ltts-tray.bat не найден в %ROOT%
  pause
  exit /b 1
)

call "%ROOT%\ltts-tray.bat" nopause
exit /b %ERRORLEVEL%
