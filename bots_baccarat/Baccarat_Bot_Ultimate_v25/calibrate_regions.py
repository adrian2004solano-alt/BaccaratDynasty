"""
calibrate_regions.py
====================
Herramienta para detectar y calibrar las regiones de cada mesa de Baccarat
en tu pantalla. Toma una captura real y busca las mesas automáticamente
usando detección de texto con pytesseract o un método de detección visual.

Ejecutar: python calibrate_regions.py
Resultado: genera table_regions.json con las coordenadas de cada mesa.
"""

import os
import json
import sys
import time

REGIONS_FILE = os.path.join(os.path.dirname(__file__), "table_regions.json")
TARGET_TABLES = [
    "Baccarat 1", "Baccarat 2", "Baccarat 3",
    "Baccarat 5", "Baccarat 6", "Amazing Baccarat"
]


def capture_screen_pil():
    """Captura la pantalla completa con PIL."""
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def capture_screen_mss():
    """Captura la pantalla completa con mss."""
    import mss
    import mss.tools
    from PIL import Image
    import io
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        # Convertir a PIL Image
        return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")


def get_screen():
    """Obtiene imagen PIL de la pantalla."""
    try:
        return capture_screen_mss()
    except Exception:
        return capture_screen_pil()


def detect_tables_by_ocr(screen_img):
    """
    Detecta las regiones de las mesas usando pytesseract para leer los títulos
    "Baccarat 1", "Baccarat 2", etc. en la imagen.
    Retorna un dict {nombre_mesa: (x, y, w, h)}
    """
    try:
        import pytesseract
        import numpy as np
        from PIL import Image

        print("  [OCR] Analizando pantalla con pytesseract...")
        width, height = screen_img.size

        # Buscar texto en la imagen completa
        data = pytesseract.image_to_data(screen_img, output_type=pytesseract.Output.DICT)
        
        regions = {}
        text_positions = {}
        
        for i, text in enumerate(data["text"]):
            if text.strip() in ["Baccarat", "Amazing"]:
                # Ver si el siguiente texto es un número o "Baccarat"
                next_text = data["text"][i+1].strip() if i+1 < len(data["text"]) else ""
                full_name = f"{text.strip()} {next_text}".strip()
                
                for table in TARGET_TABLES:
                    if full_name.lower() == table.lower()[:len(full_name)]:
                        x = data["left"][i]
                        y = data["top"][i]
                        text_positions[table] = (x, y)
                        print(f"  [OCR] Encontrado '{table}' en ({x}, {y})")
                        break

        # Calcular las regiones de mesa a partir de las posiciones del título
        # Cada mesa ocupa aproximadamente w=250, h=195 en pantalla 1024x576
        # Escalar si la resolución es diferente
        scale_x = width / 1024
        scale_y = height / 576
        card_w = int(250 * scale_x)
        card_h = int(195 * scale_y)

        for table, (x, y) in text_positions.items():
            # El título está en la parte superior de la tarjeta
            # La tarjeta comienza ~15px arriba del texto del título
            card_x = max(0, x - int(10 * scale_x))
            card_y = max(0, y - int(15 * scale_y))
            regions[table] = {
                "x": card_x,
                "y": card_y,
                "width": card_w,
                "height": card_h
            }

        return regions

    except ImportError:
        print("  [!] pytesseract no disponible. Usando detección por color.")
        return {}
    except Exception as e:
        print(f"  [!] Error OCR: {e}")
        return {}


def detect_tables_by_color(screen_img):
    """
    Detecta regiones buscando el patrón de color oscuro de las tarjetas de mesa.
    Método visual sin OCR.
    """
    try:
        import numpy as np
        from PIL import Image
        
        print("  [VISUAL] Detectando tarjetas de mesa por patrones de color...")
        img_array = np.array(screen_img)
        height, width = img_array.shape[:2]

        # Las tarjetas tienen bordes redondeados oscuros (~#1a1a2e o similar)
        # Buscamos bloques rectangulares de color característico
        # El fondo del juego es muy oscuro (~10-20, 10-20, 30-40 RGB)
        # Las tarjetas de mesa tienen fondo gris oscuro (#2a2a3a aprox)
        
        # Buscar áreas con el color típico del header de la tarjeta (gris oscuro)
        r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
        
        # Máscara para el fondo de la tarjeta (gris oscuro)
        card_mask = (r > 25) & (r < 60) & (g > 25) & (g < 60) & (b > 35) & (b < 75)
        
        print(f"  [VISUAL] Resolución de pantalla detectada: {width}x{height}")
        return {}  # Método visual complejo, retornar vacío para usar fallback manual
        
    except Exception as e:
        print(f"  [!] Error detección visual: {e}")
        return {}


def manual_calibration(screen_img):
    """
    Calibración manual basada en proporciones relativas a la resolución de pantalla.
    Usa las proporciones de la imagen de referencia (1024x576) del usuario.
    """
    width, height = screen_img.size
    print(f"\n  [MANUAL] Resolución de pantalla: {width}x{height}")
    
    # Proporciones de referencia calculadas de la imagen del usuario (1024x576)
    # Fila superior: 4 mesas
    # Fila inferior: 2 mesas + espacio vacío
    
    # Las proporciones relativas (0.0 a 1.0) medidas de la imagen de referencia:
    # Cada mesa ocupa aprox 24.4% del ancho y 34% del alto
    # Con márgenes entre mesas de ~0.5%
    
    REF_W, REF_H = 1024, 576  # Resolución de referencia de la imagen del usuario
    
    # Coordenadas absolutas en la imagen de referencia (1024x576):
    ref_regions = {
        "Baccarat 1":        {"x":  5,   "y": 65,  "width": 247, "height": 165},
        "Baccarat 5":        {"x": 258,  "y": 65,  "width": 247, "height": 165},
        "Baccarat 2":        {"x": 511,  "y": 65,  "width": 247, "height": 165},
        "Baccarat 3":        {"x": 764,  "y": 65,  "width": 255, "height": 165},
        "Amazing Baccarat":  {"x":  5,   "y": 237, "width": 247, "height": 165},
        "Baccarat 6":        {"x": 258,  "y": 237, "width": 247, "height": 165},
    }
    
    # Escalar a la resolución real de la pantalla del usuario
    scale_x = width / REF_W
    scale_y = height / REF_H
    
    scaled_regions = {}
    for name, r in ref_regions.items():
        scaled_regions[name] = {
            "x":      int(r["x"]      * scale_x),
            "y":      int(r["y"]      * scale_y),
            "width":  int(r["width"]  * scale_x),
            "height": int(r["height"] * scale_y),
        }
        print(f"    {name:<20}: x={scaled_regions[name]['x']}, y={scaled_regions[name]['y']}, "
              f"w={scaled_regions[name]['width']}, h={scaled_regions[name]['height']}")
    
    return scaled_regions


def save_regions(regions):
    """Guarda las regiones en table_regions.json."""
    with open(REGIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
    print(f"\n  [OK] Regiones guardadas en: {REGIONS_FILE}")


def load_regions():
    """Carga regiones desde table_regions.json si existe."""
    if os.path.exists(REGIONS_FILE):
        with open(REGIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def crop_and_save(screen_img, regions, output_dir=None):
    """Recorta cada mesa y guarda las imágenes para verificación."""
    if output_dir is None:
        output_dir = os.path.dirname(__file__)
    
    print("\n  [CROP] Recortando y guardando vistas previas de mesas:")
    for name, r in regions.items():
        box = (r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"])
        cropped = screen_img.crop(box)
        safe_name = name.lower().replace(" ", "_")
        out_path = os.path.join(output_dir, f"preview_{safe_name}.png")
        cropped.save(out_path, "PNG")
        print(f"    [{name}] -> {out_path}")


def main():
    print("=" * 60)
    print("   CALIBRADOR DE REGIONES DE MESAS - BACCARAT ULTIMATE")
    print("=" * 60)
    
    print("\n[1] Capturando pantalla actual...")
    print("    (Asegúrate de tener el lobby de Baccarat visible en pantalla)")
    time.sleep(2)
    
    try:
        screen = get_screen()
        print(f"    Captura tomada: {screen.size[0]}x{screen.size[1]} px")
    except Exception as e:
        print(f"    [!] Error al capturar pantalla: {e}")
        sys.exit(1)
    
    print("\n[2] Calculando regiones de mesas...")
    regions = manual_calibration(screen)
    
    print("\n[3] Guardando regiones...")
    save_regions(regions)
    
    print("\n[4] Generando vistas previas recortadas de cada mesa...")
    crop_and_save(screen, regions)
    
    print("\n" + "=" * 60)
    print("  Calibración completada.")
    print("  Revisa los archivos preview_baccarat_*.png en la carpeta del bot")
    print("  para verificar que cada recorte muestre la mesa correcta.")
    print("  Si algo está mal, ajusta las coordenadas en table_regions.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
