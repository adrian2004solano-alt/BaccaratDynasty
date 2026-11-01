@echo off
title Chrome Debugging para Bot Baccarat
echo ========================================================
echo   Iniciando Google Chrome en modo Depuracion (Puerto 9222)
echo ========================================================
echo.

set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_PATH% set CHROME_PATH="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_PATH% set CHROME_PATH="%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not exist %CHROME_PATH% (
    echo [ERROR] No se encontro Google Chrome en las rutas habituales.
    echo Por favor abre Chrome con el comando:
    echo chrome.exe --remote-debugging-port=9222
    pause
    exit /b
)

echo Abriendo Chrome con puerto 9222...
start "" %CHROME_PATH% --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome_stake_bot" "https://stake.com"
echo Chrome abierto exitosamente. Ahora puedes iniciar el bot con start_bot.bat
