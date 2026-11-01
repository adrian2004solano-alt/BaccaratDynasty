@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Bot Logro - Inteligencia Dinamica Tiro a Tiro (Telegram + Web Dynasty)
cd /d "C:\Users\raulr\Downloads\Bot_Logro"
echo ============================================================
echo   BOT LOGRO - INTELIGENCIA DINAMICA TIRO A TIRO MULTI-MESA
echo ============================================================
echo  * Modo de Senales      : 1 Jugada Concreta por Mano (Cero 6 colores fijos)
echo  * Recuperacion en Vivo : Cambio rapido de mesa y color con foto nueva
echo  * Sincronizacion       : Captura resultado previo - 15s completos
echo  * Canal de Telegram    : Baccarat Dynasty + Canal Resultados Rush
echo  * Plataforma Web       : https://baccarat-dynasty.vercel.app
echo ============================================================
echo.
"C:\Users\raulr\Downloads\Baccarat_Bot_Pensante_Venta\Baccarat_Bot_Pensante_Venta\python_env\python.exe" "C:\Users\raulr\Downloads\Bot_Logro\main.py" --solo-senales
pause
