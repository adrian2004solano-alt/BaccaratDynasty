@echo off
setlocal
cd /d %~dp0
title BACCARAT VIP - INSTALADOR DE ACCESOS

echo ============================================================
echo      INSTALANDO ACCESOS DIRECTOS EN TU ESCRITORIO
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File %~dp0crear_accesos.ps1

echo.
echo ============================================================
echo  Listo! Ya tienes la carpeta 'Bot Baccarat VIP' en tu Escritorio.
echo ============================================================
echo.
pause
