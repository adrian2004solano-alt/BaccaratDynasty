@echo off
chcp 65001 >nul
title Bot Pensante - Calibrar Pantalla
cd /d "%~dp0"

echo.
echo ============================================================
echo    BOT PENSANTE - CALIBRADOR DE PANTALLA
echo ============================================================
echo.
echo  ANTES DE CONTINUAR:
echo  1. Abre Stake.com en tu navegador
echo  2. Ve a Casino - Baccarat - Baccarat Multiplay
echo  3. Pon las 4 mesas VISIBLES (sin minimizar, sin tapar)
echo.
echo  Cuando presiones ENTER iniciara una cuenta regresiva de
echo  60 segundos para que termines de preparar la pantalla.
echo.
echo  Al finalizar la cuenta regresiva se tomara la captura
echo  automaticamente y se calibraran las regiones de las mesas.
echo.
pause

if exist "python_env\python.exe" (
    python_env\python.exe tools\auto_calibrate.py
) else (
    python tools\auto_calibrate.py
)

echo.
echo  Calibracion finalizada. Revisa "calibracion_resultado.png"
echo  para verificar que las mesas fueron detectadas correctamente.
echo.
pause
