"""
Google Gemini AI Provider.
"""

import logging
from typing import Dict, Any
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .base import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider."""
    
    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self.model = None
        
    async def initialize(self):
        """Initialize Gemini client."""
        try:
            if not self.settings.gemini_api_key:
                raise ValueError("Gemini API key not provided")
            
            genai.configure(api_key=self.settings.gemini_api_key)
            
            # Configure safety settings
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            self.model = genai.GenerativeModel(
                model_name=self.settings.gemini_model,
                safety_settings=safety_settings,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
            
            # Test the connection
            await self.is_available()
            
            self.is_initialized = True
            logger.info(f"✅ Gemini provider initialized with model: {self.settings.gemini_model}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini provider: {e}")
            raise
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Gemini."""
        try:
            if not self.is_initialized:
                await self.initialize()
            
            # Generate response
            response = await self.model.generate_content_async(prompt)
            
            if response.text:
                return response.text.strip()
            else:
                logger.warning("Gemini returned empty response")
                return "Mi dispiace, non ho potuto generare una risposta."
                
        except Exception as e:
            logger.error(f"Error generating response with Gemini: {e}")
            raise
    
    async def is_available(self) -> bool:
        """Check if Gemini is available."""
        try:
            if not self.settings.gemini_api_key:
                return False
            
            if not self.model:
                return False
            
            # Test with a simple prompt
            test_response = await self.model.generate_content_async("Test")
            return bool(test_response.text)
            
        except Exception as e:
            logger.warning(f"Gemini availability check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Gemini model information."""
        info = super().get_model_info()
        info.update({
            "api_endpoint": "generativelanguage.googleapis.com",
            "supports_streaming": True,
            "supports_vision": True,
            "max_tokens": 8192
        })
        return info
