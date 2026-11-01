"""
core/scraper.py — v16 (Calibración Exacta 3x2 Mesas con Texto Ampliado + Lectura por Columnas)
==============================================================================================
1. Captura de Pantalla Real de cada mesa sin recortes (440 x 288 px por tarjeta).
2. Reconocimiento Visual Dual de Títulos (soporta escala ampliada 3x2 y escala 4x1).
3. Extracción Columnar Exacta del Big Road (filtra puntos de par, une cortes de empate '/'
   y ordena cronológicamente columna por columna de arriba hacia abajo).
4. Evaluación Estricta del Zapato (8 a 64 manos permitidas).
"""

import os
import json
import logging
import cv2
import numpy as np

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
BACCARAT_WORD_TMPL_V2 = None
DIGIT_TEMPLATES_V2 = {}
BACCARAT_WORD_TMPL_V1 = None
DIGIT_TEMPLATES_V1 = {}
AMAZING_TMPL = None


def _load_title_templates():
    global BACCARAT_WORD_TMPL_V2, DIGIT_TEMPLATES_V2, BACCARAT_WORD_TMPL_V1, DIGIT_TEMPLATES_V1, AMAZING_TMPL
    if BACCARAT_WORD_TMPL_V2 is None and BACCARAT_WORD_TMPL_V1 is None:
        p_word_v2 = os.path.join(TEMPLATES_DIR, "tmpl_word_baccarat_v2.png")
        if os.path.exists(p_word_v2):
            BACCARAT_WORD_TMPL_V2 = cv2.imread(p_word_v2, 0)

        p_word_v1 = os.path.join(TEMPLATES_DIR, "tmpl_word_baccarat.png")
        if os.path.exists(p_word_v1):
            BACCARAT_WORD_TMPL_V1 = cv2.imread(p_word_v1, 0)

        p_amz = os.path.join(TEMPLATES_DIR, "clean_title_amazing_baccarat.png")
        if os.path.exists(p_amz):
            AMAZING_TMPL = cv2.imread(p_amz, 0)

        for d in ["1", "2", "3", "5", "6"]:
            p_d2 = os.path.join(TEMPLATES_DIR, f"exact_digit_{d}_v2.png")
            if os.path.exists(p_d2):
                DIGIT_TEMPLATES_V2[d] = cv2.imread(p_d2, 0)
            p_d1 = os.path.join(TEMPLATES_DIR, f"exact_digit_{d}.png")
            if os.path.exists(p_d1):
                DIGIT_TEMPLATES_V1[d] = cv2.imread(p_d1, 0)


def detect_table_from_crop(crop_img):
    """
    Identifica de forma 100% visual el número real de la mesa leyendo el encabezado de la tarjeta.
    Soporta tanto el diseño ampliado (3 columnas x 2 filas) como el diseño compacto.
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
        title_roi = gray[0:min(h, 48), 0:min(w, 180)]

        # 1. Comprobar primero escala ampliada V2 (3x2 mesas, palabra 'Baccarat' de 58px)
        if BACCARAT_WORD_TMPL_V2 is not None:
            tw, th = BACCARAT_WORD_TMPL_V2.shape[1], BACCARAT_WORD_TMPL_V2.shape[0]
            if th <= title_roi.shape[0] and tw <= title_roi.shape[1]:
                res2 = cv2.matchTemplate(title_roi, BACCARAT_WORD_TMPL_V2, cv2.TM_CCOEFF_NORMED)
                _, max_val2, _, (bx2, by2) = cv2.minMaxLoc(res2)
                if max_val2 >= 0.72:
                    digit_roi2 = title_roi[max(0, by2 - 2):min(h, by2 + 15), min(w, bx2 + 57):min(w, bx2 + 77)]
                    if digit_roi2.shape[0] >= 10 and digit_roi2.shape[1] >= 10:
                        best_d = "UNKNOWN"
                        best_s = -1.0
                        for d_num, dtmpl in DIGIT_TEMPLATES_V2.items():
                            if dtmpl is None:
                                continue
                            if dtmpl.shape[0] <= digit_roi2.shape[0] and dtmpl.shape[1] <= digit_roi2.shape[1]:
                                s = cv2.minMaxLoc(cv2.matchTemplate(digit_roi2, dtmpl, cv2.TM_CCOEFF_NORMED))[1]
                            else:
                                s = cv2.minMaxLoc(cv2.matchTemplate(dtmpl, digit_roi2, cv2.TM_CCOEFF_NORMED))[1]
                            if s > best_s:
                                best_s = s
                                best_d = d_num
                        if best_s >= 0.65:
                            return f"Baccarat {best_d}"

        # 2. Respaldo escala compacta V1 (4 mesas en fila, palabra 'Baccarat' de 44px)
        if BACCARAT_WORD_TMPL_V1 is not None:
            tw1, th1 = BACCARAT_WORD_TMPL_V1.shape[1], BACCARAT_WORD_TMPL_V1.shape[0]
            if th1 <= title_roi.shape[0] and tw1 <= title_roi.shape[1]:
                res1 = cv2.matchTemplate(title_roi, BACCARAT_WORD_TMPL_V1, cv2.TM_CCOEFF_NORMED)
                _, max_val1, _, (bx1, by1) = cv2.minMaxLoc(res1)
                if max_val1 >= 0.70:
                    digit_roi1 = title_roi[max(0, by1 - 2):min(h, by1 + 14), min(w, bx1 + 44):min(w, bx1 + 62)]
                    if digit_roi1.shape[0] >= 8 and digit_roi1.shape[1] >= 8:
                        best_d = "UNKNOWN"
                        best_s = -1.0
                        for d_num, dtmpl in DIGIT_TEMPLATES_V1.items():
                            if dtmpl is None:
                                continue
                            if dtmpl.shape[0] <= digit_roi1.shape[0] and dtmpl.shape[1] <= digit_roi1.shape[1]:
                                s = cv2.minMaxLoc(cv2.matchTemplate(digit_roi1, dtmpl, cv2.TM_CCOEFF_NORMED))[1]
                            else:
                                s = cv2.minMaxLoc(cv2.matchTemplate(dtmpl, digit_roi1, cv2.TM_CCOEFF_NORMED))[1]
                            if s > best_s:
                                best_s = s
                                best_d = d_num
                        if best_s >= 0.65:
                            return f"Baccarat {best_d}"

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
    Extrae la secuencia cronológica real de jugadas visuales (P, B, T) analizando las columnas
    del Big Road en las mesas de Pragmatic Play Multiplay.
    """
    if crop_img is None:
        return []

    if hasattr(crop_img, "convert"):
        crop_bgr = cv2.cvtColor(np.array(crop_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    else:
        crop_bgr = crop_img

    h, w, _ = crop_bgr.shape
    roi = crop_bgr[int(h * 0.13):int(h * 0.40), int(w * 0.02):int(w * 0.84)]
    if roi.size == 0:
        return []

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    blue_mask = cv2.inRange(hsv, np.array([95, 35, 35]), np.array([135, 255, 255]))
    red1 = cv2.inRange(hsv, np.array([0, 35, 35]), np.array([15, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([165, 35, 35]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red1, red2)
    green_mask = cv2.inRange(hsv, np.array([35, 35, 35]), np.array([85, 255, 255]))

    # Cierre morfológico 2x2 para unir círculos atravesados por la línea verde de empate ('/')
    kernel = np.ones((2, 2), np.uint8)
    blue_closed = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
    red_closed = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    raw_balls = []
    for code, mask in [("P", blue_closed), ("B", red_closed)]:
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            bx, by, bw, bh = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            # Descartar puntos pequeños de Par (3x3 px) y ruido
            if 6 <= bw <= 20 and bh >= 6 and area >= 12:
                n_vert = max(1, int(round(bh / 10.5)))
                cx = bx + bw / 2.0
                for k in range(n_vert):
                    cy = by + (k + 0.5) * (bh / n_vert)
                    y0 = int(max(0, cy - 5))
                    y1 = int(min(hsv.shape[0], cy + 5))
                    x0 = int(max(0, cx - 5))
                    x1 = int(min(hsv.shape[1], cx + 5))
                    has_tie = cv2.countNonZero(green_mask[y0:y1, x0:x1]) >= 4
                    raw_balls.append((cx, cy, code, has_tie))

    if not raw_balls:
        return []

    # Agrupar por columnas del Big Road (de izquierda a derecha) y ordenar de arriba hacia abajo
    raw_balls.sort(key=lambda b: b[0])
    columns = []
    for cx, cy, code, has_tie in raw_balls:
        if not columns or abs(cx - columns[-1]["mean_x"]) > 5.5:
            columns.append({"mean_x": cx, "balls": [(cx, cy, code, has_tie)]})
        else:
            columns[-1]["balls"].append((cx, cy, code, has_tie))
            columns[-1]["mean_x"] = sum(b[0] for b in columns[-1]["balls"]) / len(columns[-1]["balls"])

    ordered = []
    for col in columns:
        col["balls"].sort(key=lambda b: b[1])
        for _, _, code, has_tie in col["balls"]:
            ordered.append(code)
            if has_tie:
                ordered.append("T")

    return ordered


def evaluate_table_hands(crop_img):
    """
    Evalúa si la mesa está dentro del rango estrictamente permitido: 8 a 64 jugadas.
    Retorna: (total_hands: int, is_qualified: bool, reason: str)
    """
    if crop_img is None:
        return 0, False, "Sin imagen"

    history = extract_road_history_from_crop(crop_img)
    hands = len(history)

    if hands < 8:
        return hands, False, f"OMITIDA (< 8 jugadas, detectadas {hands})"
    if hands >= 65:
        return hands, False, f"OMITIDA (>= 65 jugadas, detectadas {hands})"

    return hands, True, f"APTA ({hands} jugadas)"


# ─── Resolución calibrada exactamente a la pantalla 1366x768 con escala ampliada (3x2 mesas) ─
_SLOTS_REF_W = 1366
_SLOTS_REF_H = 768

# Cuadrícula 3 columnas x 2 filas (width=440, height=288) - 100% libre de recortes:
# Fila 1 (y=95):  Slot 1 (x=15) | Slot 2 (x=464) | Slot 3 (x=913)
# Fila 2 (y=393): Slot 4 (x=15) | Slot 5 (x=464) | Slot 6 (x=913)
SLOTS_GRID = [
    {
        "slot_id": 1,
        "x": 15,  "y": 95,  "width": 440, "height": 288,
        "player": {"x": 141, "y": 292},
        "banker": {"x": 330, "y": 292},
    },
    {
        "slot_id": 2,
        "x": 464, "y": 95,  "width": 440, "height": 288,
        "player": {"x": 590, "y": 292},
        "banker": {"x": 779, "y": 292},
    },
    {
        "slot_id": 3,
        "x": 913, "y": 95,  "width": 440, "height": 288,
        "player": {"x": 1039, "y": 292},
        "banker": {"x": 1228, "y": 292},
    },
    {
        "slot_id": 4,
        "x": 15,  "y": 393, "width": 440, "height": 288,
        "player": {"x": 141, "y": 590},
        "banker": {"x": 330, "y": 590},
    },
    {
        "slot_id": 5,
        "x": 464, "y": 393, "width": 440, "height": 288,
        "player": {"x": 590, "y": 590},
        "banker": {"x": 779, "y": 590},
    },
    {
        "slot_id": 6,
        "x": 913, "y": 393, "width": 440, "height": 288,
        "player": {"x": 1039, "y": 590},
        "banker": {"x": 1228, "y": 590},
    },
]


class StakeBaccaratScraper:
    def __init__(self, target_tables=None, cdp_url=None):
        import config
        self.target_tables = target_tables or config.TARGET_TABLES
        self.regions = load_table_regions()
        self.slot_bets = {}
        coords_file = os.path.join(_BASE_DIR, "bet_coordinates.json")
        if os.path.exists(coords_file):
            try:
                with open(coords_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.slot_bets = data.get("tables", {})
            except Exception:
                pass

    def sync_slots_with_screen(self):
        """
        Escanea todos los slots de la pantalla (las 6 posiciones posibles de la cuadrícula 3x2)
        para identificar visualmente qué mesa está en cada ranura en tiempo real.
        """
        try:
            screen = capture_full_screen()
            screen_w, screen_h = screen.size
            found_regions = {}
            found_bets = {}

            for slot in SLOTS_GRID:
                x, y, w, h = slot["x"], slot["y"], slot["width"], slot["height"]
                x2, y2 = min(x + w, screen_w), min(y + h, screen_h)
                crop = screen.crop((x, y, x2, y2))
                real_name = detect_table_from_crop(crop)

                if real_name != "UNKNOWN":
                    found_regions[real_name] = {"slot": slot["slot_id"], "x": x, "y": y, "width": w, "height": h}
                    found_bets[real_name] = {"slot": slot["slot_id"], "player": slot["player"], "banker": slot["banker"]}

            if found_regions:
                self.regions.update(found_regions)
                self.slot_bets.update(found_bets)
                logger.info(f"Sincronización visual 3x2 completada: {list(found_regions.keys())}")
                try:
                    with open(REGIONS_FILE, "w", encoding="utf-8") as f:
                        json.dump(self.regions, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"No se pudo sincronizar slots visuales: {e}")

    def capture_table(self, table_name, output_path):
        try:
            screen = capture_full_screen()
            screen_w, screen_h = screen.size

            region = self.regions.get(table_name)
            if not region:
                self.sync_slots_with_screen()
                region = self.regions.get(table_name)

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

            real_name = detect_table_from_crop(img_to_save)
            actual_table_name = real_name if real_name != "UNKNOWN" else table_name
            if real_name != "UNKNOWN" and real_name != table_name:
                logger.info(f"🔄 Re-asignación visual: Se solicitó '{table_name}' pero la captura contiene '{real_name}'.")

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

        real_history = extract_road_history_from_crop(cropped_img) if cropped_img else []
        total_hands, is_qualified, reason = evaluate_table_hands(cropped_img)
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
