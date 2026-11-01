"""
core/auto_bettor.py  —  Módulo de Apuestas Automáticas (v26 - Corrección Completa)
====================================================================================

DOS MODOS DE JUEGO:
  MODO $0.20 → Tiro 1: 1 clic  ($0.20) | Martingala: 2→4→8→16→32→... clics de $0.20
  MODO $0.40 → Tiro 1: 2 clics ($0.40) | Martingala: 4→8→16→32→...  clics de $0.20

REGLAS:
  - Siempre se selecciona la ficha CORRECTA antes de cada apuesta.
  - Para montos pequeños (≤ $4.00): solo se usa la ficha de $0.20.
  - Para montos grandes: se usa la combinación más eficiente de fichas disponibles.
  - Empate → misma apuesta, no avanza martingala.
  - LOSS de mesa completa → martingala persiste a la siguiente mesa.

MARTINGALA CROSS-TABLE:
  - persistent_step acumula cada paso fallido (no salta al máximo).
  - Al ganar: reset completo a paso 0.
  - Al pasar de mesa con LOSS: la siguiente señal empieza desde el paso acumulado.
"""

import os
import json
import time
import math
import random
import logging
import pyautogui

logger = logging.getLogger("AutoBettor")

# Seguridad de PyAutoGUI — pausa mínima entre llamadas
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.06

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

# Umbral de clics: si el monto requiere MÁS de este número de clics en $0.20,
# se usan fichas más grandes para ser eficiente.
MAX_CLICKS_SMALL_CHIP = 20  # 20 clics × $0.20 = $4.00


class AutoBettor:
    def __init__(
        self,
        enabled=False,
        stop_loss=-25.0,
        take_profit=20.0,
        base_bet=0.20,
        base_chip=0.20,
        persistent_martingale=True,
        max_steps=12,
        initial_clicks=1      # MODO_40=2, MODO_20=1
    ):
        self.enabled = enabled
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.base_bet = base_bet
        self.base_chip = base_chip          # Valor de la ficha física ($0.20)
        self.persistent_martingale = persistent_martingale
        self.max_steps = max_steps
        self.initial_clicks = initial_clicks

        self.session_profit = 0.0
        self.bets_placed_count = 0

        # ── Martingala Persistente ──────────────────────────────────
        # persistent_step: número de pasos fallidos acumulados en mesas anteriores.
        # Se incrementa 1 por cada intento perdido. Se resetea en WIN.
        # cross_table_carry: True cuando venimos de un LOSS de mesa completa.
        self.persistent_step = 0
        self.cross_table_carry = False
        self.total_martingale_lost = 0.0

        self.is_paused_by_limits = False
        self.pause_reason = ""
        self.dynamic_slots = {}

        self.coordinates = self._load_coordinates()

    # ──────────────────────────────────────────────────────────────
    # Carga de coordenadas
    # ──────────────────────────────────────────────────────────────
    def _load_coordinates(self):
        default_coords = {
            "chip_02": {"x": 510, "y": 741, "description": "Ficha $0.20"},
            "chips": {
                "0.2":  {"x": 510, "y": 741},
                "1":    {"x": 559, "y": 741},
                "5":    {"x": 608, "y": 741},
                "20":   {"x": 657, "y": 741},
                "100":  {"x": 706, "y": 741},
                "250":  {"x": 756, "y": 741},
            },
            "player": {"x": 109, "y": 204},
            "banker": {"x": 236, "y": 204},
        }
        if os.path.exists(COORDS_FILE):
            try:
                with open(COORDS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando bet_coordinates.json: {e}")
        return default_coords

    def reload_coordinates(self):
        self.coordinates = self._load_coordinates()
        logger.info("Coordenadas de apuestas recargadas desde archivo.")

    def update_dynamic_slots(self, slot_bets_dict):
        if slot_bets_dict:
            self.dynamic_slots.update(slot_bets_dict)

    # ──────────────────────────────────────────────────────────────
    # Movimiento y clic humanizado
    # ──────────────────────────────────────────────────────────────
    def human_click(self, x, y, jitter=4):
        """Mueve el mouse con movimiento suave y ejecuta un clic."""
        try:
            tx = x + random.randint(-jitter, jitter)
            ty = y + random.randint(-jitter, jitter)
            pyautogui.moveTo(tx, ty, duration=random.uniform(0.15, 0.25), tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.08, 0.14))
            pyautogui.click()
            time.sleep(random.uniform(0.08, 0.13))
            return True
        except pyautogui.FailSafeException:
            logger.warning("FailSafe activado — clic cancelado.")
            return False
        except Exception as e:
            logger.error(f"Error en human_click: {e}")
            return False

    def multi_click(self, x, y, count=1):
        """
        Mueve el mouse al área de apuesta y hace 'count' clics consecutivos.
        Cada clic agrega la ficha actualmente seleccionada en el casino.
        """
        if count <= 0:
            return True
        try:
            tx = x + random.randint(-4, 4)
            ty = y + random.randint(-4, 4)
            pyautogui.moveTo(tx, ty, duration=random.uniform(0.15, 0.25), tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.10, 0.15))
            pyautogui.click()
            time.sleep(random.uniform(0.10, 0.15))
            for _ in range(count - 1):
                pyautogui.moveRel(random.randint(-1, 1), random.randint(-1, 1))
                time.sleep(random.uniform(0.07, 0.11))
                pyautogui.click()
                time.sleep(random.uniform(0.07, 0.11))
            return True
        except pyautogui.FailSafeException:
            logger.warning("FailSafe activado — clics cancelados.")
            return False
        except Exception as e:
            logger.error(f"Error en multi_click: {e}")
            return False

    # ──────────────────────────────────────────────────────────────
    # Selección de ficha
    # ──────────────────────────────────────────────────────────────
    def _get_chip_list(self):
        """
        Retorna lista de fichas disponibles [(valor, x, y)] ordenadas de mayor a menor.
        """
        chips_dict = self.coordinates.get("chips", {})
        result = []
        for label, coord in chips_dict.items():
            if isinstance(coord, dict) and "x" in coord and "y" in coord:
                try:
                    val = float(label)
                    result.append((val, coord["x"], coord["y"]))
                except (ValueError, TypeError):
                    pass
        result.sort(key=lambda t: t[0], reverse=True)
        return result

    def _get_chip_02_coords(self):
        """Retorna (x, y) de la ficha de $0.20 (la más pequeña / más a la izquierda)."""
        chip_list = self._get_chip_list()
        if chip_list:
            # La de menor valor es la última (lista ordenada desc)
            return chip_list[-1][1], chip_list[-1][2]
        # Fallback desde chip_02/chip_20
        for key in ("chip_02", "chip_20"):
            c = self.coordinates.get(key)
            if isinstance(c, dict) and "x" in c:
                return c["x"], c["y"]
        return 510, 741  # defaults calibrados

    def _select_chip_by_coords(self, cx, cy):
        """Clic en la ficha ubicada en (cx, cy) para seleccionarla en el casino."""
        self.human_click(cx, cy, jitter=3)

    # ──────────────────────────────────────────────────────────────
    # Cálculo del monto de apuesta
    # ──────────────────────────────────────────────────────────────
    def get_bet_amount(self, attempt_index=0):
        """
        Calcula el monto y el paso de martingala para el intento actual.

        MODO_20 (initial_clicks=1):
          Paso 0 → 1 clic  = $0.20
          Paso 1 → 2 clics = $0.40
          Paso 2 → 4 clics = $0.80
          Paso 3 → 8 clics = $1.60 ...

        MODO_40 (initial_clicks=2):
          Paso 0 → 2 clics  = $0.40
          Paso 1 → 4 clics  = $0.80
          Paso 2 → 8 clics  = $1.60 ...

        Cross-table carry: si venimos de LOSS de mesa anterior,
        el paso base es persistent_step (no se suma attempt_index).
        Esto garantiza que la martingala continúe exactamente donde quedó.
        """
        if self.persistent_martingale and self.cross_table_carry:
            # Usa persistent_step como paso base (acumulado de mesas anteriores)
            step = min(self.persistent_step, self.max_steps)
        else:
            # Mesa normal: attempt_index va 0..5 dentro de la sesión
            step = min(attempt_index, self.max_steps)

        clicks = self.initial_clicks * (2 ** step)
        amt = round(self.base_chip * clicks, 2)
        return amt, step

    # ──────────────────────────────────────────────────────────────
    # Colocación inteligente de apuesta (ficha correcta para el monto)
    # ──────────────────────────────────────────────────────────────
    def _place_bet_amount(self, target_x, target_y, target_amount):
        """
        Coloca exactamente target_amount en la zona (target_x, target_y).

        Para montos pequeños (≤ MAX_CLICKS_SMALL_CHIP × $0.20):
          → Selecciona ficha $0.20 y hace N clics en el área de apuesta.

        Para montos grandes:
          → Descompone el monto en combinaciones de fichas disponibles
            para minimizar el número total de clics necesarios.
        """
        chip_list = self._get_chip_list()   # [(valor, x, y)] mayor → menor
        if not chip_list:
            logger.error("No hay fichas configuradas. No se puede apostar.")
            return False

        clicks_needed_02 = round(target_amount / self.base_chip)
        chip_02_x, chip_02_y = self._get_chip_02_coords()

        if clicks_needed_02 <= MAX_CLICKS_SMALL_CHIP:
            # ── MODO SIMPLE: solo ficha $0.20 ──────────────────────
            logger.info(f"Seleccionando ficha $0.20 → {clicks_needed_02} clic(s) = ${target_amount:.2f}")
            self._select_chip_by_coords(chip_02_x, chip_02_y)
            time.sleep(0.15)
            ok = self.multi_click(target_x, target_y, count=clicks_needed_02)
            return ok
        else:
            # ── MODO EFICIENTE: fichas grandes + $0.20 para el resto ─
            remaining = round(target_amount, 2)
            logger.info(f"Monto alto ${target_amount:.2f} — usando fichas grandes para eficiencia.")

            for chip_val, cx, cy in chip_list:
                if remaining < chip_val - 0.001:
                    continue
                count = int(remaining / chip_val + 0.001)
                if count <= 0:
                    continue
                subtotal = round(chip_val * count, 2)
                logger.info(f"  → Ficha ${chip_val:.2f}: {count} clic(s) = ${subtotal:.2f}")
                self._select_chip_by_coords(cx, cy)
                time.sleep(0.15)
                ok = self.multi_click(target_x, target_y, count=count)
                if not ok:
                    return False
                time.sleep(0.12)
                remaining = round(remaining - subtotal, 2)
                if remaining < 0.01:
                    break

            if remaining > 0.01:
                # Resto con $0.20
                extra = round(remaining / self.base_chip)
                if extra > 0:
                    logger.info(f"  → Resto con $0.20: {extra} clic(s) = ${remaining:.2f}")
                    self._select_chip_by_coords(chip_02_x, chip_02_y)
                    time.sleep(0.15)
                    self.multi_click(target_x, target_y, count=extra)
            return True

    # ──────────────────────────────────────────────────────────────
    # Ejecución de apuesta
    # ──────────────────────────────────────────────────────────────
    def execute_bet(self, prediction, attempt_index=0, table_name=None, dynamic_coords=None):
        amt, step = self.get_bet_amount(attempt_index)
        pred_label = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        table_label = f"[{table_name}] " if table_name else ""
        step_label = f"(Paso #{step + 1})"

        if not self.enabled:
            msg = f"Simulación: {table_label}${amt:.2f} a {pred_label} {step_label}"
            logger.info(f"[SIMULACION] {msg}")
            return True, msg

        if self.is_paused_by_limits:
            return False, f"Apuestas en pausa: {self.pause_reason}"

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO (${self.session_profit:.2f} <= ${self.stop_loss:.2f})"
            logger.warning(self.pause_reason)
            return False, self.pause_reason

        if self.take_profit is not None and self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"🎉 TAKE-PROFIT ALCANZADO (+${self.session_profit:.2f} >= +${self.take_profit:.2f})"
            logger.info(self.pause_reason)
            return False, self.pause_reason

        # ── Obtener coordenadas del área de apuesta ─────────────────
        target_key = "player" if prediction == "P" else "banker"
        target_coord = None

        # PRIORIDAD 1: Coordenadas estáticas oficiales de bet_coordinates.json
        if table_name and "tables" in self.coordinates and table_name in self.coordinates["tables"]:
            target_coord = self.coordinates["tables"][table_name].get(target_key)
        # PRIORIDAD 2: Fallback a slots dinámicos si no existe en tablas fijas
        if not target_coord and dynamic_coords and target_key in dynamic_coords:
            target_coord = dynamic_coords[target_key]
        if not target_coord and table_name and table_name in self.dynamic_slots:
            target_coord = self.dynamic_slots[table_name].get(target_key)
        if not target_coord:
            target_coord = self.coordinates.get(target_key)

        if not target_coord:
            return False, f"Coordenada no encontrada para {target_key} ({table_name or 'general'})"

        tx, ty = target_coord["x"], target_coord["y"]

        clicks_total = self.initial_clicks * (2 ** step)
        logger.info(f"🚀 Apuesta REAL: {table_label}${amt:.2f} ({clicks_total} clic(s)) a {pred_label} {step_label} → ({tx}, {ty})")

        # ── Colocar la apuesta ────────────────────────────────────────
        ok = self._place_bet_amount(tx, ty, amt)
        if not ok:
            return False, "Interrupción de clic (FailSafe)"

        self.bets_placed_count += 1
        return True, f"✅ ${amt:.2f} ({clicks_total} clic(s)) colocados sobre {pred_label} {step_label}"

    # ──────────────────────────────────────────────────────────────
    # Registros de resultado
    # ──────────────────────────────────────────────────────────────
    def record_win(self, attempt_index=0):
        """Registra un WIN: recupera y resetea la martingala a 0 incondicionalmente."""
        amt, step = self.get_bet_amount(attempt_index)
        self.session_profit += amt
        net_cycle = amt - self.total_martingale_lost

        # Reset completo de martingala: la próxima mesa inicia siempre en 1 clic
        self.persistent_step = 0
        self.cross_table_carry = False
        self.total_martingale_lost = 0.0

        logger.info(
            f"🏆 WIN en paso {step + 1}! +${amt:.2f} (neto ciclo: +${net_cycle:.2f}) | "
            f"Total sesión: ${self.session_profit:.2f} | Martingala reseteada a 0"
        )

        if self.take_profit is not None and self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"🎉 TAKE-PROFIT ALCANZADO (+${self.session_profit:.2f})"
            logger.info(self.pause_reason)

    def record_step_loss(self, attempt_index=0):
        """
        Registra la pérdida de un intento individual dentro de la mesa.
        NO incrementa persistent_step de forma permanente (solo aplica si la mesa completa pierde).
        """
        amt, step = self.get_bet_amount(attempt_index)
        self.session_profit -= amt
        self.total_martingale_lost += amt

        base_step = self.persistent_step if self.cross_table_carry else 0
        next_step = min(base_step + attempt_index + 1, self.max_steps)
        next_clicks = self.initial_clicks * (2 ** next_step)
        next_amt = round(self.base_chip * next_clicks, 2)
        logger.info(
            f"✗ Intento {attempt_index + 1} fallido: -${amt:.2f} | "
            f"Próximo tiro: ${next_amt:.2f} ({next_clicks} clics, paso {next_step + 1}) | "
            f"Balance: ${self.session_profit:.2f}"
        )

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO (${self.session_profit:.2f} <= ${self.stop_loss:.2f})"
            logger.warning(self.pause_reason)

    def record_table_finished_loss(self, attempt_index=None):
        """
        Registra que la sesión completa de 6 intentos fue LOSS.
        Activa cross-table carry para que la SIGUIENTE mesa continúe la martingala.
        """
        if self.persistent_martingale:
            self.cross_table_carry = True   # La SIGUIENTE mesa continúa la martingala
            self.persistent_step = min(self.persistent_step + 6, self.max_steps)
            next_clicks = self.initial_clicks * (2 ** self.persistent_step)
            next_amt = round(self.base_chip * next_clicks, 2)
            logger.info(
                f"💔 LOSS completo de mesa (6 tiros). MARTINGALA CROSS-TABLE ACTIVA: "
                f"próxima mesa inicia en paso {self.persistent_step + 1} (${next_amt:.2f}, {next_clicks} clics)"
            )
        else:
            self.persistent_step = 0
            self.cross_table_carry = False
            self.total_martingale_lost = 0.0
            logger.info("💔 Mesa finalizada en LOSS. Martingala reiniciada a paso 1.")

    def reset_martingale(self):
        """Reinicia la martingala completamente a paso 0 (1 clic base)."""
        self.persistent_step = 0
        self.cross_table_carry = False
        self.total_martingale_lost = 0.0
        logger.info("🔄 Martingala reseteada a paso 0 (inicio limpio).")

    # ──────────────────────────────────────────────────────────────
    # Utilidades
    # ──────────────────────────────────────────────────────────────
    def select_chip_base(self):
        """Selecciona la ficha de $0.20 en el casino (alias de compatibilidad)."""
        cx, cy = self._get_chip_02_coords()
        self._select_chip_by_coords(cx, cy)

    def get_status(self):
        step = min(self.persistent_step, self.max_steps)
        next_clicks = self.initial_clicks * (2 ** step)
        next_amt = round(self.base_chip * next_clicks, 2)
        return {
            "enabled":               self.enabled,
            "modo":                  f"MODO_{'40' if self.initial_clicks == 2 else '20'}",
            "initial_clicks":        self.initial_clicks,
            "base_chip":             self.base_chip,
            "persistent_martingale": self.persistent_martingale,
            "max_steps":             self.max_steps,
            "persistent_step":       self.persistent_step,
            "cross_table_carry":     self.cross_table_carry,
            "next_bet_amount":       next_amt,
            "next_clicks":           next_clicks,
            "session_profit":        round(self.session_profit, 2),
            "bets_placed":           self.bets_placed_count,
            "is_paused":             self.is_paused_by_limits,
            "pause_reason":          self.pause_reason,
            "stop_loss":             self.stop_loss,
            "take_profit":           self.take_profit,
        }
