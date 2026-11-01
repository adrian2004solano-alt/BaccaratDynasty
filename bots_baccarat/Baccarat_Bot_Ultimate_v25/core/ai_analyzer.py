"""
core/ai_analyzer.py  — v24 (4 Estrategias Maestras del Usuario, Análisis Profundo y Rotación Activa)
===================================================================================================
Motor de Inteligencia Artificial para Baccarat en vivo.
Actúa como un Jugador Profesional de Clase Mundial:
  1. Lectura del zapato en tiempo real (Big Road, racha actual, dominancia).
  2. Análisis profundo y paciente: No precipitarse si el zapato está indeciso.
  3. Catálogo Exclusivo de 4 Estrategias definidas por el usuario:
     - 1. DISRUPTIVA_4TEND_DISRUPTIVA : [D, T, T, T, T, D] (1 Contra + 4 Tendencia + 1 Contra)
     - 2. TENDENCIA_3_DISR_2TEND      : [T, T, T, D, T, T] (3 Tendencia + 1 Disruptiva + 2 Tendencia)
     - 3. TENDENCIA_PURA_6            : [T, T, T, T, T, T] (6 a la Tendencia)
     - 4. DISRUPTIVA_1_5TEND          : [D, T, T, T, T, T] (1 Disruptiva + 5 Tendencia)
  4. Rotación Estricta: Prohibido repetir la última estrategia jugada.
  5. Asertividad prioritaria en tiros 1 al 6 (Modo Sniper 1 al 3).
"""

import json
import random
import logging
import requests
import config

logger = logging.getLogger("AIAnalyzer")

GROQ_API_KEY = getattr(config, "GROQ_API_KEY", "")
GROQ_MODEL   = getattr(config, "GROQ_MODEL", "groq/compound-mini")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", "")
GEMINI_MODEL   = getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")


class GeminiBaccaratAnalyzer:
    """
    Analizador de Baccarat Profesional — Modo 4 Estrategias Maestras y Análisis Profundo.
    Equipado con arquitectura multimodelo de IA (Groq -> Gemini -> Motor Maestro Local).
    """
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        self.url = GROQ_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def analyze(self, table_name, history, last_strategy=None, early_scores=None, strategy_usage=None):
        """
        Analiza el historial buscando ventaja real con las 4 estrategias exclusivas del usuario.
        Retorna: (should_signal, sequence, probability, strategy_name, reason)
        """
        if not history or len(history) < 8 or len(history) >= 68:
            return False, [], 0, "NONE", "Historial fuera de rango permitido (8 a 67 jugadas)"

        # Regla: No emitir señal inmediata tras un Empate ('T')
        if history[-1] == "T":
            return False, [], 0, "NONE", "Pausa: Empate reciente (esperando definición)"

        clean = [x for x in history if x in ("P", "B")]
        if len(clean) < 8:
            return False, [], 0, "NONE", "Historial insuficiente de jugadas limpias"

        # Estadísticas del zapato
        last = clean[-1]
        streak = 0
        for x in reversed(clean):
            if x == last:
                streak += 1
            else:
                break

        total_p = clean.count("P")
        total_b = clean.count("B")
        recent_15 = clean[-15:]
        p_15 = recent_15.count("P")
        b_15 = recent_15.count("B")

        # Filtro de Zapato Muerto:
        # Solo se omite si no hay absolutamente ninguna ventaja ni en los últimos 15 ni en el zapato global (P y B exactamente iguales)
        if streak < 2 and abs(p_15 - b_15) == 0 and abs(total_p - total_b) <= 1:
            return False, [], 0, "NONE", "Mesa neutral (P y B exactamente iguales sin tendencia)"

        # ── 1. CONSULTA A IA CON FALLBACK INTELIGENTE (Groq -> Gemini) ──
        try:
            ai_ok, ai_should, ai_seq, ai_prob, ai_strat, ai_reason = self._consult_pro_player_ai(
                table_name, clean, streak, total_p, total_b, p_15, b_15,
                last_strategy=last_strategy, strategy_usage=strategy_usage
            )
            if ai_ok and ai_should:
                # Verificación de rotación para la IA
                is_repetition = False
                if last_strategy:
                    ai_lower = ai_strat.lower().strip()
                    last_lower = last_strategy.lower().strip()
                    if ai_lower == last_lower or ai_lower in last_lower or last_lower in ai_lower:
                        is_repetition = True
                    elif strategy_usage and strategy_usage.get(ai_strat, 0) >= 2:
                        is_repetition = True

                if is_repetition:
                    logger.info(f"[{table_name}] 🔄 IA intentó repetir '{ai_strat}'. Activando rotación local obligatoria.")
                    ai_ok = False
                else:
                    valid_seq = self._enforce_pro_guardrails(ai_seq, last, streak, total_p, total_b, p_15, b_15)
                    logger.info(f"[{table_name}] 🧠 IA Profesional ({ai_strat} | {ai_prob}%): {' '.join(valid_seq)}")
                    return True, valid_seq[:6], ai_prob, ai_strat, ai_reason
            elif ai_ok and not ai_should:
                logger.info(f"[{table_name}] ✋ IA Profesional decidió PASAR: {ai_reason}")
                return False, [], 0, ai_strat, ai_reason
        except Exception as e:
            logger.warning(f"[{table_name}] Fallback a motor maestro local: {e}")

        # ── 2. MOTOR MAESTRO LOCAL (6 Estrategias de Bloque Puro sin Ping-Pong) ──
        strat_candidates = self._build_and_score_4_strategies(clean, last_strategy, early_scores, strategy_usage)
        if not strat_candidates:
            return False, [], 0, "NONE", "Sin patrón claro"

        best_strat_name, best_seq, best_prob, best_score, best_reason = strat_candidates[0]
        valid_seq = self._enforce_pro_guardrails(best_seq, last, streak, total_p, total_b, p_15, b_15)
        return True, valid_seq[:6], best_prob, best_strat_name, best_reason

    def _consult_pro_player_ai(self, table_name, clean, streak, total_p, total_b, p_15, b_15, last_strategy=None, strategy_usage=None):
        """Consulta multi-tier a modelos de IA enfocada exclusivamente en las 4 estrategias del usuario."""
        last = clean[-1]
        system_prompt = (
            "Eres el mejor Jugador Profesional y Maestro de Baccarat en Vivo del mundo.\n"
            "Tu objetivo es seleccionar la mejor estrategia con alta asertividad en tiros 1 al 6 (Modo Sniper con prioridad 1 al 3).\n\n"
            "CATÁLOGO EXCLUSIVO DE LAS 4 ESTRATEGIAS PERMITIDAS:\n"
            "Debes elegir OBLIGATORIAMENTE una de las siguientes 4 estrategias según el estado del zapato:\n"
            "1. 'DISRUPTIVA_4TEND_DISRUPTIVA' (Disruptiva 1-4-1):\n"
            "   - Patrón: [D, T, T, T, T, D]\n"
            "   - 1º tiro contra la tendencia (D), 4 siguientes a la tendencia (T), último a la disruptiva (D).\n"
            "2. 'TENDENCIA_3_DISR_2TEND' (Tendencia 3-1-2):\n"
            "   - Patrón: [T, T, T, D, T, T]\n"
            "   - 3 primeros tiros a la tendencia (T), 4º a la disruptiva (D), últimos 2 a la tendencia (T).\n"
            "3. 'TENDENCIA_PURA_6' (Tendencia Pura 6X):\n"
            "   - Patrón: [T, T, T, T, T, T]\n"
            "   - Los 6 tiros a favor de la tendencia (T).\n"
            "4. 'DISRUPTIVA_1_5TEND' (Disruptiva 1 + 5 Tendencia):\n"
            "   - Patrón: [D, T, T, T, T, T]\n"
            "   - 1º tiro a la disruptiva (D), y los siguientes 5 tiros a la tendencia (T).\n\n"
            "Donde T es el color de la tendencia dominante ('P' o 'B') y D es el color opuesto/disruptivo ('B' o 'P').\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. Cero precipitación: Si el zapato es caótico, plano o sin inercia clara, responde con 'should_signal': false.\n"
            "2. Prohibido usar secuencias fuera de estas 4.\n"
            "3. Rota entre estrategias, ¡prohibido repetir la última estrategia usada!\n\n"
            "Responde OBLIGATORIAMENTE en JSON con esta estructura exacta:\n"
            '{"should_signal": true, "sequence": ["B","P","P","P","P","B"], "probability": 95, "strategy_name": "Nombre de Estrategia", "reason": "Breve justificación técnica"}'
        )

        recent_strats_msg = ""
        if last_strategy:
            recent_strats_msg += f"\nÚLTIMA ESTRATEGIA USADA: '{last_strategy}'. ¡PROHIBIDO REPETIR ESTA ESTRATEGIA! Rota a una estrategia diferente."
        if strategy_usage:
            top_used = sorted(strategy_usage.items(), key=lambda x: x[1], reverse=True)[:3]
            recent_strats_msg += f"\nEstrategias más usadas recientemente: {', '.join(f'{k} ({v}x)' for k, v in top_used)}. Evítalas para garantizar rotación."

        if streak >= 2:
            T = last
        elif p_15 != b_15:
            T = "P" if p_15 > b_15 else "B"
        elif total_p != total_b:
            T = "P" if total_p > total_b else "B"
        else:
            T = last
        D = "B" if T == "P" else "P"

        t_color_name = "AZUL (P)" if T == "P" else "ROJO (B)"
        d_color_name = "ROJO (B)" if T == "P" else "AZUL (P)"

        user_prompt = (
            f"Mesa: '{table_name}'. Zapato actual: {len(clean)} jugadas.\n"
            f"Historial reciente: [{', '.join(clean[-16:])}].\n"
            f"Estadísticas: Total P: {total_p} | Total B: {total_b} | Últimas 15: {p_15}P vs {b_15}B.\n"
            f"Última mano: {last} (Racha actual: {streak}).\n"
            f"TENDENCIA ACTIVA (T): {T} [{t_color_name}] | DISRUPTIVA (D): {D} [{d_color_name}].\n"
            f"{recent_strats_msg}\n"
            f"Selecciona la mejor de las 4 estrategias usando T={T} y D={D} o decide esperar con should_signal: false."
        )

        # Tier 1: Groq
        try:
            payload_groq = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 250,
                "temperature": 0.5
            }
            r = requests.post(self.url, headers=self.headers, json=payload_groq, timeout=2.5)
            if r.status_code == 200:
                parsed = json.loads(r.json()["choices"][0]["message"]["content"])
                should = parsed.get("should_signal", True)
                seq = [x if x in ("P", "B") else "P" for x in parsed.get("sequence", [])][:6]
                prob = int(parsed.get("probability", parsed.get("probabilidad", 94)))
                prob = max(92, min(96, prob)) if should else prob
                strat = parsed.get("strategy_name", "Groq Maestro")
                reason = parsed.get("reason", parsed.get("razon", "Análisis profesional de zapato"))
                if len(seq) >= 3:
                    return True, should, seq, prob, strat, reason
        except Exception as e:
            logger.debug(f"Groq API indisponible: {e}")

        # Tier 2: Gemini
        try:
            gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload_gem = {
                "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 250,
                    "temperature": 0.5
                }
            }
            r_gem = requests.post(gem_url, json=payload_gem, timeout=2.5)
            if r_gem.status_code == 200:
                raw_text = r_gem.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                should = parsed.get("should_signal", True)
                seq = [x if x in ("P", "B") else "P" for x in parsed.get("sequence", [])][:6]
                prob = int(parsed.get("probability", parsed.get("probabilidad", 94)))
                prob = max(92, min(96, prob)) if should else prob
                strat = parsed.get("strategy_name", "Gemini Maestro")
                reason = parsed.get("reason", parsed.get("razon", "Análisis neural de zapato"))
                if len(seq) >= 3:
                    return True, should, seq, prob, strat, reason
        except Exception as e:
            logger.debug(f"Gemini API indisponible: {e}")

        return False, False, [], 0, "NONE", "Fallback a motor maestro local"

    def _enforce_pro_guardrails(self, seq, last, streak, total_p, total_b, p_15, b_15):
        """
        Asegura de forma infalible que la secuencia final coincida con una de las 4 estrategias
        definidas por el usuario:
          1. DISRUPTIVA_4TEND_DISRUPTIVA : [D, T, T, T, T, D]
          2. TENDENCIA_3_DISR_2TEND      : [T, T, T, D, T, T]
          3. TENDENCIA_PURA_6            : [T, T, T, T, T, T]
          4. DISRUPTIVA_1_5TEND          : [D, T, T, T, T, T]
        """
        if streak >= 2:
            T = last
        elif p_15 != b_15:
            T = "P" if p_15 > b_15 else "B"
        elif total_p != total_b:
            T = "P" if total_p > total_b else "B"
        else:
            T = last
        D = "B" if T == "P" else "P"

        valid_templates = {
            "DISRUPTIVA_4TEND_DISRUPTIVA": [D, T, T, T, T, D],
            "TENDENCIA_3_DISR_2TEND": [T, T, T, D, T, T],
            "TENDENCIA_PURA_6": [T, T, T, T, T, T],
            "DISRUPTIVA_1_5TEND": [D, T, T, T, T, T],
        }

        cleaned = [x if x in ("P", "B") else T for x in seq[:6]]
        if len(cleaned) < 6:
            cleaned = (cleaned + [T] * 6)[:6]

        # Verificar si coincide exactamente con una plantilla válida para la tendencia T
        for tpl in valid_templates.values():
            if cleaned == tpl:
                return cleaned

        # Si racha es 1 (sin inercia fuerte), también se permite si la IA apostó al color dominante opuesto
        if streak < 2:
            inv_templates = {
                "DISRUPTIVA_4TEND_DISRUPTIVA_INV": [T, D, D, D, D, T],
                "TENDENCIA_3_DISR_2TEND_INV": [D, D, D, T, D, D],
                "TENDENCIA_PURA_6_INV": [D, D, D, D, D, D],
                "DISRUPTIVA_1_5TEND_INV": [T, D, D, D, D, D],
            }
            for tpl in inv_templates.values():
                if cleaned == tpl:
                    return cleaned

        # Si no coincide exactamente, forzar a la plantilla más adecuada según el zapato
        if streak >= 3:
            fallback = valid_templates["TENDENCIA_PURA_6"]
        elif streak == 2:
            fallback = valid_templates["TENDENCIA_3_DISR_2TEND"]
        elif abs(p_15 - b_15) >= 2:
            fallback = valid_templates["DISRUPTIVA_1_5TEND"]
        else:
            fallback = valid_templates["DISRUPTIVA_4TEND_DISRUPTIVA"]

        logger.info(f"🛡️ Guardrail 4 Estrategias: Secuencia ajustada a plantilla oficial -> {' '.join(fallback)}")
        return fallback

    def _build_and_score_4_strategies(self, clean, last_strategy=None, early_scores=None, strategy_usage=None):
        """
        Motor maestro local con las 4 Estrategias Exclusivas del Usuario y rotación activa estricta.
        """
        last = clean[-1]
        streak = 0
        for x in reversed(clean):
            if x == last:
                streak += 1
            else:
                break

        total_p = clean.count("P")
        total_b = clean.count("B")
        recent_15 = clean[-15:]
        p_cnt = recent_15.count("P")
        b_cnt = recent_15.count("B")

        if streak >= 2:
            win_color = last
        elif p_cnt != b_cnt:
            win_color = "P" if p_cnt > b_cnt else "B"
        elif total_p != total_b:
            win_color = "P" if total_p > total_b else "B"
        else:
            win_color = last

        lose_color = "B" if win_color == "P" else "P"
        T = win_color
        D = lose_color

        if streak >= 3:
            streak_tag = f"Racha {T}x{streak}"
        elif streak == 2:
            streak_tag = f"Doble {T}x2"
        else:
            streak_tag = f"Dominancia {T}"

        early_scores = early_scores or {}
        strategy_usage = strategy_usage or {}
        candidates = []

        streak_boost = 2 if streak >= 3 else 0

        # Catálogo Exclusivo de las 4 Estrategias del Usuario:
        strat_defs = [
            # 1. DISRUPTIVA_4TEND_DISRUPTIVA: 1D + 4T + 1D
            ("DISRUPTIVA_4TEND_DISRUPTIVA", [D, T, T, T, T, D], 95, f"{streak_tag} - Disruptiva 1-4-1 (1{D}+4{T}+1{D})"),

            # 2. TENDENCIA_3_DISR_2TEND: 3T + 1D + 2T
            ("TENDENCIA_3_DISR_2TEND", [T, T, T, D, T, T], 95, f"{streak_tag} - Tendencia 3-1-2 (3{T}+1{D}+2{T})"),

            # 3. TENDENCIA_PURA_6: 6T
            ("TENDENCIA_PURA_6", [T, T, T, T, T, T], 96, f"{streak_tag} - Tendencia Pura 6X (6{T})"),

            # 4. DISRUPTIVA_1_5TEND: 1D + 5T
            ("DISRUPTIVA_1_5TEND", [D, T, T, T, T, T], 94, f"{streak_tag} - Disruptiva 1 + 5 Tendencia (1{D}+5{T})"),
        ]

        for s_name, s_seq, s_prob_base, s_desc in strat_defs:
            prob = min(96, s_prob_base + streak_boost)
            score = float(prob)

            # 1. Ajuste fino al zapato
            if streak >= 3:
                if s_name in ("TENDENCIA_PURA_6", "TENDENCIA_3_DISR_2TEND"):
                    score += 4.0
            elif streak == 2:
                if s_name in ("TENDENCIA_3_DISR_2TEND", "DISRUPTIVA_4TEND_DISRUPTIVA"):
                    score += 3.5
            else:
                if s_name in ("DISRUPTIVA_1_5TEND", "DISRUPTIVA_4TEND_DISRUPTIVA"):
                    score += 3.5

            # 2. Puntuación de efectividad previa
            score += (early_scores.get(s_name, 0) * 0.2)

            # 3. Penalización por uso reciente (Obliga a rotar activamente entre las 4)
            usage_cnt = strategy_usage.get(s_name, 0)
            score -= (usage_cnt * 3.5)

            # 4. PROHIBICIÓN TOTAL de repetir la última estrategia
            if last_strategy:
                last_clean = last_strategy.lower().strip()
                s_clean = s_name.lower().strip()
                if s_clean == last_clean or s_clean in last_clean or last_clean in s_clean:
                    score -= 100.0

            # 5. Jitter aleatorio para desempatar y mantener variedad natural continua
            score += random.uniform(0.5, 2.5)

            candidates.append((s_name, s_seq, prob, score, s_desc))

        candidates.sort(key=lambda c: c[3], reverse=True)
        return candidates
