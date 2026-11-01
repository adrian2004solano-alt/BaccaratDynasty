"""
core/auto_bettor.py  —  Módulo de Apuestas Automáticas Multi-Divisa (USD / TRY)
=====================================================================================
1. Clics Hardware Anti-Detección (ctypes WinAPI):
   - Usa mouse_event LEFTDOWN + hold 65ms + LEFTUP via ctypes.windll.user32.
   - Movimiento suave con pyautogui + jitter natural para imitar comportamiento humano.
2. Lógica Inteligente de 2 Fichas (Moneda 1 + Moneda 2):
   - Moneda 1 (Base, Extremo Izquierdo): $0.20 USD o 4 TRY
   - Moneda 2 (Alta, Segunda a la Izquierda): $1.00 USD o 20 TRY (Equivale a 5x Base)
   - En tiros bajos (1, 2, 4 fichas): usa Moneda 1.
   - En tiros altos (8, 16, 32, 64, 128... fichas): usa Moneda 2 para bloques de 5x
     y completa el resto exacto con Moneda 1.
   - ¡Garantiza que la apuesta siempre se coloque en menos de 5 segundos!
3. Martingala Global Persistente:
   - Si una mesa completa termina en LOSS, la martingala continúa en la siguiente mesa.
   - Al ganar cualquier tiro, se resetea inmediatamente al monto base.
4. Soporte Multi-Divisa:
   - Modo Dólares (USD: $0.20 / $1.00)
   - Modo Lira Turca (TRY: 4 TRY / 20 TRY)
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
pyautogui.PAUSE = 0.03

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

_REF_W = 1434
_REF_H = 899

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP   = 0x0004


def _hardware_click(x, y, hold=0.065):
    """Clic hardware real via ctypes WinAPI para canvas HTML5."""
    try:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        time.sleep(0.04)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(hold)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.04)
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
        currency_symbol="$",
        stop_loss=None,
        take_profit=None,
        persistent_martingale=True,
        max_steps=50,
        currency_label=""
    ):
        self.enabled = enabled
        self.currency = currency.upper()
        self.chip1_value = float(chip1_value)
        self.chip2_value = float(chip2_value)
        self.currency_symbol = currency_symbol
        self.base_bet = self.chip1_value
        self.base_chip = self.chip1_value
        self.currency_label = currency_label or f"{self.currency} ({self.currency_symbol})"

        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.persistent_martingale = persistent_martingale
        self.max_steps = max_steps

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
            "chip_20": {"x": 532, "y": 866, "description": "Ficha 1 (Base)"},
            "chips": [
                {"value": 1.0, "x": 585, "y": 870, "description": "Ficha 2 (5x)"},
                {"value": 0.20, "x": 532, "y": 866, "description": "Ficha 1 (Base)"}
            ]
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
        Identifica físicamente la Moneda 1 (extrema izquierda) y la Moneda 2 (segunda a la izquierda)
        ordenando las fichas disponibles por coordenada X ascendente.
        """
        raw_chips = self.coordinates.get("chips", [])
        valid_chips = [c for c in raw_chips if isinstance(c, dict) and "x" in c and "y" in c]

        if valid_chips:
            # Ordenar por X ascendente (de izquierda a derecha en la barra)
            sorted_chips = sorted(valid_chips, key=lambda c: c["x"])
            self.chip1_coord = sorted_chips[0]
            self.chip2_coord = sorted_chips[1] if len(sorted_chips) > 1 else sorted_chips[0]
        else:
            # Fallback seguro a chip_base / chip_20
            fallback = self.coordinates.get("chip_base") or self.coordinates.get("chip_20") or {"x": 532, "y": 866}
            self.chip1_coord = fallback
            self.chip2_coord = {"x": fallback["x"] + 53, "y": fallback["y"]}

        logger.info(
            f"Fichas configuradas: Moneda 1 ({self.chip1_value} {self.currency}) en ({self.chip1_coord['x']}, {self.chip1_coord['y']}) | "
            f"Moneda 2 ({self.chip2_value} {self.currency}) en ({self.chip2_coord['x']}, {self.chip2_coord['y']})"
        )

    def reload_coordinates(self):
        self.coordinates = self._load_coordinates()
        self._resolve_chip_coordinates()
        logger.info("Coordenadas de apuestas recargadas.")

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

    def human_click(self, x, y, jitter=3):
        try:
            target_x = x + random.randint(-jitter, jitter)
            target_y = y + random.randint(-jitter, jitter)
            duration = random.uniform(0.10, 0.18)
            pyautogui.moveTo(target_x, target_y, duration=duration, tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.02, 0.04))
            ok = _hardware_click(target_x, target_y, hold=random.uniform(0.060, 0.075))
            time.sleep(random.uniform(0.03, 0.05))
            return ok
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI FailSafe activado (mouse en esquina). Clic cancelado.")
            return False
        except Exception as e:
            logger.error(f"Error en human_click: {e}")
            return False

    def multi_click(self, x, y, count=1):
        if count <= 0:
            return True
        try:
            target_x = x + random.randint(-3, 3)
            target_y = y + random.randint(-3, 3)
            duration = random.uniform(0.10, 0.18)
            pyautogui.moveTo(target_x, target_y, duration=duration, tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.02, 0.04))

            # Primer clic
            _hardware_click(target_x, target_y, hold=random.uniform(0.060, 0.070))

            for _ in range(count - 1):
                time.sleep(random.uniform(0.08, 0.12))
                adj_x = target_x + random.randint(-1, 1)
                adj_y = target_y + random.randint(-1, 1)
                _hardware_click(adj_x, adj_y, hold=random.uniform(0.060, 0.070))

            time.sleep(random.uniform(0.03, 0.05))
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
            pyautogui.moveTo(jx, jy, duration=random.uniform(0.08, 0.14), tween=pyautogui.easeOutQuad)
            time.sleep(0.03)
            _hardware_click(jx, jy, hold=0.065)
            time.sleep(0.05)
            return True
        except Exception as e:
            logger.error(f"Error seleccionando ficha: {e}")
            return False

    def select_chip_base(self):
        """Selecciona la Moneda 1 (extremo izquierdo)."""
        self.select_chip(self.chip1_coord)

    # ──────────────────────────────────────────────────────────────
    # Cálculo inteligente de apuestas (Moneda 1 + Moneda 2)
    # ──────────────────────────────────────────────────────────────
    def get_bet_amount(self, attempt_index=0):
        step = self.persistent_step if self.persistent_martingale else attempt_index
        if self.max_steps is not None and self.max_steps > 0:
            step = min(step, self.max_steps)

        units = 2 ** step
        total_amt = round(units * self.chip1_value, 2)
        return total_amt, step, units

    def calculate_chip_plan(self, units):
        """
        Descompone 'units' (fichas base) en Moneda 2 (5x) y Moneda 1 (1x).
        Retorna: (count_chip2, count_chip1, plan_str)
        """
        ratio = int(round(self.chip2_value / self.chip1_value))
        if ratio <= 0:
            ratio = 5

        if units < ratio:
            c2 = 0
            c1 = units
        else:
            c2 = units // ratio
            c1 = units % ratio

        parts = []
        if c2 > 0:
            parts.append(f"{c2}x {self.chip2_value:.2f} {self.currency}")
        if c1 > 0:
            parts.append(f"{c1}x {self.chip1_value:.2f} {self.currency}")
        plan_str = " + ".join(parts) if parts else f"{units}x {self.chip1_value:.2f} {self.currency}"

        return c2, c1, plan_str

    # ──────────────────────────────────────────────────────────────
    # Ejecución de Apuesta
    # ──────────────────────────────────────────────────────────────
    def execute_bet(self, prediction, attempt_index=0, table_name=None, dynamic_coords=None):
        amt, step, units = self.get_bet_amount(attempt_index)
        c2_count, c1_count, plan_str = self.calculate_chip_plan(units)
        total_clicks = c2_count + c1_count

        pred_label = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        table_label = f"[{table_name}] " if table_name else ""
        step_label = f"(Paso Martingala #{step+1})" if self.persistent_martingale else f"(Tiro #{attempt_index+1})"

        if not self.enabled:
            sim_msg = f"Simulación: {table_label}{amt:.2f} {self.currency} a {pred_label} [{plan_str}] {step_label}"
            logger.info(f"[SIMULACION] {sim_msg}")
            return True, sim_msg

        if self.is_paused_by_limits:
            return False, f"Apuestas en pausa: {self.pause_reason}"

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO ({self.session_profit:.2f} <= {self.stop_loss:.2f} {self.currency})"
            logger.warning(self.pause_reason)
            return False, self.pause_reason

        if self.take_profit is not None and self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"🎉 TAKE-PROFIT ALCANZADO (+{self.session_profit:.2f} >= +{self.take_profit:.2f} {self.currency})"
            logger.info(self.pause_reason)
            return False, self.pause_reason

        # Ubicar coordenadas de la mesa
        target_key = "player" if prediction == "P" else "banker"
        target_coord = None

        # Prioridad 1: Coordenadas fijas calibradas de la mesa
        if table_name and "tables" in self.coordinates and table_name in self.coordinates["tables"]:
            target_coord = self.coordinates["tables"][table_name].get(target_key)
        # Prioridad 2: Coordenadas dinámicas de slots si aplica
        if not target_coord and dynamic_coords and target_key in dynamic_coords:
            target_coord = dynamic_coords[target_key]
        if not target_coord and table_name and table_name in self.dynamic_slots:
            target_coord = self.dynamic_slots[table_name].get(target_key)
        if not target_coord:
            target_coord = self.coordinates.get(target_key)

        if not target_coord:
            return False, f"Coordenada no encontrada para {target_key} ({table_name or 'general'})"

        raw_x, raw_y = target_coord["x"], target_coord["y"]
        scaled_x, scaled_y = self._scale_coord(raw_x, raw_y)

        logger.info(
            f"🚀 Apuesta REAL: {table_label}{amt:.2f} {self.currency} a {pred_label} "
            f"[{plan_str}] ({total_clicks} toques en total)"
        )

        # 1. Colocar fichas de Moneda 2 (Ficha de mayor valor) si corresponde
        if c2_count > 0:
            self.select_chip(self.chip2_coord)
            time.sleep(0.06)
            ok = self.multi_click(scaled_x, scaled_y, count=c2_count)
            if not ok:
                return False, "Interrupción de clic (FailSafe)"
            time.sleep(0.06)

        # 2. Completar con Moneda 1 (Ficha base) hasta la suma exacta
        if c1_count > 0:
            self.select_chip(self.chip1_coord)
            time.sleep(0.06)
            ok = self.multi_click(scaled_x, scaled_y, count=c1_count)
            if not ok:
                return False, "Interrupción de clic (FailSafe)"
            time.sleep(0.05)

        self.bets_placed_count += 1
        return True, f"✅ Apuesta de {amt:.2f} {self.currency} en {pred_label} [{plan_str}, {total_clicks} clics] {step_label}"

    # ──────────────────────────────────────────────────────────────
    # Resultados y Martingala
    # ──────────────────────────────────────────────────────────────
    def record_win(self, attempt_index=0):
        amt, step, _ = self.get_bet_amount(attempt_index)
        self.session_profit += amt
        net_cycle = amt - self.total_martingale_lost

        # Reset total incondicional tras WIN
        self.persistent_step = 0
        self.total_martingale_lost = 0.0

        logger.info(
            f"🏆 WIN en paso {step+1}! +{amt:.2f} {self.currency} (Neto ciclo: +{net_cycle:.2f} {self.currency}) | "
            f"Balance total: {self.session_profit:.2f} {self.currency}"
        )

        if self.take_profit is not None and self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"🎉 TAKE-PROFIT ALCANZADO (+{self.session_profit:.2f} {self.currency})"
            logger.info(self.pause_reason)

    def record_step_loss(self, attempt_index=0):
        amt, step, _ = self.get_bet_amount(attempt_index)
        self.session_profit -= amt
        self.total_martingale_lost += amt

        if self.persistent_martingale:
            self.persistent_step += 1
            calc_step = min(self.persistent_step, self.max_steps) if self.max_steps else self.persistent_step
            next_amt = round((2 ** calc_step) * self.chip1_value, 2)
            logger.info(
                f"✗ Intento {attempt_index+1} fallido: -{amt:.2f} {self.currency} | "
                f"Próximo tiro: {next_amt:.2f} {self.currency} (paso {self.persistent_step+1}) | "
                f"Balance: {self.session_profit:.2f} {self.currency}"
            )
        else:
            logger.info(f"✗ Intento fallido: -{amt:.2f} {self.currency} | Balance: {self.session_profit:.2f} {self.currency}")

        if self.stop_loss is not None and self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"🛑 STOP-LOSS ALCANZADO ({self.session_profit:.2f} <= {self.stop_loss:.2f} {self.currency})"
            logger.warning(self.pause_reason)

    def record_table_finished_loss(self, attempt_index=5):
        if self.persistent_martingale:
            calc_step = min(self.persistent_step, self.max_steps) if self.max_steps else self.persistent_step
            next_amt = round((2 ** calc_step) * self.chip1_value, 2)
            logger.info(
                f"💔 Mesa en LOSS. MARTINGALA PERSISTENTE: la siguiente mesa inicia en paso "
                f"{self.persistent_step+1} ({next_amt:.2f} {self.currency})."
            )
        else:
            self.persistent_step = 0
            self.total_martingale_lost = 0.0

    def reset_martingale(self):
        """Resetea completamente la martingala a paso 0 tras ganar."""
        self.persistent_step = 0
        self.total_martingale_lost = 0.0
        logger.info("🔄 Martingala reseteada a paso 0 (inicio limpio).")

    def get_status(self):
        calc_step = min(self.persistent_step, self.max_steps) if self.max_steps else self.persistent_step
        next_amt = round((2 ** calc_step) * self.chip1_value, 2)
        return {
            "enabled": self.enabled,
            "currency": self.currency,
            "chip1_value": self.chip1_value,
            "chip2_value": self.chip2_value,
            "base_bet": self.base_bet,
            "persistent_martingale": self.persistent_martingale,
            "persistent_step": self.persistent_step,
            "next_bet_amount": next_amt,
            "session_profit": round(self.session_profit, 2),
            "bets_placed": self.bets_placed_count,
            "is_paused": self.is_paused_by_limits,
            "pause_reason": self.pause_reason,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }
