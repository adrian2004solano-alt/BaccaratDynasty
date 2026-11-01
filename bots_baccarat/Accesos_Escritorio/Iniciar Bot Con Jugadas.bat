@echo off
title Bot Adrian - Con Jugadas (Apuestas Automaticas + Web Dynasty)
cd /d "C:\Users\raulr\Downloads\Bot_Version_Final"
echo ============================================================
echo   BOT ADRIAN - MODO CON JUGADAS (APUESTAS + TELEGRAM + WEB)
echo ============================================================
echo  * Apuestas en pantalla : ACTIVADAS CON DINERO REAL
echo  * Ficha Base           : $0.20 USD (Moneda 1) / $1.00 USD (Moneda 2)
echo  * Sincronizacion       : Captura resultado previo - Tiro 1 en Segundo 0
echo  * Plataforma Web       : https://baccarat-dynasty.vercel.app (Senales + Rush)
echo ============================================================
echo.
"C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe" "C:\Users\raulr\Downloads\Bot_Version_Final\main.py" --con-apuestas
pause
