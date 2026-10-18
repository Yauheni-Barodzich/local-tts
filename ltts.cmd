@echo off
REM Обёртка: ltts.exe в %USERPROFILE%\.local\bin (uv). Не ltts.bat — иначе перекроет ltts.exe в этой папке.
setlocal EnableExtensions EnableDelayedExpansion
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>&1 && for /f "usebackq delims=" %%i in (`uv tool dir --bin 2^>nul`) do set "PATH=%%i;%PATH%"
if exist "%USERPROFILE%\.local\bin\ltts.exe" (
  "%USERPROFILE%\.local\bin\ltts.exe" %*
  exit /b %ERRORLEVEL%
)
for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  "%%i" %*
  exit /b !ERRORLEVEL!
)
echo [ltts] Не найден ltts.exe. Установка: ltts-menu.bat install
exit /b 1
