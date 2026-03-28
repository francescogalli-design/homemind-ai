"""Constants for HomeMind AI integration."""

DOMAIN = "homemind_ai"

# --- Config keys ---
CONF_OLLAMA_URL = "ollama_url"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"
CONF_CAMERAS = "cameras"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_REPORT_TIME = "report_time"

# --- Defaults ---
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llava"
DEFAULT_NIGHT_START = "22:00:00"
DEFAULT_NIGHT_END = "06:00:00"
DEFAULT_REPORT_TIME = "07:00:00"

# --- HA Events ---
EVENT_HOMEMIND_ALERT = f"{DOMAIN}_alert"
EVENT_HOMEMIND_REPORT = f"{DOMAIN}_report"

# --- Services ---
SERVICE_GENERATE_REPORT = "generate_report"
SERVICE_ANALYZE_CAMERA = "analyze_camera"
SERVICE_CLEAR_ALERTS = "clear_alerts"
