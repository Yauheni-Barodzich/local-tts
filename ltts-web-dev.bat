@echo off
REM Web dev: HTML/JS from src\ltts\web, live-reload in browser. Needs .venv or uv in clone.
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "LTTS_WEB_DEV=1"
set "LTTS_WEB_ROOT=%ROOT%\src\ltts\web"

echo.
echo  === ltts web dev ===
echo  Files: src\ltts\web  ^(settings, index, common.js^)
echo  Browser reloads on save. Stop desktop if port 8765 is busy.
echo  Ctrl+C to stop.
echo.

if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -m ltts.cli serve --open
  exit /b %ERRORLEVEL%
)

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>&1 || (
  echo [ltts] Need .venv ^(uv sync^) or uv in PATH.
  pause
  exit /b 1
)
pushd "%ROOT%"
uv run ltts serve --open
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
