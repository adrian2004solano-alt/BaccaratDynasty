@echo off
title BACCARAT DYNASTY VIP - PLATAFORMA WEB OFICIAL
cd /d %~dp0
echo ============================================================
echo   BACCARAT DYNASTY VIP - SERVIDOR WEB + SUPABASE SYNC
echo ============================================================
start http://localhost:5000
python server.py
pause
