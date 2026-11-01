"""
calibrate_bets.py — Calibrador Rapido de Puntos de Apuesta en Pantalla (Stake / Evolution)
========================================================================================
Permite capturar las coordenadas de:
1. Ficha de $0.20
2. Area de Jugador (Player / Azul)
3. Area de Banca (Banker / Rojo)
4. Boton Doblar x2 (Opcional)

Guarda los resultados en bet_coordinates.json
"""

import os
import sys
import time
import json
import pyautogui

try:
    import winsound
    def beep():
        winsound.Beep(1200, 150)
except Exception:
    def beep():
        pass

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_FILE = os.path.join(_BASE_DIR, "bet_coordinates.json")

ELEMENTS = [
    ("chip_20",   "FICHA DE $0.20 USD",              "Coloca el mouse sobre la ficha de 20 centavos."),
    ("player",    "BOTON / AREA JUGADOR (PLAYER)",   "Coloca el mouse sobre el area de apuesta de Jugador (Azul)."),
    ("banker",    "BOTON / AREA BANCA (BANKER)",     "Coloca el mouse sobre el area de apuesta de Banca (Rojo)."),
    ("double_x2", "BOTON x2 (DOBLAR)",               "Coloca el mouse sobre el boton x2.")
]

def countdown(seconds, label):
    for r in range(seconds, 0, -1):
        sys.stdout.write(f"\r   ⏳ {label} en {r}s... (Mueve el mouse al objetivo)   ")
        sys.stdout.flush()
        time.sleep(1)
    print()

def main():
    print("=" * 65)
    print("  🎯  CALIBRADOR DE COORDENADAS DE APUESTA (STAKE / EVOLUTION)  🎯")
    print("=" * 65)
    print("Este asistente capturara los puntos exactos donde el bot apostara.")
    print("Asegurate de tener la mesa de Baccarat abierta y visible en pantalla.\n")
    
    input("Presiona ENTER cuando estes listo para comenzar...")
    print()

    captured = {}
    
    if os.path.exists(COORDS_FILE):
        try:
            with open(COORDS_FILE, "r", encoding="utf-8") as f:
                captured = json.load(f)
        except Exception:
            pass

    for key, name, hint in ELEMENTS:
        print("-" * 65)
        print(f">> OBJETIVO: {name}")
        print(f"   {hint}")
        countdown(4, "Capturando")
        pos = pyautogui.position()
        beep()
        print(f"   ✅ ¡CAPTURADO! Coordenadas: X={pos.x}, Y={pos.y}")
        captured[key] = {
            "x": pos.x,
            "y": pos.y,
            "description": name
        }
        time.sleep(1)

    print("=" * 65)
    with open(COORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(captured, f, indent=2, ensure_ascii=False)
    
    print("💾 ¡Coordenadas guardadas exitosamente en bet_coordinates.json!")
    print("=" * 65)

    test = input("\n¿Deseas hacer una prueba visual de movimiento a cada boton? (s/n): ").strip().lower()
    if test in ("s", "si", "y", "yes"):
        print("\nIniciando verificacion en 3 segundos...")
        time.sleep(3)
        for key, name, _ in ELEMENTS:
            coord = captured.get(key)
            if coord:
                print(f"   -> Moviendo a: {name} ({coord['x']}, {coord['y']})...")
                pyautogui.moveTo(coord["x"], coord["y"], duration=0.8, tween=pyautogui.easeOutQuad)
                time.sleep(1.2)
        print("\n✅ Verificacion completada con exito.")

if __name__ == "__main__":
    main()
