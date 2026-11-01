@echo off
chcp 65001 >nul
title Bot Pensante - Configuración
cd /d "%~dp0"

if exist "python_env\python.exe" (
    python_env\python.exe tools\config_bot.py
) else (
    python tools\config_bot.py
)
