@echo off
REM Иконка в трее (extra tray: ltts-update.bat).
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

set "UV="
where uv >nul 2>&1 && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if defined UV for /f "usebackq delims=" %%i in (`"%UV%" tool dir --bin 2^>nul`) do set "PATH=%%i;!PATH!"
if exist "%APPDATA%\uv\tools\ltts\Scripts" set "PATH=%APPDATA%\uv\tools\ltts\Scripts;!PATH!"

set "TOOL_PY=%APPDATA%\uv\tools\ltts\Scripts\python.exe"
set "TOOL_PYW=%APPDATA%\uv\tools\ltts\Scripts\pythonw.exe"
set "TOOL_LTTS=%APPDATA%\uv\tools\ltts\Scripts\ltts.exe"
set "TRAY_LOG=%LOCALAPPDATA%\ltts\tray.log"
set "TRAY_PID=%LOCALAPPDATA%\ltts\tray.pid"

if not exist "!TOOL_PY!" (
  echo [ltts] Не найден uv tool ltts. Сначала: ltts-update.bat
  goto fail
)

"!TOOL_PY!" -c "import pystray" >nul 2>&1 || (
  echo [ltts] Нет pystray. Запустите: ltts-update.bat
  goto fail
)

set "TRAY_ARGS="
set "NOPAUSE="
set "FORCE="
:parse_args
if "%~1"=="" goto run_tray
if /i "%~1"=="nopause" set "NOPAUSE=1" & shift & goto parse_args
if /i "%~1"=="force" set "FORCE=1" & shift & goto parse_args
if /i "%~1"=="console" shift & goto run_console
set "TRAY_ARGS=!TRAY_ARGS! %~1"
shift
goto parse_args

:run_tray
if not defined FORCE call :tray_running && (
  echo [ltts] Трей уже запущен — иконка у часов ^(скрытые значки^).
  echo        Перезапуск: ltts-tray.bat force
  goto done_ok
)

if defined FORCE call :stop_tray

if exist "!TRAY_LOG!" del /f /q "!TRAY_LOG!" >nul 2>&1

REM pythonw — без окна; ошибки в %%LOCALAPPDATA%%\ltts\tray.log
if exist "!TOOL_PYW!" (
  start "" /D "%ROOT%" "!TOOL_PYW!" -m ltts.cli tray!TRAY_ARGS!
) else (
  start "" /D "%ROOT%" "!TOOL_LTTS!" tray!TRAY_ARGS!
)

ping -n 6 127.0.0.1 >nul
if exist "!TRAY_PID!" (
  echo.
  echo  ltts tray запущен. Иконка — у часов, возможно в «скрытых значках» ^(^)...^).
  echo  Лог: !TRAY_LOG!
  goto done_ok
)
echo [ltts] Трей не стартовал. Смотрите !TRAY_LOG!
echo        Или: ltts-tray.bat console
if exist "!TRAY_LOG!" type "!TRAY_LOG!"
goto fail

:run_console
echo  Режим console — окно не закрывайте, пока нужен трей.
if exist "!TOOL_LTTS!" (
  "!TOOL_LTTS!" tray!TRAY_ARGS!
) else (
  "!TOOL_PY!" -m ltts.cli tray!TRAY_ARGS!
)
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" goto fail
goto done_ok

:tray_running
if not exist "!TRAY_PID!" exit /b 1
set /p TPID=<"!TRAY_PID!"
tasklist /FI "PID eq !TPID!" 2>nul | find /I "ltts.exe" >nul
exit /b !ERRORLEVEL!

:stop_tray
if exist "!TRAY_PID!" (
  set /p TPID=<"!TRAY_PID!"
  taskkill /F /PID !TPID! >nul 2>&1
  del /f /q "!TRAY_PID!" >nul 2>&1
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ltts.exe'\" -EA 0 | Where-Object { $_.CommandLine -match ' tray' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA 0 }" >nul 2>&1
ping -n 2 127.0.0.1 >nul
exit /b 0

:fail
pause
exit /b 1

:done_ok
if not defined NOPAUSE pause
exit /b 0
