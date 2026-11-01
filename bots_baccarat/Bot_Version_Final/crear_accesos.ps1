$botDir = $PSScriptRoot
$desktop = [System.Environment]::GetFolderPath('Desktop')
$wsh = New-Object -ComObject WScript.Shell

$folder = Join-Path $desktop 'Bot Baccarat VIP'
if (-not (Test-Path $folder)) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}

$lnk1 = $wsh.CreateShortcut((Join-Path $folder 'Iniciar Bot VIP.lnk'))
$lnk1.TargetPath = (Join-Path $botDir 'INICIAR_BOT.bat')
$lnk1.WorkingDirectory = $botDir
$lnk1.Description = 'Iniciar Baccarat Auto-Bettor VIP'
$lnk1.Save()

$lnk2 = $wsh.CreateShortcut((Join-Path $folder 'Configurar Apuestas.lnk'))
$lnk2.TargetPath = (Join-Path $botDir 'CONFIGURAR.bat')
$lnk2.WorkingDirectory = $botDir
$lnk2.Description = 'Configurar Entradas y Limites'
$lnk2.Save()

$lnk3 = $wsh.CreateShortcut((Join-Path $folder 'Instrucciones.lnk'))
$lnk3.TargetPath = (Join-Path $botDir 'LEEME_INSTRUCCIONES.txt')
$lnk3.WorkingDirectory = $botDir
$lnk3.Description = 'Guia de Uso Rapido'
$lnk3.Save()

$lnkDesktop = $wsh.CreateShortcut((Join-Path $desktop 'Iniciar Bot VIP.lnk'))
$lnkDesktop.TargetPath = (Join-Path $botDir 'INICIAR_BOT.bat')
$lnkDesktop.WorkingDirectory = $botDir
$lnkDesktop.Save()

Write-Host '[OK] Carpeta y accesos directos creados en el Escritorio con exito.'
