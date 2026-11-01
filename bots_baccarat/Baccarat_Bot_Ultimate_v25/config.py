import os
from dotenv import load_dotenv

load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8849297437:AAGyKmSOdDIUOznSdyzBTP1YHptREGyy8T0")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1004395102774")

# Configuración del Canal Exclusivo de Resultados (Solo WIN 1-6 / LOSS)
TELEGRAM_RESULTS_BOT_TOKEN = os.getenv("TELEGRAM_RESULTS_BOT_TOKEN", "8972617801:AAEh1tu8bbGRhHB250QE7vXYz0cGFT7SLoI")
TELEGRAM_RESULTS_CHAT_ID = os.getenv("TELEGRAM_RESULTS_CHAT_ID", "-1003636592278")

# Configuración de Inteligencia Artificial
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/compound-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

TARGET_TABLES = [
    "Baccarat 1",
    "Baccarat 2",
    "Baccarat 3",
    "Baccarat 5",
]
# Coordenadas de cada mesa cargadas desde table_regions.json

MIN_SIGNAL_DELAY = int(os.getenv("MIN_SIGNAL_DELAY", 2))
MAX_SIGNAL_DELAY = int(os.getenv("MAX_SIGNAL_DELAY", 6))
MAX_ATTEMPTS = 6
CDP_URL = os.getenv("CDP_URL", "http://localhost:9222")

# ==========================================
# CONFIGURACIÓN DEL SISTEMA DE ESTRATEGIAS
# ==========================================
# 4 Estrategias Exclusivas del Usuario:
# 1. DISRUPTIVA_4TEND_DISRUPTIVA : [D, T, T, T, T, D] (1 Contra + 4 Tendencia + 1 Contra)
# 2. TENDENCIA_3_DISR_2TEND      : [T, T, T, D, T, T] (3 Tendencia + 1 Disruptiva + 2 Tendencia)
# 3. TENDENCIA_PURA_6            : [T, T, T, T, T, T] (6 a la Tendencia)
# 4. DISRUPTIVA_1_5TEND          : [D, T, T, T, T, T] (1 Disruptiva + 5 Tendencia)
ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "USER_4_STRATEGIES")

# Parámetros para ajuste de estrategias (Cadencia Ágil y Alta Precisión)
MIN_STREAK_LENGTH = int(os.getenv("MIN_STREAK_LENGTH", 1)) # Permite evaluar desde racha 1 para estrategias disruptivas
MIN_CONFIDENCE_THRESHOLD = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", 75)) # Umbral ágil para disparar mesas rápido (máx 40s)

# Tiempo de espera inicial para que el usuario abra la mesa (5 segundos)
STARTUP_DELAY = int(os.getenv("STARTUP_DELAY", 5))

# Estilo de mensaje en Telegram:
# - "CLEAN" : Formato conciso con emojis (🤓 M5 | 1🔵 2🔴 3🔴 4🔴 5🔵 6🔴)
# - "VIP"   : Formato extendido con tarjeta completa
CAPTION_STYLE = os.getenv("CAPTION_STYLE", "CLEAN")

# ==========================================
# CONFIGURACIÓN DEL SISTEMA DE APUESTAS AUTOMÁTICAS
# ==========================================
#
# ╔══════════════════════════════════════════════════════════╗
# ║         DOS MODOS DE JUEGO DISPONIBLES                  ║
# ║                                                          ║
# ║  MODO_40  →  Monto base $0.40 (2 clics por tiro 1)      ║
# ║             Progresión: $0.40→$0.80→$1.60→$3.20→...    ║
# ║             Máximo 12 niveles de Martingala              ║
# ║                                                          ║
# ║  MODO_20  →  Monto base $0.20 (1 clic por tiro 1)       ║
# ║             Progresión: $0.20→$0.40→$0.80→$1.60→...    ║
# ║             Máximo 12 niveles de Martingala              ║
# ║                                                          ║
# ║  El modo se elige al ARRANCAR el bot.                    ║
# ╚══════════════════════════════════════════════════════════╝
#
AUTO_BET_ENABLED              = os.getenv("AUTO_BET_ENABLED", "true").lower() in ("true", "1", "yes")
AUTO_BET_BASE_BET             = float(os.getenv("AUTO_BET_BASE_BET", "0.20"))   # Se sobreescribe al elegir modo
AUTO_BET_BASE_CHIP            = float(os.getenv("AUTO_BET_BASE_CHIP", "0.20"))  # Ficha física de la barra (siempre $0.20)
AUTO_BET_PERSISTENT_MARTINGALE= os.getenv("AUTO_BET_PERSISTENT_MARTINGALE", "true").lower() in ("true", "1", "yes")
AUTO_BET_STOP_LOSS            = None    # Sin Stop-Loss (libre, usuario detiene manualmente)
AUTO_BET_TAKE_PROFIT          = None    # Sin Take-Profit (libre, usuario detiene manualmente)
AUTO_BET_MAX_STEPS            = int(os.getenv("AUTO_BET_MAX_STEPS", "12"))      # 12 niveles de Martingala

# Modos de juego predefinidos (base_bet, base_clics_tiro1, descripcion)
MODO_40 = {"base_bet": 0.40, "initial_clicks": 2, "label": "MODO $0.40  (2 clics — Martingala x12)"}
MODO_20 = {"base_bet": 0.20, "initial_clicks": 1, "label": "MODO $0.20  (1 clic  — Martingala x12)"}



