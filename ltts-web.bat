@echo off
REM Веб-морда ltts: http://127.0.0.1:8765 — сервер + браузер (см. ltts serve --open).
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\ltts.cmd" (
  echo [ltts] ltts.cmd не найден в %ROOT%
  exit /b 1
)

call "%ROOT%\ltts.cmd" serve --open
exit /b %ERRORLEVEL%
