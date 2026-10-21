@echo off
REM Dev avatar: console, hot-reload avatar.html, DevTools. Only this launcher.
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "LTTS_AVATAR_DEV=1"

echo.
echo  === ltts-desktop-dev ===
echo  Правки: src\ltts\web\avatar.html — окно аватара перезагрузится само.
echo  Не закрывайте это окно, пока нужен ltts.
echo.

call "%ROOT%\ltts-desktop.bat" force console %*
exit /b %ERRORLEVEL%
