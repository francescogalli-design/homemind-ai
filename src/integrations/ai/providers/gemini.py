"""
Google Gemini AI Provider - con supporto Vision per analisi immagini camera.
"""

import base64
import io
import logging
from typing import Dict, Any, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .base import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider con supporto testo e immagini (vision)."""

    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self.model = None
        self.vision_model = None

    async def initialize(self):
        """Inizializza il client Gemini."""
        try:
            if not self.settings.gemini_api_key:
                raise ValueError("Gemini API key non configurata")

            genai.configure(api_key=self.settings.gemini_api_key)

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }

            generation_config = {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,
            }

            # Modello testo principale
            self.model = genai.GenerativeModel(
                model_name=self.settings.gemini_model,
                safety_settings=safety_settings,
                generation_config=generation_config,
            )

            # Modello vision (gemini-2.0-flash supporta vision nativamente)
            vision_model_name = getattr(
                self.settings, "gemini_vision_model", self.settings.gemini_model
            )
            self.vision_model = genai.GenerativeModel(
                model_name=vision_model_name,
                safety_settings=safety_settings,
                generation_config={**generation_config, "temperature": 0.4},
            )

            self.is_initialized = True
            logger.info(
                f"✅ Gemini provider inizializzato: testo={self.settings.gemini_model}, "
                f"vision={vision_model_name}"
            )

        except Exception as e:
            logger.error(f"❌ Errore inizializzazione Gemini: {e}")
            raise

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Genera una risposta testuale con Gemini."""
        try:
            if not self.is_initialized:
                await self.initialize()

            response = await self.model.generate_content_async(prompt)

            if response.text:
                return response.text.strip()
            else:
                logger.warning("Gemini ha restituito una risposta vuota")
                return "Mi dispiace, non ho potuto generare una risposta."

        except Exception as e:
            logger.error(f"Errore risposta Gemini: {e}")
            raise

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
    ) -> str:
        """
        Analizza un'immagine con Gemini Vision.

        Args:
            image_bytes: Immagine raw in bytes (JPEG, PNG, ecc.)
            prompt: Domanda/istruzione da applicare all'immagine
            mime_type: Tipo MIME dell'immagine (default: image/jpeg)

        Returns:
            Descrizione testuale dell'immagine generata da Gemini
        """
        try:
            if not self.is_initialized:
                await self.initialize()

            # Encode immagine in base64
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # Contenuto multimodale: [immagine, testo]
            content = [
                {"mime_type": mime_type, "data": image_b64},
                prompt,
            ]

            response = await self.vision_model.generate_content_async(content)

            if response.text:
                return response.text.strip()
            else:
                return "Nessuna descrizione disponibile per questa immagine."

        except Exception as e:
            logger.error(f"Errore analisi immagine Gemini Vision: {e}")
            raise

    async def analyze_camera_for_security(
        self,
        image_bytes: bytes,
        camera_name: str = "camera",
    ) -> Dict[str, Any]:
        """
        Analizza uno snapshot di camera per sicurezza domestica.

        Returns dict con:
          - description: descrizione completa della scena
          - threat_detected: True se rileva persone/attività sospette
          - threat_level: 'none' | 'low' | 'medium' | 'high'
          - summary: breve riepilogo (1 frase)
        """
        prompt = (
            f"Analizza questa immagine della telecamera '{camera_name}' "
            "per la sicurezza domestica. Rispondi SOLO in italiano.\n\n"
            "Descrivi:\n"
            "1. Cosa vedi nell'immagine (persone, oggetti, animali, veicoli)\n"
            "2. C'è qualcosa di insolito o sospetto?\n"
            "3. Il livello di rischio è: NESSUNO, BASSO, MEDIO o ALTO?\n\n"
            "Formato risposta:\n"
            "DESCRIZIONE: [descrizione dettagliata]\n"
            "INSOLITO: [sì/no - cosa]\n"
            "RISCHIO: [NESSUNO/BASSO/MEDIO/ALTO]\n"
            "RIEPILOGO: [una frase breve]"
        )

        try:
            raw_response = await self.analyze_image(image_bytes, prompt)

            # Parse risposta strutturata
            lines = raw_response.strip().split("\n")
            result = {
                "description": "",
                "unusual": "",
                "threat_level": "none",
                "threat_detected": False,
                "summary": "",
                "raw_response": raw_response,
                "camera": camera_name,
            }

            for line in lines:
                if line.startswith("DESCRIZIONE:"):
                    result["description"] = line.replace("DESCRIZIONE:", "").strip()
                elif line.startswith("INSOLITO:"):
                    result["unusual"] = line.replace("INSOLITO:", "").strip()
                elif line.startswith("RISCHIO:"):
                    level_str = line.replace("RISCHIO:", "").strip().upper()
                    if "ALTO" in level_str:
                        result["threat_level"] = "high"
                        result["threat_detected"] = True
                    elif "MEDIO" in level_str:
                        result["threat_level"] = "medium"
                        result["threat_detected"] = True
                    elif "BASSO" in level_str:
                        result["threat_level"] = "low"
                    else:
                        result["threat_level"] = "none"
                elif line.startswith("RIEPILOGO:"):
                    result["summary"] = line.replace("RIEPILOGO:", "").strip()

            # Fallback se il parsing non funziona
            if not result["description"]:
                result["description"] = raw_response
                result["summary"] = raw_response[:200]

            return result

        except Exception as e:
            logger.error(f"Errore analisi sicurezza camera: {e}")
            return {
                "description": "Errore nell'analisi dell'immagine.",
                "threat_detected": False,
                "threat_level": "none",
                "summary": "Errore analisi",
                "camera": camera_name,
                "error": str(e),
            }

    async def is_available(self) -> bool:
        """Verifica disponibilità Gemini."""
        try:
            if not self.settings.gemini_api_key:
                return False
            if not self.model:
                return False
            test_response = await self.model.generate_content_async("Test")
            return bool(test_response.text)
        except Exception as e:
            logger.warning(f"Controllo disponibilità Gemini fallito: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Informazioni sul modello Gemini."""
        info = super().get_model_info()
        info.update(
            {
                "api_endpoint": "generativelanguage.googleapis.com",
                "supports_streaming": True,
                "supports_vision": True,
                "max_tokens": 8192,
                "vision_model": getattr(
                    self.settings, "gemini_vision_model", self.settings.gemini_model
                ),
            }
        )
        return info
