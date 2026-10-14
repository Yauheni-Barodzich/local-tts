# Установка ltts на Windows одной командой (PowerShell):
#   irm https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.ps1 | iex
# Из локального клона: powershell -ExecutionPolicy Bypass -File install.ps1
# На Windows работают Silero и Piper; RHVoice пока только macOS/Linux.
$ErrorActionPreference = "Stop"

$Repo   = if ($env:LTTS_REPO)   { $env:LTTS_REPO }   else { "https://github.com/nikitakashin/local-tts" }
$Python = if ($env:LTTS_PYTHON) { $env:LTTS_PYTHON } else { "3.12" }

function Say($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "!! $msg" -ForegroundColor Yellow }

function Stop-BlockingLtts {
    # uv tool install не может перезаписать Scripts, пока жив ltts serve / python из этого venv
    $toolRoot = Join-Path $env:APPDATA "uv\tools\ltts"
    $pids = @()
    foreach ($name in @("ltts", "python", "pythonw")) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $path = $_.Path
                if ($name -eq "ltts" -or ($path -and $path -like "*\uv\tools\ltts*")) { $pids += $_.Id }
            } catch { }
        }
    }
    $pids = $pids | Select-Object -Unique
    if (-not $pids) { return }
    Warn "останавливаю процессы, которые держат ltts ($($pids -join ', ')) — закройте ltts serve (Ctrl+C), если ещё запущен"
    foreach ($id in $pids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Install-LttsTool([string]$Src, [string]$Python) {
    Stop-BlockingLtts
    uv tool install --force --python $Python $Src
    if ($LASTEXITCODE -eq 0) { return }
    Warn "не удалось обновить с первого раза — ещё раз останавливаю процессы и пробую снова"
    Stop-BlockingLtts
    Start-Sleep -Seconds 3
    uv tool install --force --python $Python $Src
    if ($LASTEXITCODE -ne 0) {
        throw @"
uv tool install завершился с ошибкой (часто «Отказано в доступе» к ...\uv\tools\ltts\Scripts).

Сделайте:
  1) Закройте все окна с ltts serve и ltts mcp (Ctrl+C).
  2) Закройте другие терминалы, где шёл ltts.
  3) Повторите: powershell -ExecutionPolicy Bypass -File install.ps1

Если не помогло — перезагрузка ПК или временно отключите антивирус для папки $env:APPDATA\uv\tools\ltts
"@
    }
}

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    Warn "нужна 64-битная x86 Windows (у piper-tts нет сборок под $($env:PROCESSOR_ARCHITECTURE))"
}

# 1. uv — ставит Python и зависимости изолированно
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Say "ставлю uv"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. ltts: из локального клона, если скрипт запущен из него, иначе из GitHub
$Src = "ltts @ $Repo/archive/refs/heads/master.zip"  # zip, а не git+ — git на Windows часто нет
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) {
    if (Select-String -Path (Join-Path $PSScriptRoot "pyproject.toml") -Pattern '^name = "ltts"' -Quiet) { $Src = $PSScriptRoot }
}
Say "ставлю ltts из $Src (Python $Python, torch — пара сотен МБ)"
Install-LttsTool $Src $Python

$Bin = (uv tool dir --bin).Trim()
if (-not ($env:Path -split ";" | Where-Object { $_ -eq $Bin })) {
    uv tool update-shell | Out-Null
    $env:Path = "$Bin;$env:Path"
}

# 3. голоса по умолчанию (RHVoice на Windows пропускается сам)
Say "качаю голоса"
ltts setup --no-rhvoice

Write-Host @"

Готово! Попробуй:
  ltts say "Привет, я говорю локально" --play
  ltts serve --open                    # веб-морда: http://127.0.0.1:8765
  ltts-menu.bat                        # меню Windows (не называйте его ltts.bat — перекроет ltts.exe)
  ltts voices
  claude mcp add ltts -- ltts mcp      # подключить к Claude Code как MCP

Если `ltts` не находится — открой новый терминал.
"@
