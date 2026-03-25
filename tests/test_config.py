"""
Configuration tests for HomeMind AI Assistant.
"""

import pytest
import os
from unittest.mock import patch
from src.core.config import Settings, get_settings, get_active_ai_providers, validate_settings


class TestSettings:
    """Test Settings class."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.app_name == "HomeMind AI Assistant"
        assert settings.version == "2.0.0"
        assert settings.debug is False
        assert settings.telegram_language == "it"
        assert settings.memory_retention_days == 365
    
    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        with patch.dict(os.environ, {
            'HOMEMIND_DEBUG': 'true',
            'HA_URL': 'http://test.local:8123',
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'GEMINI_API_KEY': 'test_gemini_key'
        }):
            settings = Settings()
            
            assert settings.debug is True
            assert settings.ha_url == 'http://test.local:8123'
            assert settings.telegram_bot_token == 'test_token'
            assert settings.gemini_api_key == 'test_gemini_key'
    
    def test_get_active_ai_providers(self):
        """Test getting active AI providers."""
        settings = Settings()
        settings.gemini_api_key = "test_gemini"
        settings.groq_api_key = "test_groq"
        settings.openai_api_key = ""  # Empty, should not be included
        
        providers = get_active_ai_providers(settings)
        
        assert "gemini" in providers
        assert "groq" in providers
        assert "openai" not in providers
    
    def test_validate_settings_success(self):
        """Test successful settings validation."""
        settings = Settings()
        settings.ha_url = "http://test.local:8123"
        settings.ha_token = "test_token"
        settings.gemini_api_key = "test_gemini"
        settings.telegram_bot_token = "test_token"
        settings.telegram_chat_id = "test_chat_id"
        
        issues = validate_settings(settings)
        
        assert len(issues) == 0
    
    def test_validate_settings_missing_required(self):
        """Test settings validation with missing required fields."""
        settings = Settings()
        settings.ha_url = ""
        settings.ha_token = ""
        settings.gemini_api_key = ""
        
        issues = validate_settings(settings)
        
        assert len(issues) >= 2
        assert any("HA_URL" in issue for issue in issues)
        assert any("HA_TOKEN" in issue for issue in issues)
    
    def test_validate_settings_telegram_incomplete(self):
        """Test settings validation with incomplete Telegram setup."""
        settings = Settings()
        settings.ha_url = "http://test.local:8123"
        settings.ha_token = "test_token"
        settings.gemini_api_key = "test_gemini"
        settings.telegram_bot_token = "test_token"
        settings.telegram_chat_id = ""  # Missing
        
        issues = validate_settings(settings)
        
        assert any("TELEGRAM_CHAT_ID" in issue for issue in issues)


class TestGetSettings:
    """Test get_settings function."""
    
    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
