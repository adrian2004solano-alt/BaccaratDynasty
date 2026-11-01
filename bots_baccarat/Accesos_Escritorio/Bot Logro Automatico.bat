@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Bot Logro Automatico - Con Jugadas ($0.20 Base + 8 Tiros: Tiro 8 repite Tiro 7)
cd /d "C:\Users\raulr\Downloads\Bot_Logro"
echo ====================================================================
echo   BOT LOGRO AUTOMATICO - MODO CON JUGADAS (STAKE + TELEGRAM + WEB)
echo ====================================================================
echo  * Apuestas Automaticas : ACTIVADAS EN STAKE (Juega acorde a cada senal)
echo  * Moneda Inicial       : $0.20 USD (Primera moneda a la izquierda)
echo  * Progresion 8 Tiros   : Tiros 1..7 doblan ($0.20 a $12.80)
echo  * Tiro 8 (Recuperacion): Repite la misma cantidad del Tiro 7 ($12.80)
echo  * Parada de Seguridad  : Si gana el 8 sigue jugando; si pierde se para
echo  * Stop-Profit          : SIN STOP-PROFIT (Ganar todo lo que pueda)
echo  * Canales Conectados   : Telegram Baccarat Dynasty + Rush + Web Dynasty
echo ====================================================================
echo.
"C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe" "C:\Users\raulr\Downloads\Bot_Logro\main.py" --con-apuestas --usd
pause
