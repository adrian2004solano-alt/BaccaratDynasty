"""
tools/config_telegram.py — Configurador de Telegram
=====================================================
Asistente interactivo para que el usuario ingrese
sus credenciales de Telegram y las guarde en .env
"""

import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE  = os.path.join(_BASE_DIR, ".env")


def test_telegram(token, chat_id):
    """Prueba el token y chat_id enviando un mensaje de prueba."""
    try:
        import requests
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": "<b>Bot Pensante conectado correctamente!</b>\nTu bot esta listo para enviar senales.",
            "parse_mode": "HTML"
        }, timeout=10)
        data = resp.json()
        return data.get("ok", False), data.get("description", "")
    except Exception as e:
        return False, str(e)


def read_env():
    """Lee el archivo .env actual."""
    values = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
    return values


def write_env(values):
    """Escribe el archivo .env con los valores dados."""
    lines = [
        "# =============================================",
        "# CONFIGURACION BOT PENSANTE",
        "# =============================================",
        "",
        f"TELEGRAM_BOT_TOKEN={values.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_CHAT_ID={values.get('TELEGRAM_CHAT_ID', '')}",
        "",
        f"AUTO_BET_ENABLED={values.get('AUTO_BET_ENABLED', 'true')}",
        f"AUTO_BET_BASE_BET={values.get('AUTO_BET_BASE_BET', '0.20')}",
        f"AUTO_BET_BASE_CHIP={values.get('AUTO_BET_BASE_CHIP', '0.20')}",
        f"AUTO_BET_BASE_CLICKS={values.get('AUTO_BET_BASE_CLICKS', '1')}",
        f"AUTO_BET_STOP_LOSS={values.get('AUTO_BET_STOP_LOSS', '-15.0')}",
        f"AUTO_BET_TAKE_PROFIT={values.get('AUTO_BET_TAKE_PROFIT', '20.0')}",
        f"AUTO_BET_MAX_STEPS={values.get('AUTO_BET_MAX_STEPS', '10')}",
        "",
        f"STARTUP_DELAY={values.get('STARTUP_DELAY', '60')}",
        f"MIN_SIGNAL_DELAY={values.get('MIN_SIGNAL_DELAY', '2')}",
        f"MAX_SIGNAL_DELAY={values.get('MAX_SIGNAL_DELAY', '6')}",
        f"MIN_CONFIDENCE_THRESHOLD={values.get('MIN_CONFIDENCE_THRESHOLD', '88')}",
        f"CONSECUTIVE_LOSS_LIMIT={values.get('CONSECUTIVE_LOSS_LIMIT', '2')}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    print("=" * 60)
    print("   CONFIGURACION DE TELEGRAM — BOT PENSANTE")
    print("=" * 60)
    print()
    print("  Para conectar tu Telegram necesitas:")
    print("  1. El TOKEN de tu bot (de @BotFather en Telegram)")
    print("  2. El ID de tu canal o grupo donde recibirlas senales")
    print()
    print("  Como obtener el TOKEN:")
    print("  - Abre Telegram y busca @BotFather")
    print("  - Escribe /newbot y sigue las instrucciones")
    print("  - Copia el token que te da (ej: 123456:AABBcc...)")
    print()
    print("  Como obtener el CHAT ID:")
    print("  - Crea un canal o grupo en Telegram")
    print("  - Agrega tu bot como Administrador con permiso de enviar mensajes")
    print("  - Para canales el ID empieza con -100...")
    print("  - Puedes obtenerlo con @userinfobot o @getidsbot")
    print()

    current = read_env()
    current_token   = current.get("TELEGRAM_BOT_TOKEN", "")
    current_chat_id = current.get("TELEGRAM_CHAT_ID", "")

    if current_token:
        print(f"  Token actual: {current_token[:20]}...")
        print(f"  Chat ID actual: {current_chat_id}")
        print()
        resp = input("  Deseas cambiar la configuracion? (s/n): ").strip().lower()
        if resp != "s":
            print("  Configuracion sin cambios.")
            input("\n  Presiona ENTER para cerrar...")
            return

    print()
    token = input("  Ingresa el TOKEN de tu bot: ").strip()
    if not token:
        print("  ERROR: El token no puede estar vacio.")
        input("\n  Presiona ENTER para cerrar...")
        return

    chat_id = input("  Ingresa el CHAT ID de tu canal/grupo: ").strip()
    if not chat_id:
        print("  ERROR: El Chat ID no puede estar vacio.")
        input("\n  Presiona ENTER para cerrar...")
        return

    print()
    print("  Probando conexion con Telegram...")
    ok, msg = test_telegram(token, chat_id)

    if ok:
        print("  CONEXION EXITOSA! Mensaje de prueba enviado a tu Telegram.")
        current["TELEGRAM_BOT_TOKEN"] = token
        current["TELEGRAM_CHAT_ID"]   = chat_id
        write_env(current)
        print("  Credenciales guardadas en .env")
        print()
        print("=" * 60)
        print("  Configuracion completada!")
        print("  Ahora ejecuta: 2. CALIBRAR_PANTALLA.bat")
        print("=" * 60)
    else:
        print(f"  ERROR de conexion: {msg}")
        print()
        print("  Verifica que:")
        print("  - El token sea correcto (sin espacios)")
        print("  - Tu bot sea Administrador del canal/grupo")
        print("  - El Chat ID sea correcto (con el - inicial si aplica)")
        print()
        print("  Vuelve a ejecutar este configurador para intentarlo de nuevo.")

    print()
    input("  Presiona ENTER para cerrar...")


if __name__ == "__main__":
    main()
