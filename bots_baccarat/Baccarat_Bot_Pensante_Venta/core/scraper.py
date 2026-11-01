"""
core/scraper.py  — v14 (Lectura Real de Jugadas y Filtro Estricto 10 a 64 Manos)
================================================================================
1. Captura de Pantalla Real de cada mesa.
2. Extracción de Jugadas Reales del Road.
3. Evaluación Estricta del Zapato:
   - Si tiene menos de 10 jugadas -> Omitida.
   - Si tiene 65 o más jugadas (65+) -> Omitida.
   - Solo califica si: 10 <= jugadas <= 64.
"""

import os
import json
import logging
import cv2
import numpy as np
from core.shoe_detector import evaluate_table_hands_exact

logger = logging.getLogger("Scraper")
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS_FILE = os.path.join(_BASE_DIR, "table_regions.json")


def _capture_full_screen_mss():
    import mss
    from PIL import Image
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")


def _capture_full_screen_pil():
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def _capture_full_screen_pyautogui():
    import pyautogui
    return pyautogui.screenshot()


def capture_full_screen():
    methods = [
        ("mss",       _capture_full_screen_mss),
        ("PIL",       _capture_full_screen_pil),
        ("pyautogui", _capture_full_screen_pyautogui),
    ]
    last_error = None
    for name, fn in methods:
        try:
            return fn()
        except Exception as e:
            last_error = e
    raise RuntimeError(f"No se pudo capturar la pantalla: {last_error}")


TEMPLATES_DIR = os.path.join(_BASE_DIR, "core", "templates")
BACCARAT_WORD_TMPL = None
DIGIT_TEMPLATES = {}
AMAZING_TMPL = None
PRAGMATIC_TEMPLATES = {}


def _load_title_templates():
    global BACCARAT_WORD_TMPL, DIGIT_TEMPLATES, AMAZING_TMPL, PRAGMATIC_TEMPLATES
    # Cargar plantillas de títulos de Pragmatic Play
    prag_map = {
        "Baccarat 5": "tmpl_prag_baccarat_5.png",
        "Baccarat 6": "tmpl_prag_baccarat_6.png",
        "Baccarat 1": "tmpl_prag_baccarat_1.png",
        "Baccarat 2": "tmpl_prag_baccarat_2.png",
        "Speed Baccarat 8": "tmpl_prag_speed_8.png",
        "Speed Baccarat 9": "tmpl_prag_speed_9.png",
        "Baccarat 3": "tmpl_prag_baccarat_3.png",
    }
    for tname, fname in prag_map.items():
        if tname not in PRAGMATIC_TEMPLATES:
            fpath = os.path.join(TEMPLATES_DIR, fname)
            if os.path.exists(fpath):
                PRAGMATIC_TEMPLATES[tname] = cv2.imread(fpath, 0)

    if BACCARAT_WORD_TMPL is None:
        p_word = os.path.join(TEMPLATES_DIR, "tmpl_word_baccarat.png")
        if os.path.exists(p_word):
            BACCARAT_WORD_TMPL = cv2.imread(p_word, 0)

        p_amz = os.path.join(TEMPLATES_DIR, "clean_title_amazing_baccarat.png")
        if os.path.exists(p_amz):
            AMAZING_TMPL = cv2.imread(p_amz, 0)

        for d in ["1", "2", "3", "5", "6"]:
            p_digit = os.path.join(TEMPLATES_DIR, f"exact_digit_{d}.png")
            if os.path.exists(p_digit):
                DIGIT_TEMPLATES[d] = cv2.imread(p_digit, 0)


def detect_table_from_crop(crop_img):
    """
    Identifica de forma 100% visual el número real de la mesa leyendo el encabezado de la tarjeta.
    Garantiza que el bot reconozca tanto mesas de Pragmatic Play como Evolution Gaming.
    """
    _load_title_templates()
    if crop_img is None:
        return "UNKNOWN"

    try:
        if hasattr(crop_img, "convert"):
            gray = cv2.cvtColor(np.array(crop_img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        elif len(crop_img.shape) == 3:
            gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop_img

        h, w = gray.shape
        title_roi = gray[0:min(h, 45), 0:min(w, 220)]

        # 1. Comprobar plantillas de Pragmatic Play (Baccarat 1-6, Speed Baccarat 8-9)
        best_prag = "UNKNOWN"
        best_prag_score = -1.0
        for tname, tmpl in PRAGMATIC_TEMPLATES.items():
            if tmpl is not None and tmpl.shape[0] <= title_roi.shape[0] and tmpl.shape[1] <= title_roi.shape[1]:
                res = cv2.matchTemplate(title_roi, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_prag_score:
                    best_prag_score = max_val
                    best_prag = tname

        if best_prag_score >= 0.70:
            return best_prag

        # 2. Comprobar Amazing Baccarat si aplica
        if AMAZING_TMPL is not None:
            if AMAZING_TMPL.shape[0] <= title_roi.shape[0] and AMAZING_TMPL.shape[1] <= title_roi.shape[1]:
                s = cv2.minMaxLoc(cv2.matchTemplate(title_roi, AMAZING_TMPL, cv2.TM_CCOEFF_NORMED))[1]
                if s >= 0.80:
                    return "Amazing Baccarat"

        # 3. Localizar la palabra 'Baccarat' en el encabezado (Evolution)
        if BACCARAT_WORD_TMPL is not None:
            if BACCARAT_WORD_TMPL.shape[0] <= title_roi.shape[0] and BACCARAT_WORD_TMPL.shape[1] <= title_roi.shape[1]:
                res = cv2.matchTemplate(title_roi, BACCARAT_WORD_TMPL, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= 0.70:
                    bx, by = max_loc
                    digit_roi = title_roi[max(0, by-2) : min(h, by+14), min(w, bx+44) : min(w, bx+62)]
                    if digit_roi.shape[0] >= 8 and digit_roi.shape[1] >= 8:
                        best_digit = "UNKNOWN"
                        best_score = -1.0
                        for d_num, dtmpl in DIGIT_TEMPLATES.items():
                            if dtmpl is None:
                                continue
                            if dtmpl.shape[0] <= digit_roi.shape[0] and dtmpl.shape[1] <= digit_roi.shape[1]:
                                s = cv2.minMaxLoc(cv2.matchTemplate(digit_roi, dtmpl, cv2.TM_CCOEFF_NORMED))[1]
                            else:
                                s = cv2.minMaxLoc(cv2.matchTemplate(dtmpl, digit_roi, cv2.TM_CCOEFF_NORMED))[1]
                            if s > best_score:
                                best_score = s
                                best_digit = d_num
                        if best_score >= 0.65:
                            return f"Baccarat {best_digit}"

        return "UNKNOWN"
    except Exception as e:
        logger.warning(f"Error en detección visual de título: {e}")
        return "UNKNOWN"


def load_table_regions():
    if os.path.exists(REGIONS_FILE):
        with open(REGIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_road_history_from_crop(crop_img):
    """
    Extrae la secuencia real de jugadas visuales (P, B, T) analizando los puntos del Road.
    Usa umbrales de saturación estrictos para ignorar el resplandor azul del fondo y
    cv2.RETR_EXTERNAL para evitar contar círculos concéntricos de la misma ficha.
    """
    if crop_img is None:
        return []

    if hasattr(crop_img, "convert"):
        crop_bgr = cv2.cvtColor(np.array(crop_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    else:
        crop_bgr = crop_img

    h, w, _ = crop_bgr.shape
    # ROI ajustado estrictamente a la cuadrícula del Road (evita barra de estadísticas inferior)
    roi = crop_bgr[int(h * 0.14):int(h * 0.38), int(w * 0.02):int(w * 0.95)]
    if roi.size == 0:
        return []

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Umbral de saturación y brillo >= 75 para ignorar el resplandor azul pálido del fondo
    blue = cv2.inRange(hsv, np.array([95, 75, 75]), np.array([135, 255, 255]))
    red1 = cv2.inRange(hsv, np.array([0, 75, 75]), np.array([15, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([165, 75, 75]), np.array([180, 255, 255]))
    red = cv2.bitwise_or(red1, red2)
    green = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255]))

    mask = cv2.bitwise_or(cv2.bitwise_or(blue, red), green)
    # RETR_EXTERNAL garantiza no contar anillos concéntricos dentro de la misma ficha
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    items = []
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        # Una ficha real en cuadrícula 339x244 tiene área >= 15 y dimensiones mínimas 5x5
        if 15 <= area <= 300 and 5 <= bw <= 24 and 5 <= bh <= 24:
            (cx, cy), rad = cv2.minEnclosingCircle(c)
            sub = hsv[by:by+bh, bx:bx+bw]
            b_cnt = cv2.countNonZero(cv2.inRange(sub, np.array([95, 60, 60]), np.array([135, 255, 255])))
            r1_cnt = cv2.countNonZero(cv2.inRange(sub, np.array([0, 60, 60]), np.array([15, 255, 255])))
            r2_cnt = cv2.countNonZero(cv2.inRange(sub, np.array([165, 60, 60]), np.array([180, 255, 255])))
            r_cnt = r1_cnt + r2_cnt
            g_cnt = cv2.countNonZero(cv2.inRange(sub, np.array([35, 50, 50]), np.array([85, 255, 255])))

            code = "P" if (b_cnt >= r_cnt and b_cnt >= g_cnt) else ("B" if r_cnt >= g_cnt else "T")
            items.append((cx, cy, code))

    items.sort(key=lambda it: it[0])

    # Verificación de dispersión horizontal: si todos los puntos están en 1 o 2 columnas,
    # es imposible que haya 10 o más jugadas (evita artefactos acumulados en un punto)
    if len(items) >= 10:
        xs = [it[0] for it in items]
        span = max(xs) - min(xs)
        if span < 30:  # Menos de 3 columnas de cuadrícula
            return []

    return [it[2] for it in items]


def evaluate_table_hands(crop_img):
    """
    Evalúa si la mesa está dentro del rango estrictamente permitido: 10 a 64 jugadas.
    65 o más jugadas: OMITIDA bajo ninguna circunstancia (Fin de zapato).
    Verifica tanto el contador #N en la tarjeta como las jugadas del Road.
    Retorna: (total_hands: int, is_qualified: bool, reason: str)
    """
    if crop_img is None:
        return 0, False, "Sin imagen"

    history = extract_road_history_from_crop(crop_img)
    return evaluate_table_hands_exact(crop_img, history)


def load_slots_grid():
    """
    Carga la cuadrícula de slots desde table_regions.json y bet_coordinates.json
    para soportar cualquier resolución calibrada (1366x768, 1920x1080, 2K, etc.).
    """
    regions = load_table_regions()
    coords = {}
    coords_path = os.path.join(_BASE_DIR, "bet_coordinates.json")
    if os.path.exists(coords_path):
        try:
            with open(coords_path, "r", encoding="utf-8") as f:
                coords = json.load(f)
        except Exception:
            pass

    tables_coords = coords.get("tables", {})
    slots = []

    for tname, r in regions.items():
        if tname.startswith("_") or not isinstance(r, dict):
            continue
        sid = r.get("slot", len(slots) + 1)
        p_c = tables_coords.get(tname, {}).get("player", {"x": r["x"] + int(r["width"] * 0.28), "y": r["y"] + int(r["height"] * 0.76)})
        b_c = tables_coords.get(tname, {}).get("banker", {"x": r["x"] + int(r["width"] * 0.70), "y": r["y"] + int(r["height"] * 0.76)})
        slots.append({
            "slot_id": sid,
            "table_name": tname,
            "x": r["x"],
            "y": r["y"],
            "width": r["width"],
            "height": r["height"],
            "player": {"x": p_c["x"], "y": p_c["y"]},
            "banker": {"x": b_c["x"], "y": b_c["y"]}
        })

    if slots:
        slots.sort(key=lambda s: s["x"])
        return slots

    return [
        {"slot_id": 1, "table_name": "Baccarat 1", "x": 3,    "y": 66, "width": 339, "height": 244, "player": {"x": 98,   "y": 252}, "banker": {"x": 241,  "y": 252}},
        {"slot_id": 2, "table_name": "Baccarat 2", "x": 344,  "y": 66, "width": 339, "height": 244, "player": {"x": 439,  "y": 252}, "banker": {"x": 582,  "y": 252}},
        {"slot_id": 3, "table_name": "Baccarat 5", "x": 684,  "y": 66, "width": 339, "height": 244, "player": {"x": 779,  "y": 252}, "banker": {"x": 922,  "y": 252}},
        {"slot_id": 4, "table_name": "Baccarat 3", "x": 1024, "y": 66, "width": 339, "height": 244, "player": {"x": 1119, "y": 252}, "banker": {"x": 1262, "y": 252}},
    ]


SLOTS_GRID = load_slots_grid()


class StakeBaccaratScraper:
    def __init__(self, target_tables=None, cdp_url=None):
        import config
        self.target_tables = target_tables or config.TARGET_TABLES
        self.regions = load_table_regions()
        self.slot_bets = {}

    def sync_slots_with_screen(self):
        """
        Escanea todos los slots de la pantalla para identificar visualmente qué mesa
        está en cada ranura en tiempo real. Adapta el bot a cualquier orden de mesas.
        """
        try:
            screen = capture_full_screen()
            screen_w, screen_h = screen.size
            updated = False
            active_slots = load_slots_grid()

            for slot in active_slots:
                x, y, w, h = slot["x"], slot["y"], slot["width"], slot["height"]
                x2, y2 = min(x + w, screen_w), min(y + h, screen_h)
                crop = screen.crop((x, y, x2, y2))
                real_name = detect_table_from_crop(crop)

                # Si la detección visual identifica la mesa, la usa; si no, usa el valor configurado por defecto
                target_name = real_name if real_name != "UNKNOWN" else slot.get("table_name")

                if target_name:
                    self.regions[target_name] = {"x": x, "y": y, "width": w, "height": h}
                    self.slot_bets[target_name] = {"player": slot["player"], "banker": slot["banker"]}
                    updated = True

            if updated:
                logger.info(f"Sincronización visual de mesas completada: {list(self.regions.keys())}")
        except Exception as e:
            logger.warning(f"No se pudo sincronizar slots visuales: {e}")

    def capture_table(self, table_name, output_path):
        try:
            screen = capture_full_screen()
            screen_w, screen_h = screen.size

            region = self.regions.get(table_name)

            # Si no hay región registrada, intentar buscarla en los slots activos por table_name
            if not region:
                for slot in load_slots_grid():
                    if slot.get("table_name") == table_name:
                        region = {"x": slot["x"], "y": slot["y"], "width": slot["width"], "height": slot["height"]}
                        self.regions[table_name] = region
                        self.slot_bets[table_name] = {"player": slot["player"], "banker": slot["banker"]}
                        logger.info(f"[{table_name}] Región recuperada desde SLOTS_GRID")
                        break

            if region:
                x  = region["x"]
                y  = region["y"]
                w  = region["width"]
                h  = region["height"]
                x2 = min(x + w, screen_w)
                y2 = min(y + h, screen_h)
                cropped = screen.crop((x, y, x2, y2))
                img_to_save = cropped
                msg = "OK"
            else:
                img_to_save = screen
                msg = f"Sin coordenadas para '{table_name}'"

            # IMPORTANTE: Siempre se usa table_name como nombre canónico.
            # La re-detección visual puede confundir mesas similares (ej: Baccarat 6 vs Speed Baccarat 8).
            # El nombre correcto es siempre el que viene del llamador (TARGET_TABLES).
            actual_table_name = table_name

            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img_to_save.save(output_path, "PNG")
            return True, msg, img_to_save, actual_table_name

        except Exception as e:
            logger.error(f"[{table_name}] Error de captura: {e}")
            return False, str(e), None, table_name

    def get_table_data(self, table_name, screenshot_path=None):
        safe_name = table_name.lower().replace(" ", "_")
        if not screenshot_path:
            screenshot_path = os.path.join(_BASE_DIR, f"screen_{safe_name}.png")

        ok, msg, cropped_img, actual_name = self.capture_table(table_name, screenshot_path)

        # Extraer jugadas reales y evaluar zapato (exacto con #N en tarjeta + Road)
        real_history = extract_road_history_from_crop(cropped_img) if cropped_img else []
        total_hands, is_qualified, reason = evaluate_table_hands_exact(cropped_img, real_history)

        last_result = real_history[-1] if real_history else "P"

        return {
            "table_name": actual_name,
            "is_active": ok,
            "last_result": last_result,
            "history": real_history,
            "total_hands": total_hands,
            "is_qualified": is_qualified,
            "qualify_reason": reason,
            "screenshot_path": screenshot_path,
            "is_live_screenshot": ok,
            "capture_msg": msg,
        }
