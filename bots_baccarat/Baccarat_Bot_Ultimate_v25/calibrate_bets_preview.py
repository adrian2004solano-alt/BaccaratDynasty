"""
calibrate_bets_preview.py — Verificador Visual de Coordenadas de Apuesta (Sin Clics)
=====================================================================================
Mueve suavemente el cursor a cada botón configurado para que el usuario pueda
comprobar en vivo que el mouse se posa exactamente en el centro de cada botón.
"""

import time
import json
import os
import pyautogui

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

def main():
    if not os.path.exists(COORDS_FILE):
        print("❌ No se encontró bet_coordinates.json")
        return

    with open(COORDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    tables = data.get("tables", {})
    chip = data.get("chip_20", {"x": 500, "y": 744})

    print("=" * 65)
    print("  🎯  VERIFICADOR VISUAL DE BOTONES (MODO DEMO SIN CLICS)  🎯")
    print("=" * 65)
    print("Asegúrate de tener la ventana de Baccarat Multiplay visible en pantalla.")
    print("El cursor se moverá a cada botón para que compruebes su puntería.")
    print("⚠️  Mueve el mouse a cualquier esquina si deseas abortar.\n")

    for i in range(5, 0, -1):
        print(f"Iniciando en {i} segundos...")
        time.sleep(1)

    # 1. Ficha base
    print(f"\n[1] Moviendo a Ficha Base ($0.20): ({chip['x']}, {chip['y']})...")
    pyautogui.moveTo(chip["x"], chip["y"], duration=1.0, tween=pyautogui.easeOutQuad)
    time.sleep(1.2)

    # 2. Cada mesa en orden
    order = ["Baccarat 3", "Baccarat 2", "Baccarat 5", "Baccarat 1"]
    for t_name in order:
        t_data = tables.get(t_name)
        if not t_data:
            continue
        p = t_data["player"]
        b = t_data["banker"]

        print(f"\n--> {t_name} (Slot {t_data.get('slot')}):")
        print(f"    🔵 JUGADOR: ({p['x']}, {p['y']})...")
        pyautogui.moveTo(p["x"], p["y"], duration=0.8, tween=pyautogui.easeOutQuad)
        time.sleep(1.0)

        print(f"    🔴 BANCA:   ({b['x']}, {b['y']})...")
        pyautogui.moveTo(b["x"], b["y"], duration=0.8, tween=pyautogui.easeOutQuad)
        time.sleep(1.0)

    print("\n" + "=" * 65)
    print("✅ Verificación completada con éxito. Todos los botones fueron recorridos.")
    print("=" * 65)

if __name__ == "__main__":
    main()
