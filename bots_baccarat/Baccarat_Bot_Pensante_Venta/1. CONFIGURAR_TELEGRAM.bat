@echo off
chcp 65001 >nul
title Bot Pensante - Configurar Telegram
cd /d "%~dp0"

echo.
echo ============================================================
echo    BOT PENSANTE - CONFIGURAR TELEGRAM
echo ============================================================
echo.

if exist "python_env\python.exe" (
    python_env\python.exe tools\config_telegram.py
) else (
    python tools\config_telegram.py
)

pause
