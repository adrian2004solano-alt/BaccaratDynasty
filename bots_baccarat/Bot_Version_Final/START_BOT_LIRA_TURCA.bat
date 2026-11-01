@echo off
setlocal enabledelayedexpansion
title Baccarat Bot VIP - MODO LIRA TURCA (4 TRY / 20 TRY)
cd /d %~dp0

:: Detectar Python
set PY_CMD=
if exist "C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe" (
    set "PY_CMD=C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe"
    goto :START
)
python --version >nul 2>nul
if !errorlevel! equ 0 (
    set PY_CMD=python
    goto :START
)
py -3 --version >nul 2>nul
if !errorlevel! equ 0 (
    set PY_CMD=py -3
    goto :START
)
for %%P in (
    %LOCALAPPDATA%\Programs\Python\Python314\python.exe
    %LOCALAPPDATA%\Programs\Python\Python313\python.exe
    %LOCALAPPDATA%\Programs\Python\Python312\python.exe
    %LOCALAPPDATA%\Programs\Python\Python311\python.exe
    %LOCALAPPDATA%\Programs\Python\Python310\python.exe
    C:\Python314\python.exe
    C:\Python313\python.exe
    C:\Python312\python.exe
    C:\Python311\python.exe
) do (
    if exist %%~P (
        set PY_CMD=%%~P
        goto :START
    )
)
set PY_CMD=python

:START
echo ============================================================
echo   BACCARAT AUTO-BETTOR VIP - MODO LIRA TURCA (TRY)
echo   Ficha Base: 4.00 TRY  ^|  Ficha Alta: 20.00 TRY
echo ============================================================
echo.

!PY_CMD! main.py --try

echo.
echo ============================================================
echo   El bot se ha detenido.
echo ============================================================
pause
