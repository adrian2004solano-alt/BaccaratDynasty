@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Instalador de Dependencias - Baccarat Bot Ultimate
cd /d  %~dp0
echo ============================================================
echo   Instalando dependencias necesarias para el Bot de Baccarat...
echo ============================================================
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo ============================================================
echo   [OK] Dependencias instaladas correctamente.
echo   Ya puedes ejecutar 'start_bot.bat' para iniciar el bot.
echo ============================================================
echo.
pause
