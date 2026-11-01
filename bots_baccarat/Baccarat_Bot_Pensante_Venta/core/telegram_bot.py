"""
core/telegram_bot.py — Bot Pensante
====================================
Mismo formato de señales que v31.
Credenciales del canal "Baccarat personal".
"""

import os
import json
import time
import requests
import logging
from datetime import datetime
import config
from core.stats_tracker import StatsTracker

logger = logging.getLogger("TelegramBot")

ICONS = {"P": "🔵", "B": "🔴", "T": "🟢"}
ACTIVE_LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".active_table.lock")
MAX_ACTIVE_LOCK_SECONDS = 480


def _table_short(table_name):
    s = table_name.upper().replace("BACCARAT ", "M").replace("BACCARAT", "M")
    s = s.replace("SPEED M", "SM").replace("SPEED ", "S")
    return s if s.startswith("M") or s.startswith("S") else f"M{table_name}"


class TelegramNotifier:
    def __init__(self, token=None, chat_id=None, results_token=None, results_chat_id=None):
        self.token           = token           or config.TELEGRAM_BOT_TOKEN
        self.chat_id         = chat_id         or config.TELEGRAM_CHAT_ID
        self.results_token   = results_token   or getattr(config, "TELEGRAM_RESULTS_BOT_TOKEN", None)
        self.results_chat_id = results_chat_id or getattr(config, "TELEGRAM_RESULTS_CHAT_ID", None)
        self._msg_url        = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self._pho_url        = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        self.stats_tracker   = StatsTracker()

    @property
    def is_configured(self):
        return bool(self.token and self.chat_id and str(self.token).strip() != "" and str(self.chat_id).strip() != "")

    def send_results_channel_message(self, text):
        if not self.results_token or not self.results_chat_id:
            return False, "Canal de resultados no configurado"
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.results_token}/sendMessage",
                json={
                    "chat_id": self.results_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            data = r.json()
            return data.get("ok", False), data.get("description", "OK")
        except Exception as e:
            return False, str(e)

    def send_message(self, text, parse_mode="HTML", chat_id=None):
        if not self.is_configured:
            return False, "Telegram no configurado (modo local)"
        target = chat_id or self.chat_id
        try:
            r = requests.post(
                self._msg_url,
                json={
                    "chat_id": target,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            data = r.json()
            return data.get("ok", False), data.get("description", "OK")
        except Exception as e:
            return False, str(e)

    def send_photo(self, photo_path, caption="", parse_mode="HTML"):
        if not self.is_configured:
            return False, "Telegram no configurado (modo local)"
        if not photo_path or not os.path.exists(photo_path):
            return False, "Imagen no encontrada"
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    self._pho_url,
                    data={
                        "chat_id": self.chat_id,
                        "caption": caption,
                        "parse_mode": parse_mode,
                    },
                    files={"photo": f},
                    timeout=20,
                )
            data = r.json()
            return data.get("ok", False), data.get("description", "OK")
        except Exception as e:
            return False, str(e)

    def get_active_table(self):
        if not os.path.exists(ACTIVE_LOCK_FILE):
            return None
        try:
            with open(ACTIVE_LOCK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            t = data.get("timestamp", 0)
            if time.time() - t < MAX_ACTIVE_LOCK_SECONDS:
                return data.get("table")
        except Exception:
            pass
        return None

    def lock_active_table(self, table_name):
        try:
            with open(ACTIVE_LOCK_FILE, "w", encoding="utf-8") as f:
                json.dump({"table": table_name, "timestamp": time.time(), "pid": os.getpid()}, f)
        except Exception as e:
            logger.warning(f"No se pudo crear lock: {e}")

    def release_active_table(self, table_name=None):
        try:
            if os.path.exists(ACTIVE_LOCK_FILE):
                os.remove(ACTIVE_LOCK_FILE)
        except Exception as e:
            logger.warning(f"No se pudo remover lock: {e}")

    def send_baccarat_signal(self, table_name, sequence, probability=90, screenshot_path=None):
        """Señal con foto y plan de 6 tiros. Idéntica al formato v31."""
        active = self.get_active_table()
        if active and active != table_name:
            msg = f"Rechazado: [{active}] activa. No se puede enviar [{table_name}] en paralelo."
            logger.warning(f"[BLOQUEO] {msg}")
            return False, msg

        short = _table_short(table_name)
        stats = self.stats_tracker.get_stats_summary()
        recommendation = stats.get(
            "recommendation",
            "Mayor efectividad en <b>tiros 4 al 6</b> (Sniper Ghost)."
        )

        seq_text = " ".join(
            f"{i+1}{ICONS.get(x.upper(), '?')}" for i, x in enumerate(sequence[:6])
        )

        lines = [
            f"🎯 <b>{table_name} ({short})</b> | {seq_text}",
            "",
            f"🎲 <b>Probabilidad de ganar:</b> <b>{probability}%</b>",
            f"⚡ <b>Válido por 6 intentos</b>",
            f"🎭 <b>Entrada real en Tiro 4-5-6</b> (Estrategia Sniper)",
            "",
            f"💡 <b>Recomendacion de Gestion:</b>",
            f"<i>{recommendation}</i>",
            "",
            f"🕐 <i>{datetime.now().strftime('%H:%M:%S')}</i>",
        ]
        caption = "\n".join(lines)

        if not self.is_configured:
            self.lock_active_table(table_name)
            logger.info(f"[CANDADO] Mesa activa (modo local): '{table_name}'")
            try:
                from core.web_bridge import publish_signal_to_web
                publish_signal_to_web(table_name=table_name, sequence=sequence, probability=probability, screenshot_path=screenshot_path)
            except Exception:
                pass
            return True, "Modo local (sin Telegram)"

        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        if ok:
            self.lock_active_table(table_name)
            logger.info(f"[CANDADO] Mesa activa: '{table_name}'")

        try:
            from core.web_bridge import publish_signal_to_web
            publish_signal_to_web(table_name=table_name, sequence=sequence, probability=probability, screenshot_path=screenshot_path)
        except Exception:
            pass

        return ok, msg

    def send_result_message(self, table_name, result_type, attempt_number, screenshot_path=None, strategy_name=None):
        """Reporte de WIN o LOSS con foto y estadísticas."""
        short = _table_short(table_name)
        hora  = datetime.now().strftime("%H:%M:%S")

        if result_type == "win":
            self.stats_tracker.record_win(table_name, attempt_number, strategy_name=strategy_name)
            stats  = self.stats_tracker.get_stats_summary()
            header = f"<b>WIN {attempt_number} — {table_name} ({short})</b>"
            body = (
                f"Ganado en el intento {attempt_number}\n"
                f"Mesa: <b>{table_name}</b>\n"
                f"Efectividad ({stats['sample_size']} partidas): <b>{stats['winrate']}%</b>\n"
                f"<i>{hora}</i>"
            )
        else:
            self.stats_tracker.record_loss(table_name, strategy_name=strategy_name)
            stats  = self.stats_tracker.get_stats_summary()
            header = f"<b>LOSS — {table_name} ({short})</b>"
            body = (
                f"Perdida en Tiros 4-5-6.\n"
                f"Mesa: <b>{table_name}</b>\n"
                f"Efectividad ({stats['sample_size']} partidas): <b>{stats['winrate']}%</b>\n"
                f"<i>{hora}</i>"
            )

        try:
            from core.web_bridge import publish_result_to_web
            publish_result_to_web(table_name=table_name, result_type=result_type, attempt_number=attempt_number, screenshot_path=screenshot_path, strategy_name=strategy_name)
        except Exception:
            pass

        if not self.is_configured:
            self.release_active_table(table_name)
            logger.info(f"[CANDADO LIBERADO] '{table_name}' ({result_type}) - Modo local.")
            return True, "OK (modo local)"

        caption = f"{header}\n\n{body}"
        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        if self.results_chat_id and self.results_chat_id != self.chat_id:
            result_label = f"WIN {attempt_number}" if result_type == "win" else "LOSS"
            self.send_results_channel_message(f"<b>{result_label}</b>")

        self.release_active_table(table_name)
        logger.info(f"[CANDADO LIBERADO] '{table_name}' ({result_type}).")
        return ok, msg

    def send_ghost_update(self, table_name, ghost_num, result, prediction):
        """Notificación silenciosa de tiro fantasma — solo log, sin mensaje Telegram."""
        res_icon  = ICONS.get(result, "?")
        pred_icon = ICONS.get(prediction, "?")
        won = result == prediction
        logger.info(
            f"[GHOST {ghost_num}/3] [{table_name}] "
            f"Prediccion:{pred_icon} / Real:{res_icon} -> {'ACIERTO VIRTUAL' if won else 'FALLO VIRTUAL'}"
        )
        return True, "silencioso"

    def send_next_attempt_message(self, table_name, next_attempt, prediction, screenshot_path=None):
        logger.info(f"[{table_name}] Intento {next_attempt} — {prediction} (silencioso)")
        try:
            from core.web_bridge import publish_attempt_to_web
            publish_attempt_to_web(next_attempt)
        except Exception:
            pass
        return True, "silencioso"

    def send_tie_message(self, table_name, current_attempt):
        logger.info(f"[{table_name}] Empate en intento {current_attempt} — (silencioso)")
        return True, "silencioso"
