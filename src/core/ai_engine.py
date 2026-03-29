"""
AI Engine - Multi-provider AI with intelligent routing and proactive capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from .config import get_settings, get_active_ai_providers
from .memory_system import MemorySystem
from .context_manager import ContextManager
from integrations.ai.providers import (
    GeminiProvider, GroqProvider, CerebrasProvider,
    DeepSeekProvider, ClaudeProvider, OpenAIProvider
)

logger = logging.getLogger(__name__)


class AIEngine:
    """Multi-provider AI engine with intelligent routing."""
    
    def __init__(self, settings, memory_system: MemorySystem, context_manager: ContextManager):
        self.settings = settings
        self.memory_system = memory_system
        self.context_manager = context_manager
        self.providers = {}
        self.current_provider_index = 0
        
    async def initialize(self):
        """Initialize AI providers."""
        active_providers = get_active_ai_providers(self.settings)
        
        provider_classes = {
            "gemini": GeminiProvider,
            "groq": GroqProvider,
            "cerebras": CerebrasProvider,
            "deepseek": DeepSeekProvider,
            "claude": ClaudeProvider,
            "openai": OpenAIProvider
        }
        
        for provider_name in active_providers:
            try:
                provider_class = provider_classes[provider_name]
                provider = provider_class(self.settings)
                await provider.initialize()
                self.providers[provider_name] = provider
                logger.info(f"✅ Initialized AI provider: {provider_name}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {provider_name}: {e}")
        
        if not self.providers:
            raise ValueError("No AI providers could be initialized")
    
    async def process_message(self, message: str, user_id: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Process a user message with context awareness."""
        try:
            # Get current context
            current_context = context or await self.context_manager.get_current_context()
            
            # Retrieve relevant memories
            relevant_memories = await self.memory_system.search_memories(message, limit=5)
            
            # Determine message type and route to appropriate provider
            message_type = await self._classify_message(message)
            provider = await self._get_best_provider(message_type)
            
            # Build prompt with context and memories
            prompt = await self._build_prompt(message, current_context, relevant_memories)
            
            # Get AI response
            response = await provider.generate_response(prompt)
            
            # Store interaction in memory
            await self.memory_system.store_interaction(
                user_id=user_id,
                message=message,
                response=response,
                context=current_context
            )
            
            # Execute any actions if needed
            actions = await self._extract_and_execute_actions(response, user_id)
            
            return {
                "response": response,
                "actions": actions,
                "provider": provider.name,
                "context_used": current_context,
                "memories_used": len(relevant_memories)
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "response": "Mi dispiace, ho riscontrato un errore. Riprova più tardi.",
                "error": str(e)
            }
    
    async def get_proactive_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate proactive suggestions based on current context."""
        suggestions = []
        
        if not self.settings.proactive_notifications_enabled:
            return suggestions
        
        try:
            # Analyze context for proactive opportunities
            opportunities = await self._analyze_proactive_opportunities(context)
            
            for opportunity in opportunities:
                if opportunity.get("confidence", 0) > self.settings.proactive_sensitivity:
                    suggestion = await self._generate_proactive_suggestion(opportunity)
                    suggestions.append(suggestion)
            
            # Limit suggestions per hour
            suggestions = suggestions[:self.settings.max_proactive_notifications_per_hour]
            
        except Exception as e:
            logger.error(f"Error generating proactive suggestions: {e}")
        
        return suggestions
    
    async def _classify_message(self, message: str) -> str:
        """Classify message type for provider routing."""
        message_lower = message.lower()
        
        # Command patterns
        if any(word in message_lower for word in ["accendi", "spegni", "apri", "chiudi", "imposta"]):
            return "command"
        
        # Question patterns
        if any(word in message_lower for word in ["quanto", "quale", "come", "dove", "quando"]):
            return "question"
        
        # Information patterns
        if any(word in message_lower for word in ["stato", "informazioni", "dettagli"]):
            return "information"
        
        # Configuration patterns
        if any(word in message_lower for word in ["configura", "imposta", "modifica", "aggiungi"]):
            return "configuration"
        
        # Default
        return "general"
    
    async def _get_best_provider(self, message_type: str):
        """Get the best provider for the message type."""
        # Provider specializations
        specializations = {
            "command": ["gemini", "claude"],  # Good for structured commands
            "question": ["openai", "claude"],  # Good for reasoning
            "information": ["gemini", "groq"],  # Fast for data retrieval
            "configuration": ["claude", "openai"],  # Good for complex logic
            "general": ["gemini", "groq"]  # Good general purpose
        }
        
        preferred_providers = specializations.get(message_type, ["gemini"])
        
        # Try preferred providers first
        for provider_name in preferred_providers:
            if provider_name in self.providers:
                return self.providers[provider_name]
        
        # Fallback to any available provider
        for provider in self.providers.values():
            return provider
        
        raise RuntimeError("No AI providers available")
    
    async def _build_prompt(self, message: str, context: Dict, memories: List) -> str:
        """Build context-aware prompt."""
        prompt_parts = [
            "Sei un assistente AI avanzato per Home Assistant. Rispondi in italiano.",
            f"Data e ora corrente: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        
        # Add context
        if context:
            prompt_parts.append(f"\nContesto attuale:\n{json.dumps(context, indent=2, ensure_ascii=False)}")
        
        # Add relevant memories
        if memories:
            prompt_parts.append(f"\nInformazioni rilevanti precedenti:")
            for memory in memories:
                prompt_parts.append(f"- {memory}")
        
        # Add user message
        prompt_parts.append(f"\nMessaggio dell'utente: {message}")
        
        # Add instructions
        prompt_parts.append(
            "\nRispondi in modo naturale e utile. Se il messaggio contiene un comando per Home Assistant, "
            "identificalo chiaramente. Se hai bisogno di più informazioni, chiedile all'utente."
        )
        
        return "\n".join(prompt_parts)
    
    async def _extract_and_execute_actions(self, response: str, user_id: str) -> List[Dict]:
        """Extract and execute Home Assistant actions from AI response."""
        actions = []
        
        # This would integrate with Home Assistant client
        # For now, return empty list
        # TODO: Implement action extraction and execution
        
        return actions
    
    async def analyze_camera_for_security(
        self,
        camera_entity: str,
        image_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Usa Gemini Vision per analizzare uno snapshot di camera e rilevare minacce.

        Returns:
            Dict con 'threat_detected', 'threat_level', 'description', 'summary', 'camera'
        """
        gemini = self.providers.get("gemini")
        if not gemini:
            logger.warning("Gemini non disponibile per analisi camera")
            return {"threat_detected": False, "threat_level": "none", "camera": camera_entity}

        camera_name = camera_entity.replace("camera.", "").replace("_", " ").title()
        result = await gemini.analyze_camera_for_security(image_bytes, camera_name)

        # Salva in memoria se è stato rilevato qualcosa
        if result.get("threat_detected"):
            await self.memory_system.store_interaction(
                user_id="system",
                message=f"Rilevata minaccia su {camera_entity}",
                response=result.get("description", ""),
                context={"camera": camera_entity, "threat_level": result.get("threat_level")},
            )

        return result

    async def _analyze_proactive_opportunities(self, context: Dict) -> List[Dict]:
        """Analyze context for proactive opportunities."""
        opportunities = []
        
        # Time-based opportunities
        current_hour = datetime.now().hour
        
        # Morning routine
        if 6 <= current_hour <= 9:
            opportunities.append({
                "type": "morning_briefing",
                "confidence": 0.8,
                "data": context
            })
        
        # Energy optimization
        if context.get("energy", {}).get("solar_production", 0) > 0:
            opportunities.append({
                "type": "energy_optimization",
                "confidence": 0.7,
                "data": context
            })
        
        # Security
        if context.get("security", {}).get("all_away", False):
            opportunities.append({
                "type": "security_check",
                "confidence": 0.9,
                "data": context
            })
        
        return opportunities
    
    async def _generate_proactive_suggestion(self, opportunity: Dict) -> Dict:
        """Generate a proactive suggestion."""
        suggestion_templates = {
            "morning_briefing": {
                "title": "☀️ Buongiorno!",
                "message": "Ecco il tuo briefing mattutino. Vuoi sentire le previsioni del tempo e lo stato della casa?",
                "priority": "medium",
                "actions": ["weather", "home_status"]
            },
            "energy_optimization": {
                "title": "⚡ Ottimizzazione energia",
                "message": "Stai producendo energia solare. Vuoi avviare elettrodomestici ad alto consumo?",
                "priority": "high",
                "actions": ["start_appliances"]
            },
            "security_check": {
                "title": "🔒 Sicurezza",
                "message": "Tutti sono fuori di casa. Vuoi che armi l'allarme e verifichi le porte?",
                "priority": "high",
                "actions": ["arm_alarm", "check_doors"]
            }
        }
        
        template = suggestion_templates.get(opportunity["type"], {
            "title": "💡 Suggerimento",
            "message": "Ho notato qualcosa che potrebbe interessarti.",
            "priority": "low",
            "actions": []
        })
        
        return {
            **template,
            "confidence": opportunity["confidence"],
            "timestamp": datetime.now().isoformat()
        }
