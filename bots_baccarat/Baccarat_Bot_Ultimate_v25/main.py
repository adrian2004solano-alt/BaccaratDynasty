"""
main.py  —  Baccarat Ultimate Bot v25 (Modo Dual: $0.40 / $0.20 + Martingala x12)
==================================================================================
DOS MODOS DE JUEGO AL INICIO:
  [1] MODO $0.40 — Tiro 1 = 2 clics ($0.40) | Dobla 12 veces hasta $1,638.40
  [2] MODO $0.20 — Tiro 1 = 1 clic  ($0.20) | Dobla 12 veces hasta $819.20

5 Mesas Monitoreadas:
  Baccarat 1, Baccarat 2, Baccarat 3, Baccarat 5.

1. GRUPO DE TELEGRAM (Señales Limpias y Profesionales):
   - Envía la señal con foto y los intentos de la estrategia.
   - Canal de Resultados: Únicamente texto limpio (✅ WIN / ❌ LOSS).

2. AUTO-BETTOR EN LA LAPTOP (Stake / Evolution Baccarat Multiplay):
   - Selecciona automáticamente la ficha de $0.20 USD en la barra inferior.
   - Ejecuta los clics humanizados en la mesa seleccionada.
   - Martingala Persistente de 12 niveles con carry cross-table.
   - Control de Stop-Loss y Take-Profit configurables.
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

# Reconfigurar salida de consola a UTF-8 seguro para Windows
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
from core.telegram_bot    import TelegramNotifier
from core.analyzer        import BaccaratAnalyzer
from core.scraper         import StakeBaccaratScraper
from core.session_manager import BaccaratSession
from core.result_detector import ResultDetector
from core.auto_bettor     import AutoBettor

# ──────────────────────────────────────────────
# Control de Instancia Única (Anti-Duplicidad de Mesas)
# ──────────────────────────────────────────────
class SingleInstanceGuard:
    PORT = 48888
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
            # Puerto ocupado: hay otra instancia activa o colgada
            print(f"\n⚠️  [SingleInstanceGuard] Puerto {self.PORT} ocupado. Cerrando instancia previa...")
            self._kill_previous_instances()
            time.sleep(1)
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.bind((self.HOST, self.PORT))
                self._socket.listen(1)
                return True
            except OSError:
                print(f"❌ [ERROR CRÍTICO] Ya existe una instancia de Baccarat Bot en ejecución.")
                print("   Cierra la ventana anterior antes de abrir una nueva.")
                time.sleep(4)
                sys.exit(1)

    def _kill_previous_instances(self):
        current_pid = os.getpid()
        try:
            cmd = f"""
            $procs = Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" | Where-Object {{ $_.ProcessId -ne {current_pid} -and ($_.CommandLine -match 'main.py' -or $_.CommandLine -match 'baccarat-stake-bot') }}
            foreach ($p in $procs) {{
                Stop-Process -Id $p.ProcessId -Force
            }}
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
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

logger = logging.getLogger("BaccaratBot")

STARTUP_DELAY         = getattr(config, "STARTUP_DELAY", 5)
ANALYSIS_COOLDOWN     = 1      # pausa ágil entre escaneos para no perder aperturas de mesas
SESSION_PAUSE         = 2      # pausa ágil tras ganar para continuar fluido a la siguiente mesa
POST_LOSS_PAUSE       = 2      # pausa ágil tras perder para continuar de inmediato
POLL_FAST_INTERVAL    = 0.35   # escaneo rápido de pantalla a 0.35s para atrapar listones al instante
MAX_WAIT_FINISH       = 35     # espera máxima para sincronizar fin de jugada (máx ~40s para nueva mesa)
BANNER_CLEAR_DELAY    = 2      # espera para limpiar el listón


def ts():
    return datetime.now().strftime("%H:%M:%S")


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


def sep(char="=", n=68):
    print(char * n)


def print_banner(auto_bettor, pid=None, modo_label=""):
    mode_tag = "🟢 REAL (Clics Activos en Laptop)" if auto_bettor.enabled else "🟡 SIMULACIÓN (Seguro sin clics)"
    pid_tag = f"PID {pid} (Puerto 48888 Exclusivo)" if pid else "Activo"
    strat_mart = "PERSISTENTE (Continúa entre mesas hasta ganar)" if auto_bettor.persistent_martingale else "LOCAL (Reinicia tras intentos)"
    mode_icon = "💰" if auto_bettor.initial_clicks == 2 else "💵"
    sep("=")
    print("   🎯  BACCARAT ULTIMATE v25 — MODO DUAL + MARTINGALA x12 + AUTO-BETTOR  🎯")
    print("      Lobby Multiplay · Martingala Persistente 12 Niveles · Telegram Señales")
    sep("=")
    print(f"  Instancia Segura     : {pid_tag} — Anti-Duplicados ACTIVO")
    print(f"  Mesas Monitoreadas   : {', '.join(config.TARGET_TABLES)}")
    print(f"  Filtro de Zapato     : Permitido ÚNICAMENTE de 12 a 64 jugadas (65+ Omitida)")
    print(f"  Estrategias Activas  : 1. Disruptiva 1-4-1 | 2. Tendencia 3-1-2 | 3. Pura 6X | 4. Disruptiva 1+5")
    print(f"  Modo de Análisis     : Profundo / Paciente (Filtro Anti-Precipitación)")
    print(f"  Grupo de Señales     : {config.TELEGRAM_CHAT_ID} (Formato Normal Estándar)")
    print(f"  Canal Resultados     : {config.TELEGRAM_RESULTS_CHAT_ID} (Solo ✅ WIN / ❌ LOSS)")
    print(f"  Auto-Bettor Laptop   : {mode_tag}")
    print(f"  {mode_icon} MODO DE JUEGO       : {modo_label or 'Configurado'}")
    print(f"  Tiro 1 (clics)       : {auto_bettor.initial_clicks} clic(s) → ${auto_bettor.base_chip * auto_bettor.initial_clicks:.2f} USD")
    print(f"  Gestión Martingala   : {strat_mart}")
    sl_str = f"${auto_bettor.stop_loss:.2f}" if auto_bettor.stop_loss is not None else "ILIMITADO (Sin Stop-Loss)"
    tp_str = f"+${auto_bettor.take_profit:.2f}" if auto_bettor.take_profit is not None else "LIBRE (Sin Take-Profit)"
    print(f"  Límites Financieros  : Stop-Loss: {sl_str} | Take-Profit: {tp_str}")
    print(f"  ⚠️  IMPORTANTE         : Mantén Baccarat Multiplay visible en pantalla.")
    sep("=")
    print()


# ──────────────────────────────────────────────
# FASE 1 — ANÁLISIS DE MESAS
# ──────────────────────────────────────────────
def phase_analysis(scraper, analyzer, stats_tracker, auto_bettor=None, detector=None):
    last_strat = stats_tracker.get_last_strategy()
    early_scores = stats_tracker.get_strategy_early_win_scores()
    strategy_usage = stats_tracker.get_recent_strategy_usage()

    print(f"\n🔍 [{ts()}] Analizando mesas (Cadencia Ágil y Rotación de 4 Estrategias)...")
    # Sincronización visual inteligente de la pantalla: detecta qué mesa está en cada slot
    scraper.sync_slots_with_screen()
    # Coordenadas de apuestas provienen estrictamente de bet_coordinates.json
    # (No sobreescribir con slots dinámicos para garantizar máxima precisión)
    candidates = []
    cooling_candidates = []

    # Mesas detectadas visualmente en pantalla
    detected_tables = [t for t in scraper.regions.keys() if t != "UNKNOWN" and t in config.TARGET_TABLES]
    tables_to_scan = detected_tables if detected_tables else config.TARGET_TABLES
    seen_tables = set()

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

        # Filtro de Zapato: 8 a 67 jugadas (68+ Omitida)
        if not is_qualified or total_hands < 8 or total_hands >= 68:
            reason = "Menos de 8 jugadas" if total_hands < 8 else "68+ jugadas (Fin de zapato)"
            print(f"  🚫 {table_name:<18} | Jugadas: {total_hands:<2} -> OMITIDA ({reason})")
            continue

        # Pausa prudencial entre señales de la misma mesa
        can_sig, wait_sec = analyzer.can_send_signal(table_name)
        if not can_sig:
            print(f"  ⏳ {table_name:<18} | Pausa de mesa: esperando {wait_sec}s antes de reingresar...")
            continue

        # Salud y Enfriamiento de la Mesa
        is_cooling = stats_tracker.is_table_cooling_down(table_name)
        health_label = stats_tracker.get_table_health_label(table_name)
        table_momentum = stats_tracker.get_table_momentum_score(table_name)

        should, sequence, confidence, probability, _, strat_name, reason = analyzer.analyze_history(
            table_name, history, total_hands=total_hands, last_strategy=last_strat, early_scores=early_scores, strategy_usage=strategy_usage
        )

        golden_tag = " ⭐" if (18 <= total_hands <= 48) else ""

        # Detección de fin de mano en vivo (Prioridad máxima para mesas que acaban de terminar ahora)
        is_ending_now = False
        if detector and screenshot:
            c_img = load_pil_image(screenshot)
            if c_img:
                is_ending_now, _ = detector.is_round_concluded(c_img)

        if should:
            seq_preview = ' '.join(sequence[:4])
            timing_bonus = 8.0 if is_ending_now else 0.0
            selection_score = confidence + table_momentum + timing_bonus + random.uniform(0.1, 1.0)
            tag_extra = " 🔥[TERMINÓ AHORA]" if is_ending_now else golden_tag

            if is_cooling:
                rem = stats_tracker.get_table_cooldown(table_name)
                print(f"  ❄️ {table_name:<18} | {total_hands:<2} jug{tag_extra} | [{strat_name:<16}] -> {seq_preview} ({probability}%) | {health_label} (Saltada por tiro alto)")
                cooling_candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
            else:
                print(f"  🎯 {table_name:<18} | {total_hands:<2} jug{tag_extra} | [{strat_name:<16}] -> {seq_preview} ({probability}%) | Salud: {health_label} (Score: {selection_score:.1f})")
                candidates.append((selection_score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label))
        else:
            print(f"  ⏳ {table_name:<18} | {total_hands:<2} jug{golden_tag} -> Sin ventaja ({reason}) | {health_label}")

    sep()

    target_pool = candidates if candidates else []

    if not target_pool:
        if cooling_candidates:
            print(f"  → ⏳ Mesas en reposo por tiros altos recientes. Esperando rotación limpia en {ANALYSIS_COOLDOWN}s...")
        else:
            print(f"  → ⏳ Sin mesa óptima en este ciclo. Reintentando en {ANALYSIS_COOLDOWN}s...")
        return None

    target_pool.sort(key=lambda c: c[0], reverse=True)
    best = target_pool[0]
    score, table_name, screenshot, sequence, probability, total_hands, strat_name, reason, health_label = best

    seq_preview = " ".join(sequence[:6])
    print(f"  → 🚀 [MESA SELECCIONADA]: [{table_name}] ({total_hands} jugadas) | Salud: {health_label}")
    print(f"     Estrategia: [{strat_name}] | Secuencia: [{seq_preview}] | Prob: {probability}% | Score: {score:.1f}")
    return table_name, screenshot, sequence, probability, total_hands, strat_name, reason


# ──────────────────────────────────────────────
# FASE 2 — ESPERAR QUE FINALICE LA JUGADA PREVIA Y ABRIR VENTANA DE 15S
# ──────────────────────────────────────────────
def phase_wait_round_end(scraper, detector, table_name, initial_hands=None):
    """
    Sincroniza con el inicio limpio de la ventana de apuestas en [table_name].
    1. Si el listón de victoria está visible -> Disparo inmediato al segundo 0.
    2. Si el zapato incrementó (+1 jugada) -> Mano previa terminó, disparo inmediato.
    3. Si la mesa está en ventana de apuestas (sin cartas repartidas) -> Disparo inmediato.
    4. Si hay cartas repartiéndose actualmente -> Espera a que termine la mano y dispara.
    """
    print(f"\n  🕐 [{ts()}] Sincronizando mesa [{table_name}] para entrada limpia...")
    start_wait = time.time()
    init_h = initial_hands or 0

    while time.time() - start_wait < MAX_WAIT_FINISH:
        data = scraper.get_table_data(table_name)
        screenshot = data.get("screenshot_path")
        img = load_pil_image(screenshot)
        curr_hands = data.get("total_hands", len(data.get("history", [])))

        # Condición 1: Listón de victoria visible (la mano acaba de terminar)
        concluded, winner_code = detector.is_round_concluded(img)
        if concluded:
            w_lbl = "JUGADOR 🔵" if winner_code == "P" else ("BANCA 🔴" if winner_code == "B" else "EMPATE 🟢")
            print(f"  🎯 [{ts()}] ¡Mano previa concluida en [{table_name}] ({w_lbl})! Disparando al segundo 0.")
            return screenshot, data.get("history", []), curr_hands

        # Condición 2: Nueva bola asentada en el Road
        if init_h > 0 and curr_hands > init_h and not detector.are_cards_present(img):
            print(f"  🎯 [{ts()}] ¡Nueva jugada asentada en [{table_name}] ({curr_hands} manos)! Disparando entrada limpia.")
            return screenshot, data.get("history", []), curr_hands

        # Condición 3: Mesa limpia en ventana de apuestas (sin cartas repartiéndose)
        cards_active = detector.are_cards_present(img)
        if not cards_active:
            print(f"  ⚡ [{ts()}] Mesa [{table_name}] en ventana de apuestas activa (sin cartas). Disparando señal.")
            return screenshot, data.get("history", []), curr_hands

        # Si hay cartas repartiéndose: esperar a que termine el reparto
        time.sleep(0.35)

    # Fallback seguro: si transcurrió el tiempo máximo, proceder con la señal para no congelar el bot
    data = scraper.get_table_data(table_name)
    print(f"  🚀 [{ts()}] Ventana lista en [{table_name}]. Procediendo con señal.")
    return data.get("screenshot_path"), data.get("history", []), data.get("total_hands", 0)


# ──────────────────────────────────────────────
# FASE 3 — ENVIAR SEÑAL NORMAL A TELEGRAM
# ──────────────────────────────────────────────
def phase_signal(telegram, table_name, screenshot, sequence, probability, strat_name, reason):
    print(f"\n  📲 [{ts()}] Enviando señal de [{table_name}] con plan de 6 tiros a Telegram...")

    ok, msg = telegram.send_baccarat_signal(
        table_name=table_name,
        sequence=sequence,
        probability=probability,
        screenshot_path=screenshot,
    )

    if ok:
        print(f"  ✅ Señal estándar enviada con éxito al grupo de Telegram.")
        return BaccaratSession(table_name, sequence, strat_name, probability, reason)
    else:
        print(f"  ❌ Error enviando señal: {msg}")
        return None


# ──────────────────────────────────────────────
# FASE 4 — TRACKING EN TIEMPO REAL Y APUESTAS EN LAPTOP
# ──────────────────────────────────────────────
def phase_tracking(telegram, scraper, detector, session, auto_bettor, first_bet_placed=False):
    table_name = session.table_name
    strat_name = session.strategy
    amounts = [0.20, 0.40, 0.80, 1.60, 3.20, 6.40]

    sep()
    print(f"  🔒 [{ts()}] SESIÓN ACTIVA — [{table_name}] | Estrategia: [{strat_name}]")
    print(f"     Telegram: Señal normal activa | Laptop: Auto-Bettor gestionando apuestas")
    sep()

    first_round_done = False

    while not session.is_finished():
        attempt_n  = session.attempt_number
        attempt_idx = session.current_attempt
        prediction = session.current_prediction
        pred_label = "JUGADOR 🔵" if prediction == "P" else "BANCA 🔴"
        bet_amount, current_step = auto_bettor.get_bet_amount(attempt_idx)

        focus_tag = f"🎯 [PASO MARTINGALA #{current_step+1}]" if auto_bettor.persistent_martingale else (
            "🎯 [TIRO BAJO]" if attempt_n <= 3 else "⚡ [PROGRESIÓN MARTINGALA]"
        )
        print(f"\n  ⏱  [{ts()}] INTENTO {attempt_n}/6 {focus_tag} — ${bet_amount:.2f} a {pred_label}")

        # Capturar el historial del zapato al inicio de este intento
        data_start = scraper.get_table_data(table_name)
        base_history = data_start.get("history", [])
        base_count = len(base_history)

        # 1. EJECUTAR APUESTA FÍSICA EN LA LAPTOP (O SIMULACIÓN)
        # Si ya se colocó al segundo 0 de la señal inicial, no duplicar
        if first_bet_placed and attempt_idx == 0 and not first_round_done:
            print(f"     → [AutoBettor] ✅ Apuesta Inicial de Tiro 1 ya ejecutada con éxito al segundo 0.")
            first_round_done = True
        else:
            # IMPORTANTE: NO pasar dynamic_coords del scraper (puede tener player/banker invertidos).
            # Siempre usar las coordenadas estáticas calibradas de bet_coordinates.json.
            ok_bet, bet_msg = auto_bettor.execute_bet(
                prediction=prediction,
                attempt_index=attempt_idx,
                table_name=table_name,
                dynamic_coords=None   # forzar uso de coordenadas calibradas estáticas
            )
            print(f"     → [AutoBettor] {bet_msg}")
            first_round_done = True

        # 2. ESPERAR RESULTADO VISUAL REAL EN PANTALLA
        # PASO 2.0 — ESPERAR QUE EL LISTÓN DE LA MANO ANTERIOR DESAPAREZCA
        # El listón visible al enviar la señal es de la mano PREVIA.
        # No se puede aceptar ningún resultado hasta que la mesa esté limpia.
        ribbon_clear_start = time.time()
        ribbon_cleared = False
        while time.time() - ribbon_clear_start < 8:
            time.sleep(0.20)
            _d = scraper.get_table_data(table_name)
            _img = load_pil_image(_d.get("screenshot_path"))
            if _img and not detector.is_ribbon_present(_img):
                ribbon_cleared = True
                break

        # PASO 2.1 — ESPERAR QUE SE REPARTAN LAS CARTAS (nueva mano comenzó)
        cards_seen = False
        cards_wait_start = time.time()
        while time.time() - cards_wait_start < 20:
            time.sleep(0.25)
            _d2 = scraper.get_table_data(table_name)
            _img2 = load_pil_image(_d2.get("screenshot_path"))
            if _img2 and detector.are_cards_present(_img2):
                cards_seen = True
                print(f"  🃏 [{ts()}] Cartas detectadas en [{table_name}] — nueva mano en curso.")
                break

        # PASO 2.2 — DETECTAR EL RESULTADO DE LA NUEVA MANO
        result = None
        screenshot = None
        round_start_time = time.time()
        MAX_ROUND_WAIT = 35  # Tiempo máximo ágil de espera por ronda de juego

        while not session.is_finished() and (time.time() - round_start_time < MAX_ROUND_WAIT):
            time.sleep(POLL_FAST_INTERVAL)
            data        = scraper.get_table_data(table_name)
            screenshot  = data.get("screenshot_path")
            current_img = load_pil_image(screenshot)

            # A. Detección por Listón Oficial de Victoria en pantalla
            # Solo se acepta si ya se vieron las cartas de esta nueva mano
            if cards_seen:
                ribbon_res = detector.read_result(current_img, table_name)
                if ribbon_res is not None:
                    result = ribbon_res
                    break
            else:
                # Aún no vimos cartas: verificar si ya aparecieron
                if detector.are_cards_present(current_img):
                    cards_seen = True
                    print(f"  🃏 [{ts()}] Cartas detectadas en [{table_name}] durante espera de resultado.")

            # B. Detección por incremento en el Road (nueva bola asentada al retirar cartas)
            curr_hist = data.get("history", [])
            curr_count = len(curr_hist)
            if cards_seen and curr_count > base_count and not detector.are_cards_present(current_img):
                result = curr_hist[-1]
                logger.info(f"[{table_name}] Nueva jugada asentada en Road: {result} (#{curr_count})")
                break

        if result is None:
            if cards_seen:
                # Fallback seguro: sí vimos cartas, leer último resultado del road
                data = scraper.get_table_data(table_name)
                curr_hist = data.get("history", [])
                if len(curr_hist) > base_count:
                    result = curr_hist[-1]
                    print(f"  ⚠️ [{ts()}] Timeout con cartas vistas — usando road: {result}")
                else:
                    result = "T"  # No hubo cambio detectado, tratar como empate para no penalizar
                    print(f"  ⚠️ [{ts()}] Timeout sin nuevo resultado en road — manteniendo intento.")
            else:
                # NO vimos cartas: la nueva mano aún no comenzó (o no detectamos nada)
                # NO declarar resultado — continuar esperando
                result = "T"
                print(f"  ⚠️ [{ts()}] Timeout sin ver cartas en [{table_name}] — reiniciando intento para no penalizar.")

        # ── CASO A: EMPATE ─────────────────────────────────────────
        if result == "T":
            print(f"  🟢 [{ts()}] EMPATE detectado. Apuesta devuelta — Intento {attempt_n} se mantiene intacto.")
            # Esperar inicio de la PRÓXIMA ventana de apuestas (ribbon desaparece, mesa limpia)
            # Luego el loop re-apostará el MISMO monto (attempt_idx no avanza)
            t_start = time.time()
            while time.time() - t_start < 20:
                time.sleep(0.35)
                d = scraper.get_table_data(table_name)
                img_t = load_pil_image(d.get("screenshot_path"))
                if detector.is_table_in_betting_window(img_t):
                    break
            continue

        # ── CASO B: RESULTADO 'P' O 'B' ─────────────────────────────
        res_label = "JUGADOR 🔵" if result == "P" else "BANCA 🔴"
        outcome = session.register_result(result)

        if outcome.startswith("win_"):
            win_n = int(outcome.split("_")[1])
            auto_bettor.record_win(attempt_idx)
            print(f"\n  🏆 [{ts()}] ¡ACIERTO EN INTENTO {win_n}! Ganó {res_label} (coincide con {pred_label}).")
            print(f"     Ganancia neta ciclo: +${auto_bettor.base_bet:.2f} USD | Balance laptop: ${auto_bettor.session_profit:.2f} USD")

            # Reportar al grupo de Telegram con foto y formato normal
            telegram.send_result_message(
                table_name=table_name,
                result_type="win",
                attempt_number=win_n,
                screenshot_path=screenshot,
                strategy_name=strat_name,
            )
            # Esperar que el listón de victoria desaparezca antes de salir
            detector.wait_until_clean(scraper, table_name, max_wait=8)
            return "win"

        elif outcome == "continue":
            auto_bettor.record_step_loss(attempt_idx)
            next_n = session.attempt_number
            next_pred = session.current_prediction
            n_label = "JUGADOR 🔵" if next_pred == "P" else "BANCA 🔴"
            print(f"     ✗ Intento {attempt_n} falló. Salió [{res_label}], se apostó a [{pred_label}].")
            print(f"       -> Duplicando Martingala a Intento {next_n} ({n_label}).")
            detector.wait_until_clean(scraper, table_name, max_wait=8)

        elif outcome == "loss":
            auto_bettor.record_step_loss(attempt_idx)
            auto_bettor.record_table_finished_loss(attempt_idx)
            print(f"\n  💔 [{ts()}] LOSS ALCANZADO (6 intentos) — Mesa [{table_name}].")
            print(f"     Balance sesión acumulado: ${auto_bettor.session_profit:.2f} USD")

            # Reportar al grupo de Telegram con foto y formato normal
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
    guard = SingleInstanceGuard()
    guard.acquire()

    telegram = TelegramNotifier()
    # Limpieza preventiva de cualquier candado residual de sesiones previas
    telegram.release_active_table()

    try:
        # Prioridad absoluta a los argumentos de línea de comandos
        auto_bet_active = config.AUTO_BET_ENABLED
        if any(arg in sys.argv for arg in ("--no-bet", "--solo-senales", "--solo-telegram", "--simulacion")):
            auto_bet_active = False
        elif any(arg in sys.argv for arg in ("--con-apuestas", "--auto-bet", "--real")):
            auto_bet_active = True

        # ══════════════════════════════════════════════════════
        # DETECCIÓN AUTOMÁTICA DE MODO DESDE EL .BAT
        # ══════════════════════════════════════════════════════
        # START_BOT_40_CENTAVOS.bat  →  pasa --modo-40
        # START_BOT_20_CENTAVOS.bat  →  pasa --modo-20
        # Si no se pasa argumento: menú interactivo.
        # ══════════════════════════════════════════════════════
        if "--modo-40" in sys.argv:
            modo_elegido = config.MODO_40
            sep("═")
            print("   💰  BACCARAT ULTIMATE v25 — MODO $0.40 ACTIVADO")
            print("       Tiro 1: 2 clics ($0.40) | Martingala x12")
            sep("═")
            print()
        elif "--modo-20" in sys.argv:
            modo_elegido = config.MODO_20
            sep("═")
            print("   💵  BACCARAT ULTIMATE v25 — MODO $0.20 ACTIVADO")
            print("       Tiro 1: 1 clic ($0.20) | Martingala x12")
            sep("═")
            print()
        else:
            # Menú interactivo si se abre main.py directo sin argumento
            sep("═")
            print("   🎯  BACCARAT ULTIMATE v25 — SELECCIÓN DE MODO DE JUEGO")
            sep("═")
            print()
            print("   ┌─────────────────────────────────────────────────────────┐")
            print("   │  [1]  MODO $0.40  →  2 clics por tiro                  │")
            print("   │       Progresión: $0.40 → $0.80 → $1.60 → $3.20 ...   │")
            print("   │       Hasta 12 niveles de Martingala                   │")
            print("   │                                                         │")
            print("   │  [2]  MODO $0.20  →  1 clic por tiro                   │")
            print("   │       Progresión: $0.20 → $0.40 → $0.80 → $1.60 ...   │")
            print("   │       Hasta 12 niveles de Martingala                   │")
            print("   └─────────────────────────────────────────────────────────┘")
            print()
            modo_elegido = None
            while modo_elegido is None:
                try:
                    opcion = input("   👉 Elige tu modo [1] o [2]: ").strip()
                    if opcion == "1":
                        modo_elegido = config.MODO_40
                        print(f"\n   ✅ Modo seleccionado: {config.MODO_40['label']}\n")
                    elif opcion == "2":
                        modo_elegido = config.MODO_20
                        print(f"\n   ✅ Modo seleccionado: {config.MODO_20['label']}\n")
                    else:
                        print("   ⚠️  Opción inválida. Escribe 1 o 2.")
                except (KeyboardInterrupt, EOFError):
                    print("\n\n[!] Cancelado por el usuario.")
                    guard.release()
                    sys.exit(0)

        # ══════════════════════════════════════════════════════
        # INSTANCIAR AUTO-BETTOR CON EL MODO ELEGIDO
        # ══════════════════════════════════════════════════════
        auto_bettor = AutoBettor(
            enabled=auto_bet_active,
            stop_loss=config.AUTO_BET_STOP_LOSS,
            take_profit=config.AUTO_BET_TAKE_PROFIT,
            base_bet=modo_elegido["base_bet"],
            base_chip=config.AUTO_BET_BASE_CHIP,           # Siempre $0.20 (ficha física)
            persistent_martingale=getattr(config, "AUTO_BET_PERSISTENT_MARTINGALE", True),
            max_steps=getattr(config, "AUTO_BET_MAX_STEPS", 12),
            initial_clicks=modo_elegido["initial_clicks"]  # MODO_40=2 | MODO_20=1
        )
        print_banner(auto_bettor, pid=os.getpid(), modo_label=modo_elegido["label"])


        analyzer = BaccaratAnalyzer(
            min_delay=config.MIN_SIGNAL_DELAY,
            max_delay=config.MAX_SIGNAL_DELAY,
            min_confidence=getattr(config, "MIN_CONFIDENCE_THRESHOLD", 75),
        )
        scraper  = StakeBaccaratScraper(target_tables=config.TARGET_TABLES)
        detector = ResultDetector()

        print(f"[+] Mesas Monitoreadas ({len(scraper.regions)}): {list(scraper.regions.keys())}")
        print(f"[+] Filtro de Zapato: 12 a 64 jugadas permitidas (65+ Omitida)")
        print(f"[+] Estrategias Activas: 4 Exclusivas (Disruptiva 1-4-1, Tendencia 3-1-2, Pura 6X, Disruptiva 1+5)")
        print(f"[+] Análisis Ágil y Preciso: Sincronización Estricta con Fin de Jugada (Cero disparos a mitad de mano)")
        print(f"[+] Grupo Telegram: Señales estándar con foto y 6 intentos normales")
        print(f"[+] Laptop Auto-Bettor: Ficha ${auto_bettor.base_bet:.2f} con Martingala Persistente")
        print(f"[+] Candado Anti-Duplicados Telegram: ACTIVO (1 mesa simultánea garantizada)")

        print(f"\n⏳ Tienes {STARTUP_DELAY}s para abrir Stake y dejar Baccarat Multiplay visible.\n")
        countdown(STARTUP_DELAY, "Análisis inicia en")
        print("\n🚀 ¡Bot Baccarat Ultimate v24 Activo!\n")

        signal_count = 0

        while True:
            # 0. GESTIÓN DE ENFRIAMIENTO Y ROTACIÓN (Anti-Fijación de Mesas)
            telegram.stats_tracker.decrement_table_cooldowns()

            # 1. ANÁLISIS DE MESAS (Cadencia Rápida y Prioridad a Mesas Terminando)
            cand = phase_analysis(scraper, analyzer, telegram.stats_tracker, auto_bettor=auto_bettor, detector=detector)
            if cand is None:
                countdown(ANALYSIS_COOLDOWN, "Próximo análisis en")
                continue

            table_name, screenshot, sequence, probability, total_hands, strat_name, reason = cand

            # 2. ESPERAR FIN DE RONDA PREVIA (En cuanto termine la mano previa ej: 9 a 7, dispara en ese mismo instante)
            sync_screenshot, sync_hist, sync_hands = phase_wait_round_end(scraper, detector, table_name, total_hands)

            if sync_screenshot is None:
                # Cancelado por seguridad para jamás disparar a mitad de jugada
                print("  🔄 Re-escaneando mesas de inmediato para capturar apertura limpia...")
                time.sleep(1)
                continue

            # Si la mano que acaba de terminar incrementó el zapato, recalcular estrategia con zapato fresco
            if sync_hands > total_hands and sync_hist:
                should_sync, seq_sync, conf_sync, prob_sync, _, strat_sync, reason_sync = analyzer.analyze_history(
                    table_name, sync_hist, total_hands=sync_hands,
                    last_strategy=telegram.stats_tracker.get_last_strategy(),
                    early_scores=telegram.stats_tracker.get_strategy_early_win_scores(),
                    strategy_usage=telegram.stats_tracker.get_recent_strategy_usage()
                )
                if should_sync:
                    sequence, probability, strat_name, reason = seq_sync, prob_sync, strat_sync, reason_sync

            # 3. COLOCACIÓN INMEDIATA DE LA APUESTA FÍSICA EN LAPTOP (Toma solo 0.15s)
            # Se ejecuta al segundo 0 exacto de apertura, antes de la carga por internet a Telegram
            first_bet_ok = False
            if auto_bettor.enabled:
                pred_first = sequence[0]
                ok_bet, bet_msg = auto_bettor.execute_bet(
                    prediction=pred_first,
                    attempt_index=0,
                    table_name=table_name,
                    dynamic_coords=None   # Forzar uso estricto de coordenadas calibradas oficiales
                )
                print(f"  ⚡ [{ts()}] [AutoBettor Tiro 1 Inmediato] {bet_msg}")
                first_bet_ok = ok_bet

            # 4. ENVIAR SEÑAL CON FOTO A TELEGRAM (Muestra el resultado de la mano previa)
            session = phase_signal(
                telegram, table_name, sync_screenshot,
                sequence, probability, strat_name, reason
            )

            if session is None:
                print("  ⚠ Falló envío a Telegram o mesa bloqueada. Reintentando en 8s...")
                time.sleep(8)
                continue

            signal_count += 1
            print(f"\n  📊 Señal #{signal_count} activa en [{table_name}] — Estrategia: [{strat_name}] ({probability}%)")

            # 5. TRACKING VISUAL + PROGRESIÓN MARTINGALA
            final_result = phase_tracking(telegram, scraper, detector, session, auto_bettor, first_bet_placed=first_bet_ok)
            analyzer.register_signal_sent(table_name)

            # 5. CONTINUACIÓN FLUIDA
            if final_result == "win":
                auto_bettor.reset_martingale()   # Reset total: la siguiente mesa empieza limpia en 1 clic
                print(f"\n🎉 Victoria confirmada. Buscando siguiente mesa en {SESSION_PAUSE}s...")
                countdown(SESSION_PAUSE, "Buscando siguiente mesa en")
            else:
                print(f"\n💔 LOSS en [{table_name}]. Martingala persistente continuará en la siguiente mesa...")
                countdown(POST_LOSS_PAUSE, "Buscando nueva mesa en")

    except KeyboardInterrupt:
        print("\n\n[!] Bot detenido por el usuario.")
        print(f"📊 Resumen Auto-Bettor: Balance Neto: ${auto_bettor.session_profit:.2f} USD | Clics/Apuestas: {auto_bettor.bets_placed_count}")
        print("¡Hasta pronto! 🍀")

    finally:
        telegram.release_active_table()
        guard.release()


if __name__ == "__main__":
    main()
