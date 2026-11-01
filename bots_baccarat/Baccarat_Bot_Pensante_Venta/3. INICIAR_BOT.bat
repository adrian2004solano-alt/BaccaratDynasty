@echo off
chcp 65001 >nul
title Bot Pensante - En Ejecucion
cd /d "%~dp0"

echo.
echo ============================================================
echo    BOT PENSANTE - INICIANDO
echo ============================================================
echo.

set BOT_TOKEN=
set G_MODE=1

if exist ".env" (
    for /f "tokens=1,* delims==" %%A in (.env) do (
        if "%%A"=="TELEGRAM_BOT_TOKEN" set BOT_TOKEN=%%B
        if "%%A"=="GAME_MODE" set G_MODE=%%B
    )
)

if "%BOT_TOKEN%"=="" (
    echo  [INFO] Telegram no configurado: El bot jugara en MODO LOCAL.
    echo         Apuestas directas en pantalla sin senales a Telegram.
)
if not "%BOT_TOKEN%"=="" (
    echo  [OK] Telegram configurado: Notificaciones y reportes activos.
)

if "%G_MODE%"=="2" (
    echo  [ESTRATEGIA] MODO 2: Modo Seguro - Recuperacion Plana a $0.40 tras 6 tiros fallados.
)
if not "%G_MODE%"=="2" (
    echo  [ESTRATEGIA] MODO 1: Predeterminado - Ventana Rotante con Martingala Persistente.
)

echo.
echo  Iniciando Bot Pensante...
echo  Tienes 60 segundos para colocar Baccarat Multiplay visible.
echo.
echo  Para DETENER el bot: cierra esta ventana o presiona Ctrl+C
echo ============================================================
echo.

if exist "python_env\python.exe" (
    python_env\python.exe main.py
) else (
    python main.py
)

echo.
echo  El bot se detuvo.
pause
