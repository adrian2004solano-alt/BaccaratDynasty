# -*- coding: utf-8 -*-
"""
core/thinking_engine.py — Motor Pensante con Ghost Betting y Calidad de Zapato (0-100)
=====================================================================================
1. Evalúa la calidad del zapato (0 a 100) mediante carreteras derivadas y madurez.
2. Aplica estrategias fijas de alta probabilidad (Doble Pareja 2-2-2, Tendencia Fuerte, Ruptura).
3. "Ghost Betting" (Entradas Francotirador): Espera 1 o 2 fallos virtuales antes de arriesgar dinero real.
4. Martingala Corta y Asimétrica: Máximo 3 intentos con dinero real (arriesga máx ~$1.40 por racha mala).
"""

import logging
from core.baccarat_roads import calculate_all_roads
import config

logger = logging.getLogger("ThinkingEngine")


class ThinkingEngine:
    def __init__(self, sniper_level=None, min_table_score=None):
        self.sniper_level = sniper_level if sniper_level is not None else getattr(config, "SNIPER_LEVEL", 1)
        self.min_table_score = min_table_score if min_table_score is not None else getattr(config, "MIN_TABLE_SCORE", 75)

        # Seguimiento de secuencias activas por mesa
        # { table_name: { "sequence": [...], "current_step": 0, "ghost_steps_done": 0, "real_steps_done": 0, "status": "GHOST"|"REAL" } }
        self.active_sequences = {}

    def evaluate_table_quality(self, history):
        """
        Calcula un puntaje objetivo de calidad de mesa (0 a 100).
        - 0-59: Mesa deficiente o ruidosa (No operar).
        - 60-74: Mesa aceptable pero con riesgo.
        - 75-100: Mesa de alta precisión (Apta para Francotirador).
        """
        if not history or len(history) < 10:
            return 0, "Menos de 10 jugadas (inmaduro)"
        if len(history) >= 65:
            return 0, "Zapato agotado (>= 65 jugadas)"

        clean = [h for h in history if h in ("P", "B")]
        n = len(clean)
        if n < 10:
            return 0, "Menos de 10 manos limpias"

        score = 0
        reasons = []

        # 1. Madurez del Zapato (Máximo 35 pts)
        # La 'Zona Dorada' está entre las manos 15 y 52
        if 16 <= n <= 50:
            score += 35
            reasons.append(f"Mano #{n} en Zona Dorada (+35)")
        elif 10 <= n <= 15:
            score += 20
            reasons.append(f"Mano #{n} inicio de zapato (+20)")
        else:
            score += 15
            reasons.append(f"Mano #{n} zapato maduro (+15)")

        # 2. Análisis de Carreteras Derivadas (Big Eye, Small Road, Cockroach) (Máximo 35 pts)
        roads = calculate_all_roads(clean)
        consensus = roads.get("consensus_next")
        strength = roads.get("consensus_strength", 0.0)

        if strength >= 0.70:
            score += 35
            reasons.append(f"Consenso Derivadas Fuerte {int(strength*100)}% ({consensus}) (+35)")
        elif strength >= 0.50:
            score += 20
            reasons.append(f"Consenso Derivadas Moderado {int(strength*100)}% (+20)")
        else:
            score += 5
            reasons.append("Derivadas mixtas (+5)")

        # 3. Claridad de Patrón (Doble Pareja o Racha Limpia) (Máximo 30 pts)
        last_color = clean[-1]
        streak = 1
        for i in range(len(clean) - 2, -1, -1):
            if clean[i] == last_color:
                streak += 1
            else:
                break

        # Detectar patrón Doble Pareja (2P - 2B - 2P - 2B) en las últimas 8 manos
        recent8 = clean[-8:] if len(clean) >= 8 else []
        is_double_pairs = False
        if len(recent8) == 8:
            blocks = []
            cur_b = 1
            for i in range(1, len(recent8)):
                if recent8[i] == recent8[i-1]:
                    cur_b += 1
                else:
                    blocks.append(cur_b)
                    cur_b = 1
            blocks.append(cur_b)
            if all(b == 2 for b in blocks) or blocks.count(2) >= 3:
                is_double_pairs = True

        if is_double_pairs:
            score += 30
            reasons.append("Patrón Doble Pareja 2-2 confirmado (+30)")
        elif streak in (2, 3):
            score += 25
            reasons.append(f"Racha de {streak} con soporte de tendencia (+25)")
        elif streak >= 5:
            score += 20
            reasons.append(f"Racha extendida ({streak}) candidata a corte (+20)")
        else:
            score += 10
            reasons.append("Alternancia común (+10)")

        total_score = min(100, score)
        return total_score, " | ".join(reasons)

    def analyze_and_plan(self, table_name, history):
        """
        Analiza el zapato, puntúa la mesa y decide la secuencia de jugada fija.
        Retorna:
            qualifies: bool
            score: int
            prediction_sequence: list of str (6 tiros)
            entry_type: 'GHOST' o 'REAL'
            real_attempt: int (1, 2, 3)
            reason: str
        """
        score, score_reason = self.evaluate_table_quality(history)
        if score < self.min_table_score:
            return False, score, [], "NONE", f"Score insuficiente: {score}/100 ({score_reason})"

        clean = [h for h in history if h in ("P", "B")]
        last = clean[-1]
        opp = "B" if last == "P" else "P"

        roads = calculate_all_roads(clean)
        consensus = roads.get("consensus_next")

        # Calcular racha actual
        streak = 1
        for i in range(len(clean) - 2, -1, -1):
            if clean[i] == last:
                streak += 1
            else:
                break

        # ─────────────────────────────────────────────────────────────
        # ESTRATEGIAS FIJAS DE ALTA PRECISIÓN (SIN PING-PONG)
        # ─────────────────────────────────────────────────────────────
        # 1. Estrategia Doble Pareja (2-2-2)
        if streak == 2:
            # Racha de 2: apostar al cambio y luego repetir
            sequence = [opp, opp, last, last, opp, opp]
            strat_name = "DOBLE_PAREJA_2_2"
        # 2. Estrategia Ruptura de Agotamiento (Racha >= 4)
        elif streak >= 4:
            sequence = [opp, opp, last, opp, opp, last]
            strat_name = "RUPTURA_AGOTAMIENTO"
        # 3. Estrategia Seguimiento de Tendencia Fuerte con Derivadas
        elif consensus and consensus == last:
            sequence = [last, last, opp, opp, last, last]
            strat_name = "TENDENCIA_DERIVADAS"
        else:
            # Estrategia Bloque Equilibrado 2T + 3D + 1T
            sequence = [last, last, opp, opp, opp, last]
            strat_name = "BLOQUE_EQUILIBRADO"

        # ─────────────────────────────────────────────────────────────
        # GHOST BETTING (FILTRO DE FRANCOTIRADOR)
        # ─────────────────────────────────────────────────────────────
        # Si el sniper_level es 1:
        #   Tiro 0 de la secuencia es VIRTUAL (Ghost).
        #   Si falla, el Tiro 1 de la secuencia es el PRIMER TIRO REAL del usuario.
        # Si el sniper_level es 2:
        #   Tiros 0 y 1 son VIRTUALES (Ghost).
        #   Si fallan, el Tiro 2 es el PRIMER TIRO REAL del usuario.

        return True, score, sequence, strat_name, score_reason
