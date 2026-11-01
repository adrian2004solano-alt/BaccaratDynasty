"""
core/ai_analyzer.py  — v31 (IA Libre, Multi-Road, Estrategias Bloque, Sin Ping-Pong)
======================================================================================
Motor de IA con estrategias tipo bloque definidas por el usuario.
5 estrategias principales — NINGUNA es ping-pong (alternante).
La IA elige la mejor segun el zapato, usando Multi-Road y aprendizaje.
"""

import json
import random
import logging
import requests
import config

from core.baccarat_roads   import calculate_all_roads
from core.learning_tracker import LearningTracker

logger = logging.getLogger("AIAnalyzer")

GROQ_API_KEY = getattr(config, "GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

# API key actualizada por el usuario
GEMINI_API_KEY = ""
GEMINI_MODEL   = "gemini-1.5-flash"

_learning_tracker = LearningTracker()

# ──────────────────────────────────────────────────────────────────────────────
# LAS 5 ESTRATEGIAS TIPO BLOQUE DEL USUARIO (SIN PING-PONG)
# T = color de tendencia dominante | D = color opuesto/disruptivo
#
#  S1: 1T + 3D + 2T  → [T,D,D,D,T,T]  "un tendencia, tres disruptivas, dos tendencias"
#  S2: 1D + 3T + 2D  → [D,T,T,T,D,D]  (reverso de S1)
#  S3: 2T + 3D + 1T  → [T,T,D,D,D,T]  "dos tendencias, tres disruptivas, una tendencia"
#  S4: 2T + 2D + 2T  → [T,T,D,D,T,T]  "dos, dos y dos"
#  S5: 3T + 2D + 1T  → [T,T,T,D,D,T]  "bloque pesado de tendencia" (aportado por IA)
#
# Filosofia: apostar en BLOQUES del mismo color — no alternar cada tiro.
# ──────────────────────────────────────────────────────────────────────────────

STRATEGY_TEMPLATES = {
    "BLOQUE_1T_3D_2T": lambda T, D: [T, D, D, D, T, T],
    "BLOQUE_1D_3T_2D": lambda T, D: [D, T, T, T, D, D],
    "BLOQUE_2T_3D_1T": lambda T, D: [T, T, D, D, D, T],
    "BLOQUE_2T_2D_2T": lambda T, D: [T, T, D, D, T, T],
    "BLOQUE_3T_2D_1T": lambda T, D: [T, T, T, D, D, T],
}


def shoe_type_from_history(recent):
    if len(recent) < 4:
        return "neutral"
    alt = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
    r   = alt / (len(recent) - 1)
    return "alternating" if r >= 0.7 else ("streaky" if r <= 0.3 else "neutral")


class GeminiBaccaratAnalyzer:
    """
    Analizador con estrategias tipo bloque, IA libre, Multi-Road y Aprendizaje.
    """
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or GROQ_API_KEY
        self.model   = model   or GROQ_MODEL
        self.url     = GROQ_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    def analyze(self, table_name, history, last_strategy=None,
                early_scores=None, strategy_usage=None):
        """
        Analiza el zapato con IA + Multi-Road + Aprendizaje.
        Retorna: (should_signal, sequence, probability, strategy_name, reason)
        Minimo 10 jugadas limpias requeridas.
        """
        if not history or len(history) < 10 or len(history) >= 65:
            return False, [], 0, "NONE", "Historial fuera de rango (10 a 64 jugadas permitidas)"

        clean = [x for x in history if x in ("P", "B")]
        if len(clean) < 10:
            return False, [], 0, "NONE", "Menos de 10 jugadas limpias — mesa inestable"

        # Empate reciente: esperar definicion
        if history[-1] == "T":
            return False, [], 0, "NONE", "Empate reciente — esperando definicion"

        last   = clean[-1]
        streak = 0
        for x in reversed(clean):
            if x == last:
                streak += 1
            else:
                break

        total_p  = clean.count("P")
        total_b  = clean.count("B")
        recent15 = clean[-15:]
        p15      = recent15.count("P")
        b15      = recent15.count("B")

        # Zapato totalmente neutro sin ninguna ventaja
        if streak < 2 and abs(p15 - b15) == 0 and abs(total_p - total_b) <= 1:
            return False, [], 0, "NONE", "Zapato neutral sin ventaja"

        # Calcular tendencia
        if streak >= 2:
            T = last
        elif p15 != b15:
            T = "P" if p15 > b15 else "B"
        elif total_p != total_b:
            T = "P" if total_p > total_b else "B"
        else:
            T = last
        D = "B" if T == "P" else "P"

        # Multi-Road Analysis
        roads = calculate_all_roads(clean)
        roads_text     = roads["analysis_text"]
        road_consensus = roads["consensus_next"]
        road_strength  = roads["consensus_strength"]

        # Aprendizaje
        shoe_type        = shoe_type_from_history(recent15)
        learning_summary = _learning_tracker.get_summary_for_ai()
        best_hint        = _learning_tracker.get_best_strategy_hint(shoe_type)

        # Intentar consulta a la IA
        try:
            ok, should, seq, prob, strat, reason = self._consult_ai(
                table_name=table_name, clean=clean, last=last, streak=streak,
                total_p=total_p, total_b=total_b, p15=p15, b15=b15,
                T=T, D=D, roads_text=roads_text,
                road_consensus=road_consensus, road_strength=road_strength,
                learning_summary=learning_summary, best_hint=best_hint,
                last_strategy=last_strategy, shoe_type=shoe_type,
            )
            if ok and should and seq and len(seq) >= 6:
                logger.info(f"[{table_name}] IA ({strat} | {prob}%): {chr(32).join(seq)}")
                return True, seq[:6], prob, strat, reason
            elif ok and not should:
                logger.info(f"[{table_name}] IA decidio PASAR: {reason}")
                return False, [], 0, "NONE", reason
        except Exception as e:
            logger.warning(f"[{table_name}] Fallback local: {e}")

        # Fallback local con las 5 estrategias tipo bloque
        return self._local_block_fallback(
            table_name, clean, last, streak, total_p, total_b,
            p15, b15, T, D, roads, last_strategy, strategy_usage
        )

    def _consult_ai(self, table_name, clean, last, streak, total_p, total_b,
                    p15, b15, T, D, roads_text, road_consensus, road_strength,
                    learning_summary, best_hint, last_strategy, shoe_type):

        road_pct = int(road_strength * 100)
        road_rec = road_consensus if road_consensus else "No concluyente"

        hint_msg = ""
        if best_hint:
            hint_msg = f"\nHINT DE APRENDIZAJE: Para zapatos '{shoe_type}', la estrategia '{best_hint}' ha tenido el mejor win rate en tiro 1-3."

        last_msg = ""
        if last_strategy:
            last_msg = f"\nULTIMA ESTRATEGIA USADA: '{last_strategy}'. Intenta rotar a otra diferente."

        strat_catalog = (
            "CATALOGO DE 5 ESTRATEGIAS BLOQUE (ELIGE UNA):\n"
            "  BLOQUE_1T_3D_2T: [T,D,D,D,T,T] — 1 bloque tend, 3 disrup, 2 tend\n"
            "  BLOQUE_1D_3T_2D: [D,T,T,T,D,D] — 1 disrup, 3 tend, 2 disrup\n"
            "  BLOQUE_2T_3D_1T: [T,T,D,D,D,T] — 2 tend, 3 disrup, 1 tend\n"
            "  BLOQUE_2T_2D_2T: [T,T,D,D,T,T] — 2+2+2 equilibrado\n"
            "  BLOQUE_3T_2D_1T: [T,T,T,D,D,T] — 3 tend, 2 disrup, 1 tend\n"
            f"Donde T={T} (tendencia dominante) y D={D} (opuesto).\n"
            "PROHIBIDO: Secuencias ping-pong como [T,D,T,D,T,D] o [D,T,D,T,D,T]. "
            "Las estrategias deben tener bloques de al menos 2 del mismo color consecutivos."
        )

        system_prompt = (
            "Eres el mejor Jugador Profesional de Baccarat en Vivo del mundo.\n\n"
            "TU OBJETIVO: Elegir la estrategia tipo BLOQUE que maximice ganar en TIRO 1 o 2.\n\n"
            + strat_catalog + "\n\n"
            "REGLAS ESTRICTAS:\n"
            "  1. Si el zapato no tiene ventaja clara, usa should_signal: false\n"
            "  2. NUNCA uses ping-pong (alternancia T,D,T,D,T,D)\n"
            "  3. strategy_name debe ser exactamente uno de los 5 nombres del catalogo\n"
            "  4. Prioriza ganar en el tiro 1 o 2\n\n"
            "Responde SOLO en JSON:\n"
            '{"should_signal": true, "sequence": ["B","B","P","P","B","B"], '
            '"probability": 92, "strategy_name": "BLOQUE_2T_2D_2T", "reason": "Justificacion breve"}'
        )

        user_prompt = (
            f"Mesa: {table_name} | Zapato: {len(clean)} jugadas\n"
            f"Historial reciente (20): [{', '.join(clean[-20:])}]\n"
            f"Stats: P={total_p} B={total_b} | Ult15: P={p15} B={b15} | Racha: {streak}x{last}\n"
            f"Tendencia T={T} | Opuesto D={D}\n\n"
            f"{roads_text}\n"
            f"Consenso Multi-Road: {road_rec} (confianza {road_pct}%)\n\n"
            f"APRENDIZAJE:\n{learning_summary}\n"
            f"{hint_msg}{last_msg}\n\n"
            "Elige la mejor estrategia bloque para ganar en el tiro 1-2."
        )

        # Tier 1: Groq
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 250,
                "temperature": 0.35,
            }
            r = requests.post(self.url, headers=self.headers, json=payload, timeout=6)
            if r.status_code == 200:
                parsed = json.loads(r.json()["choices"][0]["message"]["content"])
                should = parsed.get("should_signal", True)
                seq    = [x for x in parsed.get("sequence", []) if x in ("P", "B")][:6]
                prob   = max(88, min(97, int(parsed.get("probability", 92))))
                strat  = parsed.get("strategy_name", "BLOQUE_2T_2D_2T")
                reason = parsed.get("reason", "Analisis Groq")
                # Validar que no sea ping-pong
                if should and len(seq) >= 6 and not _is_pingpong(seq):
                    return True, should, seq, prob, strat, reason
                elif not should:
                    return True, False, [], 0, strat, reason
        except Exception as e:
            logger.debug(f"Groq: {e}")

        # Tier 2: Gemini
        try:
            gem_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            )
            payload_gem = {
                "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 250,
                    "temperature": 0.35,
                },
            }
            rg = requests.post(gem_url, json=payload_gem, timeout=7)
            if rg.status_code == 200:
                raw    = rg.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw)
                should = parsed.get("should_signal", True)
                seq    = [x for x in parsed.get("sequence", []) if x in ("P", "B")][:6]
                prob   = max(88, min(97, int(parsed.get("probability", 92))))
                strat  = parsed.get("strategy_name", "BLOQUE_2T_2D_2T")
                reason = parsed.get("reason", "Analisis Gemini")
                if should and len(seq) >= 6 and not _is_pingpong(seq):
                    return True, should, seq, prob, strat, reason
                elif not should:
                    return True, False, [], 0, strat, reason
        except Exception as e:
            logger.debug(f"Gemini: {e}")

        return False, False, [], 0, "NONE", "Fallback local"

    def _local_block_fallback(self, table_name, clean, last, streak,
                              total_p, total_b, p15, b15, T, D,
                              roads, last_strategy, strategy_usage):
        """
        Fallback local: elige la mejor estrategia bloque segun el zapato.
        Usa Multi-Road consensus y estadisticas del zapato.
        """
        strategy_usage = strategy_usage or {}
        consensus      = roads["consensus_next"]
        strength       = roads["consensus_strength"]
        avg_streak     = roads["avg_streak"]

        # Scores para cada estrategia segun el tipo de zapato
        scores = {}
        for name in STRATEGY_TEMPLATES:
            s = 0.0
            # Zapato de rachas largas: mejor las que empiezan con bloque de tendencia largo
            if avg_streak >= 3:
                if name in ("BLOQUE_3T_2D_1T", "BLOQUE_2T_2D_2T"):
                    s += 4.0
            # Zapato de rachas cortas/alternante: mejor 1T+3D o 2T+3D
            elif avg_streak <= 1.8:
                if name in ("BLOQUE_1T_3D_2T", "BLOQUE_2T_3D_1T"):
                    s += 4.0
            else:
                if name == "BLOQUE_2T_2D_2T":
                    s += 3.0

            # Road consensus boost
            if consensus and strength >= 0.67:
                if name in ("BLOQUE_3T_2D_1T", "BLOQUE_2T_2D_2T", "BLOQUE_2T_3D_1T"):
                    s += 3.0

            # Penalizar por uso reciente
            s -= strategy_usage.get(name, 0) * 2.5

            # Prohibir repetir la ultima
            if last_strategy and last_strategy.lower() in name.lower():
                s -= 50.0

            # Jitter
            s += random.uniform(0.1, 1.5)
            scores[name] = s

        best_name = max(scores, key=lambda k: scores[k])
        seq       = STRATEGY_TEMPLATES[best_name](T, D)
        prob      = 90

        # Bonus de confianza si el road tiene consenso fuerte
        if strength >= 1.0:
            prob = 94
        elif strength >= 0.67:
            prob = 92

        reason = (
            f"Bloque local: {best_name} | T={T} D={D} | "
            f"Racha {streak}x{last} | Avg racha: {avg_streak:.1f} | "
            f"Road: {consensus or 'N/A'} ({int(strength*100)}%)"
        )
        logger.info(f"[{table_name}] Fallback bloque ({best_name} | {prob}%): {chr(32).join(seq)}")
        return True, seq, prob, best_name, reason


def _is_pingpong(seq):
    """Retorna True si la secuencia alterna cada tiro (ping-pong)."""
    if len(seq) < 4:
        return False
    alternating = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i-1])
    return alternating >= len(seq) - 1
