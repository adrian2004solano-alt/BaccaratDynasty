"""
core/ai_analyzer.py  — v24 (Motor Multi-Estrategia Dinámica: Máx 20% Mono-Color / 80% Combinaciones Mixtas)
=============================================================================================================
Motor de Inteligencia Artificial para Baccarat en vivo con calibración VIP:
  1. REGLA ESTRICTA DE DISTRIBUCIÓN:
     - Máximo 20% de las jugadas pueden ser Mono-Color (6 tiros al mismo color).
     - Mínimo 80% de las jugadas DEBEN ligar y combinar colores de forma inteligente.
  2. CATÁLOGO COMPLETO DE ESTRATEGIAS:
     - 1. ALTERNANCIA_PINGPONG     : [D, T, D, T, D, T] (Zig-Zag / Chop)
     - 2. DOBLES_PAREJAS           : [T, T, D, D, T, T] (Tren de Parejas 2-2)
     - 3. DISRUPTIVA_1_4_1         : [D, T, T, T, T, D] (Disruptiva Sándwich 1-4-1)
     - 4. TENDENCIA_3_1_2          : [T, T, T, D, T, T] (Tendencia Escalonada 3-1-2)
     - 5. QUIEBRE_ESCALONADO_2_1   : [T, T, D, T, T, D] (Quiebre Progresivo 2-1-2-1)
     - 6. TERCIAS_BLOQUE_3_3       : [T, T, T, D, D, D] (Bloques Tercias 3-3)
     - 7. TRANSICION_2_4           : [D, D, T, T, T, T] (Doble Giro + 4 Arrastre)
     - 8. PATRON_ESPEJO            : [T, D, D, T, T, D] (Patrón Espejo Swing)
     - 9. DISRUPTIVA_1_5           : [D, T, T, T, T, T] (1 Contra + 5 Tendencia)
     - 10. TENDENCIA_PURA_6        : [T, T, T, T, T, T] (Mono-Color 6X — LIMITADA A MÁX 20%)
  3. ROTACIÓN ACTIVA Y ASÍNTOTA ANTI-REPETICIÓN:
     - Prohibido repetir la última estrategia.
     - Penalización progresiva por sobreuso.
  4. MODO SNIPER (Prioridad Tiros 1 al 3).
"""

import os
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

MAX_MONOCHROME_RATIO = getattr(config, "MAX_MONOCHROME_RATIO", 0.20)


class GeminiBaccaratAnalyzer:
    """
    Analizador de Baccarat Profesional — Motor de 10 Estrategias Dinámicas.
    Equipado con arquitectura multimodelo de IA (Groq -> Gemini -> Motor Maestro Local)
    y estricto control de distribución (Máx 20% Mono-Color / 80% Combinaciones Mixtas).
    """
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        self.url = GROQ_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def check_mono_allowed(self, stats_tracker=None):
        """
        Regla de Oro: El Mono-Color (6 tiros al mismo color) NUNCA debe superar el 20%.
        Verifica la cuota reciente en StatsTracker o signal_stats.json y un tiro de probabilidad (20%).
        """
        if stats_tracker and hasattr(stats_tracker, "is_mono_allowed"):
            return stats_tracker.is_mono_allowed(max_ratio=MAX_MONOCHROME_RATIO)

        # Fallback de lectura directa de estadísticas en disco
        try:
            from core.stats_tracker import STATS_FILE
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        recent = data[-10:]
                        mono_cnt = sum(1 for x in recent if "PURA" in x.get("strategy", "").upper() or "MONO" in x.get("strategy", "").upper())
                        if (mono_cnt / len(recent)) >= MAX_MONOCHROME_RATIO:
                            return False
        except Exception:
            pass

        return random.random() < MAX_MONOCHROME_RATIO

    def _detect_shoe_patterns(self, clean):
        """
        Analiza profundamente la estructura del zapato en tiempo real:
        - streak: longitud de la racha actual del último resultado
        - is_chopping: si el zapato reciente está en alternancia (Ping-Pong / Zig-Zag)
        - is_pairing: si el zapato reciente forma bloques de parejas (2-2)
        - T: color de tendencia / dominante
        - D: color disruptivo / opuesto
        """
        last = clean[-1]
        streak = 0
        for x in reversed(clean):
            if x == last:
                streak += 1
            else:
                break

        # Alternancia / Ping-Pong: detectar cambios de color en las últimas 8 manos
        recent_8 = clean[-8:]
        changes = sum(1 for i in range(len(recent_8) - 1) if recent_8[i] != recent_8[i+1])
        is_chopping = (changes >= 5)

        # Parejas: detectar si los runs recientes son de longitud 2
        runs = []
        curr_len = 1
        for i in range(1, len(clean[-12:])):
            if clean[-12:][i] == clean[-12:][i-1]:
                curr_len += 1
            else:
                runs.append(curr_len)
                curr_len = 1
        runs.append(curr_len)
        pairs_count = sum(1 for r in runs if r == 2)
        is_pairing = (pairs_count >= 2 and streak <= 2)

        total_p = clean.count("P")
        total_b = clean.count("B")
        recent_15 = clean[-15:]
        p_15 = recent_15.count("P")
        b_15 = recent_15.count("B")

        if streak >= 2:
            T = last
        elif is_chopping:
            T = last
        elif p_15 != b_15:
            T = "P" if p_15 > b_15 else "B"
        elif total_p != total_b:
            T = "P" if total_p > total_b else "B"
        else:
            T = last

        D = "B" if T == "P" else "P"
        return streak, is_chopping, is_pairing, T, D, total_p, total_b, p_15, b_15

    def analyze(self, table_name, history, last_strategy=None, early_scores=None, strategy_usage=None, stats_tracker=None):
        """
        Analiza el historial buscando ventaja real con el catálogo dinámico de estrategias.
        Aplica estrictamente el límite del 20% para mono-color y 80% combinaciones mixtas.
        Retorna: (should_signal, sequence, probability, strategy_name, reason)
        """
        if not history or len(history) < 8 or len(history) >= 65:
            return False, [], 0, "NONE", "Historial fuera de rango permitido (8 a 64 jugadas)"

        # Regla: No emitir señal inmediata tras un Empate ('T')
        if history[-1] == "T":
            return False, [], 0, "NONE", "Pausa: Empate reciente (esperando definición)"

        clean = [x for x in history if x in ("P", "B")]
        if len(clean) < 8:
            return False, [], 0, "NONE", "Historial insuficiente de jugadas limpias (< 8)"

        # Detección de patrones del zapato
        streak, is_chopping, is_pairing, T, D, total_p, total_b, p_15, b_15 = self._detect_shoe_patterns(clean)
        last = clean[-1]

        # Filtro de Calma y Profundidad:
        # Si no hay racha (streak < 2), tampoco hay alternancia clara (no chopping), ni parejas,
        # y la diferencia en 15 manos es <= 1, la mesa está plana/indecisa.
        if streak < 2 and not is_chopping and not is_pairing and abs(p_15 - b_15) <= 1:
            return False, [], 0, "NONE", "Mesa indecisa / Sin patrón definido (esperando confirmación)"

        # Control Estricto de Cuota 20% Mono-Color
        allow_mono = self.check_mono_allowed(stats_tracker)

        # ── 1. CONSULTA A IA CON FALLBACK INTELIGENTE (Groq -> Gemini) ──
        try:
            ai_ok, ai_should, ai_seq, ai_prob, ai_strat, ai_reason = self._consult_pro_player_ai(
                table_name, clean, streak, is_chopping, is_pairing, T, D, total_p, total_b, p_15, b_15,
                last_strategy=last_strategy, strategy_usage=strategy_usage, allow_mono=allow_mono
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
                    valid_seq, final_strat = self._enforce_pro_guardrails(
                        ai_seq, T, D, streak, is_chopping, is_pairing, allow_mono=allow_mono, strat_name=ai_strat
                    )
                    logger.info(f"[{table_name}] 🧠 IA Profesional ({final_strat} | {ai_prob}%): {' '.join(valid_seq)}")
                    return True, valid_seq[:6], ai_prob, final_strat, ai_reason
            elif ai_ok and not ai_should:
                logger.info(f"[{table_name}] ✋ IA Profesional decidió PASAR: {ai_reason}")
                return False, [], 0, ai_strat, ai_reason
        except Exception as e:
            logger.warning(f"[{table_name}] Fallback a motor maestro local: {e}")

        # ── 2. MOTOR MAESTRO LOCAL (10 Estrategias Dinámicas con Control 20/80) ──
        strat_candidates = self._build_and_score_strategies(
            clean, streak, is_chopping, is_pairing, T, D, total_p, total_b, p_15, b_15,
            last_strategy=last_strategy, early_scores=early_scores, strategy_usage=strategy_usage, allow_mono=allow_mono
        )
        if not strat_candidates:
            return False, [], 0, "NONE", "Sin patrón claro"

        best_strat_name, best_seq, best_prob, best_score, best_reason = strat_candidates[0]
        valid_seq, final_strat = self._enforce_pro_guardrails(
            best_seq, T, D, streak, is_chopping, is_pairing, allow_mono=allow_mono, strat_name=best_strat_name
        )
        return True, valid_seq[:6], best_prob, final_strat, best_reason

    def _consult_pro_player_ai(self, table_name, clean, streak, is_chopping, is_pairing, T, D,
                                total_p, total_b, p_15, b_15, last_strategy=None, strategy_usage=None, allow_mono=False):
        """Consulta multi-tier a modelos de IA enfocada en el catálogo completo de combinaciones de colores."""
        last = clean[-1]
        t_color_name = "AZUL (P)" if T == "P" else "ROJO (B)"
        d_color_name = "ROJO (B)" if T == "P" else "AZUL (P)"

        system_prompt = (
            "Eres el mejor Jugador Profesional y Maestro de Baccarat en Vivo del mundo.\n"
            "Tu objetivo es seleccionar la mejor estrategia con alta asertividad en tiros 1 al 6 (Modo Sniper con prioridad 1 al 3).\n\n"
            "REGLA SUPREMA DE DISTRIBUCIÓN DE COLORES (ESTRICTA):\n"
            "1. ESTRATEGIA MONO-COLOR (6 tiros al mismo color [T,T,T,T,T,T]): LIMITADA A MÁXIMO 20% DE LAS VECES.\n"
            "2. ESTRATEGIAS DE COLORES COMBINADOS / LIGADOS (80% DE LAS VECES):\n"
            "   Debes combinar y ligar los colores de forma inteligente según el zapato:\n"
            "   - 'ALTERNANCIA_PINGPONG': [D, T, D, T, D, T] (Zig-Zag / Chop cuando la mesa salta de un color a otro).\n"
            "   - 'DOBLES_PAREJAS': [T, T, D, D, T, T] (Tren de Parejas 2-2 cuando la mesa forma dobles).\n"
            "   - 'DISRUPTIVA_1_4_1': [D, T, T, T, T, D] (1 contra la racha, 4 a favor, 1 de cobertura final).\n"
            "   - 'TENDENCIA_3_1_2': [T, T, T, D, T, T] (3 a la tendencia, 1 quiebre en tiro 4, 2 a la tendencia).\n"
            "   - 'QUIEBRE_ESCALONADO_2_1': [T, T, D, T, T, D] (2 a favor, 1 en contra, 2 a favor, 1 en contra).\n"
            "   - 'TERCIAS_BLOQUE_3_3': [T, T, T, D, D, D] (3 a favor, 3 en contra).\n"
            "   - 'TRANSICION_2_4': [D, D, T, T, T, T] (2 a la disruptiva para cazar el giro, 4 a la tendencia).\n"
            "   - 'PATRON_ESPEJO': [T, D, D, T, T, D] (Patrón espejo swing).\n"
            "   - 'DISRUPTIVA_1_5': [D, T, T, T, T, T] (1 contra-tendencia inicial y 5 de arrastre).\n"
            "   - 'TENDENCIA_PURA_6': [T, T, T, T, T, T] (Mono-Color 6X — SOLO si la cuota lo permite).\n\n"
            f"{'⛔ CUOTA MONO-COLOR CERRADA: Está terminantemente PROHIBIDO lanzar 6 tiros al mismo color en esta jugada. DEBES usar obligatoriamente una estrategia con COLORES COMBINADOS.' if not allow_mono else '⚠️ Mono-Color permitido solo si el zapato muestra una racha extraordinaria (>=4).'}\n\n"
            "Donde T es la tendencia dominante ('P' o 'B') y D es la disruptiva opuesta ('B' o 'P').\n"
            "REGLAS ADICIONALES:\n"
            "1. Cero precipitación: Si el zapato está caótico o sin patrón claro, responde con 'should_signal': false.\n"
            "2. Rota entre estrategias, ¡prohibido repetir la última estrategia jugada!\n\n"
            "Responde OBLIGATORIAMENTE en JSON con esta estructura exacta:\n"
            '{"should_signal": true, "sequence": ["B","P","B","P","B","P"], "probability": 95, "strategy_name": "Nombre de Estrategia", "reason": "Breve justificación técnica"}'
        )

        recent_strats_msg = ""
        if last_strategy:
            recent_strats_msg += f"\nÚLTIMA ESTRATEGIA USADA: '{last_strategy}'. ¡PROHIBIDO REPETIR ESTA ESTRATEGIA! Rota a una estrategia diferente."
        if strategy_usage:
            top_used = sorted(strategy_usage.items(), key=lambda x: x[1], reverse=True)[:3]
            recent_strats_msg += f"\nEstrategias más usadas recientemente: {', '.join(f'{k} ({v}x)' for k, v in top_used)}. Evítalas para garantizar rotación."

        pattern_hints = []
        if is_chopping:
            pattern_hints.append("Mesa en ALTERNANCIA (Ping-Pong / Chop activo)")
        if is_pairing:
            pattern_hints.append("Mesa en TREN DE PAREJAS (bloques de 2-2)")
        if streak >= 3:
            pattern_hints.append(f"Mesa con RACHA ACTIVA de {streak}x {T}")

        user_prompt = (
            f"Mesa: '{table_name}'. Zapato actual: {len(clean)} jugadas.\n"
            f"Historial reciente: [{', '.join(clean[-16:])}].\n"
            f"Estadísticas: Total P: {total_p} | Total B: {total_b} | Últimas 15: {p_15}P vs {b_15}B.\n"
            f"Última mano: {last} (Racha actual: {streak}).\n"
            f"Patrones detectados: {', '.join(pattern_hints) if pattern_hints else 'Evolución normal'}.\n"
            f"TENDENCIA ACTIVA (T): {T} [{t_color_name}] | DISRUPTIVA (D): {D} [{d_color_name}].\n"
            f"{recent_strats_msg}\n"
            f"Selecciona la mejor estrategia combinando T={T} y D={D} o decide esperar con should_signal: false."
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
            r = requests.post(self.url, headers=self.headers, json=payload_groq, timeout=5)
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
            r_gem = requests.post(gem_url, json=payload_gem, timeout=5)
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

    def _enforce_pro_guardrails(self, seq, T, D, streak, is_chopping, is_pairing, allow_mono=False, strat_name=None):
        """
        Asegura de forma infalible que la secuencia final sea una lista válida de 6 tiros ('P' o 'B')
        y aplica la regla estricta: MÁXIMO 20% MONO-COLOR / 80% COMBINACIONES DE COLORES.
        Si la secuencia es mono-color y allow_mono es False, se convierte automáticamente
        en la mejor combinación mixta adaptada al zapato.
        """
        cleaned = [x if x in ("P", "B") else T for x in seq[:6]]
        if len(cleaned) < 6:
            cleaned = (cleaned + [T] * 6)[:6]

        # Comprobación de mono-color (los 6 tiros del mismo color)
        is_monochrome = (len(set(cleaned)) == 1)

        final_strat = strat_name or "ESTRATEGIA_COMBINADA"

        if is_monochrome and not allow_mono:
            # BLINDAJE 20%: Convertir inmediatamente a combinación mixta según el comportamiento del zapato
            if is_chopping:
                cleaned = [D, T, D, T, D, T]
                final_strat = "ALTERNANCIA_PINGPONG"
            elif is_pairing or streak == 2:
                cleaned = [T, T, D, D, T, T]
                final_strat = "DOBLES_PAREJAS"
            elif streak >= 3:
                cleaned = [T, T, T, D, T, T]
                final_strat = "TENDENCIA_3_1_2"
            else:
                cleaned = [D, T, T, T, T, D]
                final_strat = "DISRUPTIVA_1_4_1"

            logger.info(f"🛡️ Guardrail 20% Mono: Secuencia convertida a combinación mixta [{final_strat}] -> {' '.join(cleaned)}")

        return cleaned, final_strat

    def _build_and_score_strategies(self, clean, streak, is_chopping, is_pairing, T, D, total_p, total_b, p_15, b_15,
                                    last_strategy=None, early_scores=None, strategy_usage=None, allow_mono=False):
        """
        Motor maestro local con el catálogo completo de combinaciones dinámicas
        y control probabilístico estricto (Máximo 20% Mono-Color / 80% Combinaciones Mixtas).
        """
        early_scores = early_scores or {}
        strategy_usage = strategy_usage or {}

        streak_tag = f"Racha {T}x{streak}" if streak >= 3 else (f"Doble {T}x2" if streak == 2 else f"Dominancia {T}")

        candidates = []

        # ── CATÁLOGO DE COMBINACIONES DE COLORES ("Ligar Colores") ──
        strat_defs = [
            # 1. ALTERNANCIA_PINGPONG: Zig-Zag / Chop
            ("ALTERNANCIA_PINGPONG", [D, T, D, T, D, T], 95, f"{streak_tag} - Alternancia Zig-Zag (Ping-Pong Chop)"),

            # 2. DOBLES_PAREJAS: Tren de Parejas 2-2
            ("DOBLES_PAREJAS", [T, T, D, D, T, T], 95, f"{streak_tag} - Tren de Parejas (2-2-2)"),

            # 3. DISRUPTIVA_1_4_1: Sándwich Disruptivo
            ("DISRUPTIVA_1_4_1", [D, T, T, T, T, D], 95, f"{streak_tag} - Disruptiva Sándwich 1-4-1 (1{D}+4{T}+1{D})"),

            # 4. TENDENCIA_3_1_2: Tendencia Escalonada con Quiebre en Tiro 4
            ("TENDENCIA_3_1_2", [T, T, T, D, T, T], 95, f"{streak_tag} - Tendencia Escalonada 3-1-2 (3{T}+1{D}+2{T})"),

            # 5. QUIEBRE_ESCALONADO_2_1: Doble impacto + quiebre
            ("QUIEBRE_ESCALONADO_2_1", [T, T, D, T, T, D], 94, f"{streak_tag} - Quiebre Escalonado 2-1-2-1 (2{T}+1{D}+2{T}+1{D})"),

            # 6. TERCIAS_BLOQUE_3_3: Bloques de 3
            ("TERCIAS_BLOQUE_3_3", [T, T, T, D, D, D], 94, f"{streak_tag} - Bloques Tercias 3-3 (3{T}+3{D})"),

            # 7. TRANSICION_2_4: Doble contra-ataque y arrastre
            ("TRANSICION_2_4", [D, D, T, T, T, T], 94, f"{streak_tag} - Transición Doble 2+4 (2{D}+4{T})"),

            # 8. PATRON_ESPEJO: Simetría swing
            ("PATRON_ESPEJO", [T, D, D, T, T, D], 94, f"{streak_tag} - Patrón Espejo Swing (1{T}+2{D}+2{T}+1{D})"),

            # 9. DISRUPTIVA_1_5: 1 quiebre inicial y 5 de arrastre
            ("DISRUPTIVA_1_5", [D, T, T, T, T, T], 94, f"{streak_tag} - Disruptiva 1 + 5 Tendencia (1{D}+5{T})"),
        ]

        # 10. TENDENCIA_PURA_6: Mono-Color 6X
        # ESTRICTAMENTE CONDICIONADA A LA CUOTA MÁXIMA DEL 20%
        if allow_mono and streak >= 3:
            strat_defs.append(
                ("TENDENCIA_PURA_6", [T, T, T, T, T, T], 96, f"{streak_tag} - Tendencia Pura 6X (6{T} Mono-Color)")
            )

        for s_name, s_seq, s_prob_base, s_desc in strat_defs:
            prob = s_prob_base
            score = float(prob)

            # 1. PONDERACIÓN POR PATRÓN REAL DEL ZAPATO
            if is_chopping:
                if s_name == "ALTERNANCIA_PINGPONG":
                    score += 6.0
                elif s_name == "QUIEBRE_ESCALONADO_2_1":
                    score += 3.5
            elif is_pairing:
                if s_name == "DOBLES_PAREJAS":
                    score += 6.0
                elif s_name == "QUIEBRE_ESCALONADO_2_1":
                    score += 3.5
            elif streak >= 3:
                if s_name == "TENDENCIA_3_1_2":
                    score += 5.0
                elif s_name == "DISRUPTIVA_1_4_1":
                    score += 4.5
                elif s_name == "TENDENCIA_PURA_6":
                    score += 4.0
                elif s_name == "TERCIAS_BLOQUE_3_3":
                    score += 3.0
            elif streak == 2:
                if s_name in ("DOBLES_PAREJAS", "TENDENCIA_3_1_2"):
                    score += 4.5
                elif s_name in ("DISRUPTIVA_1_4_1", "QUIEBRE_ESCALONADO_2_1"):
                    score += 3.5
            else:
                # streak == 1 (sin racha fuerte)
                if s_name in ("DISRUPTIVA_1_4_1", "TRANSICION_2_4", "PATRON_ESPEJO"):
                    score += 3.5

            # 2. Puntuación de efectividad previa (Modo Sniper 1 al 3)
            score += (early_scores.get(s_name, 0) * 0.2)

            # 3. Penalización por uso reciente (Garantiza rotación continua entre combinaciones)
            usage_cnt = strategy_usage.get(s_name, 0)
            score -= (usage_cnt * 3.5)

            # 4. PROHIBICIÓN TOTAL de repetir la última estrategia jugada
            if last_strategy:
                last_clean = last_strategy.lower().strip()
                s_clean = s_name.lower().strip()
                if s_clean == last_clean or s_clean in last_clean or last_clean in s_clean:
                    score -= 100.0

            # 5. Jitter aleatorio para desempatar y mantener variedad continua
            score += random.uniform(0.5, 2.5)

            candidates.append((s_name, s_seq, prob, score, s_desc))

        candidates.sort(key=lambda c: c[3], reverse=True)
        return candidates
