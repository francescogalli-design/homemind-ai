"""Costanti per HomeMind AI v4.0 — 100% locale con Ollama, zero costi."""

DOMAIN = "homemind_ai"
VERSION = "4.0.0"

# ── Configurazione ────────────────────────────────────────────────
CONF_OLLAMA_HOST = "ollama_host"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"
CONF_CAMERAS = "cameras"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_PERSON_ENTITY = "person_entity"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_MORNING_REPORT_HOUR = "morning_report_hour"

# ── ALPR (riconoscimento targhe) ─────────────────────────────────
CONF_ALPR_ENTITIES = "alpr_entities"
CONF_VEHICLE_SENSORS = "vehicle_sensors"

# ── Ollama (locale, gratuito) ────────────────────────────────────
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llava"
OLLAMA_MODELS = ["moondream2", "llava-phi3", "llava", "llava:7b", "llava:13b", "bakllava"]

# ── Entità ping HA per check internet ────────────────────────────
PING_ENTITY = "binary_sensor.8_8_8_8"
INTERNET_CHECK_INTERVAL = 120  # secondi tra i check
INTERNET_CHECK_TARGETS = [
    "https://1.1.1.1",
    "https://dns.google",
]

# ── Default orari ────────────────────────────────────────────────
DEFAULT_NIGHT_START = 22
DEFAULT_NIGHT_END = 6
DEFAULT_MORNING_REPORT_HOUR = 7

# ── Sensori stato ────────────────────────────────────────────────
SENSOR_AI_STATUS = "ai_status"
SENSOR_NIGHT_MODE = "night_mode"
SENSOR_ALERTS_TONIGHT = "alerts_tonight"
SENSOR_LAST_ALERT = "last_alert"
SENSOR_LAST_REPORT = "last_report"
SENSOR_LAST_AI_ANSWER = "last_ai_answer"

# ── Sensori debug ────────────────────────────────────────────────
SENSOR_API_HEALTH = "api_health"
SENSOR_LAST_ERROR = "last_error"
SENSOR_CAMERAS_ONLINE = "cameras_online"
SENSOR_BOT_STATUS = "bot_status"
SENSOR_INTERNET_STATUS = "internet_status"

# ── Sensori ALPR ─────────────────────────────────────────────────
SENSOR_LAST_PLATE = "last_plate"
SENSOR_PLATES_TODAY = "plates_today"

# ── Servizi ──────────────────────────────────────────────────────
SERVICE_ANALYZE_CAMERA = "analyze_camera"
SERVICE_GENERATE_REPORT = "generate_report"
SERVICE_CLEAR_ALERTS = "clear_alerts"
SERVICE_ASK_AI = "ask_ai"
SERVICE_VALIDATE_PLATE = "validate_plate"

# ── Threat levels ────────────────────────────────────────────────
THREAT_NONE = "none"
THREAT_LOW = "low"
THREAT_MEDIUM = "medium"
THREAT_HIGH = "high"

# ── Scheduling adattivo (secondi) ────────────────────────────────
INTERVAL_AWAY_NIGHT = 90
INTERVAL_AWAY_DAY = 180
INTERVAL_HOME_NIGHT = 300
INTERVAL_HOME_DAY = 0          # 0 = nessuna analisi automatica

# ── Notifiche intelligenti ───────────────────────────────────────
COOLDOWN_AWAY_NIGHT = 600      # 10 min
COOLDOWN_AWAY_DAY = 900        # 15 min
COOLDOWN_HOME_NIGHT = 900      # 15 min
MAX_NOTIFICATIONS_PER_HOUR = 3
DEDUP_WINDOW = 1800            # 30 min — stesso evento = skip

# ── Legacy (per migrazione) ──────────────────────────────────────
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_GEMINI_MODEL = "gemini_model"
CONF_AI_PROVIDER = "ai_provider"
