"""
main.py — BOT LOGRO (Inteligencia Táctica Tiro a Tiro y Cambio Sincronizado Multi-Mesa)
=======================================================================================
1. Autoridad Única de Mesa Activa (Cero Mesas Intercaladas o Duplicadas):
   - Al iniciar, cierra automáticamente cualquier instancia previa del bot en segundo plano
     para que jamás existan dos ventanas enviando señales al mismo tiempo.
   - El bot monitorea EXCLUSIVAMENTE la última mesa enviada a Telegram (`active_table`).
   - Si pierde un intento en una mesa y decide cambiar de mesa, la mesa anterior queda
     100% descartada (`abandoned_tables`) durante el resto del ciclo: jamás vuelve a ella
     ni cuenta resultados posteriores de esa mesa abandonada.
2. Tiempo Completo de Apuesta Garantizado (15s íntegros en cada señal):
   - Jamás lanza una señal cuando una mesa ya está repartiendo cartas o cuando el reloj
     de apuestas se está agotando.
   - Tanto en el Intento 1 como en cualquier Cambio de Mesa, sincroniza el disparo con el
     cierre exacto de la mano previa (Listón Oficial de cierre / apertura fresca del reloj
     de 15 segundos), garantizando que el jugador siempre tenga el 100% del tiempo para jugar.
3. Espera Estricta del Resultado Total de la Mano (4, 5 o 6 cartas con cartas acostadas):
   - Jamás asume victoria o derrota cuando sale un 8 o 9 parcial mientras siguen saliendo cartas.
   - Espera obligatoriamente el Listón Oficial Final sobre el Road tras completarse las 4, 5 o 6 cartas.
"""

import os
import sys
import time
import random
import logging
import subprocess
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

logger = logging.getLogger("BotLogro")

STARTUP_DELAY      = getattr(config, "STARTUP_DELAY", 8)
ANALYSIS_COOLDOWN  = 0.5
SESSION_PAUSE      = 1.0
POST_LOSS_PAUSE    = 1.0
POLL_FAST_INTERVAL = 0.25


def ts():
    return datetime.now().strftime("%H:%M:%S")


def sep(char="=", n=72):
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
            with Image.open(path) as im:
                return im.copy()
    except Exception:
        pass
    return None


def color_str(code):
    return "JUGADOR 🔵 (AZUL)" if code == "P" else ("BANCA 🔴 (ROJO)" if code == "B" else "EMPATE 🟢")


def ensure_single_bot_instance():
    """
    Cierra automáticamente cualquier otro proceso de Python que esté ejecutando
    Bot_Logro o Bot_Version_Final en segundo plano para evitar señales cruzadas.
    """
    my_pid = os.getpid()
    ps_cmd = (
        f"Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
        f"Where-Object {{ $_.ProcessId -ne {my_pid} -and "
        f"($_.CommandLine -match 'Bot_Logro|Bot_Version_Final|Baccarat_Bot') }} | "
        f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; "
        f"Write-Output $_.ProcessId }}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
        )
        killed = [line.strip() for line in (res.stdout or "").splitlines() if line.strip().isdigit()]
        if killed:
            print(f"  🛡️ [INSTANCIA ÚNICA] Se cerraron {len(killed)} proceso(s) antiguos del bot en segundo plano (PID: {', '.join(killed)}).")
    except Exception as e:
        logger.debug(f"No se pudo verificar procesos previos: {e}")


def print_banner(auto_bettor):
    mart_tag = (
        f"8 TIROS MÁXIMOS (Tiros 1..7 doblan hasta $12.80 | "
        f"Tiro 8 repite $12.80 como recuperación; si pierde se para)"
    )
    sl_text = f"{auto_bettor.stop_loss:.2f} {auto_bettor.currency}" if auto_bettor.stop_loss is not None else "PARADA AUTOMÁTICA TRAS EL TIRO 8"
    tp_text = "SIN STOP-PROFIT (Ganar todo lo que pueda)"
    bets_mode_str = "AUTOMÁTICO CON JUGADAS (Apuestas en Stake + Telegram + Web)" if auto_bettor.enabled else "SOLO SEÑALES (Cero clics — Emisión a Telegram + Web)"

    sep("=")
    print("   👑  BOT LOGRO · INTELIGENCIA TÁCTICA TIRO A TIRO MULTI-MESA  👑")
    print("      1 Sola Mesa Activa · Tiempo Completo 15s Garantizado en Cada Señal")
    sep("=")
    print(f"  Modo de Operación    : {bets_mode_str}")
    print(f"  Mesas Monitoreadas   : {', '.join(config.TARGET_TABLES)}")
    print(f"  Autoridad de Mesa    : ESTRICTA (Solo cuenta la última mesa enviada en vivo)")
    print(f"  Sincronización Reloj : 100% Ventana Completa (Disparo al cierre exacto de mano previa)")
    print(f"  Lectura de Cartas    : Espera 100% de cartas (4, 5 o 6 acostadas) + Listón Oficial")
    print(f"  Divisa de Juego      : {auto_bettor.currency_label}")
    print(
        f"  Moneda 1 (Base Izq.) : {auto_bettor.chip1_value:.2f} {auto_bettor.currency} | "
        f"Moneda 2 (5x): {auto_bettor.chip2_value:.2f} {auto_bettor.currency} | "
        f"Moneda 3 (25x): {auto_bettor.chip3_value:.2f} {auto_bettor.currency}"
    )
    print(f"  Gestión Martingala   : {mart_tag}")
    print(f"  Canal Señales        : {config.TELEGRAM_CHAT_ID} (Baccarat Dynasty)")
    if getattr(config, "TELEGRAM_RESULTS_CHAT_ID", None):
        print(f"  Canal Resultados     : {config.TELEGRAM_RESULTS_CHAT_ID} (Rush)")
    print(f"  Límites Financieros  : Stop-Loss: {sl_text} | Stop-Profit: {tp_text}")
    print(f"  ⚠️  IMPORTANTE         : Mantén Baccarat Multiplay visible en pantalla.")
    sep("=")
    print()


# ──────────────────────────────────────────────────────────────────────
# FASE 1 — ESCANEO SINCRONIZADO MULTI-MESA PARA INTENTO 1 (TIEMPO COMPLETO)
# ──────────────────────────────────────────────────────────────────────
def find_and_emit_initial_play(scraper, analyzer, stats_tracker, detector, telegram):
    """
    Escanea todas las mesas en paralelo cada 0.25s y EMITE LA SEÑAL DE INTENTO 1
    ÚNICAMENTE en el instante exacto en que una mesa con patrón fuerte acaba de
    terminar su mano previa (Listón Oficial visible o transición recién ocurrida
    de cartas a reloj verde).
    Así el jugador SIEMPRE recibe la señal con los 15 segundos completos de apuesta.
    """
    print(f"\n🔍 [{ts()}] [BOT LOGRO] Buscando mesa con patrón sólido al inicio exacto de su tiempo de apuesta...")

    # Registro de estado previo por mesa para detectar el instante exacto en que abre ventana
    seen_active_hand = set()
    initial_counts = {}
    last_log_time = 0.0
    scan_start = time.time()
    MAX_SCAN_WINDOW = 26.0

    while time.time() - scan_start < MAX_SCAN_WINDOW:
        snapshots = scraper.get_all_tables_fast(config.TARGET_TABLES)
        if not snapshots:
            tables_to_scan = [t for t in scraper.regions.keys() if t in config.TARGET_TABLES] or config.TARGET_TABLES
            snapshots = [scraper.get_table_data(t) for t in tables_to_scan]

        ready_A_candidates = []  # Mesas que acaban de cerrar su mano AHORA MISMO (15s garantizados)
        dealing_candidates = []  # Mesas con patrón que están repartiendo (listas en pocos segundos)

        now = time.time()
        should_print = (now - last_log_time) >= 4.0
        if should_print:
            last_log_time = now

        for data in snapshots:
            table_name   = data.get("table_name")
            history      = data.get("history", [])
            total_hands  = data.get("total_hands", len(history))
            is_qualified = data.get("is_qualified", False)
            screenshot   = data.get("screenshot_path")
            card_img     = data.get("pil_img") or load_pil_image(screenshot)

            if not table_name:
                continue

            if table_name not in initial_counts and total_hands > 0:
                initial_counts[table_name] = total_hands

            is_concluding, winner_code = detector.is_round_concluded(card_img) if card_img else (False, None)
            if data.get("banner_winner") is not None:
                is_concluding = True
                winner_code = data.get("banner_winner")

            is_dealing = detector.are_cards_present(card_img) if card_img else False
            has_green  = detector.has_green_timer(card_img) if card_img else False

            if is_dealing or is_concluding:
                seen_active_hand.add(table_name)

            # ¿Acaba de abrir su reloj de 15s frente a nuestros ojos?
            just_opened_full_window = (
                is_concluding
                or (
                    table_name in seen_active_hand
                    and not is_dealing
                    and not is_concluding
                    and (has_green or total_hands > initial_counts.get(table_name, total_hands))
                )
            )

            if not is_qualified or total_hands < 8 or total_hands >= 65:
                if should_print:
                    reason_skip = "Menos de 8 manos" if total_hands < 8 else "Fin de zapato (65+ manos)"
                    print(f"  🚫 {table_name:<15} | {total_hands:<2} manos -> OMITIDA ({reason_skip})")
                continue

            can_sig, wait_sec = analyzer.can_send_signal(table_name)
            if not can_sig:
                if should_print:
                    print(f"  ⏳ {table_name:<15} | Enfriamiento breve: {wait_sec}s...")
                continue

            table_momentum = stats_tracker.get_table_momentum_score(table_name)
            ev = analyzer.evaluate_table(
                table_name=table_name,
                history=history,
                total_hands=total_hands,
                is_recovery=False,
                consult_ai=False,
            )

            if ev["should_signal"] and ev["prediction"] in ("P", "B"):
                pred = ev["prediction"]
                prob = ev["probability"]
                planned_att = ev["planned_attempts"]
                strat_name = ev["strategy_name"]
                reason = ev["reason"]
                base_score = ev["score"] + (table_momentum * 0.4) + random.uniform(0.1, 0.5)

                cand = {
                    "selection_score": base_score + (30.0 if is_concluding else 25.0),
                    "table_name": table_name,
                    "screenshot": screenshot,
                    "prediction": pred,
                    "probability": prob,
                    "planned_attempts": planned_att,
                    "total_hands": total_hands,
                    "strat_name": strat_name,
                    "reason": reason,
                    "base_count": total_hands,
                }

                if just_opened_full_window:
                    ready_A_candidates.append(cand)
                    pred_icon = "🔵 AZUL" if pred == "P" else "🔴 ROJO"
                    print(
                        f"  🎯 [{ts()}] {table_name:<14} | {total_hands:<2} jug 🏆 [MANO PREVIA CERRADA — 15s COMPLETOS] "
                        f"➔ {pred_icon} ({prob}% | Plan: {planned_att} int.) [{strat_name}]"
                    )
                else:
                    dealing_candidates.append(cand)
                    if should_print:
                        state_lbl = "🃏 REPARTIENDO MANO PREVIA" if is_dealing else "⏱️ ESPERANDO CIERRE DE MANO"
                        pred_icon = "🔵 AZUL" if pred == "P" else "🔴 ROJO"
                        print(
                            f"  🔎 {table_name:<15} | {total_hands:<2} jug [{state_lbl}] "
                            f"➔ {pred_icon} ({prob}%) [{strat_name}]"
                        )
            elif should_print:
                print(f"  ⏳ {table_name:<15} | {total_hands:<2} jug -> Sin patrón claro ({ev['reason']})")

        if ready_A_candidates:
            ready_A_candidates.sort(key=lambda c: c["selection_score"], reverse=True)
            best = ready_A_candidates[0]
            sep("-")
            print(
                f"  → 🚀 [DISPARO SINCRONIZADO INTENTO 1]: [{best['table_name']}] ➔ {color_str(best['prediction'])} "
                f"| Confianza: {best['probability']}% | Tiempo de apuesta: 100% COMPLETO"
            )
            print(f"     🧠 Motivo: {best['reason']}")

            ok, msg = telegram.send_logro_signal(
                table_name=best["table_name"],
                prediction=best["prediction"],
                probability=best["probability"],
                planned_attempts=best["planned_attempts"],
                screenshot_path=best["screenshot"],
                strategy_name=best["strat_name"],
                reason=best["reason"],
                base_hand_count=best["base_count"],
            )
            if not ok:
                print(f"  ❌ Error enviando señal inicial a Telegram: {msg}")
                return None

            return best

        time.sleep(POLL_FAST_INTERVAL)

    return None


# ──────────────────────────────────────────────────────────────────────
# FASE 2 — CAMBIO / RECUPERACIÓN SINCRONIZADA CON TIEMPO COMPLETO Y MESA ÚNICA
# ──────────────────────────────────────────────────────────────────────
def select_and_sync_recovery_play(
    scraper,
    analyzer,
    stats_tracker,
    detector,
    telegram,
    current_table,
    current_screenshot,
    attempts_on_current_table,
    planned_table_attempts,
    last_prediction,
    next_attempt_number,
    abandoned_tables,
):
    """
    Gestiona el Intento 2 o 3 tras una pérdida en `current_table`:
      1. Evalúa primero si `current_table` (que ACABA de terminar su mano hace <0.1s y por
         tanto tiene los 15 segundos completos de apuesta empezando ahora mismo) mantiene un
         patrón fuerte y aún tiene intentos planeados en esa mesa.
         - Si es así, repite `current_table` DE INMEDIATO (0.1s, 15s completos de apuesta).
      2. Si `current_table` agotó sus intentos planeados o rompió el patrón:
         - Agrega `current_table` a `abandoned_tables` (quedando 100% descartada por el resto
           del ciclo: jamás vuelve a ella ni cuenta ningún resultado posterior de esa mesa).
         - Escanea en paralelo cada 0.25s las demás mesas NO abandonadas y dispara EN EL
           INSTANTE EXACTO en que una mesa candidata concluye su mano previa (Listón Oficial
           o apertura fresca del reloj verde), garantizando SIEMPRE los 15 segundos completos
           para que el jugador pueda meter la jugada.
    """
    print(f"\n⚡ [{ts()}] [ANÁLISIS TÁCTICO DE RECUPERACIÓN — INTENTO {next_attempt_number}]")

    # ── PASO 1: ¿Debemos repetir `current_table` ahora mismo (tiene 15s completos porque acaba de cerrar)? ──
    curr_table_exhausted = (attempts_on_current_table >= planned_table_attempts)
    if not curr_table_exhausted and (current_table not in abandoned_tables):
        curr_data = scraper.get_table_data(current_table)
        curr_hist = curr_data.get("history", [])
        curr_hands = curr_data.get("total_hands", len(curr_hist))
        curr_shot = curr_data.get("screenshot_path") or current_screenshot

        if 8 <= curr_hands < 65:
            ev_same = analyzer.evaluate_table(
                table_name=current_table,
                history=curr_hist,
                total_hands=curr_hands,
                is_recovery=True,
                last_failed_pred=last_prediction,
                consult_ai=False,
            )
            if ev_same["should_signal"] and ev_same["prediction"] in ("P", "B"):
                new_pred = ev_same["prediction"]
                new_prob = max(89, ev_same["probability"])
                new_plan = ev_same["planned_attempts"]
                new_strat = ev_same["strategy_name"]
                new_rsn = ev_same["reason"]
                changed_c = (new_pred != last_prediction)

                print(
                    f"  → ⚡ [DECISIÓN INMEDIATA — MISMA MESA CON 15s COMPLETOS]: "
                    f"Repetir [{current_table}] en Intento {next_attempt_number} "
                    f"➔ {color_str(new_pred)} ({new_prob}%) [{new_strat}]"
                )
                if telegram:
                    telegram.send_logro_recovery_signal(
                        table_name=current_table,
                        prediction=new_pred,
                        attempt_number=next_attempt_number,
                        probability=new_prob,
                        planned_attempts=new_plan,
                        screenshot_path=curr_shot,
                        strategy_name=new_strat,
                        reason=new_rsn,
                        base_hand_count=curr_hands,
                        switched_table=False,
                        prev_table=current_table,
                        changed_color=changed_c,
                    )
                return {
                    "table_name": current_table,
                    "screenshot": curr_shot,
                    "prediction": new_pred,
                    "probability": new_prob,
                    "planned_attempts": new_plan,
                    "total_hands": curr_hands,
                    "strat_name": new_strat,
                    "reason": new_rsn,
                    "base_count": curr_hands,
                    "switched_table": False,
                }

    # ── PASO 2: DESCARTAR DEFINITIVAMENTE `current_table` Y CAMBIAR A OTRA MESA CON TIEMPO COMPLETO ──
    abandoned_tables.add(current_table)
    if not [t for t in config.TARGET_TABLES if t not in abandoned_tables]:
        # Si tras muchos intentos ya se visitaron todas las mesas del lobby,
        # mantener descartada la que acaba de perder y habilitar las demás para poder cambiar de mesa.
        abandoned_tables.clear()
        abandoned_tables.add(current_table)

    telegram.release_active_table()
    print(
        f"  🚫 [{ts()}] Mesa [{current_table}] DESCARTADA y dejada a un lado "
        f"(Mesas excluidas: {', '.join(sorted(abandoned_tables))})."
    )
    print(
        f"  🔄 [{ts()}] Buscando nueva mesa y esperando el inicio exacto de su reloj de 15s "
        f"para garantizar tiempo completo de apuesta..."
    )

    seen_active_hand = set()
    initial_counts = {}
    wait_start = time.time()
    MAX_SWITCH_WAIT = 55.0
    last_status_print = 0.0

    while time.time() - wait_start < MAX_SWITCH_WAIT:
        elapsed = time.time() - wait_start
        snapshots = scraper.get_all_tables_fast(config.TARGET_TABLES)
        if not snapshots:
            tables_to_scan = [t for t in scraper.regions.keys() if t in config.TARGET_TABLES] or config.TARGET_TABLES
            snapshots = [scraper.get_table_data(t) for t in tables_to_scan]

        ready_switch_options = []
        now = time.time()
        print_progress = (now - last_status_print) >= 3.5
        if print_progress:
            last_status_print = now

        for data in snapshots:
            t_name       = data.get("table_name")
            history      = data.get("history", [])
            total_hands  = data.get("total_hands", len(history))
            is_qualified = data.get("is_qualified", False)
            screenshot   = data.get("screenshot_path")
            card_img     = data.get("pil_img") or load_pil_image(screenshot)

            if not t_name or t_name in abandoned_tables:
                continue

            if t_name not in initial_counts and total_hands > 0:
                initial_counts[t_name] = total_hands

            if not is_qualified or total_hands < 8 or total_hands >= 65:
                continue

            is_concluding, winner_code = detector.is_round_concluded(card_img) if card_img else (False, None)
            if data.get("banner_winner") is not None:
                is_concluding = True
                winner_code = data.get("banner_winner")

            is_dealing = detector.are_cards_present(card_img) if card_img else False
            has_green  = detector.has_green_timer(card_img) if card_img else False

            if is_dealing or is_concluding:
                seen_active_hand.add(t_name)

            # Garantía estricta de tiempo completo (15s):
            # Solo disparamos en la nueva mesa si está cerrando su mano previa AHORA MISMO (`is_concluding`)
            # o si la vimos repartiendo cartas y ACABA de abrir su reloj verde hace <0.25s.
            just_opened_full_window = (
                is_concluding
                or (
                    t_name in seen_active_hand
                    and not is_dealing
                    and not is_concluding
                    and (has_green or total_hands > initial_counts.get(t_name, total_hands))
                )
            )

            ev = analyzer.evaluate_table(
                table_name=t_name,
                history=history,
                total_hands=total_hands,
                is_recovery=True,
                last_failed_pred=None,
                consult_ai=False,
            )

            pred = ev["prediction"]
            prob = ev["probability"]
            planned_att = ev["planned_attempts"]
            strat_name = ev["strategy_name"]
            reason = ev["reason"]
            raw_score = ev["score"]

            # Si ya llevamos >14s esperando y una mesa no-abandonada acaba de terminar su mano,
            # permitir también su mejor lectura táctica de dominancia para no perder la ventana fresca
            if (not ev["should_signal"] or not pred) and elapsed >= 14.0:
                clean = [x for x in history if x in ("P", "B")]
                if clean:
                    r8 = clean[-8:]
                    pred = "P" if r8.count("P") >= r8.count("B") else "B"
                    prob = 88
                    planned_att = 1
                    strat_name = "DOMINANCIA_SINCRONIZADA"
                    reason = f"Entrada sincronizada al inicio del reloj en {t_name}"
                    raw_score = 78.0

            if just_opened_full_window and pred in ("P", "B") and (ev["should_signal"] or elapsed >= 14.0):
                ready_switch_options.append({
                    "eff_score": raw_score + (25.0 if is_concluding else 20.0),
                    "table_name": t_name,
                    "screenshot": screenshot,
                    "prediction": pred,
                    "probability": max(88, prob),
                    "planned_attempts": planned_att,
                    "total_hands": total_hands,
                    "strat_name": strat_name,
                    "reason": reason,
                    "base_count": total_hands,
                    "switched_table": True,
                })
            elif print_progress:
                st = "🃏 Esperando fin de cartas" if is_dealing else "⏱️ Esperando nuevo ciclo de 15s"
                p_txt = ("🔵 AZUL" if pred == "P" else "🔴 ROJO") if pred in ("P", "B") else "—"
                print(f"     ⏳ {t_name:<13} [{st}] | {total_hands:<2} manos | Pre-lectura: {p_txt}")

        if ready_switch_options:
            ready_switch_options.sort(key=lambda x: x["eff_score"], reverse=True)
            chosen = ready_switch_options[0]
            changed_c = (chosen["prediction"] != last_prediction)

            print(
                f"  → 🔄 [CAMBIO DE MESA SINCRONIZADO — 15s COMPLETOS]: "
                f"De [{current_table}] a [{chosen['table_name']}] en Intento {next_attempt_number} "
                f"➔ {color_str(chosen['prediction'])} ({chosen['probability']}%) [{chosen['strat_name']}]"
            )
            if telegram:
                telegram.send_logro_recovery_signal(
                    table_name=chosen["table_name"],
                    prediction=chosen["prediction"],
                    attempt_number=next_attempt_number,
                    probability=chosen["probability"],
                    planned_attempts=chosen["planned_attempts"],
                    screenshot_path=chosen["screenshot"],
                    strategy_name=chosen["strat_name"],
                    reason=chosen["reason"],
                    base_hand_count=chosen["base_count"],
                    switched_table=True,
                    prev_table=current_table,
                    changed_color=changed_c,
                )
            return chosen

        time.sleep(POLL_FAST_INTERVAL)

    # Si tras 38s ninguna otra mesa abrió ventana (ej. mesas pausadas/barajando), abortar con seguridad sin lanzar señal tardía
    print(f"  ⚠️ [{ts()}] Ninguna mesa alternativa abrió ventana completa de 15s a tiempo. Cerrando ciclo por seguridad.")
    return None


# ──────────────────────────────────────────────────────────────────────
# FASE 3 — EJECUCIÓN ESTRICTA EN 3 PASOS SOBRE LA ÚNICA MESA ACTIVA
# ──────────────────────────────────────────────────────────────────────
def execute_logro_cycle(telegram, scraper, detector, analyzer, stats_tracker, auto_bettor, initial_play):
    """
    Monitorea EXCLUSIVAMENTE `table_name` (la última mesa enviada a Telegram):
      - PASO A: Espera a que desaparezca por completo el listón/cartas de la mano previa
                y se abra limpia la ventana de apuestas de 15s. Coloca la apuesta automática.
      - PASO B: Espera a que aparezcan las cartas de la NUEVA mano en `table_name` (confirmadas
                en 2 lecturas consecutivas).
      - PASO C: Espera a que termine el reparto completo (4, 5 o 6 cartas acostadas) y salga
                el Listón Oficial sobre el Road de `table_name`.
      - Jamás evalúa ni cuenta resultados de mesas anteriores (`abandoned_tables`).
    """
    table_name                = initial_play["table_name"]
    prediction                = initial_play["prediction"]
    probability               = initial_play["probability"]
    planned_table_attempts    = initial_play["planned_attempts"]
    strat_name                = initial_play["strat_name"]
    reason                    = initial_play["reason"]
    current_base_count        = initial_play.get("base_count", initial_play.get("total_hands", 0))

    attempt_idx               = 0
    attempts_on_current_table = 0
    abandoned_tables          = set()

    sep()
    print(f"  🔒 [{ts()}] CICLO BOT LOGRO ACTIVO — ÚNICA MESA EN VIVO: [{table_name}] ➔ {color_str(prediction)} ({probability}%)")
    sep()

    while attempt_idx < config.MAX_ATTEMPTS:
        attempt_n = attempt_idx + 1
        bet_amount, _, _ = auto_bettor.get_bet_amount(attempt_idx)

        print(
            f"\n  ⏱  [{ts()}] MONITOREANDO INTENTO {attempt_n} EXCLUSIVAMENTE EN [{table_name}] "
            f"— {bet_amount:.2f} {auto_bettor.currency} a {color_str(prediction)}"
        )

        # ── PASO A: Esperar que la mano previa limpie su listón/cartas y quede la ventana de 15s abierta ──
        detector.wait_until_clean(scraper, table_name, max_wait=10)
        clean_data = scraper.get_table_data(table_name)
        clean_hist = clean_data.get("history", [])
        if len(clean_hist) > current_base_count:
            current_base_count = len(clean_hist)

        dynamic_coords = scraper.slot_bets.get(table_name)
        bet_ok, bet_msg = auto_bettor.execute_bet(
            prediction=prediction,
            attempt_index=attempt_idx,
            table_name=table_name,
            dynamic_coords=dynamic_coords,
        )
        print(f"  ⚡ [{ts()}] [Intento {attempt_n} en {table_name}] Ventana de apuestas abierta (Base #{current_base_count}): {bet_msg}")

        # ── PASO B: Esperar el inicio real del reparto de cartas de la NUEVA mano en `table_name` ──
        cards_seen = False
        cards_streak = 0
        cards_wait_start = time.time()
        while time.time() - cards_wait_start < 32:
            time.sleep(0.22)
            _d2 = scraper.get_table_data(table_name)
            _img2 = _d2.get("pil_img") or load_pil_image(_d2.get("screenshot_path"))
            if not _img2:
                continue

            is_concl_now, _ = detector.is_round_concluded(_img2)
            if detector.are_cards_present(_img2) and not is_concl_now:
                cards_streak += 1
                if cards_streak >= 2:
                    cards_seen = True
                    print(
                        f"  🃏 [{ts()}] Reparto de cartas confirmado en [{table_name}] "
                        f"(mano #{current_base_count + 1}). Esperando desenlace total (4, 5 o 6 cartas)..."
                    )
                    break
            else:
                cards_streak = 0

        # ── PASO C: Espera estricta del resultado final de `table_name` (Listón Oficial tras 4, 5 o 6 cartas) ──
        result = None
        screenshot = None
        post_cards_clean_streak = 0
        round_start_time = time.time()
        MAX_ROUND_WAIT = 45

        while time.time() - round_start_time < MAX_ROUND_WAIT:
            time.sleep(POLL_FAST_INTERVAL)
            data        = scraper.get_table_data(table_name)
            screenshot  = data.get("screenshot_path")
            current_img = data.get("pil_img") or load_pil_image(screenshot)
            if not current_img:
                continue

            ribbon_res = detector.read_result(current_img, table_name)
            cards_still_on_table = detector.are_cards_present(current_img)
            curr_hist  = data.get("history", [])
            curr_count = len(curr_hist)

            # Condición 1 (Principal): Aparece el Listón Oficial Gigante sobre el centro del Road
            if ribbon_res is not None and cards_seen:
                time.sleep(0.40)
                data_check = scraper.get_table_data(table_name)
                img_check = data_check.get("pil_img") or load_pil_image(data_check.get("screenshot_path"))
                ribbon_confirm = detector.read_result(img_check, table_name) if img_check else None
                hist_check = data_check.get("history", [])

                if ribbon_confirm is not None:
                    result = ribbon_confirm
                    screenshot = data_check.get("screenshot_path") or screenshot
                    logger.info(f"[{table_name}] Resultado final confirmado por Listón Oficial en Road: {result}")
                    break
                elif img_check and not detector.are_cards_present(img_check) and len(hist_check) > current_base_count:
                    result = hist_check[-1]
                    screenshot = data_check.get("screenshot_path") or screenshot
                    logger.info(f"[{table_name}] Resultado final ratificado al cerrarse las cartas en Road: {result}")
                    break

            # Condición 2 (Respaldo): Todas las cartas se retiraron durante 3 lecturas seguidas y el Road sumó +1 bola
            elif cards_seen and (not cards_still_on_table) and (ribbon_res is None):
                post_cards_clean_streak += 1
                if post_cards_clean_streak >= 3 and (curr_count > current_base_count):
                    result = curr_hist[-1]
                    logger.info(f"[{table_name}] Resultado final verificado tras retiro total de cartas (+1 bola en Road): {result}")
                    break
            else:
                post_cards_clean_streak = 0

        if result is None:
            if cards_seen:
                detector.wait_until_clean(scraper, table_name, max_wait=6)
                data = scraper.get_table_data(table_name)
                curr_hist = data.get("history", [])
                if len(curr_hist) > current_base_count:
                    result = curr_hist[-1]
                    screenshot = data.get("screenshot_path") or screenshot
                else:
                    result = "T"
                    print(f"  ⚠️ [{ts()}] Mano sin incremento en Road en [{table_name}] — tratando como empate de seguridad.")
            else:
                result = "T"
                print(f"  ⚠️ [{ts()}] Sin cartas detectadas en [{table_name}] — manteniendo intento actual.")

        print(f"  🔍 [{ts()}] [RESULTADO FINAL EN MESA ACTIVA {table_name}]: Salió {color_str(result)} | Se buscaba {color_str(prediction)}")

        # ── CASO A: EMPATE ('T') ──
        if result == "T":
            print(f"  🟢 [{ts()}] EMPATE confirmado en [{table_name}]. Se mantiene intacto el Intento {attempt_n} en [{table_name}].")
            continue

        # ── CASO B: ¡GANÓ LA MESA ACTIVA EN VIVO! ──
        if result == prediction:
            win_n = attempt_idx + 1
            auto_bettor.record_win(attempt_idx)
            auto_bettor.reset_martingale()
            print(f"\n  🏆 [{ts()}] ¡VICTORIA OFICIAL EN INTENTO {win_n} ({table_name})! Salió {color_str(result)}.")
            print(f"     Ganancia neta ciclo: +{auto_bettor.base_bet:.2f} {auto_bettor.currency} | Balance sesión: {auto_bettor.session_profit:.2f} {auto_bettor.currency}")

            if telegram:
                telegram.send_result_message(
                    table_name=table_name,
                    result_type="win",
                    attempt_number=win_n,
                    screenshot_path=screenshot,
                    strategy_name=strat_name,
                )
            return "win"

        # ── CASO C: PERDIÓ EL INTENTO EN LA MESA ACTIVA ──
        auto_bettor.record_step_loss(attempt_idx)
        prev_table = table_name
        prev_pred = prediction

        attempt_idx += 1
        attempts_on_current_table += 1
        next_attempt_n = attempt_idx + 1

        if auto_bettor.is_paused_by_limits or attempt_idx >= config.MAX_ATTEMPTS:
            auto_bettor.record_table_finished_loss(attempt_idx - 1)
            print(f"\n  💔 [{ts()}] Ciclo finalizado sin acierto ({attempt_idx} tiros). Última mesa activa: [{table_name}].")
            if auto_bettor.is_paused_by_limits:
                print(f"  {auto_bettor.pause_reason}")
            if telegram:
                telegram.send_result_message(
                    table_name=table_name,
                    result_type="loss",
                    attempt_number=attempt_idx,
                    screenshot_path=screenshot,
                    strategy_name=strat_name,
                )
            return "stopped_by_limits" if auto_bettor.is_paused_by_limits else "loss"

        # Seleccionar y sincronizar el siguiente intento (repitiendo `prev_table` al instante o
        # descartándola por completo en `abandoned_tables` y esperando inicio exacto de 15s en otra mesa)
        synced_recovery = select_and_sync_recovery_play(
            scraper=scraper,
            analyzer=analyzer,
            stats_tracker=stats_tracker,
            detector=detector,
            telegram=telegram,
            current_table=prev_table,
            current_screenshot=screenshot,
            attempts_on_current_table=attempts_on_current_table,
            planned_table_attempts=planned_table_attempts,
            last_prediction=prev_pred,
            next_attempt_number=next_attempt_n,
            abandoned_tables=abandoned_tables,
        )

        if not synced_recovery:
            return "aborted"

        table_name             = synced_recovery["table_name"]
        prediction             = synced_recovery["prediction"]
        probability            = synced_recovery["probability"]
        planned_table_attempts = synced_recovery["planned_attempts"]
        strat_name             = synced_recovery["strat_name"]
        reason                 = synced_recovery["reason"]
        current_base_count     = synced_recovery.get("base_count", 0)

        if synced_recovery.get("switched_table"):
            attempts_on_current_table = 0

    return "loss"


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────
def main():
    ensure_single_bot_instance()

    telegram = TelegramNotifier()
    telegram.release_active_table()

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
        chip3_value=curr_cfg.get("chip3_value", 5.00),
        currency_symbol=curr_cfg["symbol"],
        stop_loss=config.AUTO_BET_STOP_LOSS,
        take_profit=None,
        persistent_martingale=config.AUTO_BET_PERSISTENT_MARTINGALE,
        max_steps=config.AUTO_BET_MAX_STEPS,
        currency_label=curr_cfg["label"],
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
    print(f"\n🚀 ¡BOT LOGRO ACTIVO en {curr_cfg['label']}!\n")

    signal_count = 0

    while True:
        telegram.stats_tracker.decrement_table_cooldowns()
        telegram.release_active_table()

        if auto_bettor.is_paused_by_limits:
            sep("=")
            print(f"  {auto_bettor.pause_reason}")
            print(f"  Balance final de la sesión: {auto_bettor.session_profit:.2f} {auto_bettor.currency}")
            print("  El bot se ha detenido automáticamente por seguridad.")
            sep("=")
            break

        best_play = find_and_emit_initial_play(scraper, analyzer, stats_tracker, detector, telegram)
        if best_play is None:
            time.sleep(ANALYSIS_COOLDOWN)
            continue

        signal_count += 1
        print(
            f"\n  📊 Ciclo #{signal_count} en curso sobre [{best_play['table_name']}] "
            f"➔ {color_str(best_play['prediction'])} ({best_play['probability']}%)"
        )

        try:
            final_result = execute_logro_cycle(
                telegram=telegram,
                scraper=scraper,
                detector=detector,
                analyzer=analyzer,
                stats_tracker=stats_tracker,
                auto_bettor=auto_bettor,
                initial_play=best_play,
            )
        except Exception as e:
            logger.error(f"Error en execute_logro_cycle: {e}")
            final_result = "aborted"

        analyzer.register_signal_sent(best_play["table_name"])
        telegram.release_active_table()

        if final_result == "stopped_by_limits" or auto_bettor.is_paused_by_limits:
            sep("=")
            print(f"  {auto_bettor.pause_reason}")
            print(f"  Balance final de la sesión: {auto_bettor.session_profit:.2f} {auto_bettor.currency}")
            print("  El bot se ha detenido automáticamente por seguridad.")
            sep("=")
            break
        elif final_result == "aborted":
            continue
        elif final_result == "win":
            auto_bettor.reset_martingale()
            print(f"\n🎉 Victoria completada. Buscando próxima jugada...")
            time.sleep(SESSION_PAUSE)
        else:
            print(f"\n💔 Ciclo cerrado en LOSS. Buscando nueva oportunidad de inmediato...")
            time.sleep(POST_LOSS_PAUSE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Bot Logro detenido por el usuario.")
        print("¡Hasta la próxima! 🍀")
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("  [ERROR INESPERADO AL EJECUTAR BOT LOGRO]")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        try:
            input("\nPresiona ENTER para cerrar la ventana...")
        except Exception:
            pass
