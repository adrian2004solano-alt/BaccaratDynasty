@echo off
chcp 65001 >nul
title Bot Pensante - Crear Acceso Directo en Escritorio
cd /d "%~dp0"

echo.
echo ============================================================
echo   CREAR ACCESO DIRECTO EN EL ESCRITORIO
echo ============================================================
echo.

if exist "python_env\python.exe" (
    python_env\python.exe -c "import sys; sys.path.insert(0, '.'); from tools.config_bot import create_desktop_shortcut; create_desktop_shortcut()"
) else (
    python -c "import sys; sys.path.insert(0, '.'); from tools.config_bot import create_desktop_shortcut; create_desktop_shortcut()"
)

echo.
pause
