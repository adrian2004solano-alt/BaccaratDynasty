@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Baccarat Bot - MODO SOLO SENALES TELEGRAM (SIN CLICS)
cd /d "%~dp0"

echo ============================================================
echo   BACCARAT BOT - MODO SOLO SENALES A TELEGRAM (SEGURO)
echo ============================================================
echo.
echo [OK] Clics fisicos: DESACTIVADOS (Tu mouse esta libre)
echo [OK] Senales Telegram: ACTIVADAS
echo [OK] Fotos y Resultados: ACTIVADOS
echo.

set AUTO_BET_ENABLED=false
python main.py --solo-senales
pause
