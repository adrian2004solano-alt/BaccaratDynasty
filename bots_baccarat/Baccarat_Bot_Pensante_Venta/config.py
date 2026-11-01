import os
from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=True)
load_dotenv(override=True)


def _get_int(key, default):
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


def _get_float(key, default):
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


# ==========================================
# CREDENCIALES TELEGRAM (Opcionales)
# ==========================================
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN",  "").strip()
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID",    "").strip()

TELEGRAM_RESULTS_BOT_TOKEN = os.getenv("TELEGRAM_RESULTS_BOT_TOKEN", TELEGRAM_BOT_TOKEN).strip()
TELEGRAM_RESULTS_CHAT_ID   = os.getenv("TELEGRAM_RESULTS_CHAT_ID",   TELEGRAM_CHAT_ID).strip()

# ==========================================
# IA — claves opcionales (el bot funciona sin ellas)
# ==========================================
GROQ_API_KEY  = os.getenv("GROQ_API_KEY",  "")
GROQ_MODEL    = os.getenv("GROQ_MODEL",    "groq/compound-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL  = os.getenv("GEMINI_MODEL",  "gemini-1.5-flash")

# ==========================================
# MESAS MONITOREADAS
# ==========================================
TARGET_TABLES = [
    "Baccarat 1",
    "Baccarat 2",
    "Baccarat 3",
    "Baccarat 5",
]

# ==========================================
# SEÑALES Y ANÁLISIS
# ==========================================
MIN_SIGNAL_DELAY        = _get_int("MIN_SIGNAL_DELAY", 2)
MAX_SIGNAL_DELAY        = _get_int("MAX_SIGNAL_DELAY", 6)
MAX_ATTEMPTS            = 6
CDP_URL                 = os.getenv("CDP_URL", "http://localhost:9222")
ACTIVE_STRATEGY         = os.getenv("ACTIVE_STRATEGY", "IA_LIBRE_MULTI_ROAD")
MIN_STREAK_LENGTH       = _get_int("MIN_STREAK_LENGTH", 1)
MIN_CONFIDENCE_THRESHOLD = _get_int("MIN_CONFIDENCE_THRESHOLD", 88)
STARTUP_DELAY           = _get_int("STARTUP_DELAY", 60)   # 60s para calibrar pantalla
CAPTION_STYLE           = os.getenv("CAPTION_STYLE", "CLEAN")

# ==========================================
# AUTO-BETTOR — ESTRATEGIA PREDETERMINADA
# Ventana Rotante (1-2-3 / 2-3-4) + Recuperación Plana $0.40 tras 5 tiros perdidos
# Stop-Loss: -40.0 USDT / Stop-Profit: +50.0 USDT
# ==========================================
AUTO_BET_ENABLED            = os.getenv("AUTO_BET_ENABLED", "true").lower() in ("true", "1", "yes")
AUTO_BET_BASE_BET           = _get_float("AUTO_BET_BASE_BET",  _get_float("BASE_BET", 0.20))
AUTO_BET_BASE_CHIP          = _get_float("AUTO_BET_BASE_CHIP", 0.20)
AUTO_BET_BASE_CLICKS        = _get_int("AUTO_BET_BASE_CLICKS", 1)
AUTO_BET_PERSISTENT_MARTINGALE = True
AUTO_BET_STOP_LOSS          = _get_float("AUTO_BET_STOP_LOSS",  _get_float("STOP_LOSS", -40.0))
AUTO_BET_TAKE_PROFIT        = _get_float("AUTO_BET_TAKE_PROFIT", _get_float("TAKE_PROFIT", 50.0))
AUTO_BET_MAX_STEPS          = _get_int("AUTO_BET_MAX_STEPS", 10)

CONSECUTIVE_LOSS_LIMIT      = _get_int("CONSECUTIVE_LOSS_LIMIT", 5)

# Modo de juego activo (1 = Predeterminado con Recuperación a 5 pérdidas)
GAME_MODE                   = _get_int("GAME_MODE", 1)
