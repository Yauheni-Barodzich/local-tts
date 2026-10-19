# Сборка onedir PyInstaller + (опционально) Inno Setup.
# Запуск из корня репозитория: powershell -ExecutionPolicy Bypass -File packaging/windows/build.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    $Root = Split-Path -Parent $PSScriptRoot
}
Set-Location $Root

Write-Host "==> uv sync (desktop extra)"
uv sync --extra desktop

Write-Host "==> pyinstaller"
uv pip install pyinstaller
uv run pyinstaller packaging/windows/ltts.spec --noconfirm --distpath dist --workpath build/pyinstaller

$Iss = Join-Path $PSScriptRoot "ltts.iss"
$Iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($Iscc) {
    Write-Host "==> Inno Setup"
    & $Iscc.Source "/DRepoRoot=$Root" $Iss
} else {
    Write-Host "!! iscc.exe не найден — пропуск Setup.exe (установите Inno Setup)"
    Write-Host "   Артефакт onedir: $Root\dist\ltts\"
}
