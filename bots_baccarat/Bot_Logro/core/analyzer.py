"""
core/analyzer.py — Analizador Maestro para "Bot Logro" (Tiro a Tiro y Cambio Dinámico de Mesa)
==============================================================================================
Evalúa todas las mesas configuradas en tiempo real buscando el patrón más limpio y confiable
para emitir 1 sola jugada concreta ('P' o 'B') con estimación dinámica de intentos (1, 2 o 3).
"""

import time
import logging
import config
from core.ai_analyzer import GeminiBaccaratAnalyzer

logger = logging.getLogger("Analyzer")

GOLDEN_RANGE_MIN = 16
GOLDEN_RANGE_MAX = 50


class BaccaratAnalyzer:
    def __init__(self, min_delay=None, max_delay=None, strategy_mode=None, min_streak=None, min_confidence=None, stats_tracker=None):
        self.min_delay = min_delay if min_delay is not None else getattr(config, "MIN_SIGNAL_DELAY", 0)
        self.max_delay = max_delay if max_delay is not None else getattr(config, "MAX_SIGNAL_DELAY", 6)
        self.min_confidence = min_confidence if min_confidence is not None else getattr(config, "MIN_CONFIDENCE_THRESHOLD", 89)
        self.recovery_min_confidence = getattr(config, "RECOVERY_MIN_CONFIDENCE", 86)
        self.last_signal_time = {}
        self.global_last_signal = 0
        self.stats_tracker = stats_tracker
        self.ai = GeminiBaccaratAnalyzer()

    def set_stats_tracker(self, tracker):
        self.stats_tracker = tracker

    def can_send_signal(self, table_name):
        now = time.time()
        if self.min_delay > 0 and self.global_last_signal > 0 and (now - self.global_last_signal < self.min_delay):
            return False, int(self.min_delay - (now - self.global_last_signal))
        last_table_time = self.last_signal_time.get(table_name, 0)
        if self.max_delay > 0 and last_table_time > 0 and (now - last_table_time < self.max_delay):
            return False, int(self.max_delay - (now - last_table_time))
        return True, 0

    def register_signal_sent(self, table_name):
        now = time.time()
        self.last_signal_time[table_name] = now
        self.global_last_signal = now

    def evaluate_table(self, table_name, history, total_hands=None, is_recovery=False, last_failed_pred=None, consult_ai=True):
        """
        Evalúa la mesa para Bot Logro (1 jugada concreta).
        Retorna dict con:
          should_signal, prediction ('P'/'B'), probability, score, planned_attempts (1..3),
          strategy_name, reason, total_hands
        """
        if total_hands is None:
            total_hands = len(history) if history else 0

        if total_hands < 8 or total_hands >= 65:
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": 0.0,
                "planned_attempts": 1,
                "strategy_name": "NONE",
                "reason": f"Zapato fuera de rango (8 a 64 manos, detectadas {total_hands})",
                "total_hands": total_hands,
            }

        res = self.ai.analyze_single_hand(
            table_name=table_name,
            history=history,
            is_recovery=is_recovery,
            last_failed_pred=last_failed_pred,
            consult_ai=consult_ai,
        )

        prob = int(res.get("probability", 0))
        score = float(res.get("score", 0.0))

        # Bono por Rango de Oro del zapato (16 a 50 manos: estructura madura y lejos del corte)
        if res.get("should_signal") and (GOLDEN_RANGE_MIN <= total_hands <= GOLDEN_RANGE_MAX):
            prob = min(97, prob + 1)
            score += 2.0

        threshold = self.recovery_min_confidence if is_recovery else self.min_confidence
        should_signal = bool(res.get("should_signal")) and (prob >= threshold) and (res.get("prediction") in ("P", "B"))

        return {
            "should_signal": should_signal,
            "prediction": res.get("prediction"),
            "probability": prob,
            "score": score,
            "planned_attempts": int(res.get("planned_attempts", 1)),
            "strategy_name": res.get("strategy_name", "NONE"),
            "reason": res.get("reason", ""),
            "total_hands": total_hands,
        }

    def analyze_history(self, table_name, history, total_hands=None, last_strategy=None, early_scores=None, strategy_usage=None, stats_tracker=None):
        """Método de compatibilidad."""
        ev = self.evaluate_table(table_name, history, total_hands=total_hands, is_recovery=False, consult_ai=True)
        if not ev["should_signal"]:
            return False, [], 0, 0, ev["total_hands"], "NONE", ev["reason"]
        pred = ev["prediction"]
        return True, [pred], ev["probability"], ev["probability"], ev["total_hands"], ev["strategy_name"], ev["reason"]
