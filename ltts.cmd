@echo off
REM Обёртка: ltts.exe (uv tool) или uv run из клона. Без аргументов — desktop (ltts-desktop.bat).
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%APPDATA%\uv\tools\ltts\Scripts" set "PATH=%APPDATA%\uv\tools\ltts\Scripts;%PATH%"

if "%~1"=="" goto launch_desktop
if /i "%~1"=="desktop" if "%~2"=="" goto launch_desktop
set "_UV=uv"
where uv >nul 2>&1 || if exist "%USERPROFILE%\.local\bin\uv.exe" set "_UV=%USERPROFILE%\.local\bin\uv.exe"
if exist "%APPDATA%\uv\tools\ltts\Scripts\ltts.exe" (
  "%APPDATA%\uv\tools\ltts\Scripts\ltts.exe" %*
  exit /b !ERRORLEVEL!
)
if exist "%USERPROFILE%\.local\bin\ltts.exe" (
  "%USERPROFILE%\.local\bin\ltts.exe" %*
  exit /b !ERRORLEVEL!
)
if not "%_UV%"=="uv" if exist "%_UV%" for /f "usebackq delims=" %%i in (`"%_UV%" tool dir --bin 2^>nul`) do set "PATH=%%i;!PATH!"
for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  "%%i" %*
  exit /b !ERRORLEVEL!
)
if exist "%ROOT%\pyproject.toml" (
  where uv >nul 2>&1 && (
    pushd "%ROOT%"
    uv run ltts %*
    set "EC=!ERRORLEVEL!"
    popd
    exit /b !EC!
  )
  if exist "%_UV%" (
    pushd "%ROOT%"
    "%_UV%" run ltts %*
    set "EC=!ERRORLEVEL!"
    popd
    exit /b !EC!
  )
)

echo [ltts] Не найден ltts.exe. Установка: ltts-menu.bat install  или  ltts-update.bat
pause
exit /b 1

:launch_desktop
if not exist "%ROOT%\ltts-desktop.bat" (
  echo [ltts] ltts-desktop.bat не найден в %ROOT%
  pause
  exit /b 1
)
call "%ROOT%\ltts-desktop.bat"
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" pause
exit /b !EC!

