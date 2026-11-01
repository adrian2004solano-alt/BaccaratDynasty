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

MIN_SIGNAL_DELAY = int(os.getenv("MIN_SIGNAL_DELAY", 0))
MAX_SIGNAL_DELAY = int(os.getenv("MAX_SIGNAL_DELAY", 15))
MAX_ATTEMPTS = 6

# Estrategias Activas
ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "DYNAMIC_10_STRATEGIES")
MAX_MONOCHROME_RATIO = float(os.getenv("MAX_MONOCHROME_RATIO", "0.20"))  # Máximo 20% Mono-Color (6 tiros mismo color)
MIN_STREAK_LENGTH = int(os.getenv("MIN_STREAK_LENGTH", 2))
MIN_CONFIDENCE_THRESHOLD = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", 80))

# Espera inicial para dejar el juego visible (segundos)
STARTUP_DELAY = int(os.getenv("STARTUP_DELAY", 8))

# ==========================================
# CONFIGURACIÓN DEL AUTO-BETTOR Y DIVISAS
# ==========================================
AUTO_BET_ENABLED = True
AUTO_BET_PERSISTENT_MARTINGALE = os.getenv("AUTO_BET_PERSISTENT_MARTINGALE", "true").lower() in ("true", "1", "yes")

# Modos de Divisa disponibles:
# Moneda 1: Extremo izquierdo (Base)
# Moneda 2: Segunda ficha a la izquierda (5x el valor base)
CURRENCY_MODES = {
    "USD": {
        "name": "USD",
        "symbol": "$",
        "chip1_value": 0.20,
        "chip2_value": 1.00,
        "base_bet": 0.20,
        "label": "DÓLARES ($0.20 Base | $1.00 Ficha Alta)"
    },
    "TRY": {
        "name": "TRY",
        "symbol": "TL",
        "chip1_value": 4.0,
        "chip2_value": 20.0,
        "base_bet": 4.0,
        "label": "LIRA TURCA (4 TRY Base | 20 TRY Ficha Alta)"
    }
}

# Límites financieros (none = ilimitado)
_raw_sl = os.getenv("AUTO_BET_STOP_LOSS", "none").strip().lower()
AUTO_BET_STOP_LOSS = None if _raw_sl in ("none", "", "null", "false", "0") else float(_raw_sl)

_raw_tp = os.getenv("AUTO_BET_TAKE_PROFIT", "none").strip().lower()
AUTO_BET_TAKE_PROFIT = None if _raw_tp in ("none", "", "null", "false", "0") else float(_raw_tp)

# Martingala progresiva
AUTO_BET_MAX_STEPS = int(os.getenv("AUTO_BET_MAX_STEPS", "50"))
