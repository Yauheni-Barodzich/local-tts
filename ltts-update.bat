@echo off
REM Установка / обновление ltts из этого клона (uv tool install + extra tray). Голоса: ltts-menu.bat install
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

if not exist "%ROOT%\pyproject.toml" (
  echo [ltts] pyproject.toml не найден в %ROOT%
  goto fail
)

set "UV="
where uv >nul 2>&1 && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
  echo [ltts] нужен uv. Полная установка: ltts-menu.bat install
  goto fail
)

echo.
echo  === Обновление ltts из исходников ===
echo  %ROOT%
echo  CLI + desktop (трей/окно). Запуск: ltts-tray.bat
echo  Закройте ltts serve / MCP / ltts tray в других окнах (Ctrl+C^).
echo.

set "TOOL_SRC=%ROOT%[desktop]"
call :stop_ltts
ping -n 3 127.0.0.1 >nul
call :do_install
if not "!EC!"=="0" (
  echo.
  echo [ltts] повтор после остановки процессов ltts...
  call :stop_ltts
  ping -n 4 127.0.0.1 >nul
  call :do_install
)

if not "!EC!"=="0" (
  echo.
  echo [ltts] uv tool install завершился с кодом !EC!
  echo        Закройте ltts serve / tray / MCP и повторите.
  echo        Часто помогает: закрыть все терминалы с ltts, затем снова ltts-update.bat
  goto fail
)

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
for /f "usebackq delims=" %%i in (`"%UV%" tool dir --bin 2^>nul`) do set "PATH=%%i;!PATH!"

echo.
echo  uv tool:
for /f "delims=" %%a in ('"%UV%" tool list 2^>nul ^| findstr /i ltts') do echo    %%a

echo.
echo  ltts.exe в PATH:
set "N=0"
for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  set /a N+=1
  echo    %%i
)
if "!N!"=="0" (
  echo    [warn] не найден — откройте новый терминал
  goto done_ok
)

for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  "%%i" --version 2>nul
  goto version_done
)
:version_done

echo.
echo  Готово. Веб: ltts-web.bat   Трей: ltts-tray.bat
goto done_ok

:do_install
pushd "%ROOT%"
"%UV%" tool install --force --python 3.12 "!TOOL_SRC!"
set "EC=!ERRORLEVEL!"
popd
exit /b !EC!

:stop_ltts
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$names = 'ltts','python','pythonw'; foreach ($n in $names) { Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { try { $p = $_.Path } catch { $p = $null }; if ($n -eq 'ltts' -or ($p -and $p -like '*\uv\tools\ltts*')) { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } } }" >nul 2>&1
exit /b 0

:fail
if /i not "%~1"=="nopause" pause
exit /b 1

:done_ok
if /i not "%~1"=="nopause" pause
exit /b 0
