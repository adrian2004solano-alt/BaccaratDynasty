@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Instalador Automatico de Bots Baccarat (Bot Logro + Bot Version Final)
echo ========================================================================
echo   INSTALADOR AUTOMATICO EN NUEVA PC - BOT LOGRO Y BOT VERSION FINAL
echo ========================================================================
echo.

set "SRC_DIR=%~dp0"
set "DL_DIR=%USERPROFILE%\Downloads"
set "DESK_DIR=%USERPROFILE%\Desktop"
set "VENV_DIR=%DL_DIR%\Bot_Logro\python_env"

echo [1/4] Copiando Bot_Logro y Bot_Version_Final a %DL_DIR%...
xcopy "%SRC_DIR%Bot_Logro" "%DL_DIR%\Bot_Logro\" /E /I /Y >nul
xcopy "%SRC_DIR%Bot_Version_Final" "%DL_DIR%\Bot_Version_Final\" /E /I /Y >nul
if not exist "%DL_DIR%\Bot_Logro\.env" copy /Y "%DL_DIR%\Bot_Logro\.env.backup" "%DL_DIR%\Bot_Logro\.env" >nul
if not exist "%DL_DIR%\Bot_Version_Final\.env" copy /Y "%DL_DIR%\Bot_Version_Final\.env.backup" "%DL_DIR%\Bot_Version_Final\.env" >nul

echo [2/4] Configurando entorno de Python e instalando librerias...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    python -m venv "%VENV_DIR%"
)
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PY_EXE=%VENV_DIR%\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

"%PY_EXE%" -m pip install --upgrade pip >nul 2>&1
"%PY_EXE%" -m pip install -r "%DL_DIR%\Bot_Logro\requirements.txt"

echo [3/4] Creando accesos directos en el Escritorio (%DESK_DIR%)...
if not exist "%DESK_DIR%\Bot Logro Automatico" mkdir "%DESK_DIR%\Bot Logro Automatico"

(
echo @echo off
echo chcp 65001 ^>nul
echo set PYTHONIOENCODING=utf-8
echo title Bot Logro - Solo Senales ^(Telegram + Web Dynasty^)
echo cd /d "%DL_DIR%\Bot_Logro"
echo "%PY_EXE%" "%DL_DIR%\Bot_Logro\main.py" --solo-senales
echo pause
) > "%DESK_DIR%\Bot Logro.bat"

(
echo @echo off
echo chcp 65001 ^>nul
echo set PYTHONIOENCODING=utf-8
echo title Bot Logro Automatico - Con Jugadas ^($0.20 Base + 8 Tiros: Tiro 8 repite Tiro 7^)
echo cd /d "%DL_DIR%\Bot_Logro"
echo "%PY_EXE%" "%DL_DIR%\Bot_Logro\main.py" --con-apuestas --usd
echo pause
) > "%DESK_DIR%\Bot Logro Automatico.bat"

copy /Y "%DESK_DIR%\Bot Logro Automatico.bat" "%DESK_DIR%\Bot Logro Automatico\Iniciar Bot Logro Automatico.bat" >nul
copy /Y "%DESK_DIR%\Bot Logro.bat" "%DESK_DIR%\Bot Logro Automatico\Iniciar Bot Logro Solo Senales.bat" >nul

(
echo @echo off
echo chcp 65001 ^>nul
echo set PYTHONIOENCODING=utf-8
echo title Bot Adrian - Con Jugadas ^(Apuestas Automaticas + Web Dynasty^)
echo cd /d "%DL_DIR%\Bot_Version_Final"
echo "%PY_EXE%" "%DL_DIR%\Bot_Version_Final\main.py" --con-apuestas
echo pause
) > "%DESK_DIR%\Iniciar Bot Con Jugadas.bat"

(
echo @echo off
echo chcp 65001 ^>nul
echo set PYTHONIOENCODING=utf-8
echo title Bot Adrian - Sin Jugadas ^(Solo Senales Telegram + Web Dynasty^)
echo cd /d "%DL_DIR%\Bot_Version_Final"
echo "%PY_EXE%" "%DL_DIR%\Bot_Version_Final\main.py" --solo-senales
echo pause
) > "%DESK_DIR%\Iniciar Bot Sin Jugadas.bat"

echo [4/4] ¡Instalacion completada con exito!
echo ========================================================================
echo   Ya tienes en tu Escritorio:
echo   1. Bot Logro.bat (Solo Senales)
echo   2. Bot Logro Automatico.bat (Juega solo $0.20 + 8 Tiros, Tiro 8 repite Tiro 7)
echo   3. Carpeta "Bot Logro Automatico"
echo   4. Iniciar Bot Con Jugadas.bat / Iniciar Bot Sin Jugadas.bat
echo ========================================================================
pause
