# -*- coding: utf-8 -*-
"""
core/risk_manager.py — Gestor Profesional de Capital y Registro Contable (SQLite)
================================================================================
1. Administra el capital ($110), objetivo (+ $20) y stop-loss (- $15).
2. Registra cada apuesta y resultado en una base de datos local SQLite (session_data.db).
3. Provee APIs para el Dashboard Web (KPIs, Calendario P&L, Curva de Capital).
4. No bloquea el sistema operativo ni el casino: al llegar a la meta, pasa a Reposo Ganador.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
import logging
import config

logger = logging.getLogger("RiskManager")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "session_data.db")


class RiskManager:
    def __init__(self, initial_balance=None, take_profit=None, stop_loss=None, mode=None):
        self.initial_balance = initial_balance if initial_balance is not None else getattr(config, "INITIAL_BALANCE", 110.0)
        self.take_profit     = take_profit if take_profit is not None else getattr(config, "TAKE_PROFIT", 20.0)
        self.stop_loss       = stop_loss if stop_loss is not None else getattr(config, "STOP_LOSS", -15.0)
        self.mode            = mode or getattr(config, "BOT_MODE", "REAL")

        self.current_session_id = None
        self.current_profit     = 0.0
        self.current_balance    = self.initial_balance
        self.is_finished        = False
        self.finish_reason      = ""

        self._init_database()
        self._start_new_session()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT,
                    end_time TEXT,
                    initial_balance REAL,
                    final_balance REAL,
                    profit REAL,
                    target_profit REAL,
                    stop_loss REAL,
                    status TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT,
                    date_str TEXT,
                    table_name TEXT,
                    prediction TEXT,
                    bet_type TEXT,
                    attempt_number INTEGER,
                    bet_amount REAL,
                    outcome TEXT,
                    profit_loss REAL,
                    balance_after REAL
                )
            """)
            conn.commit()

    def _start_new_session(self):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions (start_time, initial_balance, profit, target_profit, stop_loss, status)
                VALUES (?, ?, 0.0, ?, ?, 'ACTIVE')
            """, (now_str, self.initial_balance, self.take_profit, self.stop_loss))
            self.current_session_id = cur.lastrowid
            conn.commit()
        logger.info(f"Sesión #{self.current_session_id} iniciada. Saldo: ${self.initial_balance:.2f} | Meta: +${self.take_profit:.2f} | Stop: -${abs(self.stop_loss):.2f}")

    def update_settings(self, initial_balance=None, take_profit=None, stop_loss=None, mode=None):
        if initial_balance is not None:
            diff = initial_balance - self.initial_balance
            self.initial_balance = initial_balance
            self.current_balance += diff
        if take_profit is not None:
            self.take_profit = take_profit
        if stop_loss is not None:
            self.stop_loss = stop_loss
        if mode is not None:
            self.mode = mode

    def record_bet_outcome(self, table_name, prediction, attempt_num, bet_amount, is_win, is_ghost=False):
        """
        Registra el resultado de cada mano jugada o simulada.
        """
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        if is_ghost:
            profit_loss = 0.0
            outcome = "GHOST_WIN" if is_win else "GHOST_LOSS"
            bet_type = "GHOST"
        else:
            bet_type = self.mode
            if is_win:
                # En Baccarat: Jugador paga 1:1, Banca paga 0.95:1 (comisión del 5%)
                payout_rate = 0.95 if prediction == "B" else 1.00
                profit_loss = bet_amount * payout_rate
                outcome = "WIN"
            else:
                profit_loss = -bet_amount
                outcome = "LOSS"

            self.current_profit += profit_loss
            self.current_balance = self.initial_balance + self.current_profit

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO bets (session_id, timestamp, date_str, table_name, prediction, bet_type, attempt_number, bet_amount, outcome, profit_loss, balance_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.current_session_id, now_str, date_str, table_name, prediction, bet_type, attempt_num, bet_amount, outcome, profit_loss, self.current_balance))

            cur.execute("""
                UPDATE sessions
                SET final_balance = ?, profit = ?
                WHERE id = ?
            """, (self.current_balance, self.current_profit, self.current_session_id))
            conn.commit()

        # Evaluación de límites
        return self.check_limits()

    def check_limits(self):
        """
        Evalúa si la sesión actual ha cumplido el objetivo de ganancia o el límite de pérdida.
        Retorna: (should_stop: bool, status_code: str, message: str)
        """
        if self.current_profit >= self.take_profit:
            self.is_finished = True
            self.finish_reason = f"🎉 ¡OBJETIVO DIARIO ALCANZADO! Beneficio: +${self.current_profit:.2f} USD."
            self._close_session("COMPLETED_WIN")
            return True, "TAKE_PROFIT", self.finish_reason

        if self.current_profit <= self.stop_loss:
            self.is_finished = True
            self.finish_reason = f"🛑 STOP-LOSS ALCANZADO (-${abs(self.stop_loss):.2f}). Capital protegido en ${self.current_balance:.2f}."
            self._close_session("STOP_LOSS_HIT")
            return True, "STOP_LOSS", self.finish_reason

        return False, "ACTIVE", "Sesión en curso"

    def _close_session(self, status):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE sessions
                SET end_time = ?, final_balance = ?, profit = ?, status = ?
                WHERE id = ?
            """, (now_str, self.current_balance, self.current_profit, status, self.current_session_id))
            conn.commit()

    def reset_session(self):
        self.current_profit = 0.0
        self.current_balance = self.initial_balance
        self.is_finished = False
        self.finish_reason = ""
        self._start_new_session()

    # ─────────────────────────────────────────────────────────────
    # MÉTODOS PARA EL DASHBOARD WEB
    # ─────────────────────────────────────────────────────────────
    def get_live_kpi(self):
        pct = 0.0
        if self.take_profit > 0:
            pct = round(min(100.0, max(0.0, (self.current_profit / self.take_profit) * 100)), 1)

        # Contar victorias y derrotas de la sesión actual
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT outcome, COUNT(*) FROM bets WHERE session_id = ? GROUP BY outcome", (self.current_session_id,))
            rows = cur.fetchall()
            wins = 0
            losses = 0
            for r in rows:
                if r["outcome"] in ("WIN", "GHOST_WIN"):
                    wins += r[1]
                elif r["outcome"] in ("LOSS", "GHOST_LOSS"):
                    losses += r[1]

        total_hands = wins + losses
        win_rate = round((wins / total_hands * 100), 1) if total_hands > 0 else 0.0

        return {
            "initial_balance": round(self.initial_balance, 2),
            "current_balance": round(self.current_balance, 2),
            "current_profit": round(self.current_profit, 2),
            "target_profit": round(self.take_profit, 2),
            "stop_loss": round(self.stop_loss, 2),
            "progress_pct": pct,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "mode": self.mode,
            "is_finished": self.is_finished,
            "finish_reason": self.finish_reason
        }

    def get_daily_pnl_calendar(self):
        """
        Retorna la ganancia o pérdida neta agrupada por fecha YYYY-MM-DD.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date_str, SUM(profit_loss) as daily_profit, COUNT(*) as bets_count
                FROM bets
                WHERE outcome IN ('WIN', 'LOSS')
                GROUP BY date_str
                ORDER BY date_str ASC
            """)
            rows = cur.fetchall()

        result = {}
        for r in rows:
            result[r["date_str"]] = {
                "profit": round(r["daily_profit"], 2),
                "count": r["bets_count"]
            }
        return result

    def get_equity_curve(self, limit=100):
        """
        Retorna la curva de capital mano a mano para Chart.js.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT timestamp, balance_after
                FROM bets
                WHERE outcome IN ('WIN', 'LOSS')
                ORDER BY id ASC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()

        labels = []
        data = []
        # Punto inicial
        labels.append("Inicio")
        data.append(self.initial_balance)

        for r in rows:
            labels.append(r["timestamp"].split(" ")[1])  # Solo hora HH:MM:SS
            data.append(round(r["balance_after"], 2))

        return {"labels": labels, "data": data}

    def get_recent_bets(self, limit=30):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, timestamp, table_name, prediction, bet_type, attempt_number, bet_amount, outcome, profit_loss, balance_after
                FROM bets
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()

        bets = []
        for r in rows:
            bets.append({
                "id": r["id"],
                "time": r["timestamp"].split(" ")[1],
                "table": r["table_name"],
                "prediction": r["prediction"],
                "type": r["bet_type"],
                "attempt": r["attempt_number"],
                "amount": round(r["bet_amount"], 2),
                "outcome": r["outcome"],
                "profit": round(r["profit_loss"], 2),
                "balance": round(r["balance_after"], 2)
            })
        return bets
