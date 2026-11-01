@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Baccarat Bot - MODO CON APUESTAS AUTOMATICAS EN LAPTOP
cd /d "%~dp0"

echo ============================================================
echo   BACCARAT BOT - MODO APUESTAS AUTOMATICAS (LAPTOP)
echo ============================================================
echo.
echo [!] Clics fisicos: ACTIVADOS
echo [!] Senales Telegram: ACTIVADAS
echo [!] Martingala Persistente: ACTIVA
echo.

set AUTO_BET_ENABLED=true
python main.py --con-apuestas
pause
