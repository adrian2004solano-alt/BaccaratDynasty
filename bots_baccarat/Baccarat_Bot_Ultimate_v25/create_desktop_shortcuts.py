import os
import subprocess

vbs_content = r'''
Set oWS = WScript.CreateObject("WScript.Shell")
sDesk = oWS.SpecialFolders("Desktop")

' 1. Carpeta Bot Ultimate Baccarat
Set oLink = oWS.CreateShortcut(sDesk & "\Bot Ultimate Baccarat.lnk")
oLink.TargetPath = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot"
oLink.Save

' 2. Configurar Entradas y Stop Loss
Set oLink = oWS.CreateShortcut(sDesk & "\Configurar Entradas y Stop Loss.lnk")
oLink.TargetPath = "notepad.exe"
oLink.Arguments = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot\.env"
oLink.Save

' 3. Iniciar Bot con Apuestas
Set oLink = oWS.CreateShortcut(sDesk & "\Iniciar Bot - Con Apuestas.lnk")
oLink.TargetPath = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot\start_bot_con_apuestas.bat"
oLink.WorkingDirectory = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot"
oLink.Save

' 4. Iniciar Bot Solo Senales
Set oLink = oWS.CreateShortcut(sDesk & "\Iniciar Bot - Solo Senales.lnk")
oLink.TargetPath = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot\start_bot_solo_senales.bat"
oLink.WorkingDirectory = "C:\Users\raulr\.gemini\antigravity\scratch\baccarat-stake-bot"
oLink.Save
'''

vbs_path = os.path.join(os.path.dirname(__file__), "make_shortcuts.vbs")
with open(vbs_path, "w", encoding="utf-8") as f:
    f.write(vbs_content)

subprocess.run(["cscript", "//nologo", vbs_path], check=True)
if os.path.exists(vbs_path):
    os.remove(vbs_path)
print("Shortcuts created on Desktop successfully!")
