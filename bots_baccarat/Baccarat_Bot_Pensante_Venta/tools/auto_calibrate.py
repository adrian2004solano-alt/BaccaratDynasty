# -*- coding: utf-8 -*-
"""
tools/auto_calibrate.py — Calibrador Visual Automático Universal (Baccarat Multiplay)
=====================================================================================
Permite calibrar el bot a cualquier resolución de pantalla (1366x768, 1920x1080, 2K, etc.)
en solo 25 segundos sin necesidad de ingresar coordenadas manualmente.

1. Cuenta regresiva interactiva de 25s para abrir y maximizar el casino.
2. Captura la pantalla completa a resolución nativa.
3. Detecta y calcula las coordenadas de las 4 mesas, Jugador, Banca y Fichas.
4. Genera automáticamente 'bet_coordinates.json' y 'table_regions.json'.
5. Genera la imagen de confirmación 'calibracion_resultado.png' y la abre para verificación.
"""

import os
import sys
import time
import json
import numpy as np

# Asegurar path al directorio raíz del bot
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import cv2
except ImportError:
    print("[ERROR] OpenCV (cv2) no está instalado en el entorno.")
    sys.exit(1)

try:
    import mss
    from PIL import Image
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

from core.scraper import detect_table_from_crop


def beep(freq, duration_ms):
    if HAS_WINSOUND:
        try:
            winsound.Beep(freq, duration_ms)
        except Exception:
            pass


def capture_screen():
    if HAS_MSS:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                frame = np.array(img)
                bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                return bgr
        except Exception as e:
            print(f"  [Aviso] mss falló ({e}), intentando ImageGrab...")

    try:
        from PIL import ImageGrab
        pil_img = ImageGrab.grab(all_screens=False)
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"  [Aviso] ImageGrab falló ({e}), intentando PyAutoGUI...")

    try:
        import pyautogui
        pil_img = pyautogui.screenshot()
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"[ERROR] No se pudo capturar la pantalla: {e}")
        return None


def run_countdown(seconds=60):
    print("=" * 66)
    print("      BACCARAT BOT - CALIBRADOR AUTOMÁTICO DE PANTALLA")
    print("=" * 66)
    print("  Instrucciones:")
    print("  1. Abre tu navegador (Chrome / Edge / Opera) con Stake u otro casino.")
    print("  2. Entra a la mesa 'Baccarat Multiplay' (Pragmatic Play).")
    print("  3. Coloca la ventana en PANTALLA COMPLETA (F11 o maximizada).")
    print("  4. Asegúrate de que las 4 mesas y la barra de fichas sean visibles.")
    print(f"  Tienes {seconds} segundos (1 minuto) para preparar la pantalla.")
    print("=" * 66)
    print()

    for r in range(seconds, 0, -1):
        if r in (60, 45, 30, 20, 10):
            beep(750, 100)
        elif r <= 3:
            beep(1100, 150)

        mins = r // 60
        secs = r % 60
        time_str = f"{mins:02d}:{secs:02d}" if mins > 0 else f"{secs:02d}s"
        sys.stdout.write(f"\r  ⏳ Calibrando en {time_str}... (Por favor abre el casino ahora)   ")
        sys.stdout.flush()
        time.sleep(1)

    print("\n\n  📸 ¡CAPTURANDO PANTALLA Y CALCULANDO COORDENADAS AHORA...!")
    beep(1300, 250)


def calibrate(test_image_path=None, skip_countdown=False):
    if not skip_countdown:
        run_countdown(60)

    if test_image_path and os.path.exists(test_image_path):
        print(f"  [Modo Prueba] Cargando imagen de prueba: {test_image_path}")
        screen = cv2.imread(test_image_path)
    else:
        screen = capture_screen()

    if screen is None:
        print("  [ERROR] No se pudo obtener la captura de pantalla.")
        return False

    h_screen, w_screen = screen.shape[:2]
    print(f"  Resolución detectada: {w_screen} x {h_screen} píxeles.")

    # Escala proporcional tomando como referencia la resolución base 1366x768
    BASE_W = 1366.0
    BASE_H = 768.0
    fx = w_screen / BASE_W
    fy = h_screen / BASE_H

    # Parámetros base de las 4 mesas en 1 sola fila
    # Base 1366x768:
    # Slot 1: x=3,    y=66, w=339, h=244
    # Slot 2: x=344,  y=66, w=339, h=244
    # Slot 3: x=684,  y=66, w=339, h=244
    # Slot 4: x=1024, y=66, w=339, h=244
    base_slots = [
        {"slot": 1, "bx": 3,    "default_name": "Baccarat 1"},
        {"slot": 2, "bx": 344,  "default_name": "Baccarat 2"},
        {"slot": 3, "bx": 684,  "default_name": "Baccarat 5"},
        {"slot": 4, "bx": 1024, "default_name": "Baccarat 3"},
    ]

    card_h = int(round(244 * fy))
    card_w = int(round(339 * fx))
    card_y = int(round(66 * fy))

    table_regions = {
        "_comment": f"Calibración Generada Automáticamente ({w_screen}x{h_screen})"
    }
    tables_coords = {}

    annotated = screen.copy()

    # Colores BGR
    COLOR_BOX = (0, 255, 0)       # Verde brillante para tarjetas
    COLOR_PLAYER = (255, 140, 0)   # Azul / Cyan para Jugador
    COLOR_BANKER = (50, 50, 255)   # Rojo para Banca
    COLOR_CHIP = (0, 220, 255)     # Amarillo para Fichas
    COLOR_TEXT = (255, 255, 255)   # Blanco

    detected_names = []
    used_names = set()

    for s_info in base_slots:
        slot_num = s_info["slot"]
        sx = int(round(s_info["bx"] * fx))
        sy = card_y
        sw = card_w
        sh = card_h

        # Ajuste de bordes
        sx = max(0, min(sx, w_screen - 10))
        sy = max(0, min(sy, h_screen - 10))
        sw = min(sw, w_screen - sx)
        sh = min(sh, h_screen - sy)

        crop = screen[sy:sy+sh, sx:sx+sw]
        table_name = "UNKNOWN"
        if crop.size > 0:
            table_name = detect_table_from_crop(crop)

        # Si no se detectó con certeza o ya está en uso, usar nombre por defecto
        if table_name == "UNKNOWN" or table_name in used_names:
            table_name = s_info["default_name"]

        used_names.add(table_name)
        detected_names.append(table_name)

        # Registro en table_regions.json
        table_regions[table_name] = {
            "x": sx,
            "y": sy,
            "width": sw,
            "height": sh,
            "slot": slot_num
        }

        # Coordenadas relativas exactas de Jugador y Banca dentro de la tarjeta
        # dx_player ~ 28.02% del ancho, dy ~ 76.23% del alto
        # dx_banker ~ 70.21% del ancho, dy ~ 76.23% del alto
        px = sx + int(round(sw * 0.2802))
        py = sy + int(round(sh * 0.7623))
        bx = sx + int(round(sw * 0.7021))
        by = sy + int(round(sh * 0.7623))

        tables_coords[table_name] = {
            "slot": slot_num,
            "player": {"x": px, "y": py, "description": f"{table_name} - Jugador"},
            "banker": {"x": bx, "y": by, "description": f"{table_name} - Banca"}
        }

        # Dibujar en imagen anotada
        # Rectángulo de mesa
        cv2.rectangle(annotated, (sx, sy), (sx + sw, sy + sh), COLOR_BOX, 2)
        # Etiqueta de cabecera
        header_text = f"Slot {slot_num}: {table_name}"
        cv2.putText(annotated, header_text, (sx + 8, sy + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55 * fx, (0, 0, 0), 3)
        cv2.putText(annotated, header_text, (sx + 8, sy + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55 * fx, COLOR_BOX, 1)

        # Círculo Jugador (Azul)
        cv2.circle(annotated, (px, py), int(round(9 * fx)), COLOR_PLAYER, -1)
        cv2.circle(annotated, (px, py), int(round(11 * fx)), (255, 255, 255), 1)
        cv2.putText(annotated, "P", (px - int(round(4 * fx)), py + int(round(4 * fy))), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * fx, (255, 255, 255), 1)

        # Círculo Banca (Rojo)
        cv2.circle(annotated, (bx, by), int(round(9 * fx)), COLOR_BANKER, -1)
        cv2.circle(annotated, (bx, by), int(round(11 * fx)), (255, 255, 255), 1)
        cv2.putText(annotated, "B", (bx - int(round(4 * fx)), py + int(round(4 * fy))), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * fx, (255, 255, 255), 1)

    # Coordenadas de fichas (Pragmatic Play / Stake)
    # Base 1366x768: 501, 736 (Ficha 4 / base)
    chip_base_x = int(round(501 * fx))
    chip_base_y = int(round(736 * fy))

    chips_dict = {
        "4":    {"x": chip_base_x,              "y": chip_base_y,              "description": "Ficha 4 — Menor valor / Extremo izquierdo"},
        "20":   {"x": int(round(552 * fx)),     "y": int(round(741 * fy)),     "description": "Ficha 20"},
        "100":  {"x": int(round(605 * fx)),     "y": int(round(741 * fy)),     "description": "Ficha 100"},
        "400":  {"x": int(round(657 * fx)),     "y": int(round(741 * fy)),     "description": "Ficha 400"},
        "2000": {"x": int(round(708 * fx)),     "y": int(round(741 * fy)),     "description": "Ficha 2K"},
        "5000": {"x": int(round(760 * fx)),     "y": int(round(741 * fy)),     "description": "Ficha 5K"}
    }

    # Dibujar fichas en imagen
    for c_val, c_pos in chips_dict.items():
        cx = c_pos["x"]
        cy = c_pos["y"]
        if 0 <= cx < w_screen and 0 <= cy < h_screen:
            cv2.circle(annotated, (cx, cy), int(round(12 * fx)), COLOR_CHIP, -1)
            cv2.circle(annotated, (cx, cy), int(round(14 * fx)), (0, 0, 0), 1)
            cv2.putText(annotated, c_val, (cx - int(round(8 * fx)), cy + int(round(4 * fy))), cv2.FONT_HERSHEY_SIMPLEX, 0.40 * fx, (0, 0, 0), 1)

    # Primer slot como predeterminado
    first_table = detected_names[0] if detected_names else "Baccarat 1"
    first_player = tables_coords[first_table]["player"]
    first_banker = tables_coords[first_table]["banker"]

    bet_coordinates = {
        "_comment": f"Calibración Oficial ({w_screen}x{h_screen}): {', '.join(detected_names)}",
        "screen_resolution": {
            "width": w_screen,
            "height": h_screen
        },
        "chip_02": {
            "x": chip_base_x,
            "y": chip_base_y,
            "description": "Ficha base 4 TRY (extremo izquierdo)"
        },
        "chip_20": {
            "x": chip_base_x,
            "y": chip_base_y,
            "description": "Alias de compatibilidad"
        },
        "chips": chips_dict,
        "tables": tables_coords,
        "player": {
            "x": first_player["x"],
            "y": first_player["y"],
            "description": f"Jugador predeterminado (Slot 1 - {first_table})"
        },
        "banker": {
            "x": first_banker["x"],
            "y": first_banker["y"],
            "description": f"Banca predeterminada (Slot 1 - {first_table})"
        }
    }

    # Guardar archivos JSON
    regions_file = os.path.join(_BOT_ROOT, "table_regions.json")
    coords_file = os.path.join(_BOT_ROOT, "bet_coordinates.json")
    result_img_path = os.path.join(_BOT_ROOT, "calibracion_resultado.png")

    try:
        with open(regions_file, "w", encoding="utf-8") as f:
            json.dump(table_regions, f, indent=2, ensure_ascii=False)
        print(f"  [OK] Guardado: {regions_file}")

        with open(coords_file, "w", encoding="utf-8") as f:
            json.dump(bet_coordinates, f, indent=2, ensure_ascii=False)
        print(f"  [OK] Guardado: {coords_file}")

        cv2.imwrite(result_img_path, annotated)
        print(f"  [OK] Imagen de confirmación guardada: {result_img_path}")
    except Exception as e:
        print(f"  [ERROR] Falló al guardar archivos de calibración: {e}")
        return False

    print("\n" + "=" * 66)
    print("      ¡CALIBRACIÓN COMPLETADA EXITOSAMENTE!")
    print("=" * 66)
    print(f"  Resolución calibrada: {w_screen} x {h_screen}")
    for s_idx, t_name in enumerate(detected_names, start=1):
        p_c = tables_coords[t_name]["player"]
        b_c = tables_coords[t_name]["banker"]
        print(f"  - Mesa {s_idx} ({t_name}): Jugador=({p_c['x']}, {p_c['y']}) | Banca=({b_c['x']}, {b_c['y']})")
    print(f"  - Ficha Base (4 TRY): ({chip_base_x}, {chip_base_y})")
    print("=" * 66)
    print("  Se ha abierto la imagen 'calibracion_resultado.png'.")
    print("  Verifica que las cajas verdes coincidan con las 4 mesas.")
    print("  ¡Ya puedes iniciar el bot con el lanzador bat deseado!")
    print("=" * 66)

    beep(1600, 400)

    # Intentar abrir la imagen para que el usuario la vea de inmediato
    try:
        os.startfile(result_img_path)
    except Exception:
        pass

    return True


if __name__ == "__main__":
    skip = "--no-countdown" in sys.argv or "-y" in sys.argv
    test_img = None
    for arg in sys.argv[1:]:
        if arg.endswith((".png", ".jpg", ".jpeg")) and os.path.exists(arg):
            test_img = arg
            break

    success = calibrate(test_image_path=test_img, skip_countdown=skip)
    if not success:
        sys.exit(1)
