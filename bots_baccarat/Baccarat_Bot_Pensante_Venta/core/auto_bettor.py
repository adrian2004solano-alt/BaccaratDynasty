"""
core/auto_bettor.py — Bot Pensante
================================================================
Estrategia Predeterminada:
  - Base: $0.20 (1 clic) con Martingala Persistente cross-mesa.
  - Ventana A (bet_window=0): Apuesta en Tiros 1, 2, 3
  - Ventana B (bet_window=1): Apuesta en Tiros 2, 3, 4
  - Ciclo: A → LOSS → B → LOSS → A ...
  - Disparador de Modo Recuperación: Si el bot pierde 5 tiros consecutivos:
      * ¡DETIENE LA MARTINGALA NORMAL! (No dobla a $6.40 ni $12.80).
      * Pasa a MODO RECUPERACIÓN con su propia martingala de 4 tiros:
        - Tiro 1 rec: $0.40 (2 clics)
        - Tiro 2 rec: $0.80 (4 clics)
        - Tiro 3 rec: $1.60 (8 clics)
        - Tiro 4 rec: $3.20 (16 clics)
      * Si pierde los 4 tiros de recuperación: vuelve a jugar desde $0.40 (2 clics).
      * Si gana y aún no llega a la meta: vuelve al inicio de recuperación ($0.40).
      * Al alcanzar nuevamente la meta previa (100% recuperado): vuelve a $0.20 normal (1 clic).
  - Stop-Loss: -40.0 USDT / Stop-Profit: +50.0 USDT
"""

import os
import json
import time
import random
import logging
import pyautogui

logger = logging.getLogger("AutoBettor")

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.03

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

# Ventanas de tiros (índices de intento 0-5)
WINDOW_A = (0, 1, 2)       # Tiros 1, 2, 3
WINDOW_B = (1, 2, 3)       # Tiros 2, 3, 4
WINDOW_REC = (0, 1, 2, 3)  # Tiros 1, 2, 3, 4 en recuperación


class AutoBettor:
    def __init__(
        self,
        enabled=False,
        stop_loss=-40.0,
        take_profit=50.0,
        base_bet=0.20,
        base_chip=0.20,
        base_clicks=1,
        persistent_martingale=True,
        max_steps=10,
        game_mode=1,
    ):
        self.enabled               = enabled
        self.stop_loss             = stop_loss       # -40.0 USDT
        self.take_profit           = take_profit     # +50.0 USDT
        self.base_bet              = base_bet        # $0.20 primer tiro
        self.base_chip             = base_chip       # Ficha $0.20
        self.base_clicks           = base_clicks     # 1 clic para $0.20
        self.persistent_martingale = persistent_martingale
        self.max_steps             = max_steps
        self.game_mode             = game_mode

        # Estado persistente cross-mesa (modo normal)
        self.persistent_step       = 0      # 0=$0.20, 1=$0.40, 2=$0.80, 3=$1.60, 4=$3.20
        self.session_profit        = 0.0
        self.bets_placed_count     = 0
        self.is_paused_by_limits   = False
        self.pause_reason          = ""
        self.dynamic_slots         = {}

        # MODO RECUPERACIÓN tras 5 pérdidas consecutivas
        self.consecutive_real_losses = 0
        self.target_recovery_profit  = 0.0   # Meta de balance previa a recuperar
        self.recovery_mode           = False # True cuando está en modo recuperación
        self.recovery_debt           = 0.0   # Monto que falta para llegar a la meta
        self.recovery_clicks         = 2     # Base de recuperación ($0.40 = 2 clics)
        self.recovery_step           = 0     # Paso de martingala en recuperación (0-3)
        self.max_recovery_steps      = 4     # Máximo 4 tiros en martingala de recuperación
        self.loss_threshold          = 5     # 5 tiros consecutivos perdidos activan recuperación

        self.coordinates = self._load_coordinates()

    # ── Carga de coordenadas ──────────────────────────────────────────────
    def _load_coordinates(self):
        default_coords = {
            "screen_resolution": {"width": 1366, "height": 768},
            "chip_20": {"x": 500, "y": 744, "description": "Ficha $0.20 USD"},
            "player":  {"x": 104, "y": 228, "description": "Area Jugador"},
            "banker":  {"x": 245, "y": 228, "description": "Area Banca"},
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
        logger.info("Coordenadas recargadas.")

    def update_dynamic_slots(self, slot_bets_dict):
        if slot_bets_dict:
            self.dynamic_slots.update(slot_bets_dict)

    def _scale_coord(self, x, y):
        """Escala automáticamente las coordenadas si la resolución del monitor difiere de la referencia."""
        ref_w = self.coordinates.get("screen_resolution", {}).get("width", 1366)
        ref_h = self.coordinates.get("screen_resolution", {}).get("height", 768)
        try:
            cur_w, cur_h = pyautogui.size()
            if cur_w > 0 and ref_w > 0 and (cur_w != ref_w or cur_h != ref_h):
                fx = cur_w / ref_w
                fy = cur_h / ref_h
                return int(round(x * fx)), int(round(y * fy))
        except Exception:
            pass
        return int(x), int(y)

    # ── Clics humanizados ─────────────────────────────────────────────────
    def human_click(self, x, y, jitter=5):
        try:
            tx = x + random.randint(-jitter, jitter)
            ty = y + random.randint(-jitter, jitter)
            pyautogui.moveTo(tx, ty, duration=random.uniform(0.12, 0.22), tween=pyautogui.easeOutQuad)
            time.sleep(random.uniform(0.03, 0.06))
            pyautogui.click()
            time.sleep(random.uniform(0.04, 0.07))
            return True
        except pyautogui.FailSafeException:
            logger.warning("FailSafe activado. Clic cancelado.")
            return False
        except Exception as e:
            logger.error(f"Error en human_click: {e}")
            return False

    def multi_click(self, x, y, count=1):
        """Mueve el mouse una vez y ejecuta `count` clics."""
        try:
            tx = x + random.randint(-2, 2)
            ty = y + random.randint(-2, 2)
            pyautogui.moveTo(tx, ty, duration=random.uniform(0.10, 0.15), tween=pyautogui.easeOutQuad)
            time.sleep(0.04)
            pyautogui.click()
            for _ in range(count - 1):
                time.sleep(0.12)
                pyautogui.click()
            time.sleep(0.05)
            return True
        except pyautogui.FailSafeException:
            logger.warning("FailSafe activado. Clic cancelado.")
            return False
        except Exception as e:
            logger.error(f"Error en multi_click: {e}")
            return False

    # ── Selección de ficha ────────────────────────────────────────────────
    def _select_leftmost_chip(self):
        """Selecciona la ficha más a la izquierda ($0.20)."""
        candidates = []
        chips_dict = self.coordinates.get("chips", {})
        for label, coord in chips_dict.items():
            if isinstance(coord, dict) and "x" in coord and "y" in coord:
                candidates.append((coord["x"], coord["y"], label))
        for key in ("chip_02", "chip_20"):
            c = self.coordinates.get(key)
            if isinstance(c, dict) and "x" in c and "y" in c:
                candidates.append((c["x"], c["y"], key))
        if candidates:
            candidates.sort(key=lambda t: t[0])
            cx, cy, clabel = candidates[0]
            sx, sy = self._scale_coord(cx, cy)
            logger.info(f"Seleccionando ficha izquierda: '{clabel}' en ({sx}, {sy})")
            if self.enabled and not self.is_paused_by_limits:
                self.human_click(sx, sy, jitter=3)
        else:
            logger.warning("No se encontraron fichas configuradas.")

    def select_chip_base(self):
        self._select_leftmost_chip()

    # ── Lógica de ventana ─────────────────────────────────────────────────
    def is_bet_shot(self, attempt_index, bet_window):
        """
        Retorna True si el tiro debe tener apuesta real.
        En modo recuperación: permite hasta 4 tiros (tiros 1, 2, 3, 4).
        En modo normal:
          bet_window=0 → tiros 1, 2, 3
          bet_window=1 → tiros 2, 3, 4
        """
        if self.recovery_mode:
            return attempt_index in WINDOW_REC
        window = WINDOW_A if bet_window == 0 else WINDOW_B
        return attempt_index in window

    def get_window_label(self, bet_window):
        if self.recovery_mode:
            return f"RECUPERACIÓN (Paso {self.recovery_step + 1}/4 - Martingala desde $0.40)"
        return "Tiros 1-2-3" if bet_window == 0 else "Tiros 2-3-4"

    # ── Cálculo de apuesta ────────────────────────────────────────────────
    def get_current_bet(self):
        """
        Calcula monto y clics.
        En recuperación: martingala de 4 tiros desde $0.40:
          Paso 0: 2 clics = $0.40
          Paso 1: 4 clics = $0.80
          Paso 2: 8 clics = $1.60
          Paso 3: 16 clics = $3.20
        En normal (martingala desde $0.20):
          Paso 0: 1 clic = $0.20
          Paso 1: 2 clics = $0.40
          Paso 2: 4 clics = $0.80
          Paso 3: 8 clics = $1.60
          Paso 4: 16 clics = $3.20
        """
        if self.recovery_mode:
            step   = min(self.recovery_step, self.max_recovery_steps - 1)
            clicks = self.recovery_clicks * (2 ** step)
            amount = self.base_chip * clicks
            return amount, step, clicks

        step   = min(self.persistent_step, self.max_steps - 1)
        clicks = self.base_clicks * (2 ** step)
        amount = self.base_chip * clicks
        return amount, step, clicks

    def get_bet_amount(self, attempt_index=0):
        amount, step, _ = self.get_current_bet()
        return amount, step

    def is_in_recovery(self):
        return self.recovery_mode

    def get_recovery_info(self):
        return {
            "active": self.recovery_mode,
            "target_profit": round(self.target_recovery_profit, 2),
            "debt": round(self.recovery_debt, 2),
            "recovery_step": self.recovery_step,
            "max_recovery_steps": self.max_recovery_steps,
            "consecutive_losses": self.consecutive_real_losses,
        }

    # ── Ejecución de apuesta ──────────────────────────────────────────────
    def reset_for_new_table(self):
        if self.recovery_mode:
            amt, step, clicks = self.get_current_bet()
            logger.info(f"Nueva mesa. MODO RECUPERACIÓN activo | Meta: ${self.target_recovery_profit:.2f} (Faltan: ${self.recovery_debt:.2f}) | Próximo tiro: Paso {step + 1}/4 (${amt:.2f}, {clicks} clics)")
        else:
            logger.info(f"Nueva mesa. Martingala mantiene paso {self.persistent_step} (${self.get_current_bet()[0]:.2f}) | Pérdidas racha: {self.consecutive_real_losses}/5")

    def execute_bet(self, prediction, attempt_index=0, table_name=None, dynamic_coords=None):
        amount, step, clicks = self.get_current_bet()
        pred_label  = "JUGADOR" if prediction == "P" else "BANCA"
        table_label = f"[{table_name}] " if table_name else ""
        tiro_num    = attempt_index + 1
        mode_label  = f"[RECUPERACIÓN Paso {self.recovery_step + 1}/4] " if self.recovery_mode else ""

        if not self.enabled:
            logger.info(f"[SIMULACION] {mode_label}{table_label}Tiro#{tiro_num} | {clicks} clic(s) | ${amount:.2f} a {pred_label}")
            return True, f"Simulacion: Tiro#{tiro_num} ${amount:.2f} a {pred_label}"

        if self.is_paused_by_limits:
            return False, f"Pausado: {self.pause_reason}"

        if self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"STOP-LOSS (${self.session_profit:.2f} <= ${self.stop_loss:.2f})"
            logger.warning(self.pause_reason)
            return False, self.pause_reason

        if self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"TAKE-PROFIT (+${self.session_profit:.2f} >= +${self.take_profit:.2f})"
            logger.info(self.pause_reason)
            return False, self.pause_reason

        target_key   = "player" if prediction == "P" else "banker"
        target_coord = None
        if dynamic_coords and target_key in dynamic_coords:
            target_coord = dynamic_coords[target_key]
        elif table_name and table_name in self.dynamic_slots:
            target_coord = self.dynamic_slots[table_name].get(target_key)
        elif table_name and "tables" in self.coordinates and table_name in self.coordinates["tables"]:
            target_coord = self.coordinates["tables"][table_name].get(target_key)
        if not target_coord:
            target_coord = self.coordinates.get(target_key)

        if not target_coord:
            return False, f"Coordenada no encontrada para {target_key}"

        # Seleccionar ficha $0.20 (izquierda)
        self._select_leftmost_chip()
        time.sleep(0.25)

        if self.recovery_mode:
            logger.info(f"Apuesta REAL [RECUPERACIÓN Paso {self.recovery_step + 1}/4]: {table_label}Tiro#{tiro_num} | {clicks} clics | ${amount:.2f} a {pred_label} | Faltan ${self.recovery_debt:.2f} para meta ${self.target_recovery_profit:.2f}")
        else:
            logger.info(f"Apuesta REAL: {table_label}Tiro#{tiro_num} | {clicks} clics (paso {step}) | ${amount:.2f} a {pred_label} | Racha pérdidas: {self.consecutive_real_losses}/5")

        tx, ty = self._scale_coord(target_coord["x"], target_coord["y"])
        ok = self.multi_click(tx, ty, count=clicks)
        if not ok:
            return False, "Interrupcion de clic (FailSafe)"

        self.bets_placed_count += 1
        return True, f"OK {clicks} clics [Tiro#{tiro_num}] ${amount:.2f} a {pred_label}"

    # ── Registro de resultados ────────────────────────────────────────────
    def record_win(self, attempt_index=0):
        amount, step, clicks = self.get_current_bet()
        self.session_profit += amount

        if self.recovery_mode:
            self.recovery_debt = round(self.target_recovery_profit - self.session_profit, 2)
            logger.info(
                f"🎯 [RECUPERACIÓN] WIN +${amount:.2f} | Balance: ${self.session_profit:.2f} | "
                f"Meta: ${self.target_recovery_profit:.2f} (Faltan: ${max(self.recovery_debt, 0.0):.2f})"
            )
            # ¿Se alcanzó la meta que teníamos antes de empezar a perder?
            if self.session_profit >= self.target_recovery_profit - 0.001:
                self.recovery_mode = False
                self.consecutive_real_losses = 0
                self.recovery_debt = 0.0
                self.recovery_step = 0
                self.persistent_step = 0
                logger.info(
                    f"\n" + "=" * 70 + "\n"
                    f"  🎉 [RECUPERACIÓN COMPLETADA AL 100%] Balance restaurado a ${self.session_profit:.2f} USD!\n"
                    f"  ¡Toda la pérdida anterior ha sido recuperada!\n"
                    f"  Volviendo a apuestas normales de $0.20 (1 clic) y martingala rotante.\n"
                    f"=" * 70
                )
            else:
                # Si ganó pero aún falta para llegar a la meta, reinicia la martingala de recuperación a $0.40
                self.recovery_step = 0
                logger.info(f"   [RECUPERACIÓN] Acierto. Martingala reiniciada a $0.40 (2 clics) para seguir avanzando hacia la meta.")
        else:
            self.persistent_step = 0
            self.consecutive_real_losses = 0
            logger.info(f"🏆 WIN! +${amount:.2f} | Martingala reiniciada a ${self.base_bet:.2f} | Balance: ${self.session_profit:.2f}")

        if self.session_profit >= self.take_profit:
            self.is_paused_by_limits = True
            self.pause_reason = f"TAKE-PROFIT (+${self.session_profit:.2f} >= +${self.take_profit:.2f})"
            logger.info(self.pause_reason)

    def record_step_loss(self, attempt_index=0):
        amount, step, clicks = self.get_current_bet()

        if not self.recovery_mode:
            # Guardar balance previo si es el inicio de la racha perdedora
            if self.consecutive_real_losses == 0:
                self.target_recovery_profit = self.session_profit

            self.session_profit -= amount
            self.consecutive_real_losses += 1
            self.persistent_step += 1

            logger.info(f"✗ LOSS -${amount:.2f} | Racha pérdidas: {self.consecutive_real_losses}/5 | Balance: ${self.session_profit:.2f}")

            # DISPARADOR: Si pierde 5 tiros consecutivos -> MODO RECUPERACIÓN AUTOMÁTICO
            if self.consecutive_real_losses >= self.loss_threshold:
                self.recovery_mode = True
                self.recovery_step = 0  # Comienza en $0.40 (2 clics)
                self.persistent_step = 0
                self.recovery_debt = round(self.target_recovery_profit - self.session_profit, 2)
                logger.warning(
                    f"\n" + "=" * 70 + "\n"
                    f"  ⚠️ [5 TIROS CONSECUTIVOS PERDIDOS] ACTIVANDO MODO RECUPERACIÓN:\n"
                    f"  - Martingala normal DETENIDA (no habrá apuestas de $6.40 ni $12.80).\n"
                    f"  - Martingala de Recuperación activada: 4 tiros ($0.40 -> $0.80 -> $1.60 -> $3.20).\n"
                    f"  - Si pierde los 4 tiros de recuperación, vuelve a jugar desde $0.40 (2 clics).\n"
                    f"  - Balance previo a recuperar: ${self.target_recovery_profit:.2f} USD.\n"
                    f"  - Monto a recuperar: ${self.recovery_debt:.2f} USD.\n"
                    f"  - Al alcanzar nuevamente ${self.target_recovery_profit:.2f}, volverá a $0.20 normal.\n"
                    f"=" * 70
                )
        else:
            # En modo recuperación con martingala (hasta 4 tiros)
            self.session_profit -= amount
            self.recovery_debt = round(self.target_recovery_profit - self.session_profit, 2)
            self.recovery_step += 1

            if self.recovery_step >= self.max_recovery_steps:
                # Perdió los 4 tiros de recuperación -> Vuelve a jugar de $0.40
                logger.warning(
                    f"\n  ⚠️ [RECUPERACIÓN] Se perdieron los 4 tiros de recuperación.\n"
                    f"     Reiniciando ciclo de recuperación a $0.40 (2 clics). Deuda: ${self.recovery_debt:.2f}"
                )
                self.recovery_step = 0
            else:
                next_amt = (self.base_chip * self.recovery_clicks) * (2 ** self.recovery_step)
                logger.info(
                    f"✗ [RECUPERACIÓN] Fallo -${amount:.2f} | Paso {self.recovery_step}/4 -> Siguiente: ${next_amt:.2f} | "
                    f"Balance: ${self.session_profit:.2f} | Meta: ${self.target_recovery_profit:.2f}"
                )

        if self.session_profit <= self.stop_loss:
            self.is_paused_by_limits = True
            self.pause_reason = f"STOP-LOSS (${self.session_profit:.2f} <= ${self.stop_loss:.2f})"
            logger.warning(self.pause_reason)

    def activate_recovery_mode(self, total_lost=None):
        """Activa manualmente el modo recuperación si fuese necesario."""
        if self.recovery_mode:
            return
        self.recovery_mode = True
        self.recovery_step = 0
        self.persistent_step = 0
        if total_lost is not None:
            self.recovery_debt = round(total_lost, 2)
            self.target_recovery_profit = round(self.session_profit + total_lost, 2)
        else:
            self.recovery_debt = round(self.target_recovery_profit - self.session_profit, 2)
        logger.info(f"[RECUPERACIÓN ACTIVADA] Meta: ${self.target_recovery_profit:.2f} | Deuda: ${self.recovery_debt:.2f} | Martingala 4 tiros desde $0.40")

    def record_table_finished_loss(self, attempt_index=None):
        if self.recovery_mode:
            logger.info(f"Mesa finalizada en MODO RECUPERACIÓN. Meta: ${self.target_recovery_profit:.2f} (Faltan: ${self.recovery_debt:.2f}) | Paso recuperación: {self.recovery_step}/4")
        else:
            logger.info(f"Mesa finalizada. Racha pérdidas acumuladas: {self.consecutive_real_losses}/5. Paso martingala: {self.persistent_step}")

    def get_status(self):
        amount, step, clicks = self.get_current_bet()
        return {
            "enabled":                 self.enabled,
            "game_mode":               self.game_mode,
            "base_bet":                self.base_bet,
            "base_chip":               self.base_chip,
            "base_clicks":             self.base_clicks,
            "persistent_step":         self.persistent_step,
            "next_bet_amount":         round(amount, 2),
            "next_bet_clicks":         clicks,
            "session_profit":          round(self.session_profit, 2),
            "bets_placed":             self.bets_placed_count,
            "is_paused":               self.is_paused_by_limits,
            "pause_reason":            self.pause_reason,
            "stop_loss":               self.stop_loss,
            "take_profit":             self.take_profit,
            "recovery_mode":           self.recovery_mode,
            "recovery_step":           self.recovery_step,
            "max_recovery_steps":      self.max_recovery_steps,
            "target_recovery_profit":  round(self.target_recovery_profit, 2),
            "recovery_debt":           round(self.recovery_debt, 2),
            "consecutive_real_losses": self.consecutive_real_losses,
        }
