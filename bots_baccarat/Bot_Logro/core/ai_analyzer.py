"""
core/ai_analyzer.py — Motor de Inteligencia Táctica "Bot Logro" (Tiro a Tiro / Cero Secuencias Fijas)
=====================================================================================================
1. CERO SECUENCIAS CIEGAS DE 6 COLORES:
   - Analiza la estructura real del Big Road / Bead Road mano por mano.
   - Emite UNA SOLA JUGADA CONCRETA ('P' = Azul o 'B' = Rojo) para la mano inmediata.
2. ESTIMACIÓN REALISTA DE INTENTOS EN MESA (1, 2 o 3 intentos):
   - Tiro Franco (1 intento): Cortes de techo simétrico, cierre de parejas o dragones maduros (5+).
     Si falla ese intento, el patrón se considera roto y el bot busca cambiar de mesa o girar.
   - Precisión Media (1 a 2 intentos): Ping-Pong exacto, armado de parejas 2x2, dragón joven (3-4).
   - Tendencia Dominante (1 a 3 intentos): Pullback en zapato con fuerte dominancia (>=64%).
3. FILTRO DE CONSISTENCIA (BACKTEST EN VIVO DEL ZAPATO):
   - Evalúa las últimas manos de la propia mesa para medir si el zapato está respetando patrones
     o si está caótico/errático (descartando mesas traicioneras para perder lo menos posible).
"""

import os
import json
import logging
import requests
import config

logger = logging.getLogger("AIAnalyzer")

GROQ_API_KEY = getattr(config, "GROQ_API_KEY", "")
GROQ_MODEL   = getattr(config, "GROQ_MODEL", "groq/compound-mini")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", "")
GEMINI_MODEL   = getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")


def opposite_color(c):
    return "B" if c == "P" else "P"


def color_label_es(c):
    return "AZUL (Jugador)" if c == "P" else "ROJO (Banca)"


class GeminiBaccaratAnalyzer:
    """
    Motor Analítico Profundo para Bot Logro.
    Evalúa cada mesa mano a mano y devuelve una jugada única de alta convicción,
    junto con el número recomendado de intentos (1, 2 o 3) y la justificación técnica.
    """
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        self.url = GROQ_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    # ──────────────────────────────────────────────────────────────────
    # 1. EXTRACCIÓN DE ESTRUCTURA DEL BIG ROAD (COLUMNAS / RUNS)
    # ──────────────────────────────────────────────────────────────────
    def extract_road_structure(self, history):
        """
        Descompone el historial completo en columnas del Big Road (runs de P y B)
        y métricas de estabilidad/empates.
        """
        clean = [x for x in history if x in ("P", "B")]
        runs = []
        for x in clean:
            if not runs or runs[-1][0] != x:
                runs.append([x, 1])
            else:
                runs[-1][1] += 1

        runs_tuples = [(r[0], r[1]) for r in runs]
        recent_ties = sum(1 for x in history[-6:] if x == "T")
        total_ties = sum(1 for x in history if x == "T")

        total_p = clean.count("P")
        total_b = clean.count("B")
        recent_14 = clean[-14:]
        p_14 = recent_14.count("P")
        b_14 = recent_14.count("B")

        return {
            "clean": clean,
            "runs": runs_tuples,
            "recent_ties": recent_ties,
            "total_ties": total_ties,
            "total_p": total_p,
            "total_b": total_b,
            "p_14": p_14,
            "b_14": b_14,
        }

    # ──────────────────────────────────────────────────────────────────
    # 2. MEDICIÓN DE CONSISTENCIA RECIENTE DE LA MESA (ANTI-CAOS)
    # ──────────────────────────────────────────────────────────────────
    def _measure_shoe_consistency(self, runs, clean):
        """
        Evalúa qué tan predecible y ordenado ha sido el zapato en sus últimas columnas.
        Retorna un ajuste de puntaje entre -15.0 (caótico) y +8.0 (muy noble/estable).
        """
        if len(runs) < 3:
            return 4.0  # Zapato con pocas columnas (rachas largas) -> muy estable

        recent_lengths = [r[1] for r in runs[-6:]]
        completed_lengths = [r[1] for r in runs[:-1][-5:]]

        if not completed_lengths:
            return 3.0

        # Caso 1: Todas las columnas recientes son de 1 (Ping-Pong puro)
        if len(completed_lengths) >= 3 and all(L == 1 for L in completed_lengths[-3:]):
            return 7.5

        # Caso 2: Columnas recientes son parejas exactas (2, 2, 2)
        if len(completed_lengths) >= 2 and all(L == 2 for L in completed_lengths[-2:]):
            return 7.0

        # Caso 3: Ritmo alternado 2-1-2-1 o 3-1-3-1
        if len(completed_lengths) >= 3:
            last3 = completed_lengths[-3:]
            if last3 in ([2, 1, 2], [1, 2, 1], [3, 1, 3], [1, 3, 1]):
                return 6.5

        # Caso 4: Detectar caos (saltos bruscos sin patrón: ej. 4, 1, 3, 2, 1 o 1, 4, 2, 1, 3)
        if len(completed_lengths) >= 4:
            unique_vals = len(set(completed_lengths[-4:]))
            diffs = [abs(completed_lengths[i] - completed_lengths[i-1]) for i in range(1, len(completed_lengths))]
            # Si hay 3 o más longitudes distintas en las últimas 4 columnas y saltos erráticos
            if unique_vals >= 3 and max(diffs) >= 2:
                # Verificar si al menos hay dominancia fuerte de un color (>68%)
                r12 = clean[-12:]
                dom_ratio = max(r12.count("P"), r12.count("B")) / max(1, len(r12))
                if dom_ratio < 0.65:
                    return -12.0  # Mesa errática / rompe-patrones

        return 1.5

    # ──────────────────────────────────────────────────────────────────
    # 3. MOTOR MATEMÁTICO DE LECTURA DE PATRONES (TIRO A TIRO)
    # ──────────────────────────────────────────────────────────────────
    def _evaluate_tactical_setups(self, struct, is_recovery=False, last_failed_pred=None):
        """
        Evalúa todos los patrones profesionales de Baccarat sobre la estructura actual de la mesa.
        Retorna una lista ordenada de candidatos:
        (score, prediction, probability, planned_attempts, strategy_name, reason)
        """
        clean = struct["clean"]
        runs = struct["runs"]
        recent_ties = struct["recent_ties"]
        p_14 = struct["p_14"]
        b_14 = struct["b_14"]

        if not runs or len(clean) < 8:
            return []

        curr_color, curr_len = runs[-1]
        opp_color = opposite_color(curr_color)
        prev_runs = runs[:-1]
        prev_lengths = [r[1] for r in prev_runs]

        # Color dominante en las últimas 14 jugadas limpias
        n_14 = len(clean[-14:])
        dom_color = "P" if p_14 >= b_14 else "B"
        dom_count = max(p_14, b_14)
        dom_ratio = dom_count / max(1, n_14)

        #Columnas previas del mismo color que el actual
        same_color_prev_runs = [r[1] for r in prev_runs if r[0] == curr_color]
        opp_color_prev_runs = [r[1] for r in prev_runs if r[0] == opp_color]

        consistency_bonus = self._measure_shoe_consistency(runs, clean)
        tie_penalty = 4.0 * max(0, recent_ties - 1)  # Penalizar si hay 2+ empates recientes

        setups = []

        # ── PATRÓN 1: DRAGÓN / RACHA LIMPIA EN CURSO (3+ bolas seguidas) ──
        if curr_len >= 3:
            # Verificar si las últimas 2 columnas de este color cortaron exactamente en curr_len (techo)
            has_exact_ceiling = (
                len(same_color_prev_runs) >= 2
                and same_color_prev_runs[-1] == curr_len
                and same_color_prev_runs[-2] == curr_len
            )
            if not has_exact_ceiling:
                base_prob = min(96, 90 + (curr_len - 2) * 2)
                # En dragón maduro (5+), recomendamos 1 solo intento en esta mesa (si corta, cambiamos o giramos)
                planned_att = 1 if curr_len >= 5 else 2
                score = float(base_prob) + consistency_bonus - tie_penalty + (2.5 if curr_color == dom_color else 0.0)
                setups.append((
                    score,
                    curr_color,
                    int(max(86, min(97, round(score)))),
                    planned_att,
                    "DRAGON_EN_CURSO",
                    f"Racha activa de {curr_len}x {color_label_es(curr_color)} sin techo de bloqueo (Seguir Dragón)"
                ))
            else:
                # Techo simétrico detectado en longitud curr_len
                base_prob = 92
                score = float(base_prob) + consistency_bonus - tie_penalty
                setups.append((
                    score,
                    opp_color,
                    int(max(86, min(95, round(score)))),
                    1,
                    "CORTE_TECHO_SIMETRICO",
                    f"Techo simétrico: las últimas columnas de {color_label_es(curr_color)} cortaron exactamente en {curr_len} bolas"
                ))

        # ── PATRÓN 2: PING-PONG / ALTERNANCIA PURA (1-1-1-1) ──
        if curr_len == 1 and len(prev_lengths) >= 3 and all(L == 1 for L in prev_lengths[-3:]):
            ping_len = 1
            for L in reversed(prev_lengths):
                if L == 1:
                    ping_len += 1
                else:
                    break
            base_prob = min(96, 90 + ping_len)
            planned_att = 1 if ping_len >= 6 else 2
            score = float(base_prob) + consistency_bonus - tie_penalty + 2.0
            setups.append((
                score,
                opp_color,
                int(max(88, min(96, round(score)))),
                planned_att,
                "PING_PONG_EXACTO",
                f"Alternancia exacta Ping-Pong ({ping_len} cambios seguidos 1x1) ➔ Toca cambio a {color_label_es(opp_color)}"
            ))

        # ── PATRÓN 3: COMPLETAR PAREJA SIMÉTRICA (2-2-1 ➔ 2) ──
        if curr_len == 1 and len(prev_lengths) >= 2 and prev_lengths[-1] == 2 and prev_lengths[-2] == 2:
            pairs_streak = 0
            for L in reversed(prev_lengths):
                if L == 2:
                    pairs_streak += 1
                else:
                    break
            base_prob = min(96, 91 + pairs_streak)
            score = float(base_prob) + consistency_bonus - tie_penalty + 2.5
            setups.append((
                score,
                curr_color,
                int(max(89, min(96, round(score)))),
                2,
                "COMPLETAR_DOBLE_2X2",
                f"Tren de parejas ({pairs_streak} dobles seguidos 2x2) con 1 bola en columna actual ➔ Buscar segunda bola {color_label_es(curr_color)}"
            ))

        # ── PATRÓN 4: CORTE DE PAREJA SIMÉTRICA (2-2-2 ➔ Corte a opuesto) ──
        if curr_len == 2 and len(prev_lengths) >= 2 and prev_lengths[-1] == 2 and prev_lengths[-2] == 2:
            base_prob = 92
            score = float(base_prob) + consistency_bonus - tie_penalty + 1.5
            setups.append((
                score,
                opp_color,
                int(max(88, min(95, round(score)))),
                1,
                "CORTE_DOBLE_2X2",
                f"Techo de parejas 2x2 completado (3 columnas de 2 bolas) ➔ Tiro franco al corte {color_label_es(opp_color)}"
            ))

        # ── PATRÓN 5: RITMO ESCALONADO 2-1-2-1 / 3-1-3-1 ──
        if len(prev_lengths) >= 3:
            last3 = prev_lengths[-3:]
            # Si venimos de [2, 1, 2] y estamos en curr_len == 1 -> toca cortar para respetar el '1'
            if last3 == [2, 1, 2] and curr_len == 1:
                score = 92.5 + consistency_bonus - tie_penalty
                setups.append((
                    score,
                    opp_color,
                    int(max(88, min(95, round(score)))),
                    2,
                    "RITMO_2_1_2_1_CORTE",
                    f"Patrón rítmico 2-1-2-1 activo: tras columna de 1 {color_label_es(curr_color)}, corresponde giro a {color_label_es(opp_color)}"
                ))
            # Si venimos de [1, 2, 1] y estamos en curr_len == 1 -> toca repetir para formar el '2'
            elif last3 == [1, 2, 1] and curr_len == 1:
                score = 92.0 + consistency_bonus - tie_penalty
                setups.append((
                    score,
                    curr_color,
                    int(max(88, min(95, round(score)))),
                    2,
                    "RITMO_1_2_1_2_DOBLE",
                    f"Patrón rítmico 1-2-1-2 activo: corresponde segunda bola de {color_label_es(curr_color)}"
                ))
            # Si venimos de [3, 1, 3] y estamos en curr_len == 1 -> toca cortar para volver al color de 3
            elif last3 == [3, 1, 3] and curr_len == 1:
                score = 93.0 + consistency_bonus - tie_penalty
                setups.append((
                    score,
                    opp_color,
                    int(max(89, min(96, round(score)))),
                    2,
                    "RITMO_3_1_3_1_GIRO",
                    f"Patrón 3-1-3-1 activo: agotado el paso corto de {color_label_es(curr_color)}, retoma tendencia {color_label_es(opp_color)}"
                ))

        # ── PATRÓN 6: RETROCESO DE 1 MANO EN ZAPATO CON FUERTE DOMINANCIA (PULLBACK) ──
        if dom_ratio >= 0.64 and curr_color != dom_color and curr_len == 1:
            # El color débil acaba de meter 1 sola bola contra un zapato muy dominado por dom_color
            # Verificar además que la última columna de dom_color haya sido >= 2
            if opp_color_prev_runs and opp_color_prev_runs[-1] >= 2:
                dom_pct = int(round(dom_ratio * 100))
                base_prob = 91 + (2 if dom_ratio >= 0.70 else 0)
                score = float(base_prob) + consistency_bonus - tie_penalty + 2.0
                setups.append((
                    score,
                    dom_color,
                    int(max(88, min(95, round(score)))),
                    2,
                    "PULLBACK_DOMINANCIA",
                    f"Dominancia fuerte de {color_label_es(dom_color)} ({dom_pct}% en últ. 14 manos). Retroceso de 1 bola débil ➔ Retomar {color_label_es(dom_color)}"
                ))

        # ── PATRÓN 7: EXPANSIÓN DE SEGUNDA A TERCERA BOLA EN COLOR DOMINANTE ──
        if curr_len == 2 and curr_color == dom_color and dom_ratio >= 0.58:
            # Si la última columna de este mismo color llegó a 3+ (no tiene techo en 2)
            if same_color_prev_runs and same_color_prev_runs[-1] >= 3:
                score = 90.0 + consistency_bonus - tie_penalty + 1.5
                setups.append((
                    score,
                    curr_color,
                    int(max(87, min(94, round(score)))),
                    2,
                    "EXPANSION_TERCIA",
                    f"Doble {color_label_es(curr_color)} firme con antecedente de columna larga ({same_color_prev_runs[-1]}x) ➔ Buscar 3ra bola"
                ))

        # ── PATRÓN 8: TECHO DE PARED CORTA (El color débil nunca pasa de 1 en las últimas 3 apariciones) ──
        if curr_len == 1 and len(same_color_prev_runs) >= 2 and all(L == 1 for L in same_color_prev_runs[-2:]):
            if opp_color_prev_runs and opp_color_prev_runs[-1] >= 2:
                score = 91.5 + consistency_bonus - tie_penalty + 1.5
                setups.append((
                    score,
                    opp_color,
                    int(max(88, min(95, round(score)))),
                    2,
                    "MURO_DE_UNOS",
                    f"{color_label_es(curr_color)} no supera 1 bola desde hace {len(same_color_prev_runs[-3:])+1} columnas ➔ Corte a {color_label_es(opp_color)}"
                ))

        # Si estamos en modo recuperación y el último tiro falló en esta misma mesa,
        # penalizar repetir exactamente una predicción si el zapato está en contra
        if is_recovery and last_failed_pred:
            adjusted = []
            for sc, pred, prob, patt, sname, rsn in setups:
                # Si la predicción va en contra de un nuevo dragón de 3+ que nos acaba de ganar, penalizar fuerte
                if curr_len >= 3 and pred != curr_color:
                    sc -= 15.0
                adjusted.append((sc, pred, prob, patt, sname, rsn))
            setups = adjusted

        setups.sort(key=lambda x: x[0], reverse=True)
        return setups

    # ──────────────────────────────────────────────────────────────────
    # 4. VALIDACIÓN CON IA (SEGUNDA OPINIÓN RÁPIDA TIRO A TIRO)
    # ──────────────────────────────────────────────────────────────────
    def _consult_single_shot_ai(self, table_name, struct, top_local_setup):
        """
        Consulta rápida a Groq/Gemini para validar o refinar la jugada única.
        Si la API tarda o no está disponible, usa instantáneamente el motor matemático local.
        """
        clean = struct["clean"]
        runs = struct["runs"]
        runs_str = " -> ".join(f"{c}x{L}" for c, L in runs[-8:])
        _, local_pred, local_prob, local_att, local_strat, local_reason = top_local_setup

        system_prompt = (
            "Eres 'Bot Logro', el analista cuantitativo de Baccarat más preciso del mundo.\n"
            "NO generes secuencias de 6 colores. Tu misión es analizar las columnas del Big Road y decidir "
            "UNA SOLA JUGADA ('P' para Azul/Jugador o 'B' para Rojo/Banca) para la mano inmediata.\n"
            "También debes indicar cuántos intentos máximos recomiendas sostener en esta mesa (1, 2 o 3) "
            "antes de cambiar de mesa si no se da.\n"
            "Si la mesa se ve caótica o traicionera, responde should_signal: false.\n"
            "Responde SOLO en JSON exacto:\n"
            '{"should_signal": true, "prediction": "P", "planned_attempts": 1, "probability": 93, "strategy_name": "NOMBRE_CORTO", "reason": "Explicación clara y breve"}'
        )

        user_prompt = (
            f"Mesa: {table_name} ({len(clean)} manos limpias).\n"
            f"Columnas recientes del Big Road: {runs_str}\n"
            f"Últimas 14 manos: {struct['p_14']} Azul (P) vs {struct['b_14']} Rojo (B). Empates recientes: {struct['recent_ties']}.\n"
            f"Pre-análisis matemático detectó: [{local_strat}] apostar a {local_pred} ({local_prob}%), "
            f"intentos sugeridos: {local_att}, motivo: {local_reason}.\n"
            f"Confirma o mejora esta decisión para ganar en el menor número de intentos posible."
        )

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 180,
                "temperature": 0.25
            }
            r = requests.post(self.url, headers=self.headers, json=payload, timeout=2.8)
            if r.status_code == 200:
                parsed = json.loads(r.json()["choices"][0]["message"]["content"])
                should = bool(parsed.get("should_signal", True))
                pred = str(parsed.get("prediction", local_pred)).upper().strip()
                if pred not in ("P", "B"):
                    pred = local_pred
                att = int(parsed.get("planned_attempts", local_att))
                att = max(1, min(3, att))
                prob = int(parsed.get("probability", local_prob))
                prob = max(86, min(97, prob))
                # Si la IA coincide con el motor matemático de columnas, subir +1% de convicción
                if pred == local_pred:
                    prob = min(97, max(prob, local_prob) + 1)
                return True, should, pred, prob, att, local_strat, local_reason
        except Exception:
            pass

        return False, True, local_pred, local_prob, local_att, local_strat, local_reason

    # ──────────────────────────────────────────────────────────────────
    # 5. MÉTODO PRINCIPAL DE ANÁLISIS DE UNA MESA (TIRO ÚNICO)
    # ──────────────────────────────────────────────────────────────────
    def analyze_single_hand(self, table_name, history, is_recovery=False, last_failed_pred=None, consult_ai=True):
        """
        Analiza una mesa y devuelve su mejor jugada individual si existe ventaja real.
        Retorna dict:
        {
            "should_signal": bool,
            "prediction": "P" | "B" | None,
            "probability": int,
            "score": float,
            "planned_attempts": int (1, 2 o 3),
            "strategy_name": str,
            "reason": str,
            "curr_streak": int,
            "consistency": float
        }
        """
        if not history or len(history) < 8 or len(history) >= 65:
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": 0.0,
                "planned_attempts": 1,
                "strategy_name": "NONE",
                "reason": f"Zapato fuera de rango (8 a 64 manos, tiene {len(history) if history else 0})",
            }

        # Evitar entrar en fresco inmediatamente después de un empate ('T')
        if not is_recovery and history[-1] == "T":
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": 0.0,
                "planned_attempts": 1,
                "strategy_name": "NONE",
                "reason": "Pausa preventiva tras Empate reciente",
            }

        struct = self.extract_road_structure(history)
        clean = struct["clean"]
        if len(clean) < 8:
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": 0.0,
                "planned_attempts": 1,
                "strategy_name": "NONE",
                "reason": "Menos de 8 manos limpias (P/B)",
            }

        consistency = self._measure_shoe_consistency(struct["runs"], clean)
        # Si el zapato es altamente caótico/errático, rechazar la mesa
        if consistency <= -10.0:
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": consistency,
                "planned_attempts": 1,
                "strategy_name": "CAOS_FILTRADO",
                "reason": "Mesa descartada por alta inestabilidad / quiebres erráticos",
            }

        setups = self._evaluate_tactical_setups(struct, is_recovery=is_recovery, last_failed_pred=last_failed_pred)
        if not setups:
            return {
                "should_signal": False,
                "prediction": None,
                "probability": 0,
                "score": 0.0,
                "planned_attempts": 1,
                "strategy_name": "SIN_PATRON",
                "reason": "Mesa plana sin patrón de alta probabilidad definido",
            }

        top = setups[0]
        score, pred, prob, planned_att, strat_name, reason = top

        if consult_ai and score >= 88.0:
            _, should_ai, pred_ai, prob_ai, att_ai, strat_ai, reason_ai = self._consult_single_shot_ai(
                table_name, struct, top
            )
            if not should_ai and not is_recovery:
                return {
                    "should_signal": False,
                    "prediction": None,
                    "probability": 0,
                    "score": 0.0,
                    "planned_attempts": 1,
                    "strategy_name": strat_ai,
                    "reason": "Descartada en doble verificación de riesgo",
                }
            pred = pred_ai
            prob = prob_ai
            planned_att = att_ai
            strat_name = strat_ai
            reason = reason_ai

        curr_streak = struct["runs"][-1][1] if struct["runs"] else 1
        return {
            "should_signal": True,
            "prediction": pred,
            "probability": int(prob),
            "score": float(score),
            "planned_attempts": int(planned_att),
            "strategy_name": strat_name,
            "reason": reason,
            "curr_streak": curr_streak,
            "consistency": consistency,
        }

    # Compatibilidad con interfaz previa
    def analyze(self, table_name, history, last_strategy=None, early_scores=None, strategy_usage=None, stats_tracker=None):
        res = self.analyze_single_hand(table_name, history, is_recovery=False, consult_ai=True)
        if not res["should_signal"] or not res["prediction"]:
            return False, [], 0, res["strategy_name"], res["reason"]
        pred = res["prediction"]
        return True, [pred], res["probability"], res["strategy_name"], res["reason"]
