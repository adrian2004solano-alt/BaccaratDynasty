"""
core/auto_bettor.py  —  Módulo de Apuestas Automáticas Bot Logro ($0.20 Base + 8 Martingalas)
=============================================================================================
1. Clics Hardware Anti-Detección (ctypes WinAPI):
   - Usa mouse_event LEFTDOWN + hold 55ms + LEFTUP via ctypes.windll.user32.
   - Movimiento suave con pyautogui + jitter natural para imitar comportamiento humano.
2. Lógica Inteligente de Fichas Izquierdas (Moneda 1 Base $0.20 + Apoyo 5x $1.00 y 25x $5.00):
   - Moneda 1 (Base, Primera a la Izquierda, x=511, y=734): $0.20 USD
   - Moneda 2 (Segunda a la Izquierda, x=559, y=734): $1.00 USD (5x Base)
   - Moneda 3 (Tercera a la Izquierda, x=609, y=734): $5.00 USD (25x Base)
   - Progresión exacta de 8 Tiros (Tiro 8 repite el monto del Tiro 7 como recuperación):
     * Tiro 1 (Base)          : $0.20  (1x $0.20 — 1 clic)
     * Tiro 2 (Martingala 1)  : $0.40  (2x $0.20 — 2 clics)
     * Tiro 3 (Martingala 2)  : $0.80  (4x $0.20 — 4 clics)
     * Tiro 4 (Martingala 3)  : $1.60  (1x $1.00 + 3x $0.20 — 4 clics)
     * Tiro 5 (Martingala 4)  : $3.20  (3x $1.00 + 1x $0.20 — 4 clics)
     * Tiro 6 (Martingala 5)  : $6.40  (1x $5.00 + 1x $1.00 + 2x $0.20 — 4 clics)
     * Tiro 7 (Martingala 6)  : $12.80 (2x $5.00 + 2x $1.00 + 4x $0.20 — 8 clics)
     * Tiro 8 (Recuperación)  : $12.80 (Misma cantidad que el Tiro 7 — 8 clics)
3. Parada Automática tras Perder el Tiro 8 y Cero Límite de Ganancia (Sin Stop-Profit):
   - Si gana el Tiro 8 (o cualquier tiro previo), reinicia a $0.20 y continúa jugando sin límite.
   - Si pierde el Tiro 8 ($12.80), el bot se detiene automáticamente por completo.
"""

import os
import json
import time
import random
import logging
import ctypes
import pyautogui

logger = logging.getLogger("AutoBettor")

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

_REF_W = 1366
_REF_H = 768

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP   = 0x0004


def _hardware_click(x, y, hold=0.055):
    """Clic hardware real via ctypes WinAPI para canvas HTML5."""
    try:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        time.sleep(0.03)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(hold)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.03)
        return True
    except Exception as e:
        logger.error(f"Error en _hardware_click({x},{y}): {e}")
        return False


class AutoBettor:
    def __init__(
        self,
        enabled=True,
        currency="USD",
        chip1_value=0.20,
        chip2_value=1.00,
        chip3_value=5.00,
        currency_symbol="$",
        stop_loss=None,
        take_profit=None,
        persistent_martingale=True,
        max_steps=8,
        currency_label="",
    ):
        self.enabled = enabled
        self.currency = currency.upper()
        self.chip1_value = float(chip1_value)
        self.chip2_value = float(chip2_value)
        self.chip3_value = float(chip3_value)
        self.currency_symbol = currency_symbol
        self.base_bet = self.chip1_value
        self.base_chip = self.chip1_value
        self.currency_label = currency_label or f"{self.currency} ({self.currency_symbol})"

        self.stop_loss = stop_loss
        self.take_profit = None  # Sin Stop-Profit: ganar todo lo que pueda
        self.persistent_martingale = persistent_martingale
        self.max_steps = int(max_steps) if max_steps is not None else 8

        self.session_profit = 0.0
        self.bets_placed_count = 0
        self.persistent_step = 0
        self.total_martingale_lost = 0.0
        self.is_paused_by_limits = False
        self.pause_reason = ""
        self.dynamic_slots = {}

        self.coordinates = self._load_coordinates()
        self._resolve_chip_coordinates()

    def _load_coordinates(self):
        default_coords = {
            "reference_resolution": {"width": 1366, "height": 768},
            "chip_20": {"x": 511, "y": 734, "description": "Ficha 1 (Base $0.20)"},
            "chips": [
                {"value": 5.00, "x": 609, "y": 734, "description": "Ficha 3 (25x - $5.00)"},
                {"value": 1.00, "x": 559, "y": 734, "description": "Ficha 2 (5x - $1.00)"},
                {"value": 0.20, "x": 511, "y": 734, "description": "Ficha 1 (Base - $0.20)"},
            ],
        }
        if os.path.exists(COORDS_FILE):
            try:
                with open(COORDS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando bet_coordinates.json: {e}")
        return default_coords

    def _resolve_chip_coordinates(self):
        """
        Identifica físicamente de izquierda a derecha en la barra inferior:
          - Moneda 1 (extrema izquierda): $0.20 (x=511, y=734)
          - Moneda 2 (segunda a la izquierda): $1.00 (x=559, y=734)
          - Moneda 3 (tercera a la izquierda): $5.00 (x=609, y=734)
        """
        raw_chips = self.coordinates.get("chips", [])
        valid_chips = [c for c in raw_chips if isinstance(c, dict) and "x" in c and "y" in c]

        if valid_chips:
            sorted_chips = sorted(valid_chips, key=lambda c: c["x"])
            self.chip1_coord = sorted_chips[0]
            self.chip2_coord = sorted_chips[1] if len(sorted_chips) > 1 else sorted_chips[0]
            self.chip3_coord = sorted_chips[2] if len(sorted_chips) > 2 else self.chip2_coord
        else:
            fallback = self.coordinates.get("chip_base") or self.coordinates.get("chip_20") or {"x": 511, "y": 734}
            self.chip1_coord = fallback
            self.chip2_coord = {"x": fallback["x"] + 48, "y": fallback["y"]}
            self.chip3_coord = {"x": fallback["x"] + 98, "y": fallback["y"]}

        logger.info(
            f"Fichas calibradas: Moneda 1 ({self.chip1_value:.2f} {self.currency}) en ({self.chip1_coord['x']}, {self.chip1_coord['y']}) | "
            f"Moneda 2 ({self.chip2_value:.2f} {self.currency}) en ({self.chip2_coord['x']}, {self.chip2_coord['y']}) | "
            f"Moneda 3 ({self.chip3_value:.2f} {self.currency}) en ({self.chip3_coord['x']}, {self.chip3_coord['y']})"
        )

    def reload_coordinates(self):
        self.coordinates = self._load_coordinates()
        self._resolve_chip_coordinates()

    def update_dynamic_slots(self, slot_bets_dict):
        if slot_bets_dict:
            self.dynamic_slots.update(slot_bets_dict)

    def _scale_coord(self, x, y):
        ref = self.coordinates.get("reference_resolution", {})
        ref_w = ref.get("width", _REF_W)
        ref_h = ref.get("height", _REF_H)
        try:
            sw, sh = pyautogui.size()
            sx = sw / ref_w
            sy = sh / ref_h
        except Exception:
            sx, sy = 1.0, 1.0
        return int(round(x * sx)), int(round(y * sy))

    def multi_click(self, x, y, count=1):
        if count <= 0:
            return True
        try:
            target_x = x + random.randint(-3, 3)
            target_y = y + random.randint(-3, 3)
            duration = random.uniform(0.08, 0.14)
            pyautogui.moveTo(target_x, target_y, duration=duration, tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.02, 0.03))

            _hardware_click(target_x, target_y, hold=0.055)

            for _ in range(count - 1):
                time.sleep(random.uniform(0.055, 0.080))
                adj_x = target_x + random.randint(-1, 1)
                adj_y = target_y + random.randint(-1, 1)
                _hardware_click(adj_x, adj_y, hold=0.050)

            time.sleep(0.03)
            return True
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI FailSafe activado (mouse en esquina). Clic cancelado.")
            return False
        except Exception as e:
            logger.error(f"Error en multi_click: {e}")
            return False

    def select_chip(self, chip_coord):
        if not chip_coord or not self.enabled or self.is_paused_by_limits:
            return False
        sx, sy = self._scale_coord(chip_coord["x"], chip_coord["y"])
        try:
            jx = sx + random.randint(-2, 2)
            jy = sy + random.randint(-2, 2)
            pyautogui.moveTo(jx, jy, duration=random.uniform(0.07, 0.12), tween=pyautogui.easeOutQuad)
            time.sleep(0.02)
            _hardware_click(jx, jy, hold=0.055)
            time.sleep(0.04)
            return True
        except Exception as e:
            logger.error(f"Error seleccionando ficha: {e}")
            return False

    def select_chip_base(self):
        """Selecciona la Moneda 1 ($0.20, primera moneda a la izquierda)."""
        self.select_chip(self.chip1_coord)

    # ──────────────────────────────────────────────────────────────
    # Cálculo inteligente de apuestas (8 Tiros: Tiro 8 = Tiro 7 = $12.80)
    # ──────────────────────────────────────────────────────────────
    def _units_for_step(self, step):
        """
        Para `max_steps = 8` (Tiros 1 al 8, índices 0..7):
          - Tiros 1 al 7 (`step` 0..6): doblan normal (2^0=1, 2^1=2, 2^2=4, 2^3=8, 2^4=16, 2^5=32, 2^6=64 -> $12.80)
          - Tiro 8 (`step` 7, último tiro): NO dobla; usa la misma cantidad que el Tiro 7 (2^6=64 -> $12.80)
        """
        last_idx = max(0, (self.max_steps or 8) - 1)
        prev_idx = max(0, last_idx - 1)
        idx = min(int(step), last_idx)
        power = prev_idx if (idx == last_idx and last_idx >= 1) else idx
        return 2 ** power

    def get_bet_amount(self, attempt_index=0):
        step = self.persistent_step if self.persistent_martingale else attempt_index
        last_idx = max(0, (self.max_steps or 8) - 1)
        step = min(int(step), last_idx)

        units = self._units_for_step(step)
        total_amt = round(units * self.chip1_value, 2)
        return total_amt, step, units

    def calculate_chip_plan(self, units):
        """
        Descompone 'units' (múltiplos de $0.20) usando:
          - Moneda 3 (25x = $5.00) para bloques de 25 unidades
          - Moneda 2 (5x = $1.00) para bloques de 5 unidades
          - Moneda 1 (1x = $0.20) para el ajuste exacto
        Retorna: (c3_count, c2_count, c1_count, plan_str)
        """
        r3 = int(round(self.chip3_value / self.chip1_value)) or 25
        r2 = int(round(self.chip2_value / self.chip1_value)) or 5

        rem = int(units)
        c3 = rem // r3 if (rem >= r3 and self.chip3_coord != self.chip2_coord) else 0
        rem -= c3 * r3

        c2 = rem // r2 if (rem >= r2 and self.chip2_coord != self.chip1_coord) else 0
        rem -= c2 * r2

        c1 = rem

        parts = []
        if c3 > 0:
            parts.append(f"{c3}x {self.chip3_value:.2f} {self.currency}")
        if c2 > 0:
            parts.append(f"{c2}x {self.chip2_value:.2f} {self.currency}")
        if c1 > 0:
            parts.append(f"{c1}x {self.chip1_value:.2f} {self.currency}")
        plan_str = " + ".join(parts) if parts else f"{units}x {self.chip1_value:.2f} {self.currency}"

        return c3, c2, c1, plan_str

    # ──────────────────────────────────────────────────────────────
    # Ejecución de Apuesta Física en la Mesa Activa de la Señal
    # ──────────────────────────────────────────────────────────────
    def execute_bet(self, prediction, attempt_index=0, table_name=None, dynamic_coords=None):
        amt, step, units = self.get_bet_amount(attempt_index)
        c3_count, c2_count, c1_count, plan_str = self.calculate_chip_plan(units)
        total_clicks = c3_count + c2_count + c1_count

        pred_label = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        table_label = f"[{table_name}] " if table_name else ""
        shot_num = step + 1
        last_shot = self.max_steps or 8
        if shot_num == 1:
            mart_label = f"Tiro 1/{last_shot} (Apuesta Base)"
        elif shot_num == last_shot:
            mart_label = f"Tiro {shot_num}/{last_shot} (Recuperación — Igual al Tiro {last_shot - 1})"
        else:
            mart_label = f"Tiro {shot_num}/{last_shot} (Martingala #{step})"

        if not self.enabled:
            sim_msg = f"Simulación: {table_label}{amt:.2f} {self.currency} a {pred_label} [{plan_str}] ({mart_label})"
            logger.info(f"[SIMULACION] {sim_msg}")
            return True, sim_msg

        if self.is_paused_by_limits:
            return False, f"Apuestas detenidas: {self.pause_reason}"

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO ({self.session_profit:.2f} <= {self.stop_loss:.2f} {self.currency})"
            logger.warning(self.pause_reason)
            return False, self.pause_reason

        # Ubicar coordenadas exactas de la mesa activa en pantalla
        target_key = "player" if prediction == "P" else "banker"
        target_coord = None

        # Prioridad 1: Coordenadas dinámicas verificadas en vivo por el Scraper para esa mesa
        if dynamic_coords and target_key in dynamic_coords:
            target_coord = dynamic_coords[target_key]
        # Prioridad 2: Slots dinámicos guardados
        if not target_coord and table_name and table_name in self.dynamic_slots:
            target_coord = self.dynamic_slots[table_name].get(target_key)
        # Prioridad 3: Coordenadas calibradas en bet_coordinates.json
        if not target_coord and table_name and "tables" in self.coordinates and table_name in self.coordinates["tables"]:
            target_coord = self.coordinates["tables"][table_name].get(target_key)
        if not target_coord:
            target_coord = self.coordinates.get(target_key)

        if not target_coord:
            return False, f"Coordenada no encontrada para {target_key} ({table_name or 'general'})"

        raw_x, raw_y = target_coord["x"], target_coord["y"]
        scaled_x, scaled_y = self._scale_coord(raw_x, raw_y)

        logger.info(
            f"🚀 Apuesta REAL: {table_label}{amt:.2f} {self.currency} a {pred_label} "
            f"[{plan_str}] ({total_clicks} toques | {mart_label})"
        )

        # 1. Colocar fichas de Moneda 3 ($5.00 - 25x) si aplica (Martingalas 5..8)
        if c3_count > 0:
            self.select_chip(self.chip3_coord)
            time.sleep(0.05)
            if not self.multi_click(scaled_x, scaled_y, count=c3_count):
                return False, "Interrupción de clic (FailSafe)"
            time.sleep(0.05)

        # 2. Colocar fichas de Moneda 2 ($1.00 - 5x) si aplica (Martingalas 3..8)
        if c2_count > 0:
            self.select_chip(self.chip2_coord)
            time.sleep(0.05)
            if not self.multi_click(scaled_x, scaled_y, count=c2_count):
                return False, "Interrupción de clic (FailSafe)"
            time.sleep(0.05)

        # 3. Colocar fichas de Moneda 1 ($0.20 - Primera a la izquierda)
        if c1_count > 0:
            self.select_chip(self.chip1_coord)
            time.sleep(0.05)
            if not self.multi_click(scaled_x, scaled_y, count=c1_count):
                return False, "Interrupción de clic (FailSafe)"
            time.sleep(0.04)

        self.bets_placed_count += 1
        return True, f"✅ Apuesta de {amt:.2f} {self.currency} en {pred_label} [{plan_str}, {total_clicks} clics] ({mart_label})"

    # ──────────────────────────────────────────────────────────────
    # Resultados y Control Estricto de las 8 Martingalas
    # ──────────────────────────────────────────────────────────────
    def record_win(self, attempt_index=0):
        amt, step, _ = self.get_bet_amount(attempt_index)
        self.session_profit += amt
        net_cycle = amt - self.total_martingale_lost

        # Al ganar, resetear incondicionalmente a paso 0 ($0.20 primera moneda a la izquierda)
        self.persistent_step = 0
        self.total_martingale_lost = 0.0

        logger.info(
            f"🏆 WIN en tiro #{step + 1}! +{amt:.2f} {self.currency} (Neto ciclo: +{net_cycle:.2f} {self.currency}) | "
            f"Ganancia acumulada: +{self.session_profit:.2f} {self.currency} (Sin Stop-Profit: sigue jugando)"
        )

    def record_step_loss(self, attempt_index=0):
        amt, step, _ = self.get_bet_amount(attempt_index)
        self.session_profit -= amt
        self.total_martingale_lost += amt
        max_shots = self.max_steps or 8

        if self.persistent_martingale:
            self.persistent_step += 1
            if self.persistent_step >= max_shots:
                # Ya jugó los 8 tiros (incluyendo el Tiro 8 de recuperación igual al 7) y perdió el 8vo: SE DETIENE
                self.is_paused_by_limits = True
                self.pause_reason = (
                    f"🛑 SE COMPLETARON LOS {max_shots} TIROS SIN ACIERTO "
                    f"(Perdió el Tiro {max_shots} de recuperación de {amt:.2f} {self.currency}) — BOT DETENIDO AUTOMÁTICAMENTE"
                )
                logger.warning(self.pause_reason)
                return

            next_units = self._units_for_step(self.persistent_step)
            next_amt = round(next_units * self.chip1_value, 2)
            next_shot = self.persistent_step + 1
            rec_note = f" [Igual al Tiro {max_shots - 1} — Recuperación]" if next_shot == max_shots else ""
            logger.info(
                f"✗ Tiro #{step + 1}/{max_shots} fallido (-{amt:.2f} {self.currency}) | "
                f"Próximo tiro: Tiro #{next_shot}/{max_shots} ({next_amt:.2f} {self.currency}){rec_note} | "
                f"Balance sesión: {self.session_profit:.2f} {self.currency}"
            )
        else:
            if (attempt_index + 1) >= max_shots:
                self.is_paused_by_limits = True
                self.pause_reason = (
                    f"🛑 SE COMPLETARON LOS {max_shots} TIROS SIN ACIERTO — BOT DETENIDO AUTOMÁTICAMENTE"
                )
                logger.warning(self.pause_reason)
                return
            logger.info(f"✗ Intento fallido: -{amt:.2f} {self.currency} | Balance: {self.session_profit:.2f} {self.currency}")

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO ({self.session_profit:.2f} <= {self.stop_loss:.2f} {self.currency})"
            logger.warning(self.pause_reason)

    def record_table_finished_loss(self, attempt_index=7):
        if self.is_paused_by_limits:
            return
        max_shots = self.max_steps or 8
        if self.persistent_martingale:
            if self.persistent_step >= max_shots:
                self.is_paused_by_limits = True
                self.pause_reason = f"🛑 SE COMPLETARON LOS {max_shots} TIROS SIN ACIERTO — BOT DETENIDO"
                return
            next_units = self._units_for_step(self.persistent_step)
            next_amt = round(next_units * self.chip1_value, 2)
            logger.info(
                f"💔 Ciclo previo cerrado. Continúa en Tiro "
                f"#{self.persistent_step + 1}/{max_shots} ({next_amt:.2f} {self.currency})."
            )
        else:
            self.persistent_step = 0
            self.total_martingale_lost = 0.0

    def reset_martingale(self):
        """Resetea completamente la progresión a Tiro 1 ($0.20) tras ganar."""
        self.persistent_step = 0
        self.total_martingale_lost = 0.0
        logger.info("🔄 Progresión reseteada a Tiro 1 ($0.20 — Moneda 1 izquierda).")

    def get_status(self):
        max_shots = self.max_steps or 8
        calc_step = min(self.persistent_step, max_shots - 1)
        next_amt = round(self._units_for_step(calc_step) * self.chip1_value, 2)
        return {
            "enabled": self.enabled,
            "currency": self.currency,
            "chip1_value": self.chip1_value,
            "chip2_value": self.chip2_value,
            "chip3_value": self.chip3_value,
            "base_bet": self.base_bet,
            "persistent_martingale": self.persistent_martingale,
            "persistent_step": self.persistent_step,
            "max_shots": max_shots,
            "next_bet_amount": next_amt,
            "session_profit": round(self.session_profit, 2),
            "bets_placed": self.bets_placed_count,
            "is_paused": self.is_paused_by_limits,
            "pause_reason": self.pause_reason,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }
