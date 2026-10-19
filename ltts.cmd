@echo off
REM Обёртка: ltts.exe в %USERPROFILE%\.local\bin (uv). Не ltts.bat — иначе перекроет ltts.exe в этой папке.
setlocal EnableExtensions EnableDelayedExpansion
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%APPDATA%\uv\tools\ltts\Scripts" set "PATH=%APPDATA%\uv\tools\ltts\Scripts;%PATH%"
if /i "%~1"=="desktop" if exist "%APPDATA%\uv\tools\ltts\Scripts\pythonw.exe" (
  start "" "%APPDATA%\uv\tools\ltts\Scripts\pythonw.exe" -m ltts.cli %*
  exit /b 0
)
if /i "%~1"=="desktop" if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" -m ltts.cli %*
  exit /b 0
)
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
echo [ltts] Не найден ltts.exe. Установка: ltts-menu.bat install
exit /b 1
