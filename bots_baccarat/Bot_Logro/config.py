import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Credenciales de Telegram (Canal Principal de Señales: Baccarat Dynasty)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8849297437:AAGyKmSOdDIUOznSdyzBTP1YHptREGyy8T0")
_raw_chat = os.getenv("TELEGRAM_CHAT_ID", "-1004395102774").strip()
TELEGRAM_CHAT_ID = f"-{_raw_chat}" if _raw_chat.startswith("100") else _raw_chat

# Credenciales de Telegram (Canal de Resultados: Rush)
TELEGRAM_RESULTS_BOT_TOKEN = os.getenv("TELEGRAM_RESULTS_BOT_TOKEN", "8972617801:AAEh1tu8bbGRhHB250QE7vXYz0cGFT7SLoI")
TELEGRAM_RESULTS_CHAT_ID = os.getenv("TELEGRAM_RESULTS_CHAT_ID", "-1003636592278")

TARGET_TABLES = [
    "Baccarat 3",
    "Baccarat 5",
    "Baccarat 1",
    "Baccarat 2",
    "Baccarat 6",
]

BOT_EDITION = "BOT LOGRO — INTELIGENCIA TÁCTICA TIRO A TIRO"

MIN_SIGNAL_DELAY = int(os.getenv("MIN_SIGNAL_DELAY", 0))
MAX_SIGNAL_DELAY = int(os.getenv("MAX_SIGNAL_DELAY", 2))

# 8 Tiros máximos en total:
# Tiros 1 al 7 doblan ($0.20 -> $0.40 -> $0.80 -> $1.60 -> $3.20 -> $6.40 -> $12.80)
# Tiro 8 repite el monto del Tiro 7 ($12.80) como tiro de recuperación. Si pierde el 8, se para.
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", 8))

# Umbral mínimo de confianza real para emitir entrada inicial (Modo Sniper Logro)
MIN_CONFIDENCE_THRESHOLD = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", 89))
RECOVERY_MIN_CONFIDENCE = int(os.getenv("RECOVERY_MIN_CONFIDENCE", 86))

# Espera inicial para dejar el juego visible (segundos)
STARTUP_DELAY = int(os.getenv("STARTUP_DELAY", 8))

# ==========================================
# CONFIGURACIÓN DEL AUTO-BETTOR Y DIVISAS
# ==========================================
AUTO_BET_ENABLED = True
AUTO_BET_PERSISTENT_MARTINGALE = os.getenv("AUTO_BET_PERSISTENT_MARTINGALE", "true").lower() in ("true", "1", "yes")

# Modos de Divisa disponibles:
# Moneda 1: Extremo izquierdo (Base: $0.20 USD)
# Moneda 2: Segunda ficha a la izquierda (5x: $1.00 USD)
# Moneda 3: Tercera ficha a la izquierda (25x: $5.00 USD)
CURRENCY_MODES = {
    "USD": {
        "name": "USD",
        "symbol": "$",
        "chip1_value": 0.20,
        "chip2_value": 1.00,
        "chip3_value": 5.00,
        "base_bet": 0.20,
        "label": "DÓLARES ($0.20 Base | 8 Tiros: Tiro 8 repite $12.80 | Sin Stop-Profit)"
    },
    "TRY": {
        "name": "TRY",
        "symbol": "TL",
        "chip1_value": 4.0,
        "chip2_value": 20.0,
        "chip3_value": 100.0,
        "base_bet": 4.0,
        "label": "LIRA TURCA (4 TRY Base | 8 Tiros: Tiro 8 repite Tiro 7 | Sin Stop-Profit)"
    }
}

# Límites financieros (none = ilimitado / sin stop-profit)
_raw_sl = os.getenv("AUTO_BET_STOP_LOSS", "none").strip().lower()
AUTO_BET_STOP_LOSS = None if _raw_sl in ("none", "", "null", "false", "0") else float(_raw_sl)

# Sin Stop-Profit (ganar todo lo que pueda)
AUTO_BET_TAKE_PROFIT = None

# 8 Tiros totales (Tiro 8 repite la cantidad del Tiro 7; si pierde el Tiro 8, se detiene)
AUTO_BET_MAX_STEPS = int(os.getenv("AUTO_BET_MAX_STEPS", 8))
