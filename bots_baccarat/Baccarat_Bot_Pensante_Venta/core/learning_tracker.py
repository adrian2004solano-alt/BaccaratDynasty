"""
core/learning_tracker.py — Sistema de Aprendizaje Acumulativo
=============================================================
Guarda cada senal enviada y su resultado. Con el tiempo aprende:
- Que estrategias ganan en tiro 1-3 (el objetivo prioritario)
- Que tipo de zapato (racha larga, alternancia, neutro) favorece a cada estrategia
- Que mesas tienen mejor rendimiento historico

El LearningTracker se consulta antes de cada analisis de IA para
enriquecer el contexto con datos reales de rendimiento.
"""

import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("LearningTracker")

_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE   = os.path.join(_BASE_DIR, "learning_data.json")
MAX_RECORDS = 500   # Maximo de registros en memoria (circulares)


class LearningTracker:
    def __init__(self):
        self.records = self._load()

    def _load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando learning_data.json: {e}")
        return []

    def _save(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.records[-MAX_RECORDS:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error guardando learning_data.json: {e}")

    def record_signal(self, table_name, history, strategy_name, shoe_length,
                      win_attempt=None, is_loss=False):
        """
        Registra el resultado de una senal.
        win_attempt: 1-6 si gano (o 7-12 en mesa 2), None si fue LOSS.
        is_loss: True si agoto todos los intentos sin ganar.
        """
        clean = [x for x in history if x in ("P", "B")]
        recent = clean[-10:] if len(clean) >= 10 else clean

        # Clasificar tipo de zapato
        if len(recent) >= 4:
            alternating = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
            alt_ratio = alternating / (len(recent) - 1)
            if alt_ratio >= 0.7:
                shoe_type = "alternating"
            elif alt_ratio <= 0.3:
                shoe_type = "streaky"
            else:
                shoe_type = "neutral"
        else:
            shoe_type = "neutral"

        entry = {
            "ts":           datetime.now().isoformat(),
            "table":        table_name,
            "shoe_length":  shoe_length,
            "shoe_type":    shoe_type,
            "strategy":     strategy_name,
            "win_attempt":  win_attempt,
            "is_loss":      is_loss,
            "early_win":    win_attempt is not None and win_attempt <= 3,
        }
        self.records.append(entry)
        self._save()
        logger.info(f"[Learning] Registrado: {table_name} | {strategy_name} | "
                    f"{'WIN tiro ' + str(win_attempt) if win_attempt else 'LOSS'} | Zapato: {shoe_type}")

    def get_summary_for_ai(self, min_records=5):
        """
        Genera un resumen de rendimiento para incluir en el prompt de la IA.
        Solo incluye estrategias con >= min_records registros.
        """
        if not self.records:
            return "Sin datos de aprendizaje aun (primera sesion)."

        # Ultimos 60 dias
        cutoff = (datetime.now() - timedelta(days=60)).isoformat()
        recent = [r for r in self.records if r.get("ts", "") >= cutoff]

        if not recent:
            recent = self.records[-50:]

        # Agrupar por estrategia
        by_strategy = {}
        for r in recent:
            strat = r.get("strategy", "UNKNOWN")
            if strat not in by_strategy:
                by_strategy[strat] = {"total": 0, "wins": 0, "early_wins": 0, "losses": 0}
            by_strategy[strat]["total"] += 1
            if r.get("is_loss"):
                by_strategy[strat]["losses"] += 1
            elif r.get("win_attempt"):
                by_strategy[strat]["wins"] += 1
                if r.get("early_win"):
                    by_strategy[strat]["early_wins"] += 1

        lines = ["HISTORIAL DE RENDIMIENTO REAL (ultimos 60 dias):"]
        sorted_strats = sorted(by_strategy.items(),
                               key=lambda x: x[1]["early_wins"] / max(x[1]["total"], 1),
                               reverse=True)

        for strat, stats in sorted_strats:
            total = stats["total"]
            if total < min_records:
                continue
            wins  = stats["wins"]
            early = stats["early_wins"]
            losses = stats["losses"]
            wr    = int(wins / total * 100) if total else 0
            er    = int(early / total * 100) if total else 0
            lines.append(f"  {strat}: {total} senales | Win Rate: {wr}% | "
                         f"Gano en tiro 1-3: {er}% | LOSS: {losses}")

        # Resumen global
        total_all   = len(recent)
        wins_all    = sum(1 for r in recent if not r.get("is_loss") and r.get("win_attempt"))
        early_all   = sum(1 for r in recent if r.get("early_win"))
        losses_all  = sum(1 for r in recent if r.get("is_loss"))
        global_wr   = int(wins_all / total_all * 100) if total_all else 0
        global_er   = int(early_all / total_all * 100) if total_all else 0

        lines.append(f"GLOBAL: {total_all} senales | Win Rate: {global_wr}% | "
                     f"Gano en tiro 1-3: {global_er}% | LOSS total: {losses_all}")
        lines.append("OBJETIVO: PRIORIZAR estrategias con mayor porcentaje de victoria en tiro 1-3.")

        return "\n".join(lines)

    def get_best_strategy_hint(self, shoe_type="neutral"):
        """
        Retorna la estrategia con mejor tasa de victoria en tiro 1-3 para el tipo de zapato dado.
        """
        if not self.records:
            return None

        relevant = [r for r in self.records[-100:] if r.get("shoe_type") == shoe_type]
        if len(relevant) < 5:
            relevant = self.records[-50:]

        by_strategy = {}
        for r in relevant:
            strat = r.get("strategy", "UNKNOWN")
            if strat not in by_strategy:
                by_strategy[strat] = {"total": 0, "early_wins": 0}
            by_strategy[strat]["total"] += 1
            if r.get("early_win"):
                by_strategy[strat]["early_wins"] += 1

        best_strat  = None
        best_ratio  = -1.0

        for strat, stats in by_strategy.items():
            if stats["total"] >= 5:
                ratio = stats["early_wins"] / stats["total"]
                if ratio > best_ratio:
                    best_ratio  = ratio
                    best_strat  = strat

        return best_strat

    def consecutive_losses(self):
        """Retorna cuantos LOSS consecutivos hay al final de los registros."""
        count = 0
        for r in reversed(self.records):
            if r.get("is_loss"):
                count += 1
            else:
                break
        return count
