"""
core/shoe_detector.py — Detección Exacta del Contador de Zapato (#N) en Pragmatic Play
====================================================================================
Lee directamente los dígitos del zapato (#N) ubicados junto a la barra de estadísticas
de cada mesa (a la izquierda de la insignia circular azul 'P').
Filtra con máxima prioridad y de forma estricta:
  - Menos de 10 jugadas: OMITIDA (< 10)
  - 65 o más jugadas: OMITIDA (65+ Fin de zapato — ESTRICTAMENTE PROHIBIDA)
"""

import cv2
import numpy as np

# Plantillas exactas de 5x7 píxeles para dígitos 0-9 (fuente de Pragmatic Play)
DIGIT_MAP = {
    0: np.array([
        [1, 1, 1, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ]),
    1: np.array([
        [0, 1, 1, 1, 0],
        [0, 1, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0]
    ]),
    2: np.array([
        [1, 1, 1, 1, 0],
        [1, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 0],
        [0, 1, 1, 0, 0],
        [1, 1, 0, 0, 0],
        [1, 1, 1, 1, 1]
    ]),
    3: np.array([
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ]),
    4: np.array([
        [0, 0, 1, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 1, 0],
        [1, 1, 0, 1, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 1, 0]
    ]),
    5: np.array([
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 1, 0],
        [1, 1, 1, 1, 0]
    ]),
    6: np.array([
        [0, 1, 1, 1, 0],
        [1, 0, 0, 1, 1],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [1, 0, 0, 1, 1],
        [1, 1, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ]),
    7: np.array([
        [1, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 1, 0, 0]
    ]),
    8: np.array([
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ]),
    9: np.array([
        [0, 1, 1, 1, 0],
        [1, 0, 0, 1, 1],
        [1, 1, 0, 0, 1],
        [0, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [1, 1, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ])
}

def classify_single_digit(cand_5x7):
    """Compara una imagen binaria de 5x7 con las plantillas de dígitos 0-9."""
    cand = (cand_5x7 > 0).astype(int)
    best_d = None
    best_s = -1.0
    for d, tmpl in DIGIT_MAP.items():
        s = np.mean(cand == tmpl)
        if s > best_s:
            best_s = s
            best_d = d
    return best_d, best_s

def read_shoe_number(card_bgr):
    """
    Lee con exactitud el número del zapato (#N) directamente desde la tarjeta de la mesa.
    Busca el indicador azul 'P' en la barra de estadísticas y lee el texto '#N' a su izquierda.
    Retorna el número de manos como entero (ej: 24, 50, 68), o None si no se pudo leer.
    Soporta imágenes tanto en formato NumPy (BGR) como PIL Image.
    """
    if card_bgr is None:
        return None

    if hasattr(card_bgr, "convert"):
        card_bgr = cv2.cvtColor(np.array(card_bgr.convert("RGB")), cv2.COLOR_RGB2BGR)
    elif not isinstance(card_bgr, np.ndarray) or card_bgr.size == 0:
        return None

    if len(card_bgr.shape) == 2:
        card_bgr = cv2.cvtColor(card_bgr, cv2.COLOR_GRAY2BGR)

    h, w, _ = card_bgr.shape
    hsv = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2HSV)

    # 1. Encontrar el círculo azul 'P' en la barra de estadísticas (lado izquierdo, y entre 35% y 85%)
    blue_mask = cv2.inRange(hsv, np.array([100, 120, 80]), np.array([135, 255, 255]))
    cnts, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    p_circle = None
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if 6 <= bw <= 30 and 6 <= bh <= 30 and 0.60 <= (bw / bh) <= 1.50:
            if int(h * 0.35) <= by <= int(h * 0.85) and bx < int(w * 0.35):
                p_circle = (bx, by, bw, bh)
                break

    if not p_circle:
        return None

    bx, by, bw, bh = p_circle

    # 2. El texto '#N' está inmediatamente a la izquierda del círculo azul P
    x1 = max(0, bx - 55)
    y1 = max(0, by - 4)
    y2 = min(h, by + bh + 4)

    roi = card_bgr[y1:y2, x1:bx]
    if roi.size == 0:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Probar diferentes umbrales para aislar los caracteres blancos
    for th_val in [175, 185, 195]:
        _, th = cv2.threshold(gray, th_val, 255, cv2.THRESH_BINARY)
        char_cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in char_cnts if cv2.boundingRect(c)[3] >= 5]
        boxes.sort(key=lambda b: b[0])

        cand_boxes = [b for b in boxes if b[3] >= 5 and 3 <= b[2] <= 14]
        if not cand_boxes:
            continue

        # Caso A: Dos dígitos fusionados en un solo contorno (ancho 9 a 14 px)
        for b in cand_boxes:
            if 9 <= b[2] <= 14:
                sub = th[b[1]:b[1]+b[3], b[0]:b[0]+b[2]]
                if sub.shape[0] != 7:
                    sub = cv2.resize(sub, (b[2], 7), interpolation=cv2.INTER_NEAREST)
                d1, s1 = classify_single_digit(sub[:, 0:5])
                d2, s2 = classify_single_digit(sub[:, -5:])
                if s1 >= 0.70 and s2 >= 0.70:
                    return d1 * 10 + d2

        # Caso B: Dos dígitos separados en dos contornos individuales (ancho 3 a 7 px cada uno)
        single_boxes = [b for b in cand_boxes if 3 <= b[2] <= 7]
        if len(single_boxes) >= 2:
            b1, b2 = single_boxes[-2], single_boxes[-1]
            if 0 <= (b2[0] - (b1[0] + b1[2])) <= 5:
                sub1 = cv2.resize(th[b1[1]:b1[1]+b1[3], b1[0]:b1[0]+b1[2]], (5, 7), interpolation=cv2.INTER_NEAREST)
                sub2 = cv2.resize(th[b2[1]:b2[1]+b2[3], b2[0]:b2[0]+b2[2]], (5, 7), interpolation=cv2.INTER_NEAREST)
                d1, s1 = classify_single_digit(sub1)
                d2, s2 = classify_single_digit(sub2)
                if s1 >= 0.70 and s2 >= 0.70:
                    return d1 * 10 + d2

        # Caso C: Un solo dígito (ej: #4, #1)
        if len(single_boxes) >= 1:
            b = single_boxes[-1]
            sub = cv2.resize(th[b[1]:b[1]+b[3], b[0]:b[0]+b[2]], (5, 7), interpolation=cv2.INTER_NEAREST)
            d, s = classify_single_digit(sub)
            if s >= 0.70:
                return d

    return None

def evaluate_table_hands_exact(card_bgr, history=None):
    """
    Evalúa si la mesa es apta verificando TANTO el contador '#N' de la tarjeta
    COMO la cantidad de jugadas en el historial.
    Si CUALQUIERA de ellos indica >= 65 jugadas, la mesa queda RECHAZADA.
    
    Retorna: (total_hands: int, is_qualified: bool, reason: str)
    """
    if card_bgr is None:
        return 0, False, "Sin imagen de mesa"

    if hasattr(card_bgr, "convert"):
        card_bgr = cv2.cvtColor(np.array(card_bgr.convert("RGB")), cv2.COLOR_RGB2BGR)
    elif not isinstance(card_bgr, np.ndarray) or card_bgr.size == 0:
        return 0, False, "Imagen vacía"

    # 1. Leer el número del zapato (#N) en la tarjeta
    shoe_hands = read_shoe_number(card_bgr)

    # 2. Contar jugadas detectadas en el road
    road_hands = len(history) if history else 0

    # 3. El total de manos es el máximo entre el contador #N y las jugadas del road
    if shoe_hands is not None:
        total_hands = max(shoe_hands, road_hands)
        source = f"#{shoe_hands} en tarjeta"
    else:
        total_hands = road_hands
        source = f"{road_hands} en Road"

    # ── REGLA ESTRICTA 1: Menos de 10 jugadas ──
    if total_hands < 10:
        return total_hands, False, f"OMITIDA: Solo {total_hands} jugadas ({source}, mínimo 10)"

    # ── REGLA ESTRICTA 2: 65 o más jugadas (PROHIBIDO BAJO NINGUNA CIRCUNSTANCIA) ──
    if total_hands >= 65 or (shoe_hands is not None and shoe_hands >= 65) or road_hands >= 65:
        culprit = f"#{shoe_hands}" if (shoe_hands is not None and shoe_hands >= 65) else f"{total_hands}"
        return total_hands, False, f"OMITIDA: Zapato con {culprit} jugadas (65+ Fin de zapato — ESTRICTAMENTE PROHIBIDA)"

    return total_hands, True, f"APTA ({total_hands} jugadas, {source})"
