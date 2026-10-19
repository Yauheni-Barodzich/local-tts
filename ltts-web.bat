@echo off
REM ltts desktop: трей + своё окно (без отдельного serve в консоли).
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\ltts-desktop.bat" (
  echo [ltts] ltts-desktop.bat не найден
  exit /b 1
)

call "%ROOT%\ltts-desktop.bat"
exit /b %ERRORLEVEL%
