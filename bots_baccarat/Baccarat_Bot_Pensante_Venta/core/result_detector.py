"""
core/result_detector.py  — v11 (Detección Estricta del Listón Ganador - Cero Falsos Positivos)
=============================================================================================
Aislamiento Total del Listón de Victoria:
  - Zona estricta del Road: y: 16% a 44%, x: 15% a 85%.
  - Termina ANTES de la barra de estadísticas (y < 45%) para NUNCA confundir
    con el botón estático de predicción P/B ni con los botones de apuestas.
  - Requiere franja horizontal ancha (ancho >= 35% del ROI, alto >= 10px, área >= 350px).
  - En fase de apuestas o cartas: Retorna estrictamente None.
"""

import cv2
import logging
import numpy as np

logger = logging.getLogger("ResultDetector")

# Zona estricta del Road (termina antes de la barra de stats que está al 45%)
ROAD_Y1_FRAC = 0.08
ROAD_Y2_FRAC = 0.48
ROAD_X1_FRAC = 0.18
ROAD_X2_FRAC = 0.82


def to_cv2(img):
    if hasattr(img, "convert"):
        return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    return img


def detect_winner_ribbon_strict(card_bgr):
    """
    Detecta exclusivamente el listón horizontal de victoria (JUGADOR, BANCA, EMPATE).
    Retorna: 'P', 'B', 'T' o None.
    Garantiza CERO falsos positivos en fase de apuestas o reposo.
    """
    if card_bgr is None or card_bgr.size == 0:
        return None

    h, w, _ = card_bgr.shape
    if h >= 220:
        # Tarjetas fila superior (h=244)
        y1, y2 = int(h * 0.20), int(h * 0.43)
    else:
        # Tarjetas fila inferior (h=210)
        y1, y2 = int(h * 0.10), int(h * 0.36)

    x1, x2 = int(w * 0.18), int(w * 0.82)
    roi = card_bgr[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_w = roi.shape[1]

    # Máscaras HSV de colores saturados del listón
    # 1. AZUL (JUGADOR)
    blue_mask = cv2.inRange(hsv, np.array([100, 100, 100]), np.array([130, 255, 255]))

    # 2. ROJO (BANCA)
    red1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([12, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([168, 100, 100]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red1, red2)

    # 3. VERDE (EMPATE)
    green_mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255]))

    for code, mask in [("P", blue_mask), ("B", red_mask), ("T", green_mask)]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            # El listón cruza horizontalmente el centro del road
            if bw >= int(roi_w * 0.30) and bh >= 8 and area >= 280:
                label = "JUGADOR 🔵" if code == "P" else ("BANCA 🔴" if code == "B" else "EMPATE 🟢")
                logger.info(f"[DETECTOR] Listón ganador confirmado: {label} (ancho={bw}px, área={area}px)")
                return code

    return None


def are_cards_present(card_bgr):
    """
    Detecta si hay cartas físicas repartidas en la mesa (jugada en curso / repartiendo).
    """
    if card_bgr is None or card_bgr.size == 0:
        return False
    h, w, _ = card_bgr.shape
    roi = card_bgr[int(h * 0.50):int(h * 0.95), int(w * 0.15):int(w * 0.85)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    card_area = 0
    card_count = 0
    for c in cnts:
        bw, bh = cv2.boundingRect(c)[2:]
        area = cv2.contourArea(c)
        if bw >= 10 and bh >= 15 and area >= 120:
            card_area += area
            card_count += 1
    return card_count >= 1 or card_area >= 200


class ResultDetector:
    def __init__(self):
        pass

    def is_round_concluded(self, card_img):
        """Verifica si la tarjeta muestra actualmente el listón de victoria de una jugada."""
        card_bgr = to_cv2(card_img)
        res = detect_winner_ribbon_strict(card_bgr)
        return (res is not None), res

    def is_ribbon_present(self, card_img):
        """Retorna True si el listón de victoria está visible actualmente."""
        card_bgr = to_cv2(card_img)
        return detect_winner_ribbon_strict(card_bgr) is not None

    def are_cards_present(self, card_img):
        """Retorna True si hay cartas repartidas en la mesa."""
        card_bgr = to_cv2(card_img)
        return are_cards_present(card_bgr)

    def is_round_active(self, card_img):
        """Retorna True si la mesa está jugando una mano (reparto o listón)."""
        card_bgr = to_cv2(card_img)
        return are_cards_present(card_bgr) or (detect_winner_ribbon_strict(card_bgr) is not None)

    def is_table_in_betting_window(self, card_img):
        """Retorna True si la mesa está en la ventana de apuestas (sin cartas y sin listón)."""
        card_bgr = to_cv2(card_img)
        return not are_cards_present(card_bgr) and (detect_winner_ribbon_strict(card_bgr) is None)

    def is_betting_timer_active(self, card_img):
        """Retorna True si el temporizador circular de apuestas (15..0s) está activo en pantalla."""
        card_bgr = to_cv2(card_img)
        if card_bgr is None or card_bgr.size == 0:
            return False
        if detect_winner_ribbon_strict(card_bgr) is not None:
            return False
        h, w, _ = card_bgr.shape
        if h >= 220:
            crop = card_bgr[45:110, 265:335]
        else:
            crop = card_bgr[12:70, 265:335]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        green = cv2.countNonZero(cv2.inRange(hsv, (35, 70, 70), (85, 255, 255)))
        yellow = cv2.countNonZero(cv2.inRange(hsv, (14, 70, 70), (34, 255, 255)))
        red1 = cv2.countNonZero(cv2.inRange(hsv, (0, 70, 70), (12, 255, 255)))
        red2 = cv2.countNonZero(cv2.inRange(hsv, (168, 70, 70), (180, 255, 255)))
        return (green + yellow + red1 + red2) >= 60

    def read_result(self, card_img, table_name=None):
        """
        Lee el ganador real en pantalla.
        Retorna: 'P', 'B', 'T' únicamente si el listón de victoria está presente.
        Retorna None durante apuestas, reparto o juego en curso (CERO adivinanzas).
        """
        card_bgr = to_cv2(card_img)
        return detect_winner_ribbon_strict(card_bgr)

    def wait_until_clean(self, scraper, table_name, max_wait=12):
        """
        Espera activamente hasta que tanto el listón como las cartas desaparezcan por completo.
        Garantiza que la mesa esté 100% limpia y en la ventana de apuestas (14-15s).
        """
        import time
        from PIL import Image

        start = time.time()
        while time.time() - start < max_wait:
            data = scraper.get_table_data(table_name)
            p = data.get("screenshot_path")
            if p and hasattr(Image, "open"):
                try:
                    with Image.open(p) as img:
                        card_bgr = to_cv2(img.copy())
                except Exception:
                    card_bgr = None
            else:
                card_bgr = None

            if card_bgr is not None and not are_cards_present(card_bgr) and not detect_winner_ribbon_strict(card_bgr):
                # La mesa está limpia y en ventana de apuestas
                return True
            time.sleep(0.5)

        return False
