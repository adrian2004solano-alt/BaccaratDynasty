# -*- coding: utf-8 -*-
"""
tools/config_bot.py — Panel de Configuración Universal del Bot Pensante
=======================================================================
Permite al usuario:
  1. Elegir Modo de Juego (Modo 1: Predeterminado / Modo 2: Modo Seguro Recuperación Plana)
  2. Crear Acceso Directo en el Escritorio ("Iniciar Bot Pensante")
  3. Configurar Telegram (Opcional - para enviar señales al móvil)
  4. Calibrar Pantalla (1 minuto de preparación)
  5. Iniciar el Bot directamente
"""

import os
import sys
import subprocess

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_ROOT = os.path.dirname(_SCRIPT_DIR)
ENV_FILE = os.path.join(_BOT_ROOT, ".env")


def load_env():
    data = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    return data


def save_env_key(key, val):
    data = load_env()
    data[key] = str(val)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")


def get_game_mode():
    data = load_env()
    return data.get("GAME_MODE", "1")


def create_desktop_shortcut():
    print("\n  Creando acceso directo en el Escritorio...")
    target_bat = os.path.join(_BOT_ROOT, "3. INICIAR_BOT.bat")

    desktop_dirs = [
        os.path.join(os.environ.get("USERPROFILE", "C:\\Users"), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", "C:\\Users"), "OneDrive", "Desktop"),
    ]

    dest_desktop = None
    for d in desktop_dirs:
        if os.path.exists(d):
            dest_desktop = d
            break

    if not dest_desktop:
        dest_desktop = desktop_dirs[0]

    lnk_path = os.path.join(dest_desktop, "Iniciar Bot Pensante.lnk")

    # Script PowerShell para crear el acceso directo .lnk oficial de Windows
    ps_cmd = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{lnk_path}'); "
        f"$Shortcut.TargetPath = '{target_bat}'; "
        f"$Shortcut.WorkingDirectory = '{_BOT_ROOT}'; "
        f"$Shortcut.Description = 'Iniciar Baccarat Bot Pensante'; "
        f"$Shortcut.WindowStyle = 1; "
        f"$Shortcut.Save();"
    )

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print(f"  [OK] ¡Acceso directo creado exitosamente en tu Escritorio!")
        print(f"       Ubicación: {lnk_path}")
    except Exception as e:
        # Fallback creando lanzador bat en el escritorio
        bat_shortcut = os.path.join(dest_desktop, "Iniciar Bot Pensante.bat")
        with open(bat_shortcut, "w", encoding="utf-8") as f:
            f.write(f'@echo off\ncd /d "{_BOT_ROOT}"\ncall "3. INICIAR_BOT.bat"\n')
        print(f"  [OK] ¡Lanzador creado en tu Escritorio: {bat_shortcut}!")

    input("\n  Presiona ENTER para volver al menú...")


def menu_game_mode():
    while True:
        curr = get_game_mode()
        print("\n" + "=" * 65)
        print("          SELECCIÓN DE ESTRATEGIA DE JUEGO")
        print("=" * 65)
        print(f"  Modo actual activo: MODO {curr}")
        print()
        print("  [1] MODO 1 — Predeterminado (Ventana Rotante con Martingala):")
        print("      * Mesa 1: Juega Tiros 1, 2, 3 ($0.20 -> $0.40 -> $0.80)")
        print("      * Mesa 2: Espera Tiro 1, juega 2, 3, 4 ($1.60 -> $3.20 -> $6.40)")
        print("      * Al ganar en cualquier tiro: Vuelve a 1 clic ($0.20) y a Mesa 1.")
        print()
        print("  [2] MODO 2 — Modo Seguro (Recuperación Plana tras 6 Tiros):")
        print("      * Juega igual que el Modo 1 (Mesa 1: 1-2-3 / Mesa 2: 2-3-4).")
        print("      * Si pierde esos 6 tiros: ¡DETIENE LA MARTINGALA!")
        print("      * Pasa a jugar apuestas fijas de $0.40 (2 clics) por tiro.")
        print("      * Continúa jugando plano a $0.40 hasta RECUPERAR TODO LO PERDIDO.")
        print("      * Al recuperar lo perdido: vuelve automáticamente a 1 clic ($0.20)")
        print("        y martingala rotante normal.")
        print()
        print("  [V] Volver al menú principal")
        print("=" * 65)

        opc = input("\n  Selecciona una opción (1, 2 o V): ").strip().upper()
        if opc in ("1", "2"):
            save_env_key("GAME_MODE", opc)
            print(f"\n  [OK] ¡Estrategia actualizada a MODO {opc} exitosamente!")
            input("  Presiona ENTER para continuar...")
            break
        elif opc == "V":
            break
        else:
            print("  Opción inválida.")


def menu_telegram():
    data = load_env()
    token = data.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = data.get("TELEGRAM_CHAT_ID", "")

    print("\n" + "=" * 65)
    print("      CONFIGURACIÓN DE TELEGRAM (OPCIONAL)")
    print("=" * 65)
    print("  Telegram es 100% opcional. Si no lo configuras, el bot jugará")
    print("  en modo local en tu computadora sin enviar señales.")
    print()
    print(f"  Token actual:   {token if token else '(Sin configurar - Modo Local)'}")
    print(f"  Chat ID actual: {chat_id if chat_id else '(Sin configurar - Modo Local)'}")
    print("=" * 65)
    print("  [1] Ingresar / Modificar credenciales de Telegram")
    print("  [2] Desactivar Telegram (Modo Local directo)")
    print("  [V] Volver")

    opc = input("\n  Selecciona una opción: ").strip().upper()
    if opc == "1":
        new_token = input("  Ingresa el Bot Token: ").strip()
        new_chat = input("  Ingresa el Chat ID: ").strip()
        if new_token and new_chat:
            save_env_key("TELEGRAM_BOT_TOKEN", new_token)
            save_env_key("TELEGRAM_CHAT_ID", new_chat)
            print("\n  [OK] ¡Credenciales de Telegram guardadas!")
        else:
            print("\n  [AVISO] Datos incompletos. No se guardaron cambios.")
        input("  Presiona ENTER para continuar...")
    elif opc == "2":
        save_env_key("TELEGRAM_BOT_TOKEN", "")
        save_env_key("TELEGRAM_CHAT_ID", "")
        print("\n  [OK] Telegram desactivado. El bot operará en Modo Local.")
        input("  Presiona ENTER para continuar...")


def run_calibration():
    print("\n  Iniciando Calibrador Automático de Pantalla...")
    py_exec = os.path.join(_BOT_ROOT, "python_env", "python.exe")
    script = os.path.join(_BOT_ROOT, "tools", "auto_calibrate.py")
    if not os.path.exists(py_exec):
        py_exec = "python"
    subprocess.run([py_exec, script])


def main():
    while True:
        curr_mode = get_game_mode()
        data = load_env()
        has_tg = bool(data.get("TELEGRAM_BOT_TOKEN", "").strip())

        print("\n" + "=" * 65)
        print("          BOT PENSANTE — PANEL DE CONFIGURACIÓN")
        print("=" * 65)
        print(f"  [1] Estrategia de Juego: MODO {curr_mode} " +
              ("(Predeterminada)" if curr_mode == "1" else "(Modo Seguro - Recuperación $0.40)"))
        print("  [2] Añadir al Escritorio (Crear acceso directo 'Iniciar Bot')")
        print(f"  [3] Notificaciones Telegram: {'Habilitadas' if has_tg else 'Desactivadas (Modo Local)'}")
        print("  [4] Calibrar Pantalla (1 minuto de preparación)")
        print("  [5] Iniciar Bot Ahora")
        print("  [6] Salir")
        print("=" * 65)

        opc = input("  Selecciona una opción (1-6): ").strip()

        if opc == "1":
            menu_game_mode()
        elif opc == "2":
            create_desktop_shortcut()
        elif opc == "3":
            menu_telegram()
        elif opc == "4":
            run_calibration()
        elif opc == "5":
            target_bat = os.path.join(_BOT_ROOT, "3. INICIAR_BOT.bat")
            os.system(f'cmd /c "{target_bat}"')
            break
        elif opc == "6":
            print("\n  ¡Hasta luego!")
            break
        else:
            print("  Opción no reconocida.")


if __name__ == "__main__":
    main()
