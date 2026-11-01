"""
core/stats_tracker.py
=====================
Rastreador de Estadísticas, Autoanalizador de Rendimiento Rodante (Últimas 30 Partidas)
y Ranking Dinámico de Efectividad por Estrategia (Prioridad a Tiros Bajos 1 al 3).
"""

import os
import json
import logging

logger = logging.getLogger("StatsTracker")

STATS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "signal_stats.json")
ROLLING_WINDOW = 30
MAX_HISTORY_SAVED = 100


class StatsTracker:
    def __init__(self):
        self.file_path = STATS_FILE
        self.history = self._load()
        self.table_cooldowns = {}
        self.table_consecutive_plays = {}

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data[-MAX_HISTORY_SAVED:]
            except Exception as e:
                logger.error(f"Error cargando estadísticas: {e}")
        return []

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.history[-MAX_HISTORY_SAVED:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando estadísticas: {e}")

    def record_win(self, table_name, attempt_number, strategy_name=None):
        """Registra una victoria en el intento N (1-6) y la estrategia utilizada."""
        att = int(attempt_number)
        entry = {
            "table": table_name,
            "result": "win",
            "attempt": att,
            "strategy": strategy_name or "TREND_FOLLOW"
        }
        self.history.append(entry)
        self._save()
        logger.info(f"Estadística registrada: WIN en intento {attempt_number} (Mesa {table_name}, Estrategia: {strategy_name})")

        # Control de salud de la mesa (Prioridad Tiros 1 al 3):
        if att >= 4:
            # TIRO ALTO (4, 5 o 6): Enfriamiento obligatorio para rotar a otra mesa
            cooldown_cycles = 1 if att == 4 else (2 if att == 5 else 3)
            self.set_table_cooldown(table_name, cooldown_cycles)
            self.table_consecutive_plays[table_name] = 0
            logger.warning(f"[SALUD MESA] ⚠️ [{table_name}] registró TIRO ALTO (WIN {att}). Enfriamiento forzado por {cooldown_cycles} ciclo(s) para cambiar de mesa.")
        else:
            # TIRO BAJO (1, 2 o 3): Mesa saludable
            consec = self.table_consecutive_plays.get(table_name, 0) + 1
            self.table_consecutive_plays[table_name] = consec
            if consec >= 4:
                # Si se juegan 4 victorias seguidas en la misma mesa, pausa preventiva de 1 ciclo para no agotar el zapato
                self.set_table_cooldown(table_name, 1)
                self.table_consecutive_plays[table_name] = 0
                logger.info(f"[SALUD MESA] 🔄 [{table_name}] acumuló {consec} victorias consecutivas. Pausa preventiva de 1 ciclo.")

    def record_loss(self, table_name, strategy_name=None):
        """Registra una derrota (LOSS tras 6 intentos)."""
        entry = {
            "table": table_name,
            "result": "loss",
            "attempt": 6,
            "strategy": strategy_name or "TREND_FOLLOW"
        }
        self.history.append(entry)
        self._save()
        logger.info(f"Estadística registrada: LOSS en Mesa {table_name} (Estrategia: {strategy_name})")

        # LOSS: Enfriamiento crítico de 4 ciclos para no volver a entrar en esa mesa
        self.set_table_cooldown(table_name, 4)
        self.table_consecutive_plays[table_name] = 0
        logger.warning(f"[SALUD MESA] 🚫 [{table_name}] sufrió LOSS. Mesa puesta en cuarentena/enfriamiento por 4 ciclos.")

    def set_table_cooldown(self, table_name, cycles):
        self.table_cooldowns[table_name] = max(self.table_cooldowns.get(table_name, 0), cycles)

    def is_table_cooling_down(self, table_name):
        return self.table_cooldowns.get(table_name, 0) > 0

    def get_table_cooldown(self, table_name):
        return self.table_cooldowns.get(table_name, 0)

    def decrement_table_cooldowns(self):
        """Decrementa en 1 los contadores de enfriamiento activos al iniciar un nuevo ciclo."""
        for t in list(self.table_cooldowns.keys()):
            if self.table_cooldowns[t] > 0:
                self.table_cooldowns[t] -= 1
                if self.table_cooldowns[t] == 0:
                    logger.info(f"[SALUD MESA] ❄️➡️✨ Mesa [{t}] ha completado su enfriamiento y vuelve a estar disponible.")

    def get_table_history(self, table_name, limit=6):
        """Retorna las últimas N partidas jugadas en esa mesa específica."""
        return [e for e in self.history if e.get("table") == table_name][-limit:]

    def get_table_momentum_score(self, table_name):
        """
        Calcula el bono/penalización de momento para una mesa según sus últimas jugadas:
        - Última jugada WIN 1: +5 pts (Excelente)
        - Última jugada WIN 2: +3 pts
        - Última jugada WIN 3: +1 pt
        - Última jugada WIN 4: -10 pts (Alerta de tiro alto)
        - Última jugada WIN 5: -20 pts (Fuerte penalización)
        - Última jugada WIN 6: -30 pts (Penalización severa)
        - Última jugada LOSS: -50 pts (Penalización crítica)
        - Racha reciente acumulada (últimas 3 partidas en esa mesa):
          * Si acumula tiros altos (2+): -15 pts adicionales
          * Si acumula tiros bajos (2+) sin tiros altos: +3 pts adicionales
        """
        table_hist = self.get_table_history(table_name, limit=3)
        if not table_hist:
            return 0.0  # Mesa fresca: neutral

        last = table_hist[-1]
        score = 0.0

        res = last.get("result")
        att = int(last.get("attempt", 1))

        if res == "loss":
            score -= 50.0
        elif att == 1:
            score += 5.0
        elif att == 2:
            score += 3.0
        elif att == 3:
            score += 1.0
        elif att == 4:
            score -= 10.0
        elif att == 5:
            score -= 20.0
        elif att == 6:
            score -= 30.0

        recent_highs = sum(1 for e in table_hist if e.get("result") == "loss" or int(e.get("attempt", 1)) >= 4)
        recent_lows = sum(1 for e in table_hist if e.get("result") == "win" and int(e.get("attempt", 1)) <= 3)

        if recent_highs >= 2:
            score -= 15.0  # Múltiples tiros altos acumulados
        elif recent_lows >= 2 and recent_highs == 0:
            score += 3.0   # Racha consistente de tiros bajos

        return score

    def get_table_health_label(self, table_name):
        """Retorna una etiqueta visual del estado de salud de la mesa."""
        if self.is_table_cooling_down(table_name):
            rem = self.get_table_cooldown(table_name)
            return f"❄️ EN REPOSO ({rem}c)"

        table_hist = self.get_table_history(table_name, limit=3)
        if not table_hist:
            return "✨ FRESCA"

        last = table_hist[-1]
        res = last.get("result")
        att = int(last.get("attempt", 1))

        if res == "loss":
            return "💔 POST-LOSS"
        elif att <= 3:
            low_count = sum(1 for e in table_hist if e.get("result") == "win" and int(e.get("attempt", 1)) <= 3)
            return f"🔥 CALIENTE (WIN {att}, {low_count}x bajas)"
        else:
            return f"⚠️ DESGASTE (WIN {att})"


    def get_last_strategy(self):
        """Retorna la última estrategia utilizada para evitar repetición continua."""
        if not self.history:
            return None
        return self.history[-1].get("strategy")

    def get_recent_strategy_usage(self, limit=12):
        """Retorna cuántas veces se ha usado cada estrategia en las últimas N partidas."""
        from collections import defaultdict
        usage = defaultdict(int)
        recent = self.history[-limit:]
        for e in recent:
            st = e.get("strategy")
            if st:
                usage[st] += 1
        return dict(usage)

    def get_strategy_early_win_scores(self):
        """
        Calcula la efectividad de cada estrategia en tiros bajos (1 al 3) — Modo Sniper:
        - Tiro 1 (WIN 1): +5 pts (Premio máximo por acierto inmediato)
        - Tiro 2 (WIN 2): +3 pts
        - Tiro 3 (WIN 3): +1 pt
        - Tiro 4 (WIN 4): -3 pts (Penalización por tiro alto)
        - Tiro 5 (WIN 5): -5 pts (Fuerte penalización por tiro alto)
        - Tiro 6 (WIN 6): -7 pts (Severa penalización)
        - Derrota (LOSS): -10 pts (Penalización crítica)
        """
        from collections import defaultdict
        scores = defaultdict(int)
        recent = self.history[-ROLLING_WINDOW:]
        for e in recent:
            st = e.get("strategy")
            if st:
                res = e.get("result")
                att = int(e.get("attempt", 6))
                if res == "win":
                    if att == 1:
                        scores[st] += 5
                    elif att == 2:
                        scores[st] += 3
                    elif att == 3:
                        scores[st] += 1
                    elif att == 4:
                        scores[st] -= 3
                    elif att == 5:
                        scores[st] -= 5
                    elif att == 6:
                        scores[st] -= 7
                else:
                    scores[st] -= 10
        return dict(scores)

    def was_last_result_loss(self):
        """Retorna True si la última partida registrada terminó en LOSS."""
        if not self.history:
            return False
        return self.history[-1].get("result") == "loss"

    def get_stats_summary(self):
        """
        Retorna el análisis rodante de las últimas 30 partidas reales.
        """
        total_history = len(self.history)
        if total_history == 0:
            return {
                "total": 0,
                "sample_size": 0,
                "wins": 0,
                "losses": 0,
                "wins_1_3": 0,
                "wins_4_6": 0,
                "winrate": 100,
                "recommendation": "Basado en el autoanálisis (últimas 30 partidas), mayor efectividad en <b>tiros 1 al 3</b> (Bajos)."
            }

        sample = self.history[-ROLLING_WINDOW:]
        sample_size = len(sample)

        wins = sum(1 for e in sample if e.get("result") == "win")
        losses = sum(1 for e in sample if e.get("result") == "loss")

        # Tiros 1, 2 y 3 (Bajos)
        wins_1_3 = sum(1 for e in sample if e.get("result") == "win" and int(e.get("attempt", 6)) <= 3)

        # Tiros 4, 5, 6 o Loss (Altos)
        wins_4_6 = sum(1 for e in sample if (e.get("result") == "win" and int(e.get("attempt", 0)) >= 4) or e.get("result") == "loss")

        winrate = int((wins / sample_size) * 100) if sample_size > 0 else 0

        # Autoanálisis del Rush de las últimas 30 partidas
        if wins_1_3 >= wins_4_6:
            rec = f"Basado en el autoanálisis (últimas {sample_size} partidas), mayor efectividad en <b>tiros 1 al 3</b> (Bajos)."
        else:
            rec = f"Basado en el autoanálisis (últimas {sample_size} partidas), el rush muestra efectividad en <b>tiros 4 al 6</b> (Altos)."

        return {
            "total": total_history,
            "sample_size": sample_size,
            "wins": wins,
            "losses": losses,
            "wins_1_3": wins_1_3,
            "wins_4_6": wins_4_6,
            "winrate": winrate,
            "recommendation": rec
        }
