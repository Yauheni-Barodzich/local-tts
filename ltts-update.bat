@echo off
REM Установка / обновление ltts из этого клона (uv tool install). Голоса: ltts-menu.bat install
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

if not exist "%ROOT%\pyproject.toml" (
  echo [ltts] pyproject.toml не найден в %ROOT%
  exit /b 1
)

where uv >nul 2>&1 || (
  echo [ltts] нужен uv. Полная установка: ltts-menu.bat install
  exit /b 1
)

echo.
echo  === Обновление ltts из исходников ===
echo  %ROOT%
echo  Закройте ltts serve / MCP в других окнах (Ctrl+C^).
echo.

pushd "%ROOT%"
uv tool install --force --python 3.12 "%ROOT%"
set "EC=!ERRORLEVEL!"
popd

if not "!EC!"=="0" (
  echo.
  echo [ltts] uv tool install завершился с кодом !EC!
  echo        Закройте процессы ltts и повторите, либо: ltts-menu.bat install
  exit /b !EC!
)

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
for /f "usebackq delims=" %%i in (`uv tool dir --bin 2^>nul`) do set "PATH=%%i;!PATH!"

echo.
echo  uv tool:
for /f "delims=" %%a in ('uv tool list 2^>nul ^| findstr /i ltts') do echo    %%a

echo.
echo  ltts.exe в PATH:
set "N=0"
for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  set /a N+=1
  echo    %%i
)
if "!N!"=="0" (
  echo    [warn] не найден — откройте новый терминал или добавьте PATH через ltts-menu.bat install
  exit /b 0
)

set "SRC_OK="
for /f "delims=" %%a in ('uv tool list 2^>nul') do (
  echo %%a | findstr /i /c:"%ROOT%" >nul && set "SRC_OK=1"
)
if defined SRC_OK (
  echo    OK: tool собран из этого клона
) else (
  echo    [hint] если путь не из клона — проверьте: uv tool list
)

for /f "delims=" %%i in ('where ltts.exe 2^>nul') do (
  "%%i" --version 2>nul
  goto version_done
)
:version_done

echo.
echo  Готово. Веб: ltts-web.bat  или  ltts serve --open
exit /b 0
