@echo off
REM Веб: браузер + сервер. Desktop (трей+окно): ltts.cmd или ltts-web-desktop.bat / ltts-desktop.bat
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\ltts.cmd" (
  echo [ltts] ltts.cmd не найден в %ROOT%
  pause
  exit /b 1
)

call "%ROOT%\ltts.cmd" serve --open
exit /b %ERRORLEVEL%
