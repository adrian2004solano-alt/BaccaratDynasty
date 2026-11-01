@echo off
setlocal enabledelayedexpansion
title BACCARAT AUTO-BETTOR VIP
cd /d %~dp0

echo ============================================================
echo        BACCARAT AUTO-BETTOR VIP - EDICION PROFESIONAL
echo ============================================================
echo.

:: 1. Verificar que no se este ejecutando dentro del ZIP temporal
if not exist main.py (
    echo [ERROR CRITICO] No se encuentra 'main.py' en esta carpeta.
    echo.
    echo Parece que abriste el bot directamente desde dentro del ZIP.
    echo Para solucionarlo:
    echo  1. Cierra esta ventana.
    echo  2. Haz clic derecho en el archivo ZIP y selecciona 'Extraer todo...'.
    echo  3. Abre la carpeta extraida y ejecuta INICIAR_BOT.bat desde alli.
    echo.
    pause
    exit /b 1
)

:: 2. Detectar Python
set PY_CMD=
if exist "C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe" (
    set "PY_CMD=C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe"
    goto :PYTHON_OK
)
if exist "python_env\python.exe" (
    set "PY_CMD=python_env\python.exe"
    goto :PYTHON_OK
)
python --version >nul 2>nul
if !errorlevel! equ 0 (
    set PY_CMD=python
    goto :PYTHON_OK
)

py -3 --version >nul 2>nul
if !errorlevel! equ 0 (
    set PY_CMD=py -3
    goto :PYTHON_OK
)

for %%P in (
    %LOCALAPPDATA%\Programs\Python\Python314\python.exe
    %LOCALAPPDATA%\Programs\Python\Python313\python.exe
    %LOCALAPPDATA%\Programs\Python\Python312\python.exe
    %LOCALAPPDATA%\Programs\Python\Python311\python.exe
    %LOCALAPPDATA%\Programs\Python\Python310\python.exe
    %LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe
    %ProgramFiles%\Python314\python.exe
    %ProgramFiles%\Python313\python.exe
    %ProgramFiles%\Python312\python.exe
    %ProgramFiles%\Python311\python.exe
    %ProgramFiles%\Python310\python.exe
    C:\Python314\python.exe
    C:\Python313\python.exe
    C:\Python312\python.exe
    C:\Python311\python.exe
) do (
    if exist %%~P (
        set PY_CMD=%%~P
        goto :PYTHON_OK
    )
)

echo [ERROR] No se encontro Python instalado en esta computadora.
echo.
echo ============================================================
echo    INSTRUCCIONES:
echo ============================================================
echo 1. Descarga Python gratuito desde: https://www.python.org/downloads/
echo 2. AL INSTALARLO, MARCA OBLIGATORIAMENTE LA CASILLA:
echo    [X] Add Python to PATH
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:PYTHON_OK
echo [OK] Python detectado: !PY_CMD!
echo.

:: 3. Verificar dependencias requeridas
!PY_CMD! -c "import cv2, pyautogui, PIL, mss, requests, dotenv, numpy" >nul 2>nul
if !errorlevel! neq 0 (
    echo [*] Primera ejecucion: instalando librerias necesarias...
    !PY_CMD! -m pip install -r requirements.txt --quiet >nul 2>nul
)

:: 4. Menu de seleccion de divisa
echo ============================================================
echo   SELECCIONA LA DIVISA PARA JUGAR:
echo ============================================================
echo   [1] DOLARES (USD)    - Ficha 1: $0.20  ^|  Ficha 2: $1.00
echo   [2] LIRA TURCA (TRY) - Ficha 1: 4 TRY  ^|  Ficha 2: 20 TRY
echo ============================================================
set /p OMNI_CHOICE="Elige una opcion (1 o 2, por defecto 1): "

if "%OMNI_CHOICE%"=="2" (
    set RUN_FLAG=--try
    echo Iniciando en modo LIRA TURCA (TRY)...
) else (
    set RUN_FLAG=--usd
    echo Iniciando en modo DOLARES (USD)...
)
echo.

!PY_CMD! main.py !RUN_FLAG!

echo.
echo ============================================================
echo   El bot se ha detenido.
echo ============================================================
pause
