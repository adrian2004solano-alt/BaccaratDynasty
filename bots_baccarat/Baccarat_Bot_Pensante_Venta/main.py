"""
main.py — Baccarat Bot Pensante
================================
Estrategia: VENTANA ROTANTE (1-2-3 / 2-3-4)

Mesa 1 → apuesta Tiros 1, 2, 3
  WIN → fin, buscar nueva senal (martingala reinicia)
  LOSS → Mesa 2

Mesa 2 → apuesta Tiros 2, 3, 4
  WIN → fin, buscar nueva senal (martingala reinicia)
  LOSS → Mesa 3

Mesa 3 → apuesta Tiros 1, 2, 3 (vuelve al inicio)
  ...y así sucesivamente.

La martingala es PERSISTENTE (no reinicia entre mesas, solo al ganar):
  $0.40 → $0.80 → $1.60 → $3.20 → ...
  2 clics → 4 clics → 8 clics → 16 clics → ...

Señales y análisis: idénticos al v31 (IA, 5 mesas, 6 tiros).
"""

import os
import sys
import time
import socket
import random
import logging
import subprocess
from datetime import datetime
from PIL import Image

# UTF-8 en consola Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from core.telegram_bot     import TelegramNotifier
from core.analyzer         import BaccaratAnalyzer
from core.scraper          import StakeBaccaratScraper
from core.session_manager  import BaccaratSession
from core.result_detector  import ResultDetector
from core.auto_bettor      import AutoBettor, WINDOW_A, WINDOW_B
from core.learning_tracker import LearningTracker

# ──────────────────────────────────────────────
# Control de Instancia Unica
# ──────────────────────────────────────────────
class SingleInstanceGuard:
    PORT = 48889
    HOST = "127.0.0.1"

    def __init__(self):
        self._socket = None

    def acquire(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.bind((self.HOST, self.PORT))
            self._socket.listen(1)
            return True
        except OSError:
            print(f"\n[Guard] Puerto {self.PORT} ocupado. Cerrando instancia anterior...")
            self._kill_previous()
            time.sleep(1)
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.bind((self.HOST, self.PORT))
                self._socket.listen(1)
                return True
            except OSError:
                print("[ERROR] Ya hay una instancia activa del Bot Pensante.")
                time.sleep(4)
                sys.exit(1)

    def _kill_previous(self):
        current_pid = os.getpid()
        try:
            cmd = f"""
            $procs = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
                     Where-Object {{ $_.ProcessId -ne {current_pid} -and $_.CommandLine -match 'main.py' }}
            foreach ($p in $procs) {{ Stop-Process -Id $p.ProcessId -Force }}
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=5)
        except Exception:
            pass

    def release(self):
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None


# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("Scraper").setLevel(logging.WARNING)

logger = logging.getLogger("BotPensante")

STARTUP_DELAY      = getattr(config, "STARTUP_DELAY", 5)
ANALYSIS_COOLDOWN  = 1
SESSION_PAUSE      = 1
POST_LOSS_PAUSE    = 1
POLL_FAST_INTERVAL = 0.30
MAX_WAIT_FINISH    = 55


def ts():
    return datetime.now().strftime("%H:%M:%S")


def countdown(seconds, label="En"):
    for r in range(seconds, 0, -1):
        sys.stdout.write(f"\r  {label} {r:02d}s...  ")
        sys.stdout.flush()
        time.sleep(1)
    print()


def load_pil_image(path):
    try:
        if path and os.path.exists(path):
            return Image.open(path).copy()
    except Exception:
        pass
    return None


def sep(char="=", n=68):
    print(char * n)


def print_banner(auto_bettor, pid=None):
    mode_tag = "REAL (Clics Activos)" if auto_bettor.enabled else "SIMULACION (Sin clics)"
    pid_tag  = f"PID {pid} (Puerto 48889)" if pid else "Activo"
    amount, step, clicks = auto_bettor.get_current_bet()
    sep("=")
    print("   BACCARAT BOT PENSANTE — Ventana Rotante 1-2-3 / 2-3-4")
    print("   Lobby Multiplay | Martingala Persistente | Telegram Senales")
    print(f"  Instancia        : {pid_tag}")
    print(f"  Mesas            : {', '.join(config.TARGET_TABLES)}")
    print(f"  Estrategia       : Ventana Rotante (A: 1-2-3 -> B: 2-3-4)")
    print(f"  Ficha Base       : $0.20 USD (1 clic)")
    print(f"  Recuperación     : Fija a $0.40 tras 5 tiros perdidos (hasta recuperar balance previo)")
    print(f"  Modo             : {mode_tag}")
    print(f"  Stop-Loss        : ${auto_bettor.stop_loss:.2f}")
    print(f"  Take-Profit      : +${auto_bettor.take_profit:.2f}")
    print(f"  Canal Telegram   : {config.TELEGRAM_CHAT_ID}")
    print(f"  IMPORTANTE       : Manten Baccarat Multiplay visible en pantalla.")
    sep("=")
    print()


# ──────────────────────────────────────────────
# FASE 1 — ANALISIS (idéntico al v31)
# ──────────────────────────────────────────────
def phase_analysis(scraper, analyzer, stats_tracker, auto_bettor=None, detector=None):
    last_strat      = stats_tracker.get_last_strategy()
    early_scores    = stats_tracker.get_strategy_early_win_scores()
    strategy_usage  = stats_tracker.get_recent_strategy_usage()

    print(f"\n[{ts()}] Analizando mesas...")
    scraper.sync_slots_with_screen()
    if auto_bettor and scraper.slot_bets:
        auto_bettor.update_dynamic_slots(scraper.slot_bets)

    candidates         = []
    cooling_candidates = []
    detected_tables    = [t for t in scraper.regions.keys() if t != "UNKNOWN" and t in config.TARGET_TABLES]
    tables_to_scan     = detected_tables if detected_tables else config.TARGET_TABLES
    seen_tables        = set()

    for target in tables_to_scan:
        if target in seen_tables:
            continue
        seen_tables.add(target)
        data         = scraper.get_table_data(target)
        table_name   = data.get("table_name", target)
        history      = data.get("history", [])
        total_hands  = data.get("total_hands", len(history))
        is_qualified = data.get("is_qualified", False)
        screenshot   = data.get("screenshot_path")
        clean_count  = len([x for x in history if x in ("P", "B", "T")])

        if not is_qualified or clean_count < 10 or total_hands < 10 or clean_count >= 65 or total_hands >= 65:
            detected_num = max(total_hands, clean_count)
            reason = (
                f"Solo {detected_num} jugadas (min 10)"
                if detected_num < 10
                else f"{detected_num} jugadas (65+ Fin de zapato — ESTRICTAMENTE PROHIBIDA)"
            )
            print(f"  🚫 OMITIDA {table_name:<18} | {reason}")
            continue

        can_sig, wait_sec = analyzer.can_send_signal(table_name)
        if not can_sig:
            print(f"  PAUSA   {table_name:<18} | Esperando {wait_sec}s...")
            continue

        is_cooling     = stats_tracker.is_table_cooling_down(table_name)
        health_label   = stats_tracker.get_table_health_label(table_name)
        table_momentum = stats_tracker.get_table_momentum_score(table_name)

        should, sequence, confidence, probability, _, strat_name, reason = analyzer.analyze_history(
            table_name, history, total_hands=total_hands,
            last_strategy=last_strat, early_scores=early_scores, strategy_usage=strategy_usage,
        )

        golden_tag = " [GOLDEN]" if (18 <= total_hands <= 48) else ""

        is_ending_now = False
        if detector and screenshot:
            c_img = load_pil_image(screenshot)
            if c_img:
                is_ending_now, _ = detector.is_round_concluded(c_img)

        if should:
            timing_bonus    = 8.0 if is_ending_now else 0.0
            selection_score = confidence + table_momentum + timing_bonus + random.uniform(0.1, 1.0)
            tag_extra       = " [TERMINO AHORA]" if is_ending_now else golden_tag

            if is_cooling:
                print(f"  FRIO    {table_name:<18} | {total_hands:<2} jug{tag_extra} | [{strat_name}] ({probability}%) Saltada")
                cooling_candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
            else:
                print(f"  OK      {table_name:<18} | {total_hands:<2} jug{tag_extra} | [{strat_name}] ({probability}%) Score:{selection_score:.1f}")
                candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
        else:
            print(f"  ESPERA  {table_name:<18} | {total_hands:<2} jug{golden_tag} -> Sin ventaja ({reason})")

    sep()

    if not candidates:
        msg = "Mesas en reposo." if cooling_candidates else "Sin mesa optima."
        print(f"  -> {msg} Reintentando en {ANALYSIS_COOLDOWN}s...")
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    best = candidates[0]
    score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label = best
    seq_preview = " ".join(sequence[:6])
    print(f"  -> [SELECCIONADA]: [{table_name}] ({total_hands} jugadas)")
    print(f"     [{strat_name}] | {seq_preview} | {probability}% | Score:{score:.1f}")
    return table_name, screenshot, sequence, probability, total_hands, strat_name, reason


# ──────────────────────────────────────────────
# FASE 2 — ESPERAR FIN DE JUGADA PREVIA
# ──────────────────────────────────────────────
def phase_wait_round_end(scraper, detector, table_name):
    print(f"\n  [{ts()}] Sincronizando fin de jugada en [{table_name}]...")
    start_wait = time.time()
    while time.time() - start_wait < MAX_WAIT_FINISH:
        data       = scraper.get_table_data(table_name)
        screenshot = data.get("screenshot_path")
        card_img   = load_pil_image(screenshot)
        concluded, winner_code = detector.is_round_concluded(card_img)
        if concluded:
            winner_label = "JUGADOR" if winner_code == "P" else ("BANCA" if winner_code == "B" else "EMPATE")
            print(f"  [{ts()}] Jugada previa: {winner_label}. Disparando senal...")
            return screenshot
        time.sleep(0.5)
    fresh_data = scraper.get_table_data(table_name)
    return fresh_data.get("screenshot_path")


# ──────────────────────────────────────────────
# FASE 3 — ENVIAR SENAL A TELEGRAM
# ──────────────────────────────────────────────
def phase_signal(telegram, table_name, screenshot, sequence, probability, strat_name, reason):
    print(f"\n  [{ts()}] Enviando senal de [{table_name}] a Telegram...")
    ok, msg = telegram.send_baccarat_signal(
        table_name=table_name,
        sequence=sequence,
        probability=probability,
        screenshot_path=screenshot,
    )
    if ok:
        print(f"  Senal enviada OK.")
        return BaccaratSession(table_name, sequence, strat_name, probability, reason)
    else:
        print(f"  ERROR: {msg}")
        return None


# ──────────────────────────────────────────────
# FASE 4 — TRACKING CON VENTANA ROTANTE
#
# bet_window=0 → apuesta en Tiros 1, 2, 3 (attempt_idx 0, 1, 2)
# bet_window=1 → apuesta en Tiros 2, 3, 4 (attempt_idx 1, 2, 3)
#
# Tiros fuera de la ventana activa: GHOST (solo observa, no apuesta)
# La martingala avanza con cada pérdida real y se resetea al ganar.
# ──────────────────────────────────────────────
def phase_tracking(telegram, scraper, detector, session, auto_bettor,
                   analyzer, learning_tracker, bet_window):
    table_name    = session.table_name
    strat_name    = session.strategy
    active_window = WINDOW_A if bet_window == 0 else WINDOW_B
    window_label  = auto_bettor.get_window_label(bet_window)
    amount, step, clicks = auto_bettor.get_current_bet()

    auto_bettor.reset_for_new_table()

    sep()
    print(f"  [{ts()}] SESION ACTIVA — [{table_name}] | [{strat_name}]")
    print(f"     Ventana: {window_label} | Siguiente apuesta: {clicks} clics = ${amount:.2f} | Paso martingala: {step}")
    sep()

    real_bets_placed = 0
    window_exhausted = False   # Se activa cuando fallan los 3 tiros de la ventana

    while not session.is_finished():
        attempt_n   = session.attempt_number   # 1-6
        attempt_idx = session.current_attempt  # 0-5
        prediction  = session.current_prediction
        if prediction is None:
            break

        # ¿Es tiro con apuesta de dinero real?
        # Solo si está dentro de active_window y no hemos agotado los 3 tiros de la ventana
        is_real_bet = (attempt_idx in active_window) and (not window_exhausted)
        pred_label  = "JUGADOR" if prediction == "P" else "BANCA"

        if is_real_bet:
            amount, step, clicks = auto_bettor.get_current_bet()
            print(f"\n  [{ts()}] 🎯 REAL Tiro {attempt_n}/6 [{window_label}] | {clicks} clics = ${amount:.2f} a {pred_label}")
        else:
            if window_exhausted:
                print(f"\n  [{ts()}] ⏸️ ESPERANDO FIN DE MESA (Tiro {attempt_n}/6) | Ventana {window_label} agotada, observando [{table_name}]...")
            else:
                print(f"\n  [{ts()}] 👻 GHOST Tiro {attempt_n}/6 (espera de ventana) | Observando [{table_name}]...")

        # 0. Esperar mesa limpia (listón anterior cerrado y apuestas abiertas)
        detector.wait_until_clean(scraper, table_name, max_wait=6)

        # Historial base al inicio del intento
        data_start   = scraper.get_table_data(table_name)
        base_history = data_start.get("history", [])
        base_count   = len(base_history)

        # 1. Apuesta física (solo si es tiro real)
        if is_real_bet:
            dynamic_coords = scraper.slot_bets.get(table_name)
            ok_bet, bet_msg = auto_bettor.execute_bet(
                prediction=prediction,
                attempt_index=attempt_idx,
                table_name=table_name,
                dynamic_coords=dynamic_coords,
            )
            print(f"     -> [AutoBettor] {bet_msg}")
            print(f"     [{ts()}] Esperando nueva mano (4s de seguridad)...")
            time.sleep(4.0)
            real_bets_placed += 1
        else:
            time.sleep(1.0)

        # 2. Esperar resultado visual en pantalla
        result           = None
        screenshot       = None
        round_start_time = time.time()
        MAX_ROUND_WAIT   = 55
        cards_seen       = False

        while not session.is_finished() and (time.time() - round_start_time < MAX_ROUND_WAIT):
            time.sleep(POLL_FAST_INTERVAL)
            data        = scraper.get_table_data(table_name)
            screenshot  = data.get("screenshot_path")
            current_img = load_pil_image(screenshot)

            if detector.are_cards_present(current_img):
                if not cards_seen:
                    cards_seen = True
                    print(f"     [{ts()}] Cartas en juego en [{table_name}]...")

            ribbon_res = detector.read_result(current_img, table_name)
            curr_hist  = data.get("history", [])
            curr_count = len(curr_hist)

            if cards_seen and ribbon_res is not None:
                result = ribbon_res
                break
            elif cards_seen and curr_count > base_count and curr_hist and not detector.are_cards_present(current_img):
                result = curr_hist[-1]
                break

        if result is None:
            curr_hist = scraper.get_table_data(table_name).get("history", [])
            result    = curr_hist[-1] if curr_hist else "T"

        # ── EMPATE ──
        if result == "T":
            mode = "REAL" if is_real_bet else "GHOST"
            print(f"  [{ts()}] EMPATE ({mode}). Apuesta devuelta / intento se mantiene.")
            detector.wait_until_clean(scraper, table_name, max_wait=6)
            continue

        # ── RESULTADO DE LA MANO ──
        res_label = "JUGADOR 🔵" if result == "P" else "BANCA 🔴"
        outcome   = session.register_result(result)

        if outcome.startswith("win_"):
            win_n = int(outcome.split("_")[1])

            # SIEMPRE notificar el WIN oficial de la señal en Telegram con foto y estadísticas
            telegram.send_result_message(
                table_name=table_name,
                result_type="win",
                attempt_number=win_n,
                screenshot_path=screenshot,
                strategy_name=strat_name,
            )
            learning_tracker.record_signal(
                table_name=table_name,
                history=base_history,
                strategy_name=strat_name,
                shoe_length=len(base_history),
                win_attempt=win_n,
                is_loss=False,
            )
            # Liberar candado para permitir que el bot analice la siguiente mesa de inmediato
            telegram.release_active_table(table_name)
            detector.wait_until_clean(scraper, table_name, max_wait=6)

            if is_real_bet:
                # ¡WIN CON DINERO REAL!
                was_recovery = auto_bettor.is_in_recovery()
                auto_bettor.record_win(attempt_idx)
                print(f"\n  🏆 ¡GANADO CON DINERO REAL EN TIRO {win_n}! Ganó {res_label}.")
                if was_recovery:
                    if auto_bettor.is_in_recovery():
                        print(f"     [RECUPERACIÓN] Acierto de $0.40. Deuda restante por recuperar: ${auto_bettor.recovery_debt:.2f} USD.")
                    else:
                        print(f"     🎉 ¡RECUPERACIÓN COMPLETADA AL 100%! Toda la pérdida anterior ha sido recuperada.")
                        print(f"     Volviendo al modo predeterminado: 1 clic (${auto_bettor.base_bet:.2f}) y martingala rotante.")
                else:
                    print(f"     Martingala reiniciada a ${auto_bettor.base_bet:.2f} USD. Próxima mesa: Ventana A (1-2-3).")
                return "win"
            else:
                # La mesa concluyó con WIN en un tiro que NO apostamos
                if window_exhausted:
                    # Habíamos jugado y perdido los 3 tiros de la ventana (ej. 1, 2, 3), y la mesa ganó en 4, 5 o 6
                    print(f"\n  ✅ Señal completada con WIN {win_n} en Telegram tras agotar los 3 tiros de {window_label}.")
                    print(f"     El bot de apuestas perdió sus 3 tiros en esta mesa -> Rotando a la siguiente ventana...")
                    return "loss"
                else:
                    # Estábamos esperando (ej. en Ventana B, Tiro 1 ganó en la mesa antes de poder apostar en 2, 3, 4)
                    print(f"\n  ✅ Señal completada con WIN {win_n} en Telegram durante la espera de Tiro 1.")
                    print(f"     No se realizaron apuestas en esta mesa -> Manteniendo {window_label} para la siguiente mesa...")
                    return "no_bet"

        elif outcome == "continue":
            if is_real_bet:
                auto_bettor.record_step_loss(attempt_idx)
                next_n      = session.attempt_number
                next_pred   = session.current_prediction
                n_label     = "JUGADOR 🔵" if next_pred == "P" else "BANCA 🔴"
                amt2, s2, c2 = auto_bettor.get_current_bet()

                # ¿El siguiente tiro está dentro de la ventana activa?
                if session.current_attempt in active_window:
                    print(f"     ✗ Falló Tiro {attempt_n}. Salió [{res_label}].")
                    print(f"       -> Tiro {next_n}: {c2} clic(s) = ${amt2:.2f} a {n_label}")
                else:
                    # Se acaba de perder el último tiro de la ventana activa (ej. tiro 3 en Ventana A, o tiro 4 en Ventana B)
                    window_exhausted = True
                    print(f"     ✗ Falló Tiro {attempt_n} (último intento de {window_label}).")
                    print(f"       -> 3 tiros fallados. Esperando que la mesa pase (Tiros {next_n}-6) sin apostar...")
            else:
                print(f"     Ghost Tiro {attempt_n} pasó ({res_label}).")
                if session.current_attempt in active_window and not window_exhausted:
                    next_n = session.attempt_number
                    amt2, s2, c2 = auto_bettor.get_current_bet()
                    next_pred   = session.current_prediction
                    n_label     = "JUGADOR 🔵" if next_pred == "P" else "BANCA 🔴"
                    print(f"       -> ¡Tiro 1 pasó! Ahora entra a apostar con dinero real: Tiro {next_n} ({c2} clic(s) = ${amt2:.2f} a {n_label})")

            detector.wait_until_clean(scraper, table_name, max_wait=6)

        elif outcome == "loss":
            # La mesa agotó los 6 intentos sin ganar (LOSS oficial en Telegram)
            telegram.send_result_message(
                table_name=table_name,
                result_type="loss",
                attempt_number=6,
                screenshot_path=screenshot,
                strategy_name=strat_name,
            )
            learning_tracker.record_signal(
                table_name=table_name,
                history=base_history,
                strategy_name=strat_name,
                shoe_length=len(base_history),
                win_attempt=None,
                is_loss=True,
            )
            telegram.release_active_table(table_name)
            detector.wait_until_clean(scraper, table_name, max_wait=6)

            if real_bets_placed > 0:
                print(f"\n  💔 LOSS oficial en Telegram (6 intentos). Ventana {window_label} finalizada con pérdidas.")
                return "loss"
            else:
                print(f"\n  💔 LOSS oficial en Telegram (sin apuestas realizadas por el bot).")
                return "no_bet"

    # Salida preventiva
    telegram.release_active_table(table_name)
    return "loss" if real_bets_placed > 0 else "no_bet"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    guard = SingleInstanceGuard()
    guard.acquire()

    telegram = TelegramNotifier()
    telegram.release_active_table()
    if not telegram.is_configured:
        print("[AVISO] Telegram no configurado. El bot funcionará en MODO LOCAL (sin notificaciones).")

    try:
        auto_bet_active = config.AUTO_BET_ENABLED
        if any(arg in sys.argv for arg in ("--no-bet", "--solo-senales", "--simulacion")):
            auto_bet_active = False
        elif any(arg in sys.argv for arg in ("--con-apuestas", "--real")):
            auto_bet_active = True

        game_mode = getattr(config, "GAME_MODE", 1)

        auto_bettor = AutoBettor(
            enabled=auto_bet_active,
            stop_loss=config.AUTO_BET_STOP_LOSS,
            take_profit=config.AUTO_BET_TAKE_PROFIT,
            base_bet=getattr(config, "AUTO_BET_BASE_BET", 0.20),
            base_chip=getattr(config, "AUTO_BET_BASE_CHIP", 0.20),
            base_clicks=getattr(config, "AUTO_BET_BASE_CLICKS", 1),
            persistent_martingale=True,
            max_steps=getattr(config, "AUTO_BET_MAX_STEPS", 10),
            game_mode=game_mode,
        )

        learning_tracker  = LearningTracker()
        consec_loss_limit = getattr(config, "CONSECUTIVE_LOSS_LIMIT", 5)

        print_banner(auto_bettor, pid=os.getpid())

        analyzer = BaccaratAnalyzer(
            min_delay=config.MIN_SIGNAL_DELAY,
            max_delay=config.MAX_SIGNAL_DELAY,
            min_confidence=getattr(config, "MIN_CONFIDENCE_THRESHOLD", 88),
        )
        scraper  = StakeBaccaratScraper(target_tables=config.TARGET_TABLES)
        detector = ResultDetector()

        print(f"[+] Mesas: {list(scraper.regions.keys())}")
        print(f"[+] Filtro zapato: 10 a 64 jugadas")
        print(f"[+] Estrategia: Ventana A (1-2-3) -> LOSS -> Ventana B (2-3-4) -> LOSS -> A ...")
        if game_mode == 2:
            print(f"[+] MODO 2 (SEGURO): Tras perder ambas ventanas -> Recuperación plana $0.40/tiro")
        else:
            print(f"[+] MODO 1 (NORMAL): Ficha $0.20 | Martingala persistente")
        print(f"[+] Anti-LOSS consecutivo: Pausa 90s si {consec_loss_limit} LOSS seguidos")
        print(f"[+] Telegram: {'ACTIVADO' if telegram.is_configured else 'MODO LOCAL (sin notificaciones)'}")
        hist_count = len(learning_tracker.records)
        print(f"[+] Aprendizaje: {hist_count} registros")

        print(f"\nTienes {STARTUP_DELAY}s para abrir Stake con Baccarat Multiplay visible.\n")
        countdown(STARTUP_DELAY, "Inicio en")
        print("\nBot Pensante Activo!\n")

        # Notificar inicio en Telegram
        telegram.send_message(
            "<b>Bot Pensante Iniciado</b>\n"
            "Estrategia: Ventana Rotante 1-2-3 / 2-3-4\n"
            "Ficha: $0.20 | Primera apuesta: $0.20 (1 clic)\n"
            "Martingala persistente: $0.20 -> $0.40 -> $0.80 ...\n"
            f"Stop-Loss: ${auto_bettor.stop_loss:.0f} | Take-Profit: +${auto_bettor.take_profit:.0f}\n"
            f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )

        signal_count       = 0
        consecutive_losses = 0
        # Estado de ventana: 0 = Tiros 1-2-3 | 1 = Tiros 2-3-4
        bet_window         = 0

        while True:
            # Control de enfriamiento
            telegram.stats_tracker.decrement_table_cooldowns()

            # Anti-LOSS consecutivo
            consec = learning_tracker.consecutive_losses()
            if consec >= consec_loss_limit:
                print(f"\n  [{ts()}] {consec} LOSS CONSECUTIVOS. Pausa 90s...")
                countdown(90, "Reanudando en")
                print(f"  [{ts()}] Re-escaneando mesas...\n")

            window_label = "A [Tiros 1-2-3]" if bet_window == 0 else "B [Tiros 2-3-4]"
            amount, step, clicks = auto_bettor.get_current_bet()
            print(f"\n--- Ventana Activa: {window_label} | Paso martingala: {step} | Apuesta: {clicks} clics = ${amount:.2f} ---")

            # 1. Análisis
            cand = phase_analysis(scraper, analyzer, telegram.stats_tracker,
                                   auto_bettor=auto_bettor, detector=detector)
            if cand is None:
                countdown(ANALYSIS_COOLDOWN, "Proximo analisis en")
                continue

            table_name, screenshot, sequence, probability, total_hands, strat_name, reason = cand

            # 2. Esperar fin de ronda
            clean_screenshot = phase_wait_round_end(scraper, detector, table_name)

            # 3. Señal a Telegram
            session = phase_signal(
                telegram, table_name, clean_screenshot,
                sequence, probability, strat_name, reason
            )
            if session is None:
                print("  ERROR de senal. Reintentando en 8s...")
                time.sleep(8)
                continue

            signal_count += 1
            print(f"\n  Senal #{signal_count} | [{table_name}] | [{strat_name}] | Ventana {window_label}")

            # 4. Tracking con ventana rotante
            final_result = phase_tracking(
                telegram, scraper, detector, session, auto_bettor,
                analyzer, learning_tracker, bet_window=bet_window,
            )
            analyzer.register_signal_sent(table_name)

            # 5. Actualizar ventana y estado
            if final_result == "win":
                if auto_bettor.is_in_recovery():
                    print(f"\n🎯 [RECUPERACIÓN] Acierto registrado. Balance actual: ${auto_bettor.session_profit:.2f} USD | Meta: ${auto_bettor.target_recovery_profit:.2f} USD (Faltan: ${max(auto_bettor.recovery_debt, 0.0):.2f})")
                    print(f"   Próxima mesa continúa con apuestas planas de $0.40 (2 clics).")
                else:
                    consecutive_losses = 0
                    bet_window = 0   # ← Siempre vuelve a Ventana A (1, 2, 3) al ganar
                    balance = auto_bettor.session_profit
                    print(f"\n🎉 ¡Victoria con dinero real! Balance: ${balance:.2f} | Próxima mesa: Ventana A (Tiros 1, 2, 3)")

                if auto_bettor.is_paused_by_limits:
                    print(f"\n⚠️ LÍMITE FINANCIERO ALCANZADO: {auto_bettor.pause_reason}")
                    telegram.send_message(
                        f"<b>LÍMITE FINANCIERO ALCANZADO</b>\n{auto_bettor.pause_reason}\n"
                        f"Balance final: ${auto_bettor.session_profit:.2f}\n"
                        f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
                    )
                countdown(SESSION_PAUSE, "Buscando siguiente mesa en")

            elif final_result == "loss":
                consecutive_losses += 1

                if auto_bettor.is_in_recovery():
                    print(f"\n⚠️ [RECUPERACIÓN] Ronda fallida. Balance actual: ${auto_bettor.session_profit:.2f} USD | Meta: ${auto_bettor.target_recovery_profit:.2f} USD (Faltan: ${auto_bettor.recovery_debt:.2f})")
                    print(f"   Se mantiene apuesta fija de $0.40 (2 clics) sin martingala.")
                    bet_window = 0  # En recuperación siempre juega tiros 1, 2, 3
                    countdown(POST_LOSS_PAUSE, "Buscando siguiente mesa en")
                    continue

                # Modo normal (rotación de ventanas)
                bet_window = 1 - bet_window
                next_window_label = "A (Tiros 1, 2, 3)" if bet_window == 0 else "B (Espera Tiro 1, juega 2, 3, 4)"
                amt_next, step_next, clicks_next = auto_bettor.get_current_bet()
                print(f"\n❌ Los tiros de la ventana fallaron.")
                print(f"   Rotando a Ventana {next_window_label}.")
                print(f"   Martingala acumulada: Paso {step_next} ({clicks_next} clics = ${amt_next:.2f}) | Pérdidas consecutivas: {auto_bettor.consecutive_real_losses}/5.")
                countdown(POST_LOSS_PAUSE, "Buscando nueva mesa en")

            elif final_result == "no_bet":
                # La mesa concluyó antes de poder apostar (ej. ganó Tiro 1 en Ventana B)
                # Se mantiene la misma ventana!
                current_window_label = "A (Tiros 1, 2, 3)" if bet_window == 0 else "B (Espera Tiro 1, juega 2, 3, 4)"
                print(f"\nℹ️ Mesa terminada sin apuestas realizadas por el bot.")
                print(f"   Se MANTIENE Ventana {current_window_label} para la próxima mesa.")
                countdown(SESSION_PAUSE, "Buscando siguiente mesa en")

    except KeyboardInterrupt:
        print("\n\n[!] Bot detenido.")
        print(f"Balance Neto: ${auto_bettor.session_profit:.2f} USD | Senales: {signal_count}")
        recs = len(learning_tracker.records)
        print(f"Aprendizaje: {recs} registros guardados.")
        telegram.send_message(
            f"<b>Bot Pensante Detenido</b>\n"
            f"Balance sesion: ${auto_bettor.session_profit:.2f} USD\n"
            f"Senales: {signal_count}\n"
            f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )
        print("Hasta pronto!")

    finally:
        telegram.release_active_table()
        guard.release()


if __name__ == "__main__":
    main()
