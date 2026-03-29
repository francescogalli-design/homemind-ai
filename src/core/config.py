"""
Configuration management for HomeMind AI Assistant.
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "HomeMind AI Assistant"
    version: str = "2.0.0"
    debug: bool = Field(default=False, env="HOMEMIND_DEBUG")
    
    # Home Assistant
    ha_url: str = Field(..., env="HA_URL")
    ha_token: str = Field(..., env="HA_TOKEN")
    ha_websocket_url: Optional[str] = None
    
    # AI Providers
    gemini_api_key: Optional[str] = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = "gemini-2.0-flash"
    gemini_vision_model: str = "gemini-2.0-flash"  # Stesso modello supporta vision
    
    groq_api_key: Optional[str] = Field(default="", env="GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"
    
    cerebras_api_key: Optional[str] = Field(default="", env="CEREBRAS_API_KEY")
    cerebras_model: str = "llama3.1-8b"
    
    deepseek_api_key: Optional[str] = Field(default="", env="DEEPSEEK_API_KEY")
    deepseek_model: str = "deepseek-chat"
    
    claude_api_key: Optional[str] = Field(default="", env="CLAUDE_API_KEY")
    claude_model: str = "claude-3-5-haiku-20241022"
    
    openai_api_key: Optional[str] = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini"
    
    # AI Provider priority order
    ai_provider_order: List[str] = Field(
        default=["gemini", "groq", "cerebras", "deepseek", "claude", "openai"],
        env="AI_PROVIDER_ORDER"
    )
    
    # Telegram
    telegram_bot_token: Optional[str] = Field(default="", env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default="", env="TELEGRAM_CHAT_ID")
    telegram_language: str = "it"
    
    # Memory System
    memory_db_path: str = Field(default="./data/memory.db", env="MEMORY_DB_PATH")
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    memory_retention_days: int = 365
    
    # Analytics
    energy_monitoring_enabled: bool = True
    behavior_analysis_enabled: bool = True
    routine_detection_enabled: bool = True
    
    # Proactive Features
    proactive_notifications_enabled: bool = True
    proactive_sensitivity: float = Field(default=0.7, ge=0.0, le=1.0)
    max_proactive_notifications_per_hour: int = 5
    
    # Security & Camera Monitoring
    alarm_code: str = "1234"
    trusted_users: List[str] = Field(default_factory=list)
    # Finestra monitoraggio notturno (ore, formato 24h)
    night_monitoring_start: int = Field(default=22, env="NIGHT_START")
    night_monitoring_end: int = Field(default=6, env="NIGHT_END")
    # Ora invio report mattutino
    morning_report_hour: int = Field(default=7, env="MORNING_REPORT_HOUR")
    # Camere da monitorare (opzionale: se vuoto monitora tutte)
    camera_entities: List[str] = Field(default_factory=list, env="CAMERA_ENTITIES")
    
    # Web Interface
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    web_secret_key: str = Field(default="change-me-in-production", env="WEB_SECRET_KEY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = "homemind.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_active_ai_providers(settings: Settings) -> List[str]:
    """Get list of configured AI providers."""
    providers = []
    provider_keys = {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "cerebras": settings.cerebras_api_key,
        "deepseek": settings.deepseek_api_key,
        "claude": settings.claude_api_key,
        "openai": settings.openai_api_key
    }
    
    for provider in settings.ai_provider_order:
        if provider_keys.get(provider):
            providers.append(provider)
    
    return providers


def validate_settings(settings: Settings) -> List[str]:
    """Validate settings and return list of issues."""
    issues = []
    
    # Check required Home Assistant settings
    if not settings.ha_url:
        issues.append("HA_URL is required")
    if not settings.ha_token:
        issues.append("HA_TOKEN is required")
    
    # Check AI providers
    active_providers = get_active_ai_providers(settings)
    if not active_providers:
        issues.append("At least one AI provider must be configured")
    
    # Check Telegram settings
    if settings.telegram_bot_token and not settings.telegram_chat_id:
        issues.append("TELEGRAM_CHAT_ID is required when TELEGRAM_BOT_TOKEN is set")
    
    # Check directories
    os.makedirs(os.path.dirname(settings.memory_db_path), exist_ok=True)
    
    return issues
