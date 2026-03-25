"""
Base AI Provider - Abstract class for all AI providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, settings):
        self.settings = settings
        self.name = self.__class__.__name__.replace("Provider", "").lower()
        self.is_initialized = False
        
    @abstractmethod
    async def initialize(self):
        """Initialize the AI provider."""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate AI response from prompt."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            available = await self.is_available()
            return {
                "provider": self.name,
                "available": available,
                "initialized": self.is_initialized,
                "error": None if available else "Provider not available"
            }
        except Exception as e:
            return {
                "provider": self.name,
                "available": False,
                "initialized": self.is_initialized,
                "error": str(e)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            "provider": self.name,
            "model": getattr(self.settings, f"{self.name}_model", "unknown"),
            "initialized": self.is_initialized
        }
