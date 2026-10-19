@echo off
REM Приложение ltts: трей + окно (ltts desktop). Extra: ltts-update.bat [desktop]
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
REM .venv без extra desktop — не подменяем uv tool (иначе ложное «Нет pywebview»)
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -c "import webview" >nul 2>&1 && (
    set "TOOL_PY=%ROOT%\.venv\Scripts\python.exe"
    if exist "%ROOT%\.venv\Scripts\pythonw.exe" set "TOOL_PYW=%ROOT%\.venv\Scripts\pythonw.exe"
  )
)
set "DESKTOP_LOG=%LOCALAPPDATA%\ltts\desktop.log"
set "DESKTOP_PID=%LOCALAPPDATA%\ltts\desktop.pid"

if not exist "!TOOL_PY!" (
  if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
    start "" /D "%ROOT%" "%ROOT%\.venv\Scripts\pythonw.exe" -m ltts.cli desktop %*
    exit /b 0
  )
  echo [ltts] Не найден uv tool ltts. Сначала: ltts-update.bat
  goto fail
)

"!TOOL_PY!" -c "import webview" >nul 2>&1 || (
  echo [ltts] Нет pywebview. Запустите: ltts-update.bat
  goto fail
)

set "DESKTOP_ARGS="
set "NOPAUSE="
set "FORCE="
:parse_args
if "%~1"=="" goto run_desktop
if /i "%~1"=="nopause" set "NOPAUSE=1" & shift & goto parse_args
if /i "%~1"=="force" set "FORCE=1" & shift & goto parse_args
if /i "%~1"=="console" shift & goto run_console
set "DESKTOP_ARGS=!DESKTOP_ARGS! %~1"
shift
goto parse_args

:run_desktop
if not defined FORCE call :desktop_running && (
  echo [ltts] ltts уже запущен — иконка у часов ^(скрытые значки^).
  "!TOOL_PY!" -c "from ltts.instance_lock import focus_desktop_window; focus_desktop_window()" >nul 2>&1
  echo        Не видно UI: ltts-tray.bat force
  goto done_ok
)

if defined FORCE call :stop_desktop

if exist "!DESKTOP_LOG!" del /f /q "!DESKTOP_LOG!" >nul 2>&1

if exist "!TOOL_PYW!" (
  start "" /D "%ROOT%" "!TOOL_PYW!" -m ltts.cli desktop!DESKTOP_ARGS!
) else (
  powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '!TOOL_LTTS!' -ArgumentList 'desktop'!DESKTOP_ARGS! -WindowStyle Hidden -WorkingDirectory '%ROOT%'" >nul 2>&1
)

ping -n 6 127.0.0.1 >nul
if exist "!DESKTOP_PID!" (
  echo.
  echo  ltts desktop запущен. Иконка — у часов.
  echo  Лог: !DESKTOP_LOG!
  goto done_ok
)
echo [ltts] Не стартовал. Смотрите !DESKTOP_LOG!
echo        Или: ltts-tray.bat console
if exist "!DESKTOP_LOG!" type "!DESKTOP_LOG!"
goto fail

:run_console
echo  Режим console — окно не закрывайте, пока нужен ltts.
if exist "!TOOL_LTTS!" (
  "!TOOL_LTTS!" desktop --attach-console!DESKTOP_ARGS!
) else (
  "!TOOL_PY!" -m ltts.cli desktop --attach-console!DESKTOP_ARGS!
)
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" goto fail
goto done_ok

:desktop_running
if not exist "!TOOL_PY!" exit /b 1
"!TOOL_PY!" -c "from ltts.instance_lock import DESKTOP_PID, instance_running; import sys; sys.exit(0 if instance_running(DESKTOP_PID) else 1)" >nul 2>&1
exit /b !ERRORLEVEL!

:stop_desktop
if exist "!DESKTOP_PID!" (
  set /p DPID=<"!DESKTOP_PID!"
  taskkill /F /PID !DPID! >nul 2>&1
  del /f /q "!DESKTOP_PID!" >nul 2>&1
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -EA 0 | Where-Object { $_.CommandLine -match 'ltts\.cli desktop|ltts desktop|ltts-desktop' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA 0 }" >nul 2>&1
ping -n 2 127.0.0.1 >nul
exit /b 0

:fail
pause
exit /b 1

:done_ok
if not defined NOPAUSE pause
exit /b 0
