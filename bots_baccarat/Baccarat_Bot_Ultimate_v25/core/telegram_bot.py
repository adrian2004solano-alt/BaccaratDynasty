"""
core/telegram_bot.py  — v7 (Mensaje Limpio: Probabilidad Realista y Autoanálisis de 30 Partidas)
================================================================================================
Formato Telegram Solicitado:
  🤓 M5 | 1🔵 2🔴 3🔴 4🔴 5🔵 6🔴

  🎲 Probabilidad de ganar: 90%
  ⚡ Válido por 6 intentos

  💡 Recomendación de Gestión:
  Basado en el autoanálisis (últimas 30 partidas), mayor efectividad en tiros 1 al 3 (Bajos).

  🕐 22:45:10
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
MAX_ACTIVE_LOCK_SECONDS = 480  # 8 minutos timeout de seguridad



def _table_short(table_name):
    """'Baccarat 5' → 'M5'  |  'Speed Baccarat 2' → 'SM2'  |  'Baccarat 1' → 'M1'"""
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

    def send_results_channel_message(self, text):
        """Envía el resultado limpio exclusivamente al canal de resultados usando su bot dedicado."""
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
        if not photo_path or not os.path.exists(photo_path):
            return False, "Archivo de imagen no encontrado"
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
        """Retorna el nombre de la mesa activa si hay una señal en curso no finalizada."""
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
        """Bloquea Telegram para la mesa activa hasta que reporte WIN o LOSS."""
        try:
            with open(ACTIVE_LOCK_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "table": table_name,
                    "timestamp": time.time(),
                    "pid": os.getpid()
                }, f)
        except Exception as e:
            logger.warning(f"No se pudo crear lock de mesa activa: {e}")

    def release_active_table(self, table_name=None):
        """Libera el candado de Telegram tras finalizar la mesa."""
        try:
            if os.path.exists(ACTIVE_LOCK_FILE):
                os.remove(ACTIVE_LOCK_FILE)
        except Exception as e:
            logger.warning(f"No se pudo remover lock de mesa activa: {e}")

    def send_baccarat_signal(self, table_name, sequence, probability=90, screenshot_path=None):
        """
        Envía la señal inicial limpia:
        - Mesa con nombre corto y secuencia de colores
        - Probabilidad real calibrada %
        - Válido por 6 intentos
        - Recomendación de Gestión basada en el autoanálisis de las últimas 30 partidas
        """
        # BLINDAJE ANTI-DUPLICADOS: Verificar si ya hay otra mesa activa en Telegram
        active = self.get_active_table()
        if active and active != table_name:
            msg = f"Rechazado: Mesa [{active}] activa en curso en Telegram. No se permite enviar [{table_name}] en paralelo."
            logger.warning(f"⛔ [BLOQUEO ANTI-DUPLICADOS] {msg}")
            return False, msg

        short = _table_short(table_name)
        stats = self.stats_tracker.get_stats_summary()
        recommendation = stats.get("recommendation", "Basado en el autoanálisis (últimas 30 partidas), mayor efectividad en <b>tiros 1 al 3</b> (Bajos).")

        # Secuencia compacta: 1🔵 2🔴 3🔴 4🔴 5🔵 6🔴
        seq_text = " ".join(
            f"{i+1}{ICONS.get(x.upper(), '⚪')}" for i, x in enumerate(sequence[:6])
        )

        lines = [
            f"🎯 <b>{table_name} ({short})</b> | {seq_text}",
            "",
            f"🎲 <b>Probabilidad de ganar:</b> <b>{probability}%</b>",
            f"⚡ <b>Válido por 6 intentos</b>",
            "",
            f"💡 <b>Recomendación de Gestión:</b>",
            f"<i>{recommendation}</i>",
            "",
            f"🕐 <i>{datetime.now().strftime('%H:%M:%S')}</i>",
        ]
        caption = "\n".join(lines)

        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        if ok:
            self.lock_active_table(table_name)
            logger.info(f"🔒 [CANDADO TELEGRAM] Mesa activa fijada en '{table_name}'. Ninguna otra mesa podrá emitirse hasta su WIN o LOSS.")

        return ok, msg

    def send_result_message(self, table_name, result_type, attempt_number, screenshot_path=None, strategy_name=None):
        """
        Envía la foto de la mesa con el reporte de WIN N o LOSS.
        """
        short = _table_short(table_name)
        hora = datetime.now().strftime("%H:%M:%S")

        if result_type == "win":
            self.stats_tracker.record_win(table_name, attempt_number, strategy_name=strategy_name)
            stats = self.stats_tracker.get_stats_summary()
            header = f"🏆 <b>WIN {attempt_number} — {table_name} ({short})</b>"
            body = (
                f"✅ <b>¡Ganado en el intento {attempt_number}!</b>\n"
                f"🎰 Mesa: <b>{table_name}</b>\n"
                f"📊 Efectividad ({stats['sample_size']} partidas): <b>{stats['winrate']}%</b>\n"
                f"🕐 {hora}"
            )
        else:  # loss
            self.stats_tracker.record_loss(table_name, strategy_name=strategy_name)
            stats = self.stats_tracker.get_stats_summary()
            header = f"💔 <b>LOSS — {table_name} ({short})</b>"
            body = (
                f"❌ <b>Pérdida tras 6 intentos.</b>\n"
                f"🎰 Mesa: <b>{table_name}</b>\n"
                f"📊 Efectividad ({stats['sample_size']} partidas): <b>{stats['winrate']}%</b>\n"
                f"🕐 {hora}"
            )

        caption = f"{header}\n\n{body}"
        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        # ── CANAL EXCLUSIVO DE RESULTADOS (Solo: ✅ WIN 1..6 o ❌ LOSS) ──
        if self.results_chat_id:
            result_label = f"✅ WIN {attempt_number}" if result_type == "win" else "❌ LOSS"
            self.send_results_channel_message(f"<b>{result_label}</b>")

        # LIBERAR CANDADO DE TELEGRAM
        self.release_active_table(table_name)
        logger.info(f"🔓 [CANDADO TELEGRAM] Mesa '{table_name}' finalizada ({result_type}). Canal liberado para la siguiente mesa.")

        return ok, msg

    def send_next_attempt_message(self, table_name, next_attempt, prediction, screenshot_path=None):
        logger.info(f"[{table_name}] Intento {next_attempt} — {prediction} (silencioso)")
        return True, "silencioso"

    def send_tie_message(self, table_name, current_attempt):
        logger.info(f"[{table_name}] Empate en intento {current_attempt} — (silencioso)")
        return True, "silencioso"
