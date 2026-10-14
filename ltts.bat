@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "PYTHONUNBUFFERED=1"

set "ROOT=%~dp0"
set "LTTS_DATA=%LOCALAPPDATA%\ltts"
set "ROOT=%ROOT:~0,-1%"
if exist "%ROOT%\pyproject.toml" set "REPO=%ROOT%"

call :refresh_path
call :resolve_ltts
if not defined LTTS (
  echo [ltts] Не найден ltts и нет uv для запуска из репозитория.
  echo        Установка:  ltts.bat install
  exit /b 1
)

if "%~1"=="" goto menu
if /i "%~1"=="help" goto help
if /i "%~1"=="/?" goto help
if /i "%~1"=="-h" goto help
if /i "%~1"=="menu" goto menu
if /i "%~1"=="install" goto do_install
if /i "%~1"=="update" goto do_install
if /i "%~1"=="open" (
  call :run serve --open
  exit /b !ERRORLEVEL!
)
if /i "%~1"=="dev" (
  shift
  if not defined REPO (
    echo [ltts] dev: запустите из клона репозитория с pyproject.toml
    exit /b 1
  )
  where uv >nul 2>&1 || (
    echo [ltts] нужен uv: https://docs.astral.sh/uv/
    exit /b 1
  )
  pushd "%REPO%"
  uv run ltts %*
  set "EC=!ERRORLEVEL!"
  popd
  exit /b !EC!
)

call :run %*
exit /b %ERRORLEVEL%

:help
echo.
echo ltts.bat — обёртка для локального TTS на Windows
echo.
echo   ltts.bat                  интерактивное меню
echo   ltts.bat install^|update   установка/обновление (install.ps1)
echo   ltts.bat open             веб-морда в браузере (ltts serve --open)
echo   ltts.bat dev ^<cmd^> ...    ltts из исходников (uv run), без глобальной установки
echo   ltts.bat ^<команда^> ...    как CLI: say, doctor, voices, download, serve, mcp, setup, default
echo.
echo Примеры:
echo   ltts.bat say "Привет" --play
echo   ltts.bat doctor
echo   ltts.bat dev doctor
echo.
if defined LTTS echo Сейчас: !LTTS!
exit /b 0

:do_install
if not exist "%ROOT%\install.ps1" (
  echo [ltts] install.ps1 не найден в %ROOT%
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\install.ps1"
set "EC=!ERRORLEVEL!"
call :refresh_path
call :resolve_ltts
exit /b !EC!

:menu
cls
echo.
echo  ╔══════════════════════════════════════╗
echo  ║           ltts — локальный TTS       ║
echo  ╚══════════════════════════════════════╝
if defined LTTS echo  Команда: !LTTS!
if defined REPO echo  Репозиторий: %REPO%
echo.
echo   1  Озвучить текст (say + play)
echo   2  Веб-морда и API (serve --open)
echo   3  Проверка системы (doctor)
echo   4  Голоса — только скачанные (voices -i)
echo   5  Голоса — все (voices)
echo   6  Скачать голоса по умолчанию (setup)
echo   7  Скачать конкретный голос (download)
echo   8  Голос по умолчанию (default)
echo   9  Установить / обновить ltts (install)
echo  10  Версия (ltts --version)
echo  11  MCP — подсказка для Cursor / Claude
echo   0  Выход
echo.
set "CHO="
set /p CHO=Выбор: 
set "CHO=!CHO: =!"
if "!CHO!"=="" goto menu
if "!CHO!"=="0" exit /b 0
if "!CHO!"=="1" goto menu_say
if "!CHO!"=="2" goto menu_serve
if "!CHO!"=="3" call :menu_exec doctor & goto menu
if "!CHO!"=="4" call :menu_exec voices -i & goto menu
if "!CHO!"=="5" call :menu_exec voices & goto menu
if "!CHO!"=="6" call :menu_exec setup --no-rhvoice & goto menu
if "!CHO!"=="7" goto menu_download
if "!CHO!"=="8" goto menu_default
if "!CHO!"=="9" call :do_install & echo. & pause & goto menu
if "!CHO!"=="10" call :menu_exec --version & goto menu
if "!CHO!"=="11" goto menu_mcp
echo.
echo  Неизвестный пункт "!CHO!". Введите число от 0 до 11.
timeout /t 2 >nul
goto menu

:menu_exec
cls
echo.
echo  ltts %*
echo  ────────────────────────────────────────────────────
call :ready_hint
echo  Ход выполнения — строки с ^→ ниже.
echo  ────────────────────────────────────────────────────
echo.
call :run %*
set "EC=!ERRORLEVEL!"
if "!EC!"=="0" call :mark_ready
echo.
if not "!EC!"=="0" echo  [завершено с ошибкой, код !EC!]
echo.
pause
exit /b 0

:ready_hint
set "LTTS_READY=0"
if exist "%LTTS_DATA%\config.json" set "LTTS_READY=1"
if exist "%LTTS_DATA%\models" set "LTTS_READY=1"
if "!LTTS_READY!"=="1" (
  echo  Загрузка движков — обычно несколько секунд.
) else (
  echo  Первый запуск: до 1-2 минут, пока скачаются зависимости.
)
exit /b 0

:mark_ready
if not exist "%LTTS_DATA%" mkdir "%LTTS_DATA%" 2>nul
exit /b 0

:menu_say
set "TEXT="
set /p TEXT=Текст: 
if "!TEXT!"=="" (
  echo Пустой текст.
  pause
  goto menu
)
set "VOICE="
set /p VOICE=Голос (Enter = по умолчанию, напр. piper:irina): 
echo.
echo  Синтез речи (подождите)...
echo.
if not "!VOICE!"=="" (
  call :run say "!TEXT!" -v !VOICE! --play
) else (
  call :run say "!TEXT!" --play
)
echo.
pause
goto menu

:menu_serve
echo Сервер: http://127.0.0.1:8765  (остановка: Ctrl+C)
call :run serve --open
pause
goto menu

:menu_download
set "VID="
set /p VID=ID голоса (напр. silero:xenia piper:denis): 
if "!VID!"=="" (
  echo Пример: silero:xenia
  pause
  goto menu
)
call :menu_exec download !VID!
goto menu

:menu_default
call :menu_exec default
set "SETV="
set /p SETV=Задать голос (engine:voice) или Enter — в меню: 
if not "!SETV!"=="" call :menu_exec default "!SETV!"
goto menu

:menu_mcp
echo.
echo  MCP для агентов (Cursor, Claude Code):
echo    claude mcp add ltts -- ltts mcp
echo.
echo  В Cursor: Settings - MCP — добавьте сервер с командой ltts и аргументом mcp.
echo  Либо запустите в отдельном терминале: ltts mcp
echo.
pause
goto menu

:refresh_path
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>&1 && for /f "delims=" %%i in ('uv tool dir --bin 2^>nul') do set "PATH=%%i;!PATH!"
exit /b 0

:resolve_ltts
set "LTTS="
where ltts >nul 2>&1 && set "LTTS=ltts" && exit /b 0
if defined REPO where uv >nul 2>&1 && set "LTTS=uv run ltts"
exit /b 0

:run
if /i "!LTTS!"=="ltts" (
  ltts %*
  exit /b !ERRORLEVEL!
)
if /i "!LTTS!"=="uv run ltts" (
  if not defined REPO exit /b 1
  pushd "%REPO%"
  uv run ltts %*
  set "EC=!ERRORLEVEL!"
  popd
  exit /b !EC!
)
exit /b 1
