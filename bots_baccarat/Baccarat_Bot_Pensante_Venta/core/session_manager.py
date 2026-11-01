"""
core/session_manager.py
=======================
Gestiona la sesión activa de señales y apuestas de Baccarat.
Soporta:
1. DelayedCrossTableSession:
   - Filtro de Seguridad Fantasma (Espera 2 fallos virtuales antes de entrar).
   - Apuestas Reales en Mesa 1 (Tiros 3, 4, 5, 6 con ficha base de $0.20).
   - Migración Cruzada a Mesa 2 (Tiros 1 y 2 con $3.20 y $6.40 si Mesa 1 no resuelve).
   - Reseteo automático a $0.20 tras cualquier victoria.
   - Manejo transparente de empates ('T').
2. BaccaratSession: Sesión clásica estándar (backward compatibility).
"""

import time
import logging

logger = logging.getLogger("Session")


class SessionState:
    IDLE         = "idle"
    GHOST        = "ghost"
    ACTIVE       = "active"
    NEED_TABLE_2 = "need_table_2"
    WIN          = "win"
    LOSS         = "loss"
    GHOST_RESET  = "ghost_reset"


class DelayedCrossTableSession:
    """
    Sesión con Entrada Retardada (2 Tiros Fantasma) y Martingala Cruzada entre 2 Mesas.
    """
    MARTINGALE_AMOUNTS = [0.20, 0.40, 0.80, 1.60, 3.20, 6.40]

    def __init__(self, table_1, sequence_1, strategy, confidence, reason="", ghost_max=2):
        self.table_1         = table_1
        self.sequence_1      = sequence_1           # 6 predicciones generadas por IA
        self.strategy        = strategy
        self.confidence      = confidence
        self.reason          = reason
        self.ghost_max       = ghost_max            # Por defecto 2 tiros virtuales

        self.ghost_attempt   = 0                    # 0, 1
        self.real_attempt    = 0                    # 0..5 (0: $0.20 ... 5: $6.40)
        self.table_1_attempt = 0                    # 0..3 (Tiros 3..6 de Mesa 1)
        self.table_2_attempt = 0                    # 0..1 (Tiros 1..2 de Mesa 2)

        self.table_2         = None
        self.sequence_2      = None
        self.strategy_2      = None

        self.phase           = "GHOST"              # GHOST, REAL_T1, NEED_TABLE_2, REAL_T2, FINISHED
        self.state           = "ACTIVE"             # ACTIVE, WIN, LOSS, GHOST_RESET
        self.total_invested  = 0.0
        self.net_profit      = 0.0
        self.start_time      = time.time()
        self.attempts_log    = []

    @property
    def current_table(self):
        return self.table_2 if self.phase == "REAL_T2" else self.table_1

    def is_finished(self):
        return self.phase == "FINISHED" or self.state in ("WIN", "LOSS", "GHOST_RESET")

    def is_ghost(self):
        return self.phase == "GHOST"

    def is_real_money(self):
        return self.phase in ("REAL_T1", "REAL_T2")

    def get_current_action(self):
        """Retorna la acción actual (mesa, predicción, importe en $, si es dinero real)."""
        if self.phase == "GHOST":
            pred = self.sequence_1[self.ghost_attempt] if self.ghost_attempt < len(self.sequence_1) else "P"
            return {
                "phase": "GHOST",
                "table": self.table_1,
                "is_real_money": False,
                "amount": 0.0,
                "shot_label": f"Tiro Fantasma {self.ghost_attempt + 1}/{self.ghost_max}",
                "virtual_shot_num": self.ghost_attempt + 1,
                "prediction": pred,
                "real_attempt_index": None,
                "table_shot_num": self.ghost_attempt + 1
            }

        elif self.phase == "REAL_T1":
            seq_idx = self.ghost_max + self.table_1_attempt
            pred = self.sequence_1[seq_idx] if seq_idx < len(self.sequence_1) else "P"
            amt = self.MARTINGALE_AMOUNTS[min(self.real_attempt, len(self.MARTINGALE_AMOUNTS)-1)]
            return {
                "phase": "REAL_T1",
                "table": self.table_1,
                "is_real_money": True,
                "amount": amt,
                "shot_label": f"Mesa 1 [{self.table_1}] - Tiro {self.table_1_attempt + 3} (Real #{self.real_attempt + 1})",
                "virtual_shot_num": None,
                "prediction": pred,
                "real_attempt_index": self.real_attempt,
                "table_shot_num": self.table_1_attempt + 3
            }

        elif self.phase == "REAL_T2":
            pred = self.sequence_2[self.table_2_attempt] if (self.sequence_2 and self.table_2_attempt < len(self.sequence_2)) else "P"
            amt = self.MARTINGALE_AMOUNTS[min(self.real_attempt, len(self.MARTINGALE_AMOUNTS)-1)]
            return {
                "phase": "REAL_T2",
                "table": self.table_2,
                "is_real_money": True,
                "amount": amt,
                "shot_label": f"Mesa 2 [{self.table_2}] - Tiro {self.table_2_attempt + 1} (Real #{self.real_attempt + 1})",
                "virtual_shot_num": None,
                "prediction": pred,
                "real_attempt_index": self.real_attempt,
                "table_shot_num": self.table_2_attempt + 1
            }

        return None

    def set_table_2(self, table_2, sequence_2, strategy_2=None):
        """Configura la Mesa 2 para los tiros de recuperación del Martingala ($3.20 y $6.40)."""
        self.table_2 = table_2
        self.sequence_2 = sequence_2
        self.strategy_2 = strategy_2 or self.strategy
        self.table_2_attempt = 0
        self.phase = "REAL_T2"
        logger.info(f"🔄 Migración completada a Mesa 2 [{table_2}]. Secuencia asignada: {sequence_2[:2]}")

    def register_result(self, actual_result):
        """
        Registra el resultado de la jugada actual.
        Retorna:
          ('TIE', 0.0)
          ('GHOST_WIN', 0.0)
          ('GHOST_CONTINUE', 0.0)
          ('TRIGGER_REAL_ENTRY', 0.0)
          ('REAL_WIN_N', 0.20)
          ('REAL_CONTINUE', 0.0)
          ('NEED_TABLE_2', 0.0)
          ('REAL_LOSS', -12.60)
        """
        if actual_result == "T":
            logger.info(f"[{self.current_table}] 🟢 EMPATE — La apuesta se mantiene intacta.")
            return "TIE", 0.0

        action = self.get_current_action()
        if not action:
            return "FINISHED", 0.0

        pred = action["prediction"]
        won = (actual_result == pred)
        phase = action["phase"]

        self.attempts_log.append({
            "phase": phase,
            "table": action["table"],
            "prediction": pred,
            "actual": actual_result,
            "won": won,
            "amount": action["amount"],
            "real_attempt": action["real_attempt_index"]
        })

        # ── 1. FASE FANTASMA (VIRTUAL) ──
        if phase == "GHOST":
            if won:
                self.state = "GHOST_RESET"
                self.phase = "FINISHED"
                logger.info(f"[{self.table_1}] 🎯 Victoria virtual en {action['shot_label']} ({pred} == {actual_result}). Capital intacto.")
                return "GHOST_WIN", 0.0
            else:
                self.ghost_attempt += 1
                if self.ghost_attempt >= self.ghost_max:
                    # ¡Filtro de seguridad superado! 2 fallos virtuales -> Activar entrada con dinero real
                    self.phase = "REAL_T1"
                    logger.info(f"[{self.table_1}] 🚨 ¡2 FALLOS VIRTUALES SUPERADOS! Activando apuestas reales en Tiro 3 con $0.20.")
                    return "TRIGGER_REAL_ENTRY", 0.0
                logger.info(f"[{self.table_1}] ✗ Fallo virtual {self.ghost_attempt}/{self.ghost_max}. Continuando monitoreo.")
                return "GHOST_CONTINUE", 0.0

        # ── 2. FASE DINERO REAL EN MESA 1 ──
        elif phase == "REAL_T1":
            amt = action["amount"]
            self.total_invested += amt
            if won:
                self.state = "WIN"
                self.phase = "FINISHED"
                self.net_profit = 0.20
                real_num = self.real_attempt + 1
                logger.info(f"[{self.table_1}] 🏆 WIN en Real #{real_num} (Tiro {self.table_1_attempt + 3}). Beneficio neto: +$0.20")
                return f"REAL_WIN_{real_num}", self.net_profit
            else:
                self.table_1_attempt += 1
                self.real_attempt += 1
                if self.table_1_attempt >= 4:
                    # Tiros 3, 4, 5, 6 de Mesa 1 agotados -> Pedir Mesa 2 para los 2 tiros finales
                    self.phase = "NEED_TABLE_2"
                    logger.info(f"[{self.table_1}] ⚠️ Tiros 3..6 agotados en Mesa 1. Requiere Mesa 2 para Tiros Reales #5 y #6.")
                    return "NEED_TABLE_2", 0.0
                return "REAL_CONTINUE", 0.0

        # ── 3. FASE DINERO REAL EN MESA 2 (RECUPERACIÓN) ──
        elif phase == "REAL_T2":
            amt = action["amount"]
            self.total_invested += amt
            if won:
                self.state = "WIN"
                self.phase = "FINISHED"
                self.net_profit = 0.20
                real_num = self.real_attempt + 1
                logger.info(f"[{self.table_2}] 🏆 WIN en Real #{real_num} (Mesa 2 Tiro {self.table_2_attempt + 1}). Beneficio neto: +$0.20")
                return f"REAL_WIN_{real_num}", self.net_profit
            else:
                self.table_2_attempt += 1
                self.real_attempt += 1
                if self.real_attempt >= 6:
                    self.state = "LOSS"
                    self.phase = "FINISHED"
                    self.net_profit = -self.total_invested
                    logger.info(f"[{self.table_2}] ❌ LOSS — Agotados los 6 intentos de Martingala. Pérdida: -${self.total_invested:.2f}")
                    return "REAL_LOSS", self.net_profit
                return "REAL_CONTINUE", 0.0

        return "CONTINUE", 0.0

    def elapsed(self):
        return time.time() - self.start_time

    def summary(self):
        return {
            "table_1": self.table_1,
            "table_2": self.table_2,
            "phase": self.phase,
            "state": self.state,
            "total_invested": self.total_invested,
            "net_profit": self.net_profit,
            "real_attempts_used": self.real_attempt,
            "log": self.attempts_log
        }


class BaccaratSession:
    """
    Sesion estandar de 6 tiros por mesa.

    El martingale persistente entre mesas es manejado completamente por
    AutoBettor.persistent_step. Cuando esta sesion termina en LOSS, el loop
    principal encontrara la siguiente mesa natural y auto_bettor.get_bet_amount()
    retornara automaticamente el paso acumulado correcto (ej: si perdio 6 tiros,
    la siguiente mesa empieza en persistent_step=6 = 64 clics).
    """
    MAX_ATTEMPTS = 6

    def __init__(self, table_name, sequence, strategy, confidence, reason=""):
        self.table_name      = table_name
        self.sequence        = sequence
        self.strategy        = strategy
        self.confidence      = confidence
        self.reason          = reason
        self.current_attempt = 0
        self.state           = SessionState.ACTIVE
        self.start_time      = time.time()
        self.attempts_log    = []

    @property
    def current_table(self):
        return self.table_name

    @property
    def attempt_number(self):
        return self.current_attempt + 1

    @property
    def current_prediction(self):
        if self.current_attempt < len(self.sequence):
            return self.sequence[self.current_attempt]
        return None

    def register_result(self, actual_result):
        if actual_result == "T":
            logger.info(f"[{self.table_name}] Empate — intento {self.attempt_number} mantiene")
            return "tie"

        prediction = self.current_prediction
        won        = (actual_result == prediction)
        n          = self.attempt_number

        self.attempts_log.append({
            "attempt":    n,
            "prediction": prediction,
            "actual":     actual_result,
            "won":        won,
        })

        if won:
            self.state = SessionState.WIN
            return f"win_{n}"
        else:
            self.current_attempt += 1
            if self.current_attempt >= self.MAX_ATTEMPTS:
                self.state = SessionState.LOSS
                return "loss"
            return "continue"

    def is_finished(self):
        return self.state in (SessionState.WIN, SessionState.LOSS)

    def elapsed(self):
        return time.time() - self.start_time

    def summary(self):
        return {
            "table":      self.table_name,
            "state":      self.state,
            "attempts":   self.attempt_number,
            "strategy":   self.strategy,
            "confidence": self.confidence,
            "log":        self.attempts_log,
        }

