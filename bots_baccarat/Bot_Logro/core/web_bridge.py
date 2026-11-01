"""
core/web_bridge.py — Conector en Tiempo Real de "Bot Logro" hacia la Plataforma Web y Supabase
==============================================================================================
Sincroniza cada jugada individual, cambios dinámicos de mesa en recuperación y resultados Rush
con la captura real exacta tomada por el Bot.
"""

import io
import os
import base64
import logging
import threading
from datetime import datetime
import requests

logger = logging.getLogger("WebBridge")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fevrpdoitikbosvrezxi.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_fkKH_jX8WM6Gme-eTCdfZg_ZCzq6QH3")
WEB_PLATFORM_URL = os.getenv("WEB_PLATFORM_URL", "https://baccarat-dynasty.vercel.app").rstrip("/")
BOT_API_SECRET = os.getenv("BOT_API_SECRET", "dynasty_bot_secret_2026")


def _encode_image_b64(image_path):
    """Codifica exactamente la captura real tomada por el Bot para reflejarla en la Web."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        if len(raw) > 1_200_000:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=90, optimize=True)
                return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
            except Exception:
                pass
        ext = "jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "png"
        return f"data:image/{ext};base64," + base64.b64encode(raw).decode("utf-8")
    except Exception:
        return None


def publish_signal_to_web(
    table_name,
    sequence,
    probability=92,
    screenshot_path=None,
    strategy_name="BOT_LOGRO",
    base_hand_count=0,
    current_attempt=1,
):
    """Envía la señal real del Bot (con su captura exacta) al apartado de Señales de la Web."""
    def _worker():
        img_b64 = _encode_image_b64(screenshot_path)
        if isinstance(sequence, str):
            seq_list = [sequence.upper()]
        elif sequence:
            seq_list = [str(x).upper() for x in sequence[:6]]
        else:
            seq_list = ["P"]

        payload = {
            "bot_secret": BOT_API_SECRET,
            "table_name": table_name,
            "sequence": seq_list,
            "probability": int(probability),
            "strategy_name": strategy_name or "BOT_LOGRO",
            "reference_image_b64": img_b64,
            "base_hand_count": int(base_hand_count or 0),
            "current_attempt": int(current_attempt or 1),
        }

        sent_ok = False
        try:
            r = requests.post(
                f"{WEB_PLATFORM_URL}/api/bot/signal",
                json=payload,
                timeout=8,
            )
            if r.status_code == 200:
                sent_ok = True
                logger.info(f"🌐 [WEB SEÑALES] Jugada de [{table_name}] (Intento {current_attempt}) publicada.")
                if current_attempt > 1:
                    requests.post(
                        f"{WEB_PLATFORM_URL}/api/bot/attempt",
                        json={
                            "bot_secret": BOT_API_SECRET,
                            "attempt_number": int(current_attempt),
                            "table_name": table_name,
                        },
                        timeout=5,
                    )
        except Exception as e:
            logger.warning(f"Aviso enviando señal a {WEB_PLATFORM_URL}: {e}")

        if not sent_ok:
            try:
                headers = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                }
                requests.post(
                    f"{SUPABASE_URL}/rest/v1/dynasty_signals",
                    headers=headers,
                    json={
                        "table_name": table_name,
                        "sequence": seq_list,
                        "probability": int(probability),
                        "strategy_name": strategy_name or "BOT_LOGRO",
                        "reference_image_b64": img_b64,
                        "base_hand_count": int(base_hand_count or 0),
                        "current_attempt": int(current_attempt or 1),
                        "status": "active",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    timeout=8,
                )
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


def publish_attempt_to_web(attempt_number=1, table_name=None):
    """Actualiza el número de tiro activo en la señal en vivo en la Web y Supabase."""
    def _worker():
        payload = {
            "bot_secret": BOT_API_SECRET,
            "attempt_number": int(attempt_number or 1),
        }
        if table_name:
            payload["table_name"] = table_name

        try:
            r = requests.post(
                f"{WEB_PLATFORM_URL}/api/bot/attempt",
                json=payload,
                timeout=5,
            )
            if r.status_code == 200:
                logger.info(f"🌐 [WEB INTENTO] Señal actualizada a Intento {attempt_number} en plataforma.")
        except Exception as e:
            logger.warning(f"Error notificando intento {attempt_number} a {WEB_PLATFORM_URL}: {e}")

        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            }
            patch_data = {"current_attempt": int(attempt_number or 1)}
            if table_name:
                patch_data["table_name"] = table_name
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/dynasty_signals?status=eq.active",
                headers=headers,
                json=patch_data,
                timeout=5,
            )
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def publish_result_to_web(table_name, result_type, attempt_number=1, screenshot_path=None, strategy_name="BOT_LOGRO"):
    """Envía el resultado oficial (WIN 1..6 / LOSS) al apartado RUSH de la Web."""
    def _worker():
        payload = {
            "bot_secret": BOT_API_SECRET,
            "table_name": table_name,
            "result_type": str(result_type).lower(),
            "attempt_number": int(attempt_number or 1),
            "strategy_name": strategy_name or "BOT_LOGRO",
            "screenshot_b64": None,
        }

        sent_ok = False
        try:
            r = requests.post(
                f"{WEB_PLATFORM_URL}/api/bot/result",
                json=payload,
                timeout=8,
            )
            if r.status_code == 200:
                sent_ok = True
                logger.info(f"🌐 [WEB RUSH] Resultado ({result_type.upper()} {attempt_number}) publicado en RUSH.")
        except Exception as e:
            logger.warning(f"Aviso enviando resultado Rush a {WEB_PLATFORM_URL}: {e}")

        if not sent_ok:
            try:
                headers = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                }
                requests.post(
                    f"{SUPABASE_URL}/rest/v1/dynasty_results",
                    headers=headers,
                    json={
                        "table_name": table_name,
                        "result_type": str(result_type).lower(),
                        "attempt_number": int(attempt_number or 1),
                        "strategy_name": strategy_name or "BOT_LOGRO",
                        "screenshot_b64": None,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    timeout=8,
                )
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()
