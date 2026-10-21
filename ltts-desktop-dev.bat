@echo off
REM Avatar dev: console, hot-reload avatar.html, DevTools.
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "LTTS_AVATAR_DEV=1"
set "LTTS_AVATAR_HTML=%ROOT%\src\ltts\web\avatar.html"

echo.
echo  === ltts-desktop-dev ===
echo  Edit src\ltts\web\avatar.html - avatar window hot-reloads.
echo  Keep this console open while ltts is running.
echo.

call "%ROOT%\ltts-desktop.bat" force console %*
exit /b %ERRORLEVEL%
