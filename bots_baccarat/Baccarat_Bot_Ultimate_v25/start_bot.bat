@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Baccarat Ultimate - Bot de Senales
cd /d "%~dp0"
echo ============================================================
echo   Baccarat Ultimate - Instalando dependencias si faltan...
echo ============================================================
pip install mss pyautogui pillow requests opencv-python numpy python-dotenv --quiet
echo.
echo [OK] Dependencias verificadas. Iniciando bot...
echo.
python main.py
pause
