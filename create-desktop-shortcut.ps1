# Ярлык ltts на рабочем столе с иконкой app.ico
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Icon = Join-Path $Root "src\ltts\assets\app.ico"
$Target = Join-Path $Root "ltts-desktop.vbs"
if (-not (Test-Path $Target)) { throw "нет $Target" }
if (-not (Test-Path $Icon)) {
    Push-Location $Root
    uv run python scripts/build_app_icon.py
    Pop-Location
    if (-not (Test-Path $Icon)) { throw "сначала: uv run python scripts/build_app_icon.py" }
}
$Desk = [Environment]::GetFolderPath("Desktop")
$Lnk = Join-Path $Desk "ltts.lnk"
$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($Lnk)
$Sc.TargetPath = $Target
$Sc.WorkingDirectory = $Root
$Sc.IconLocation = "$Icon,0"
$Sc.Description = "ltts — локальный синтез речи"
$Sc.Save()
Write-Host "Ярлык: $Lnk"
