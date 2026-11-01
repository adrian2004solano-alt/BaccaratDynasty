"""
core/analyzer.py  — v24 (Motor 4 Estrategias Maestras del Usuario y Análisis Profundo)
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
    def __init__(self, min_delay=None, max_delay=None, strategy_mode=None, min_streak=None, min_confidence=None):
        self.min_delay = min_delay or getattr(config, "MIN_SIGNAL_DELAY", 2)
        self.max_delay = max_delay or getattr(config, "MAX_SIGNAL_DELAY", 6)
        self.min_confidence = min_confidence or getattr(config, "MIN_CONFIDENCE_THRESHOLD", 88)
        self.last_signal_time = {}
        self.global_last_signal = 0
        self.ai = GeminiBaccaratAnalyzer()

    def can_send_signal(self, table_name):
        now = time.time()
        if self.global_last_signal > 0 and (now - self.global_last_signal < self.min_delay):
            return False, int(self.min_delay - (now - self.global_last_signal))
        last_table_time = self.last_signal_time.get(table_name, 0)
        if last_table_time > 0 and (now - last_table_time < self.max_delay):
            return False, int(self.max_delay - (now - last_table_time))
        return True, 0

    def register_signal_sent(self, table_name):
        now = time.time()
        self.last_signal_time[table_name] = now
        self.global_last_signal = now

    def analyze_history(self, table_name, history, total_hands=None, last_strategy=None, early_scores=None, strategy_usage=None):
        """
        Evalúa la mesa evaluando y ponderando las 4 estrategias exclusivas con rotación activa.
        Retorna: (should_signal, sequence, confidence, probability, total_hands, strategy_name, reason)
        """
        if total_hands is None:
            total_hands = len(history)

        # Verificación estricta del zapato (#N y Road)
        real_count = len([x for x in history if x in ("P", "B", "T")])
        effective_hands = max(total_hands, real_count)

        # ── REGLA 1: FILTRO DE ZAPATO ESTRICTO (10 a 64 jugadas) ──
        if effective_hands < 10 or effective_hands >= 65 or total_hands >= 65 or real_count >= 65:
            return False, [], 0, 0, effective_hands, "NONE", f"Zapato fuera de rango (jugadas: {effective_hands}, maximo permitido 64)"

        # ── REGLA 2: FILTRO ANTI-EMPATE INMEDIATO ──
        if history and history[-1] == "T":
            return False, [], 0, 0, total_hands, "NONE", "Pausa por Empate"

        # ── ANÁLISIS MULTIESTRATEGIA ──
        try:
            should, seq, prob, strat_name, reason = self.ai.analyze(
                table_name, history, last_strategy=last_strategy, early_scores=early_scores, strategy_usage=strategy_usage
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
