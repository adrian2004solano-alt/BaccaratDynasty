"""
core/telegram_bot.py — Emisor de Señales "Bot Logro" (Jugada Directa Tiro a Tiro y Cambio Dinámico)
====================================================================================================
1. CERO SECUENCIAS DE 6 COLORES:
   - Envía 1 sola indicación concreta de mesa y color:
     🎯 Baccarat 1 (M1) ➔ 🔵 AZUL (JUGADOR)
2. PROYECCIÓN DINÁMICA DE INTENTOS (1, 2 o 3 intentos según lectura de mesa).
3. RECUPERACIÓN INTELIGENTE CON FOTO NUEVA:
   - Si el intento 1 falla y el bot decide cambiar de mesa y/o de color,
     envía inmediatamente una NUEVA FOTO de la mesa elegida con la indicación exacta
     para el Intento 2 (o Intento 3, etc.).
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
COLOR_FULL = {"P": "🔵 AZUL (JUGADOR)", "B": "🔴 ROJO (BANCA)", "T": "🟢 EMPATE"}
COLOR_SHORT = {"P": "🔵 AZUL", "B": "🔴 ROJO", "T": "🟢 EMPATE"}

ACTIVE_LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".active_table.lock")
MAX_ACTIVE_LOCK_SECONDS = 480  # 8 minutos timeout de seguridad


def _table_short(table_name):
    """'Baccarat 5' → 'M5'  |  'Speed Baccarat 2' → 'SM2'  |  'Baccarat 1' → 'M1'"""
    s = table_name.upper().replace("BACCARAT ", "M").replace("BACCARAT", "M")
    s = s.replace("SPEED M", "SM").replace("SPEED ", "S")
    return s if s.startswith("M") or s.startswith("S") else f"M{table_name}"


def _plan_attempts_label(planned_attempts):
    att = int(planned_attempts or 1)
    if att <= 1:
        return "1 solo intento en esta mesa (Tiro Franco)"
    elif att == 2:
        return "1 a 2 intentos según respuesta de mesa"
    else:
        return "Hasta 3 intentos en tendencia dominante"


class TelegramNotifier:
    def __init__(self, token=None, chat_id=None, results_token=None, results_chat_id=None):
        self.token           = token           or config.TELEGRAM_BOT_TOKEN
        self.chat_id         = chat_id         or config.TELEGRAM_CHAT_ID
        self.results_token   = results_token   or getattr(config, "TELEGRAM_RESULTS_BOT_TOKEN", None)
        self.results_chat_id = results_chat_id or getattr(config, "TELEGRAM_RESULTS_CHAT_ID", None)
        self._msg_url        = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self._pho_url        = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        self.stats_tracker   = StatsTracker()
        self.active_table    = None

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
        """Actualiza el candado de Telegram a la mesa activa actual (la única válida para WIN/LOSS)."""
        self.active_table = table_name
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
        """Libera el candado de Telegram tras finalizar la jugada/ciclo."""
        self.active_table = None
        try:
            if os.path.exists(ACTIVE_LOCK_FILE):
                os.remove(ACTIVE_LOCK_FILE)
        except Exception as e:
            logger.warning(f"No se pudo remover lock de mesa activa: {e}")

    # ──────────────────────────────────────────────────────────────────
    # 1. EMISIÓN DE JUGADA INICIAL (INTENTO 1 — UN SOLO COLOR)
    # ──────────────────────────────────────────────────────────────────
    def send_logro_signal(
        self,
        table_name,
        prediction,
        probability=92,
        planned_attempts=1,
        screenshot_path=None,
        strategy_name="BOT_LOGRO",
        reason="",
        base_hand_count=0,
    ):
        """
        Envía la señal de entrada inicial (Intento 1) con 1 solo color concreto
        y la estimación inteligente de intentos en esa mesa (1, 2 o 3).
        """
        short = _table_short(table_name)
        pred_code = str(prediction).upper().strip()
        color_full = COLOR_FULL.get(pred_code, "🔵 AZUL (JUGADOR)")
        plan_text = _plan_attempts_label(planned_attempts)
        hora = datetime.now().strftime("%H:%M:%S")

        hand_ref = (
            f"ℹ️ <i>Captura de mano #{base_hand_count} — Apostar en mano #{base_hand_count+1}</i>"
            if (base_hand_count and base_hand_count > 0)
            else ""
        )

        lines = [
            f"🎯 <b>{table_name} ({short})</b> ➔ <b>{color_full}</b>",
        ]
        if hand_ref:
            lines.append(hand_ref)

        lines.extend([
            "",
            f"🔥 <b>Acción:</b> <b>INTENTO 1</b> (Entrada directa)",
            f"🛡️ <b>Plan en mesa:</b> <b>{plan_text}</b>",
            f"🎲 <b>Confianza del análisis:</b> <b>{probability}%</b>",
        ])

        if reason:
            lines.extend([
                "",
                f"🧠 <b>Lectura de mesa:</b>",
                f"<i>{reason}</i>",
            ])

        lines.extend([
            "",
            f"🕐 <i>{hora}</i>",
        ])
        caption = "\n".join(lines)

        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        if ok:
            self.lock_active_table(table_name)
            logger.info(f"🔒 [BOT LOGRO] Señal Intento 1 emitida en '{table_name}' ➔ {color_full}.")

        # Sincronizar con la plataforma Web BaccaratDynasty y Supabase
        try:
            from core.web_bridge import publish_signal_to_web
            publish_signal_to_web(
                table_name=table_name,
                sequence=[pred_code],
                probability=probability,
                screenshot_path=screenshot_path,
                strategy_name=strategy_name,
                base_hand_count=base_hand_count,
                current_attempt=1,
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar señal a WebBridge: {e}")

        return ok, msg

    # ──────────────────────────────────────────────────────────────────
    # 2. EMISIÓN DE RECUPERACIÓN / CAMBIO DE MESA O COLOR (INTENTO 2+)
    # ──────────────────────────────────────────────────────────────────
    def send_logro_recovery_signal(
        self,
        table_name,
        prediction,
        attempt_number,
        probability=91,
        planned_attempts=1,
        screenshot_path=None,
        strategy_name="BOT_LOGRO_REC",
        reason="",
        base_hand_count=0,
        switched_table=False,
        prev_table=None,
        changed_color=False,
    ):
        """
        Cuando un intento falla, Bot Logro re-analiza todas las mesas.
        Si cambia de mesa o actualiza el color para el siguiente intento,
        envía una NUEVA FOTO con la instrucción clara del Intento N.
        """
        short = _table_short(table_name)
        pred_code = str(prediction).upper().strip()
        color_full = COLOR_FULL.get(pred_code, "🔵 AZUL (JUGADOR)")
        hora = datetime.now().strftime("%H:%M:%S")

        hand_ref = (
            f"ℹ️ <i>Captura de mano #{base_hand_count} — Apostar en mano #{base_hand_count+1}</i>"
            if (base_hand_count and base_hand_count > 0)
            else ""
        )

        if switched_table and prev_table and prev_table != table_name:
            prev_short = _table_short(prev_table)
            header = f"🔄 <b>CAMBIO DE MESA — INTENTO {attempt_number}</b>"
            sub_line = (
                f"🚫 <i>Mesa anterior descartada: {prev_table} ({prev_short})</i>\n"
                f"🎰 <b>Nueva Mesa en Vivo:</b> <b>{table_name} ({short})</b>"
            )
            action_tag = "Cambio sincronizado con tiempo completo (15s)"
        else:
            header = f"⚡ <b>INDICACIÓN INTENTO {attempt_number} — {table_name} ({short})</b>"
            sub_line = f"🎰 <b>Mesa Activa:</b> <b>{table_name} ({short})</b>"
            action_tag = "Giro táctico de color en mesa" if changed_color else "Continuación confirmada en mesa"

        lines = [
            header,
            sub_line,
            f"👉 <b>APOSTAR A:</b> <b>{color_full}</b>",
        ]
        if hand_ref:
            lines.append(hand_ref)

        lines.extend([
            "",
            f"🧭 <b>Movimiento:</b> <i>{action_tag}</i>",
            f"🎲 <b>Confianza:</b> <b>{probability}%</b>",
        ])

        if reason:
            lines.extend([
                f"🧠 <b>Motivo:</b> <i>{reason}</i>",
            ])

        lines.extend([
            "",
            f"🕐 <i>{hora}</i>",
        ])
        caption = "\n".join(lines)

        ok, msg = self.send_photo(screenshot_path, caption=caption)
        if not ok:
            ok, msg = self.send_message(caption)

        if ok:
            self.lock_active_table(table_name)
            logger.info(
                f"🔄 [BOT LOGRO] Intento {attempt_number} emitido en '{table_name}' ➔ {color_full} "
                f"(Cambio de mesa: {switched_table})."
            )

        # Actualizar también la plataforma Web con la mesa/color/foto del intento actual
        try:
            from core.web_bridge import publish_signal_to_web
            seq_for_web = [pred_code] * max(1, int(attempt_number))
            publish_signal_to_web(
                table_name=table_name,
                sequence=seq_for_web,
                probability=probability,
                screenshot_path=screenshot_path,
                strategy_name=strategy_name,
                base_hand_count=base_hand_count,
                current_attempt=int(attempt_number),
            )
        except Exception as e:
            logger.warning(f"No se pudo actualizar intento en WebBridge: {e}")

        return ok, msg

    # Compatibilidad con llamadas antiguas
    def send_baccarat_signal(self, table_name, sequence, probability=90, screenshot_path=None, strategy_name="BOT_LOGRO", base_hand_count=0):
        pred = sequence[0] if sequence else "P"
        return self.send_logro_signal(
            table_name=table_name,
            prediction=pred,
            probability=probability,
            planned_attempts=1,
            screenshot_path=screenshot_path,
            strategy_name=strategy_name,
            base_hand_count=base_hand_count,
        )

    # ──────────────────────────────────────────────────────────────────
    # 3. REPORTE DE RESULTADO (WIN 1..6 o LOSS)
    # ──────────────────────────────────────────────────────────────────
    def send_result_message(self, table_name, result_type, attempt_number, screenshot_path=None, strategy_name=None):
        """
        Envía la foto de la mesa con el reporte de WIN N o LOSS.
        Garantiza que SOLO se emita resultado de la última mesa enviada en vivo (`self.active_table`).
        """
        if self.active_table and table_name != self.active_table:
            logger.warning(
                f"🚫 [BLOQUEO DE MESA ANTIGUA] Ignorando {result_type} de '{table_name}' "
                f"porque la única mesa activa en vivo es '{self.active_table}'."
            )
            return False, f"Ignorado: {table_name} no es la mesa activa ({self.active_table})"

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
                f"❌ <b>Ciclo finalizado sin acierto.</b>\n"
                f"🎰 Última Mesa: <b>{table_name}</b>\n"
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

        # Publicar resultado en paralelo en la Plataforma Web BaccaratDynasty y Supabase
        try:
            from core.web_bridge import publish_result_to_web
            publish_result_to_web(
                table_name=table_name,
                result_type=result_type,
                attempt_number=attempt_number,
                screenshot_path=screenshot_path,
                strategy_name=strategy_name,
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar resultado a WebBridge: {e}")

        # LIBERAR CANDADO DE TELEGRAM
        self.release_active_table(table_name)
        logger.info(f"🔓 [CANDADO TELEGRAM] Mesa '{table_name}' finalizada ({result_type}). Canal liberado.")

        return ok, msg

    def send_next_attempt_message(self, table_name, next_attempt, prediction, screenshot_path=None):
        logger.info(f"[{table_name}] Intento {next_attempt} — {prediction}")
        try:
            from core.web_bridge import publish_attempt_to_web
            publish_attempt_to_web(next_attempt, table_name=table_name)
        except Exception:
            pass
        return True, "actualizado"

    def send_tie_message(self, table_name, current_attempt):
        logger.info(f"[{table_name}] Empate en intento {current_attempt} — (se mantiene el mismo intento)")
        return True, "silencioso"
