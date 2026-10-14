@echo off
REM Меню Windows. НЕ называйте этот файл ltts.bat — в cmd перекроет ltts.exe в этой папке.
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "PYTHONUNBUFFERED=1"

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "LTTS_DATA=%LOCALAPPDATA%\ltts"
if exist "%ROOT%\pyproject.toml" set "REPO=%ROOT%"

call :refresh_path
call :resolve_ltts
if not defined LTTS (
  echo [ltts] Не найден ltts.exe и нет uv для запуска из репозитория.
  echo        Установка:  ltts-menu.bat install
  exit /b 1
)

if "%~1"=="" goto menu
if /i "%~1"=="help" goto help
if /i "%~1"=="/?" goto help
if /i "%~1"=="-h" goto help
if /i "%~1"=="menu" goto menu
if /i "%~1"=="install" goto do_install
if /i "%~1"=="update" goto do_install
if /i "%~1"=="open" goto cmd_open
if /i "%~1"=="dev" goto cmd_dev

call :run %*
exit /b %ERRORLEVEL%

:cmd_open
call :preamble serve --open
call :run serve --open
exit /b !ERRORLEVEL!

:cmd_dev
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

:help
echo.
echo ltts-menu.bat — меню и обёртка для ltts на Windows
echo.
echo   ltts-menu.bat              интерактивное меню
echo   ltts-menu.bat install      установка / обновление
echo   ltts-menu.bat open         serve --open
echo   ltts-menu.bat dev ^<cmd^>   uv run ltts из клона
echo.
echo CLI напрямую:  ltts say "..."   или  ltts serve --open
echo   из этой папки не пишите просто ltts, если здесь лежит ltts.bat — переименуйте его.
echo.
if defined LTTS_EXE echo  ltts.exe: !LTTS_EXE!
exit /b 0

:do_install
echo.
echo  === Установка / обновление ltts ===
echo  Сначала остановите ltts serve / MCP в других окнах (Ctrl+C).
echo.
if not exist "%ROOT%\install.ps1" (
  echo [ltts] install.ps1 не найден в %ROOT%
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\install.ps1"
set "EC=!ERRORLEVEL!"
set "_LTTS_PATH_OK="
call :refresh_path
call :resolve_ltts
if "!EC!"=="0" echo. & echo  Установка завершена.
exit /b !EC!

:menu
cls
echo.
echo  === ltts - локальный TTS ===
if defined LTTS_EXE echo  ltts.exe: !LTTS_EXE!
if defined REPO echo  repo: %REPO%
echo.
echo   1  Озвучить текст
echo   2  Веб-морда и API
echo   3  Проверка (doctor)
echo   4  Голоса - скачанные
echo   5  Голоса - все
echo   6  Setup - голоса по умолчанию
echo   7  Download - один голос
echo   8  Голос по умолчанию
echo   9  Установить / обновить
echo  10  Версия
echo  11  MCP - подсказка
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
echo  Неизвестный пункт: !CHO!
timeout /t 2 >nul
goto menu

:menu_exec
call :preamble %*
call :run %*
set "EC=!ERRORLEVEL!"
if "!EC!"=="0" call :mark_ready
call :footer !EC!
pause
exit /b 0

:preamble
cls
echo.
echo  ltts %*
echo  ----------------------------------------------------
call :ready_hint
echo  Прогресс: строки с ^>^> в выводе ниже.
echo  ----------------------------------------------------
echo.
exit /b 0

:footer
echo.
if "%~1"=="0" goto footer_ok
echo  [ОШИБКА] код %~1
exit /b 0
:footer_ok
echo  [OK] Готово.
exit /b 0

:ready_hint
set "LTTS_READY=0"
if exist "%LTTS_DATA%\config.json" set "LTTS_READY=1"
if exist "%LTTS_DATA%\models" set "LTTS_READY=1"
if "!LTTS_READY!"=="1" goto ready_hint_ok
echo  Первый запуск может занять 1-2 мин.
exit /b 0
:ready_hint_ok
echo  Обычно 5-30 с до первой строки прогресса.
exit /b 0

:mark_ready
if not exist "%LTTS_DATA%" mkdir "%LTTS_DATA%" 2>nul
exit /b 0

:menu_say
cls
echo  Озвучить текст
set "TEXT="
set /p TEXT=Текст: 
if "!TEXT!"=="" goto menu_say_empty
set "VOICE="
set /p VOICE=Голос [Enter=по умолчанию]: 
call :preamble say --play
if not "!VOICE!"=="" goto menu_say_v
call :run say "!TEXT!" --play
goto menu_say_done
:menu_say_v
call :run say "!TEXT!" -v !VOICE! --play
:menu_say_done
set "EC=!ERRORLEVEL!"
if "!EC!"=="0" call :mark_ready
call :footer !EC!
pause
goto menu
:menu_say_empty
echo  Пустой текст.
pause
goto menu

:menu_serve
call :preamble serve --open
echo  URL: http://127.0.0.1:8765
echo  Дождитесь Uvicorn running on ...
echo  Браузер откроется сам. Стоп: Ctrl+C
echo.
call :run serve --open
set "EC=!ERRORLEVEL!"
echo.
echo  Сервер остановлен.
call :footer !EC!
pause
goto menu

:menu_download
cls
echo  Скачать голос, например silero:xenia
set "VID="
set /p VID=ID: 
if "!VID!"=="" goto menu
call :menu_exec download !VID!
goto menu

:menu_default
call :menu_exec default
set "SETV="
set /p SETV=Новый default или Enter: 
if not "!SETV!"=="" call :menu_exec default "!SETV!"
goto menu

:menu_mcp
cls
echo  MCP: claude mcp add ltts -- ltts mcp
echo  Cursor: Settings - MCP, команда ltts, аргумент mcp
pause
goto menu

:refresh_path
if defined _LTTS_PATH_OK exit /b 0
set "_LTTS_PATH_OK=1"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>&1
if errorlevel 1 exit /b 0
for /f "usebackq delims=" %%i in (`uv tool dir --bin 2^>nul`) do (
  set "PATH=%%i;%PATH%"
  goto refresh_path_done
)
:refresh_path_done
exit /b 0

:resolve_ltts
set "LTTS="
set "LTTS_EXE="
if exist "%USERPROFILE%\.local\bin\ltts.exe" (
  set "LTTS_EXE=%USERPROFILE%\.local\bin\ltts.exe"
  set "LTTS=ltts"
  goto resolve_done
)
for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  set "LTTS_EXE=%%i"
  set "LTTS=ltts"
  goto resolve_done
)
if not defined REPO goto resolve_done
where uv >nul 2>&1
if errorlevel 1 goto resolve_done
set "LTTS=uv"
:resolve_done
exit /b 0

:run
if /i "!LTTS!"=="ltts" goto run_ltts
if /i "!LTTS!"=="uv" goto run_uv
exit /b 1

:run_ltts
if not defined LTTS_EXE exit /b 1
"%LTTS_EXE%" %*
exit /b !ERRORLEVEL!

:run_uv
if not defined REPO exit /b 1
pushd "%REPO%"
uv run ltts %*
set "EC=!ERRORLEVEL!"
popd
exit /b !EC!
