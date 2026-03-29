"""Costanti per HomeMind AI."""

DOMAIN = "homemind_ai"
VERSION = "1.4.3"

# Configurazione
CONF_GEMINI_API_KEY = "gemini_api_key"
CONF_GEMINI_MODEL = "gemini_model"
CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"
CONF_CAMERAS = "cameras"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_MORNING_REPORT_HOUR = "morning_report_hour"

# Default
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_NIGHT_START = 22
DEFAULT_NIGHT_END = 6
DEFAULT_MORNING_REPORT_HOUR = 7

# Sensori
SENSOR_AI_STATUS = "ai_status"
SENSOR_NIGHT_MODE = "night_mode"
SENSOR_ALERTS_TONIGHT = "alerts_tonight"
SENSOR_LAST_ALERT = "last_alert"
SENSOR_LAST_REPORT = "last_report"

# Servizi
SERVICE_ANALYZE_CAMERA = "analyze_camera"
SERVICE_GENERATE_REPORT = "generate_report"
SERVICE_CLEAR_ALERTS = "clear_alerts"

# Threat levels
THREAT_NONE = "none"
THREAT_LOW = "low"
THREAT_MEDIUM = "medium"
THREAT_HIGH = "high"
