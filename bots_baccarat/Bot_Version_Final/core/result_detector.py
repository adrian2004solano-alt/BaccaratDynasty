"""
core/result_detector.py — v12 (Detección Estricta de Fin Total de Mano + Temporizador Verde)
=============================================================================================
1. PROHIBICIÓN TOTAL DE DECIDIR DURANTE EL REPARTO DE CARTAS:
   - Eliminada por completo la lectura de iluminación inferior (p_glow / b_glow) que causaba
     falsos resultados cuando salía un 8 o 9 parcial o faltaban cartas acostadas (5ta/6ta carta).
   - Mientras se están repartiendo las 4, 5 o 6 cartas (incluyendo cartas acostadas a los lados),
     el detector retorna estrictamente None.
2. ÚNICA FUENTE DE VERDAD DEL RESULTADO FINAL:
   - El Listón Oficial Gigante (JUGADOR / BANCA / EMPATE) que Pragmatic Play despliega
     SOBRE EL CENTRO DEL BIG ROAD BLANCO (y: 16% a 36%, x: 28% a 72%) únicamente cuando
     TODAS las cartas han terminado de salir y el crupier/sistema cierra el total definitivo.
3. DETECCIÓN DE RELOJ VERDE DE APUESTAS:
   - Identifica si una mesa tiene la ventana de apuestas abierta con tiempo suficiente
     (anillo verde del temporizador en la esquina derecha del Road) para entrada ultrarrápida.
"""

import cv2
import logging
import numpy as np

logger = logging.getLogger("ResultDetector")

# Zona central estricta del Big Road donde aparece el Listón Oficial de Fin de Mano
BANNER_Y1_FRAC = 0.16
BANNER_Y2_FRAC = 0.36
BANNER_X1_FRAC = 0.28
BANNER_X2_FRAC = 0.72


def to_cv2(img):
    if img is None:
        return None
    if hasattr(img, "convert"):
        return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    return img


def detect_winner_ribbon_strict(card_bgr):
    """
    Detecta EXCLUSIVAMENTE el Listón Oficial de Victoria (JUGADOR, BANCA, EMPATE)
    sobre el centro del Big Road blanco, el cual solo aparece cuando la jugada
    terminó por completo (después de todas las cartas normales y acostadas).
    Retorna: 'P', 'B', 'T' o None.
    """
    if card_bgr is None or card_bgr.size == 0:
        return None

    h, w, _ = card_bgr.shape
    y1, y2 = int(h * BANNER_Y1_FRAC), int(h * BANNER_Y2_FRAC)
    x1, x2 = int(w * BANNER_X1_FRAC), int(w * BANNER_X2_FRAC)
    roi = card_bgr[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_h, roi_w = roi.shape[:2]
    total_px = float(roi_h * roi_w)

    # El listón oficial sobre el Road es un bloque sólido saturado que cubre >40% del centro del Road
    # 1. AZUL (JUGADOR)
    blue_mask = cv2.inRange(hsv, np.array([100, 95, 85]), np.array([135, 255, 255]))
    # 2. ROJO (BANCA)
    red1 = cv2.inRange(hsv, np.array([0, 95, 85]), np.array([14, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([166, 95, 85]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red1, red2)
    # 3. VERDE (EMPATE)
    green_mask = cv2.inRange(hsv, np.array([36, 95, 85]), np.array([86, 255, 255]))

    # Cerrar letras blancas ("JUGADOR" / "BANCA" / "EMPATE") dentro del listón para medir su bloque sólido
    kernel = np.ones((5, 9), np.uint8)

    for code, mask in [("P", blue_mask), ("B", red_mask), ("T", green_mask)]:
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        px_count = cv2.countNonZero(closed)
        fill_ratio = px_count / total_px

        # En juego normal los anillos huecos del road representan < 6% del área.
        # El listón ganador oficial cubre > 42% del centro del road.
        if fill_ratio >= 0.42:
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                area = cv2.contourArea(cnt)
                if bw >= int(roi_w * 0.50) and bh >= int(roi_h * 0.45) and area >= int(total_px * 0.35):
                    label = "JUGADOR 🔵" if code == "P" else ("BANCA 🔴" if code == "B" else "EMPATE 🟢")
                    logger.info(f"[DETECTOR] Listón final oficial en Road: {label} (cobertura={fill_ratio:.1%})")
                    return code

    return None


def are_cards_present(card_bgr):
    """
    Detecta si hay cartas físicas blancas repartidas en la zona inferior de la mesa
    (tanto las 4 cartas iniciales como la 5ta o 6ta carta acostada a los lados).
    """
    if card_bgr is None or card_bgr.size == 0:
        return False
    h, w, _ = card_bgr.shape
    roi = card_bgr[int(h * 0.52):int(h * 0.88), int(w * 0.14):int(w * 0.86)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    card_area = 0
    card_count = 0
    for c in cnts:
        bw, bh = cv2.boundingRect(c)[2:]
        area = cv2.contourArea(c)
        # Soporta tanto cartas verticales (bw>=12, bh>=18) como cartas acostadas (bw>=18, bh>=12)
        if ((bw >= 12 and bh >= 16) or (bw >= 16 and bh >= 12)) and area >= 150:
            card_area += area
            card_count += 1
    return card_count >= 1 or card_area >= 240


def has_green_betting_timer(card_bgr):
    """
    Detecta si el temporizador circular en la parte derecha del Road está en VERDE
    (lo que indica que la ventana de apuestas está abierta con ~7 a 15 segundos disponibles).
    """
    if card_bgr is None or card_bgr.size == 0:
        return False
    h, w, _ = card_bgr.shape
    timer_roi = card_bgr[int(h * 0.16):int(h * 0.38), int(w * 0.83):int(w * 0.98)]
    if timer_roi.size == 0:
        return False
    hsv_t = cv2.cvtColor(timer_roi, cv2.COLOR_BGR2HSV)
    green_ring = cv2.countNonZero(cv2.inRange(hsv_t, np.array([35, 80, 80]), np.array([85, 255, 255])))
    return green_ring >= 80


class ResultDetector:
    def __init__(self):
        pass

    def is_round_concluded(self, card_img):
        """Verifica si la tarjeta muestra actualmente el Listón Oficial de Victoria en el Road."""
        card_bgr = to_cv2(card_img)
        res = detect_winner_ribbon_strict(card_bgr)
        return (res is not None), res

    def is_ribbon_present(self, card_img):
        """Retorna True si el Listón Oficial de Victoria está visible actualmente."""
        card_bgr = to_cv2(card_img)
        return detect_winner_ribbon_strict(card_bgr) is not None

    def are_cards_present(self, card_img):
        """Retorna True si hay cartas repartidas en la mesa (normales o acostadas)."""
        card_bgr = to_cv2(card_img)
        return are_cards_present(card_bgr)

    def has_green_timer(self, card_img):
        """Retorna True si la mesa muestra el temporizador verde de apuestas abiertas."""
        card_bgr = to_cv2(card_img)
        return has_green_betting_timer(card_bgr)

    def is_round_active(self, card_img):
        """Retorna True si la mesa está jugando una mano (reparto o listón)."""
        card_bgr = to_cv2(card_img)
        return are_cards_present(card_bgr) or (detect_winner_ribbon_strict(card_bgr) is not None)

    def is_table_in_betting_window(self, card_img):
        """Retorna True si la mesa está limpia en la ventana de apuestas (sin cartas y sin listón)."""
        card_bgr = to_cv2(card_img)
        return not are_cards_present(card_bgr) and (detect_winner_ribbon_strict(card_bgr) is None)

    def read_result(self, card_img, table_name=None):
        """
        Lee el ganador real en pantalla ÚNICAMENTE cuando aparece el Listón Oficial sobre el Road.
        Jamás decide por el puntaje parcial de las cartas (8 o 9) mientras siguen saliendo cartas.
        """
        card_bgr = to_cv2(card_img)
        return detect_winner_ribbon_strict(card_bgr)

    def wait_until_clean(self, scraper, table_name, max_wait=6):
        """
        Espera activamente hasta que tanto el listón como las cartas desaparezcan por completo.
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
                return True
            time.sleep(0.25)

        return False
