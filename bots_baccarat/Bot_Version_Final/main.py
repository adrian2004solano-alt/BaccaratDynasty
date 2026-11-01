"""
main.py — Baccarat Auto-Bettor VIP (Edición Multi-Divisa: USD / TRY + Dynasty & Rush)
======================================================================================
1. Monitoreo y Análisis Inteligente en Vivo (Stake / Pragmatic Multiplay).
2. 4 Estrategias Maestras Adaptativas (Filtro de zapato 12 a 64 jugadas).
3. Apuestas Automáticas Físicas con Martingala Persistente Entre Mesas.
4. Lógica Inteligente de 2 Fichas (Moneda 1 + Moneda 2) para Tiros Altos.
5. Blindaje Total Anti-Falsos WINs (Verificación obligatoria de reparto de cartas).
6. Integración dual con Telegram: Canal Baccarat Dynasty + Canal de Resultados Rush.
"""

import os
import sys
import time
import random
import logging
from datetime import datetime
from PIL import Image

# Consola UTF-8 seguro
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

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.analyzer        import BaccaratAnalyzer
from core.scraper         import StakeBaccaratScraper
from core.session_manager import BaccaratSession
from core.result_detector import ResultDetector
from core.auto_bettor     import AutoBettor
from core.stats_tracker   import StatsTracker
from core.telegram_bot    import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("Scraper").setLevel(logging.WARNING)

logger = logging.getLogger("AutoBotVIP")

STARTUP_DELAY      = getattr(config, "STARTUP_DELAY", 8)
ANALYSIS_COOLDOWN  = 2
SESSION_PAUSE      = 3
POST_LOSS_PAUSE    = 2
POLL_FAST_INTERVAL = 0.4
MAX_WAIT_FINISH    = 32


def ts():
    return datetime.now().strftime("%H:%M:%S")


def sep(char="=", n=70):
    print(char * n)


def countdown(seconds, label="Iniciando en"):
    for r in range(seconds, 0, -1):
        sys.stdout.write(f"\r  ⏳ {label} {r:02d}s...  ")
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


def print_banner(auto_bettor):
    mart_tag = "PERSISTENTE (Continúa entre mesas hasta ganar)" if auto_bettor.persistent_martingale else "LOCAL (Reinicia tras 6 tiros)"
    sl_text = f"{auto_bettor.stop_loss:.2f} {auto_bettor.currency}" if auto_bettor.stop_loss is not None else "ILIMITADO (Sin Stop-Loss)"
    tp_text = f"+{auto_bettor.take_profit:.2f} {auto_bettor.currency}" if auto_bettor.take_profit is not None else "LIBRE (Sin Take-Profit)"
    steps_text = "Sin Límite (Infinita)" if (auto_bettor.max_steps is None or auto_bettor.max_steps >= 50) else f"{auto_bettor.max_steps} pasos"

    sep("=")
    print("   🎰  BACCARAT AUTO-BETTOR VIP · EDICIÓN MULTI-DIVISA (USD / TRY)  🎰")
    print("      Stake Multiplay · Clics Inteligentes 2 Fichas · Baccarat Dynasty")
    sep("=")
    print(f"  Mesas Monitoreadas   : {', '.join(config.TARGET_TABLES)}")
    print(f"  Filtro de Zapato     : 8 a 64 jugadas permitidas (< 8 o >= 65 Omitida)")
    print(f"  Estrategias Activas  : 10 Estrategias Dinámicas (Máx 20% Mono-Color / 80% Combinaciones)")
    print(f"  Divisa de Juego      : {auto_bettor.currency_label}")
    print(f"  Moneda 1 (Base)      : {auto_bettor.chip1_value:.2f} {auto_bettor.currency} (Extremo Izquierdo)")
    print(f"  Moneda 2 (Alta)      : {auto_bettor.chip2_value:.2f} {auto_bettor.currency} (Segunda a la Izquierda — 5x)")
    print(f"  Gestión de Fichas    : Inteligente (Moneda 2 para tiros altos + Moneda 1 para ajuste exacto)")
    print(f"  Gestión Martingala   : {mart_tag} | {steps_text}")
    print(f"  Canal Señales        : {config.TELEGRAM_CHAT_ID} (Baccarat Dynasty)")
    if getattr(config, "TELEGRAM_RESULTS_CHAT_ID", None):
        print(f"  Canal Resultados     : {config.TELEGRAM_RESULTS_CHAT_ID} (Rush)")
    print(f"  Límites Financieros  : Stop-Loss: {sl_text} | Stop-Profit: {tp_text}")
    print(f"  ⚠️  IMPORTANTE         : Mantén Baccarat Multiplay visible en pantalla.")
    sep("=")
    print()


# ──────────────────────────────────────────────
# FASE 1 — ANÁLISIS DE MESAS
# ──────────────────────────────────────────────
def phase_analysis(scraper, analyzer, stats_tracker, auto_bettor, detector):
    # Sincronización visual dinámica de slots (detecta en tiempo real qué mesa está en cada ranura)
    scraper.sync_slots_with_screen()

    last_strat = stats_tracker.get_last_strategy()
    early_scores = stats_tracker.get_strategy_early_win_scores()
    strategy_usage = stats_tracker.get_recent_strategy_usage()

    candidates = []
    cooling_candidates = []

    print(f"\n🔍 [{ts()}] Analizando mesas disponibles en Stake Multiplay...")
    tables_to_scan = [t for t in scraper.regions.keys() if t in config.TARGET_TABLES]
    if not tables_to_scan:
        tables_to_scan = config.TARGET_TABLES

    for target in tables_to_scan:
        data         = scraper.get_table_data(target)
        table_name   = data.get("table_name", target)
        history      = data.get("history", [])
        total_hands  = data.get("total_hands", len(history))
        is_qualified = data.get("is_qualified", False)
        screenshot   = data.get("screenshot_path")

        if not is_qualified or total_hands < 8 or total_hands >= 65:
            reason = "Menos de 8 jugadas" if total_hands < 8 else "Fin de zapato (65+ jugadas)"
            print(f"  🚫 {table_name:<18} | {total_hands:<2} manos -> OMITIDA ({reason})")
            continue

        can_sig, wait_sec = analyzer.can_send_signal(table_name)
        if not can_sig:
            print(f"  ⏳ {table_name:<18} | Pausa de mesa: esperando {wait_sec}s...")
            continue

        is_cooling = stats_tracker.is_table_cooling_down(table_name)
        health_label = stats_tracker.get_table_health_label(table_name)
        table_momentum = stats_tracker.get_table_momentum_score(table_name)

        should, sequence, confidence, probability, _, strat_name, reason = analyzer.analyze_history(
            table_name, history, total_hands=total_hands, last_strategy=last_strat, early_scores=early_scores, strategy_usage=strategy_usage, stats_tracker=stats_tracker
        )

        golden_tag = " ⭐" if (18 <= total_hands <= 48) else ""
        if should:
            seq_preview = ' '.join(sequence[:4])
            selection_score = confidence + table_momentum + random.uniform(0.1, 1.0)

            # Prioridad de sincronización en tiempo real (conclusión de la mano previa)
            card_img = load_pil_image(screenshot)
            is_concluding, winner_code = detector.is_round_concluded(card_img) if card_img else (False, None)
            is_dealing = detector.are_cards_present(card_img) if card_img else False

            timing_tag = ""
            if is_concluding:
                # Mano previa finalizando justo ahora: ¡máxima prioridad para disparo inmediato con 15s completos!
                selection_score += 30.0
                w_sym = "🔵" if winner_code == "P" else ("🔴" if winner_code == "B" else "🟢")
                timing_tag = f" 🏆 [CONCLUYENDO {w_sym} - LISTA]"
            elif is_dealing:
                selection_score += 15.0
                timing_tag = " 🃏 [JUGANDO MANO PREVIA]"
            else:
                timing_tag = " ⏱️ [VENTANA ABIERTA]"

            if is_cooling:
                cooling_candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
            else:
                print(f"  🎯 {table_name:<18} | {total_hands:<2} jug{golden_tag}{timing_tag} | [{strat_name:<16}] -> {seq_preview} ({probability}%) | Salud: {health_label}")
                candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
        else:
            print(f"  ⏳ {table_name:<18} | {total_hands:<2} jug{golden_tag} -> Sin ventaja clara | {health_label}")

    sep("-")
    target_pool = candidates if candidates else []

    if not target_pool:
        print(f"  → ⏳ Sin mesa con ventaja óptima en este ciclo. Reintentando en {ANALYSIS_COOLDOWN}s...")
        return None

    target_pool.sort(key=lambda c: c[0], reverse=True)
    best = target_pool[0]
    score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label = best

    seq_preview = " ".join(sequence[:6])
    print(f"  → 🚀 [MESA SELECCIONADA]: [{table_name}] ({total_hands} jugadas) | Salud: {health_label}")
    print(f"     Estrategia: [{strat_name}] | Secuencia: [{seq_preview}] | Prob: {probability}%")
    return table_name, screenshot, sequence, probability, total_hands, strat_name, reason


# ──────────────────────────────────────────────
# FASE 2 — ESPERAR QUE FINALICE LA JUGADA PREVIA Y EMISIÓN ANTICIPADA
# ──────────────────────────────────────────────
def phase_wait_round_end(scraper, detector, analyzer, table_name, sequence, probability, strat_name, reason, telegram=None):
    """
    Sincroniza con el FIN EXACTO de la jugada anterior en la mesa.
    Captura la pantalla con el resultado previo (listón de victoria o road actualizado)
    como REFERENCIA visual para el usuario y Telegram.
    EMITE LA SEÑAL INMEDIATAMENTE para que el usuario reciba la notificación con antelación,
    garantizando que cuando abra la ventana de apuestas, tenga los 15 segundos COMPLETOS.
    Retorna: (success, clean_screenshot, confirmed_base_count, sequence, probability, strat_name, reason, session)
    """
    print(f"\n  🕐 [{ts()}] Sincronizando con fin de ronda previa en [{table_name}]...")
    start_wait = time.time()
    MAX_WAIT_FINISH = 35

    base_data = scraper.get_table_data(table_name)
    base_count = len(base_data.get("history", []))
    last_known_screenshot = base_data.get("screenshot_path")

    # 1. VERIFICACIÓN INMEDIATA: ¿La ronda anterior está mostrando listón de victoria justo ahora?
    init_img = load_pil_image(last_known_screenshot)
    init_concluded, init_winner = detector.is_round_concluded(init_img) if init_img else (False, None)

    if init_concluded:
        w_label = "JUGADOR 🔵" if init_winner == "P" else ("BANCA 🔴" if init_winner == "B" else "EMPATE 🟢")
        print(f"  🎯 [{ts()}] ¡Mano previa recién concluida en [{table_name}] ({w_label})!")
        print(f"     -> Captura tomada con resultado anterior (REFERENCIA). Disparando señal con antelación...")

        # Emisión anticipada para que llegue a Telegram/Web antes de que empiece el conteo de 15s
        session = None
        if telegram:
            session = phase_signal(
                telegram, table_name, last_known_screenshot,
                sequence, probability, strat_name, reason,
                base_count=base_count
            )

        print(f"     -> Esperando apertura limpia de la nueva ventana de 15s...")
        detector.wait_until_clean(scraper, table_name, max_wait=8)
        clean_data = scraper.get_table_data(table_name)
        confirmed_base = len(clean_data.get("history", []))
        return True, last_known_screenshot, confirmed_base, sequence, probability, strat_name, reason, session

    # 2. Si no estaba concluyendo de inmediato, monitorear activamente hasta que concluya la mano
    print(f"  ⏳ [{ts()}] Esperando desenlace de la mano previa en [{table_name}] para capturar resultado anterior...")

    while time.time() - start_wait < MAX_WAIT_FINISH:
        time.sleep(0.30)
        data = scraper.get_table_data(table_name)
        screenshot = data.get("screenshot_path")
        card_img = load_pil_image(screenshot)

        if not card_img:
            continue

        concluded, winner_code = detector.is_round_concluded(card_img)
        curr_hist = data.get("history", [])
        curr_count = len(curr_hist)

        # Condición 1: Aparece el listón de victoria de la mano previa
        if concluded:
            w_label = "JUGADOR 🔵" if winner_code == "P" else ("BANCA 🔴" if winner_code == "B" else "EMPATE 🟢")
            print(f"  🎯 [{ts()}] Mano previa finalizada ({w_label}) en [{table_name}].")
            print(f"     -> Captura guardada con resultado anterior (REFERENCIA). Disparando señal con antelación...")

            session = None
            if telegram:
                session = phase_signal(
                    telegram, table_name, screenshot,
                    sequence, probability, strat_name, reason,
                    base_count=base_count
                )

            print(f"     -> Esperando apertura limpia de la nueva ventana de 15s...")
            detector.wait_until_clean(scraper, table_name, max_wait=8)
            clean_data = scraper.get_table_data(table_name)
            confirmed_base = len(clean_data.get("history", []))
            return True, screenshot, confirmed_base, sequence, probability, strat_name, reason, session

        # Condición 2: Zapato incrementó (se registró la mano finalizada)
        elif curr_count > base_count:
            last_res = curr_hist[-1] if curr_hist else "P"
            w_label = "JUGADOR 🔵" if last_res == "P" else ("BANCA 🔴" if last_res == "B" else "EMPATE 🟢")
            print(f"  🎯 [{ts()}] Zapato actualizado con resultado previo ({w_label}) en [{table_name}].")

            # Revalidar si la secuencia sigue vigente con la nueva jugada en zapato
            should, new_seq, _, new_prob, _, new_strat, new_reason = analyzer.analyze_history(
                table_name, curr_hist, total_hands=curr_count
            )
            if should and new_prob >= config.MIN_CONFIDENCE_THRESHOLD:
                print(f"     -> Estrategia [{new_strat}] ratificada ({new_prob}%). Disparando señal con antelación...")
                session = None
                if telegram:
                    session = phase_signal(
                        telegram, table_name, screenshot,
                        new_seq, new_prob, new_strat, new_reason,
                        base_count=curr_count
                    )

                print(f"     -> Esperando apertura limpia de la nueva ventana de 15s...")
                detector.wait_until_clean(scraper, table_name, max_wait=8)
                return True, screenshot, curr_count, new_seq, new_prob, new_strat, new_reason, session
            else:
                # El resultado cambió la tendencia (ej. empate o quiebre)
                print(f"  ⚠️ [{ts()}] El nuevo resultado modificó la estrategia en [{table_name}]. Re-analizando mesas...")
                return False, None, 0, None, None, None, None, None

    print(f"  ⏳ [{ts()}] Tiempo de espera de mano previa agotado en [{table_name}]. Reescaneando...")
    return False, None, 0, None, None, None, None, None


# ──────────────────────────────────────────────
# FASE 3 — ENVIAR SEÑAL A TELEGRAM (DYNASTY)
# ──────────────────────────────────────────────
def phase_signal(telegram, table_name, screenshot, sequence, probability, strat_name, reason, base_count=0):
    print(f"\n  📲 [{ts()}] Enviando señal de [{table_name}] con plan de 6 tiros a Baccarat Dynasty...")

    ok, msg = telegram.send_baccarat_signal(
        table_name=table_name,
        sequence=sequence,
        probability=probability,
        screenshot_path=screenshot,
        strategy_name=strat_name,
        base_hand_count=base_count,
    )

    if ok:
        print(f"  ✅ Señal estándar enviada con éxito al canal de Telegram.")
        return BaccaratSession(table_name, sequence, strat_name, probability, reason)
    else:
        print(f"  ❌ Error enviando señal a Telegram: {msg}")
        return None


# ──────────────────────────────────────────────
# FASE 4 — TRACKING EN TIEMPO REAL Y APUESTAS
# ──────────────────────────────────────────────
def phase_tracking(telegram, scraper, detector, session, auto_bettor, base_count=0, first_bet_placed=False):
    table_name = session.table_name
    strat_name = session.strategy

    sep()
    print(f"  🔒 [{ts()}] SESIÓN ACTIVA — [{table_name}] | Estrategia: [{strat_name}]")
    print(f"     Telegram: Dynasty activa | Auto-Bettor: Fichas Inteligentes en pantalla ({auto_bettor.currency})")
    print(f"     ℹ️  La captura enviada es REFERENCIA visual de la mesa previa ({base_count} jugadas).")
    print(f"     🎯 El Tiro 1 de la secuencia se evalúa en la NUEVA MANO (#{base_count+1}).")
    sep()

    first_round_done = False
    current_base_count = base_count

    while not session.is_finished():
        attempt_n   = session.attempt_number
        attempt_idx = session.current_attempt
        prediction  = session.current_prediction
        pred_label  = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        bet_amount, current_step, units = auto_bettor.get_bet_amount(attempt_idx)

        focus_tag = f"🎯 [PASO MARTINGALA #{current_step+1}]" if auto_bettor.persistent_martingale else (
            "🎯 [TIRO BAJO]" if attempt_n <= 3 else "⚡ [PROGRESIÓN MARTINGALA]"
        )
        print(f"\n  ⏱  [{ts()}] INTENTO {attempt_n}/6 {focus_tag} — {bet_amount:.2f} {auto_bettor.currency} a {pred_label}")

        # 1. EJECUCIÓN FÍSICA DE APUESTA
        # Si el tiro 1 ya fue ejecutado inmediatamente al abrir la ventana de 15s, no duplicar clic
        if first_bet_placed and attempt_idx == 0 and not first_round_done:
            print(f"     → [AutoBettor] Tiro 1 ya ejecutado al inicio de la ventana de 15s ({bet_amount:.2f} {auto_bettor.currency}).")
            if current_base_count <= 0:
                data_start = scraper.get_table_data(table_name)
                current_base_count = len(data_start.get("history", []))
        else:
            # Esperar que la mesa esté 100% limpia antes de apostar el siguiente tiro
            detector.wait_until_clean(scraper, table_name, max_wait=8)

            data_start = scraper.get_table_data(table_name)
            current_base_count = len(data_start.get("history", []))

            dynamic_coords = scraper.slot_bets.get(table_name)
            ok_bet, bet_msg = auto_bettor.execute_bet(
                prediction=prediction,
                attempt_index=attempt_idx,
                table_name=table_name,
                dynamic_coords=dynamic_coords
            )
            print(f"     → [AutoBettor] {bet_msg}")

        first_round_done = True

        # 2. BLINDAJE 2: Esperar confirmación visual de que la nueva mano COMENZÓ (cartas físicas repartidas)
        cards_seen = False
        cards_wait_start = time.time()
        while time.time() - cards_wait_start < 30:
            time.sleep(0.25)
            _d2 = scraper.get_table_data(table_name)
            _img2 = load_pil_image(_d2.get("screenshot_path"))
            if _img2 and detector.are_cards_present(_img2):
                cards_seen = True
                print(f"  🃏 [{ts()}] Cartas en mesa confirmadas en [{table_name}] — nueva mano en curso (#{current_base_count+1}).")
                break

        # 3. BLINDAJE 3: Detección estricta del resultado de la NUEVA mano
        result = None
        screenshot = None
        round_start_time = time.time()
        MAX_ROUND_WAIT = 50

        while not session.is_finished() and (time.time() - round_start_time < MAX_ROUND_WAIT):
            time.sleep(POLL_FAST_INTERVAL)
            data        = scraper.get_table_data(table_name)
            screenshot  = data.get("screenshot_path")
            current_img = load_pil_image(screenshot)

            # Detección por listón de victoria
            ribbon_res = detector.read_result(current_img, table_name)

            # Detección por bola añadida al Road
            curr_hist  = data.get("history", [])
            curr_count = len(curr_hist)

            # Solo se acepta resultado si las NUEVAS cartas fueron vistas en la mesa
            if ribbon_res is not None and cards_seen:
                # Ratificar con la actualización del Road oficial de la mesa
                time.sleep(0.4)
                data_check = scraper.get_table_data(table_name)
                hist_check = data_check.get("history", [])
                if len(hist_check) > current_base_count:
                    result = hist_check[-1]
                    logger.info(f"[{table_name}] Resultado ratificado por Road oficial de la mesa: {result}")
                else:
                    result = ribbon_res
                    logger.info(f"[{table_name}] Resultado verificado por listón de nueva mano: {result}")
                break
            elif cards_seen and curr_count > current_base_count and not detector.are_cards_present(current_img):
                result = curr_hist[-1]
                logger.info(f"[{table_name}] Resultado verificado por Road (+1 bola en mano #{curr_count}): {result}")
                break

        # BLINDAJE ANTI-FALSO WIN: Si no hubo cartas o no hubo nuevo resultado confirmado en Road
        if result is None:
            if cards_seen:
                data = scraper.get_table_data(table_name)
                curr_hist = data.get("history", [])
                if len(curr_hist) > current_base_count:
                    result = curr_hist[-1]
                else:
                    result = "T"
                    print(f"  ⚠️ [{ts()}] Timeout con cartas vistas pero sin incremento en zapato — tratando como empate de seguridad.")
            else:
                # Jamás declarar victoria si la mano no fue detectada
                result = "T"
                print(f"  ⚠️ [{ts()}] Sin cartas vistas en [{table_name}] — reintentando tiro como empate para evitar falsos WINs.")

        pred_label = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        res_label  = "JUGADOR 🔵" if result == "P" else ("BANCA 🔴" if result == "B" else "EMPATE 🟢")
        print(f"  🔍 [{ts()}] [VERIFICACIÓN {table_name}]: Salió {res_label} | Predicción era {pred_label}")

        # ── CASO A: EMPATE ─────────────────────────────────────────
        if result == "T":
            print(f"  🟢 [{ts()}] EMPATE detectado en pantalla.")
            print(f"     -> Apuesta devuelta intacta. El intento {attempt_n} se mantiene para el próximo tiro.")
            detector.wait_until_clean(scraper, table_name, max_wait=8)
            d_tie = scraper.get_table_data(table_name)
            current_base_count = len(d_tie.get("history", []))
            continue

        # ── CASO B: RESULTADO 'P' O 'B' ─────────────────────────────
        outcome = session.register_result(result)

        if outcome.startswith("win_"):
            win_n = int(outcome.split("_")[1])
            auto_bettor.record_win(attempt_idx)
            auto_bettor.reset_martingale()  # Garantizar reinicio limpio para la siguiente mesa
            print(f"\n  🏆 [{ts()}] ¡ACIERTO EN INTENTO {win_n}! Ganó {res_label} (coincide con {pred_label}).")
            print(f"     Ganancia neta ciclo: +{auto_bettor.base_bet:.2f} {auto_bettor.currency} | Balance total: {auto_bettor.session_profit:.2f} {auto_bettor.currency}")

            if telegram:
                telegram.send_result_message(
                    table_name=table_name,
                    result_type="win",
                    attempt_number=win_n,
                    screenshot_path=screenshot,
                    strategy_name=strat_name,
                )
            detector.wait_until_clean(scraper, table_name, max_wait=8)
            return "win"

        elif outcome == "continue":
            auto_bettor.record_step_loss(attempt_idx)
            next_n = session.attempt_number
            next_pred = session.current_prediction
            n_label = "JUGADOR 🔵" if next_pred == "P" else "BANCA 🔴"
            print(f"     ✗ Intento {attempt_n} falló. Salió [{res_label}], se apostó a [{pred_label}].")
            print(f"       -> Duplicando Martingala al Intento {next_n} ({n_label}).")

            # Notificar inmediatamente a la Web y Telegram que pasamos al siguiente tiro
            try:
                from core.web_bridge import publish_attempt_to_web
                publish_attempt_to_web(next_n, table_name=table_name)
            except Exception as e:
                logger.warning(f"Error actualizando tiro en Web: {e}")

            if telegram:
                try:
                    telegram.send_next_attempt_message(table_name, next_n, next_pred, screenshot_path=screenshot)
                except Exception as e:
                    logger.warning(f"Error enviando mensaje de siguiente intento a Telegram: {e}")

            detector.wait_until_clean(scraper, table_name, max_wait=8)
            d_next = scraper.get_table_data(table_name)
            current_base_count = len(d_next.get("history", []))

        elif outcome == "loss":
            auto_bettor.record_step_loss(attempt_idx)
            auto_bettor.record_table_finished_loss(attempt_idx)
            print(f"\n  💔 [{ts()}] LOSS ALCANZADO (6 intentos) en [{table_name}].")
            print(f"     Balance acumulado: {auto_bettor.session_profit:.2f} {auto_bettor.currency}")

            if telegram:
                telegram.send_result_message(
                    table_name=table_name,
                    result_type="loss",
                    attempt_number=6,
                    screenshot_path=screenshot,
                    strategy_name=strat_name,
                )
            detector.wait_until_clean(scraper, table_name, max_wait=8)
            return "loss"

    return "loss" if session.state == "loss" else "win"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    telegram = TelegramNotifier()
    telegram.release_active_table()

    # Detección o selección de Divisa (USD / TRY)
    currency_key = "USD"
    if any(arg in sys.argv for arg in ("--try", "--turca", "-try", "-turca")):
        currency_key = "TRY"
    elif any(arg in sys.argv for arg in ("--usd", "--dolares", "-usd", "-dolares")):
        currency_key = "USD"
    else:
        env_curr = os.getenv("AUTO_BET_CURRENCY", "").upper()
        if env_curr in ("TRY", "TURCA"):
            currency_key = "TRY"
        else:
            currency_key = "USD"

    curr_cfg = config.CURRENCY_MODES.get(currency_key, config.CURRENCY_MODES["USD"])
    betting_enabled = not any(arg in sys.argv for arg in ("--solo-senales", "--sin-jugadas", "--no-bets"))

    auto_bettor = AutoBettor(
        enabled=betting_enabled,
        currency=curr_cfg["name"],
        chip1_value=curr_cfg["chip1_value"],
        chip2_value=curr_cfg["chip2_value"],
        currency_symbol=curr_cfg["symbol"],
        stop_loss=config.AUTO_BET_STOP_LOSS,
        take_profit=config.AUTO_BET_TAKE_PROFIT,
        persistent_martingale=config.AUTO_BET_PERSISTENT_MARTINGALE,
        max_steps=config.AUTO_BET_MAX_STEPS,
        currency_label=curr_cfg["label"]
    )
    print_banner(auto_bettor)

    stats_tracker = StatsTracker()
    analyzer = BaccaratAnalyzer(
        min_delay=config.MIN_SIGNAL_DELAY,
        max_delay=config.MAX_SIGNAL_DELAY,
        min_confidence=config.MIN_CONFIDENCE_THRESHOLD,
        stats_tracker=stats_tracker,
    )
    scraper = StakeBaccaratScraper(target_tables=config.TARGET_TABLES)
    detector = ResultDetector()

    print(f"\n⏳ Tienes {STARTUP_DELAY}s para abrir Stake y dejar Baccarat Multiplay visible.\n")
    countdown(STARTUP_DELAY, "Inicio de escaneo en")
    print(f"\n🚀 ¡Baccarat Auto-Bettor VIP ACTIVO en {curr_cfg['label']}!\n")

    signal_count = 0

    while True:
        telegram.stats_tracker.decrement_table_cooldowns()
        telegram.release_active_table()

        if auto_bettor.is_paused_by_limits:
            print(f"\n🛑 {auto_bettor.pause_reason}. Bot pausado de seguridad.")
            print("Presiona Ctrl + C para salir o actualiza tus límites en .env.")
            time.sleep(30)
            continue

        # 1. ANÁLISIS DE MESAS (Priorizando mesas concluyendo la mano previa)
        cand = phase_analysis(scraper, analyzer, stats_tracker, auto_bettor, detector)
        if cand is None:
            print(f"  ⏳ [{ts()}] Sin mesas en rango óptimo. Esperando mesa disponible...")
            countdown(ANALYSIS_COOLDOWN, "Reescaneando en")
            continue

        table_name, screenshot, sequence, probability, total_hands, strat_name, reason = cand

        # 2. SINCRONIZAR CON FIN DE JUGADA ANTERIOR Y EMISIÓN ANTICIPADA
        ok_sync, clean_screenshot, base_count, sequence, probability, strat_name, reason, session = phase_wait_round_end(
            scraper, detector, analyzer, table_name, sequence, probability, strat_name, reason, telegram=telegram
        )
        if not ok_sync or clean_screenshot is None:
            continue

        # Si por alguna eventualidad la señal no se emitió dentro del sincronizador, emitir como respaldo
        if session is None:
            session = phase_signal(
                telegram, table_name, clean_screenshot,
                sequence, probability, strat_name, reason
            )

        if session is None:
            print("  ⚠️ Falló envío a Telegram o mesa bloqueada. Reintentando en 5s...")
            time.sleep(5)
            continue

        # 3. EJECUTAR APUESTA FÍSICA INMEDIATA DEL TIRO 1 (SEGUNDO 0 - 15s COMPLETOS)
        dynamic_coords = scraper.slot_bets.get(table_name)
        first_bet_ok, bet_msg = auto_bettor.execute_bet(
            prediction=sequence[0],
            attempt_index=0,
            table_name=table_name,
            dynamic_coords=dynamic_coords
        )
        print(f"  ⚡ [{ts()}] Apuesta Tiro 1 colocada en mesa (Segundo 0): {bet_msg}")

        signal_count += 1
        print(f"\n  📊 Señal #{signal_count} activa en [{table_name}] — Estrategia: [{strat_name}] ({probability}%)")

        # 5. TRACKING VISUAL + SEGUIMIENTO DE LA NUEVA MANO EN VIVO
        try:
            final_result = phase_tracking(
                telegram, scraper, detector, session, auto_bettor,
                base_count=base_count,
                first_bet_placed=first_bet_ok
            )
        except Exception as e:
            logger.error(f"Error en phase_tracking: {e}")
            final_result = "loss"

        analyzer.register_signal_sent(table_name)
        telegram.release_active_table()

        # 5. CONTINUACIÓN FLUIDA A LA SIGUIENTE MESA
        if final_result == "win":
            auto_bettor.reset_martingale()
            print(f"\n🎉 Victoria confirmada. Próxima mesa en {SESSION_PAUSE}s...")
            countdown(SESSION_PAUSE, "Buscando mesa en")
        else:
            print(f"\n💔 LOSS en [{table_name}]. Buscando de inmediato siguiente mesa con Martingala Persistente...")
            countdown(POST_LOSS_PAUSE, "Buscando nueva mesa en")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Bot detenido por el usuario.")
        print("¡Hasta la próxima! 🍀")
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("  [ERROR INESPERADO AL EJECUTAR EL BOT]")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        try:
            input("\nPresiona ENTER para cerrar la ventana...")
        except Exception:
            pass
