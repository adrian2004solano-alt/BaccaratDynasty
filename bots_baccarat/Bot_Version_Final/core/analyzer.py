"""
core/analyzer.py  — v23 (Motor 4 Estrategias Maestras del Usuario y Análisis Profundo)
=====================================================================================
1. Filtro Estricto de Zapato:
   - 12 a 64 jugadas permitidas (menos de 12 o 65+ queda OMITIDA).
   - Rango de Oro Maestro: 18 a 48 jugadas.
2. Catálogo Exclusivo de 4 Estrategias del Usuario:
   - 1. DISRUPTIVA_4TEND_DISRUPTIVA : [D, T, T, T, T, D]
   - 2. TENDENCIA_3_DISR_2TEND      : [T, T, T, D, T, T]
   - 3. TENDENCIA_PURA_6            : [T, T, T, T, T, T]
   - 4. DISRUPTIVA_1_5TEND          : [D, T, T, T, T, T]
3. Modo Paciente / Análisis Profundo:
   - Cero precipitación en mesas indecisas.
   - Control de cadencia y enfriamiento por mesa.
"""

import time
import logging
import config
from core.ai_analyzer import GeminiBaccaratAnalyzer

logger = logging.getLogger("Analyzer")

GOLDEN_RANGE_MIN = 18
GOLDEN_RANGE_MAX = 48


class BaccaratAnalyzer:
    def __init__(self, min_delay=None, max_delay=None, strategy_mode=None, min_streak=None, min_confidence=None, stats_tracker=None):
        self.min_delay = min_delay if min_delay is not None else getattr(config, "MIN_SIGNAL_DELAY", 10)
        self.max_delay = max_delay if max_delay is not None else getattr(config, "MAX_SIGNAL_DELAY", 25)
        self.min_confidence = min_confidence if min_confidence is not None else getattr(config, "MIN_CONFIDENCE_THRESHOLD", 88)
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

    def analyze_history(self, table_name, history, total_hands=None, last_strategy=None, early_scores=None, strategy_usage=None, stats_tracker=None):
        """
        Evalúa la mesa evaluando y ponderando el catálogo dinámico de estrategias
        (Máximo 20% Mono-Color / 80% Combinaciones Mixtas con rotación activa).
        Retorna: (should_signal, sequence, confidence, probability, total_hands, strategy_name, reason)
        """
        if total_hands is None:
            total_hands = len(history)

        # ── REGLA 1: FILTRO DE ZAPATO (8 a 64 jugadas) ──
        if total_hands < 8 or total_hands >= 65:
            return False, [], 0, 0, total_hands, "NONE", f"Zapato fuera de rango (8 a 64, detectadas {total_hands})"

        # ── REGLA 2: FILTRO ANTI-EMPATE INMEDIATO ──
        if history and history[-1] == "T":
            return False, [], 0, 0, total_hands, "NONE", "Pausa por Empate"

        # ── ANÁLISIS MULTIESTRATEGIA ──
        try:
            tracker_to_use = stats_tracker or self.stats_tracker
            should, seq, prob, strat_name, reason = self.ai.analyze(
                table_name, history, last_strategy=last_strategy, early_scores=early_scores, strategy_usage=strategy_usage, stats_tracker=tracker_to_use
            )

            if not should:
                return False, [], 0, 0, total_hands, "NONE", reason

            # Bono de Rango de Oro (18 a 48 jugadas)
            if GOLDEN_RANGE_MIN <= total_hands <= GOLDEN_RANGE_MAX:
                prob = min(96, prob + 1)

            confidence = prob
            should_signal = should and (prob >= self.min_confidence)

            return should_signal, seq[:6], confidence, prob, total_hands, strat_name, reason

        except Exception as e:
            logger.warning(f"Error en análisis: {e}")
            return False, [], 0, 0, total_hands, "NONE", str(e)
