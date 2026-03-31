"""Costanti per HomeMind AI."""

DOMAIN = "homemind_ai"
VERSION = "3.0.0"

# ---- Dominio integrazione HA Gemini ----
HA_GEMINI_DOMAIN = "google_generative_ai_conversation"

# ---- Configurazione ----
CONF_AI_PROVIDER = "ai_provider"
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_GEMINI_MODEL = "gemini_model"
CONF_OLLAMA_HOST = "ollama_host"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"
CONF_CAMERAS = "cameras"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_MORNING_REPORT_HOUR = "morning_report_hour"

# ---- Provider AI ----
AI_PROVIDER_GEMINI = "gemini"           # Chiamate REST dirette all'API Gemini
AI_PROVIDER_HA_GEMINI = "ha_gemini"     # Usa l'integrazione HA Google Generative AI (consigliato)
AI_PROVIDER_OLLAMA = "ollama"           # Ollama locale
AI_PROVIDERS = [AI_PROVIDER_HA_GEMINI, AI_PROVIDER_GEMINI, AI_PROVIDER_OLLAMA]
DEFAULT_AI_PROVIDER = AI_PROVIDER_HA_GEMINI  # Default: usa integrazione HA se presente

# ---- Modelli Gemini ----
GEMINI_MODELS = [
    "gemini-2.0-flash",        # Raccomandato — stabile, gratuito
    "gemini-2.0-flash-lite",   # Più leggero, gratuito
    "gemini-1.5-flash",        # Generazione precedente
    "gemini-1.5-flash-8b",     # Versione lite 1.5
    "gemini-1.5-pro",          # Generazione precedente — pro
]
# Fallback su modelli gratuiti in ordine di preferenza
GEMINI_FALLBACK_ORDER = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# ---- Ollama ----
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llava"

# ---- ALPR (riconoscimento targhe) ----
CONF_ALPR_ENTITIES = "alpr_entities"
CONF_VEHICLE_SENSORS = "vehicle_sensors"

# Entità ping HA per check connessione internet
PING_ENTITY = "binary_sensor.8_8_8_8"

# ---- Default ----
DEFAULT_NIGHT_START = 22
DEFAULT_NIGHT_END = 6
DEFAULT_MORNING_REPORT_HOUR = 7

# ---- Sensori stato ----
SENSOR_AI_STATUS = "ai_status"
SENSOR_NIGHT_MODE = "night_mode"
SENSOR_ALERTS_TONIGHT = "alerts_tonight"
SENSOR_LAST_ALERT = "last_alert"
SENSOR_LAST_REPORT = "last_report"
SENSOR_LAST_AI_ANSWER = "last_ai_answer"

# ---- Sensori debug ----
SENSOR_API_HEALTH = "api_health"
SENSOR_LAST_ERROR = "last_error"
SENSOR_CAMERAS_ONLINE = "cameras_online"
SENSOR_BOT_STATUS = "bot_status"
SENSOR_INTERNET_STATUS = "internet_status"

# ---- Sensori ALPR ----
SENSOR_LAST_PLATE = "last_plate"
SENSOR_PLATES_TODAY = "plates_today"

# ---- Servizi ----
SERVICE_ANALYZE_CAMERA = "analyze_camera"
SERVICE_GENERATE_REPORT = "generate_report"
SERVICE_CLEAR_ALERTS = "clear_alerts"
SERVICE_ASK_AI = "ask_ai"

# ---- Threat levels ----
THREAT_NONE = "none"
THREAT_LOW = "low"
THREAT_MEDIUM = "medium"
THREAT_HIGH = "high"
