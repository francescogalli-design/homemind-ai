"""
FastAPI Routes - Web API for HomeMind AI Assistant.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from core.config import get_settings
from integrations.homeassistant.client import HomeAssistantClient
from core.ai_engine import AIEngine
from core.memory_system import MemorySystem

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (will be set by main app)
ha_client: HomeAssistantClient = None
ai_engine: AIEngine = None
memory_system: MemorySystem = None


def get_dependencies():
    """Dependency injection for global instances."""
    return {
        "ha_client": ha_client,
        "ai_engine": ai_engine,
        "memory_system": memory_system
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "HomeMind AI Assistant API",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        components = {
            "ha_client": ha_client is not None and ha_client.is_connected if ha_client else False,
            "ai_engine": ai_engine is not None and len(ai_engine.providers) > 0 if ai_engine else False,
            "memory_system": memory_system is not None if memory_system else False
        }
        
        overall_healthy = all(components.values())
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "components": components
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/status")
async def get_system_status():
    """Get comprehensive system status."""
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "home_assistant": {},
            "ai_providers": {},
            "memory_stats": {},
            "system_info": {}
        }
        
        # Home Assistant status
        if ha_client and ha_client.is_connected:
            status["home_assistant"] = {
                "connected": True,
                "last_update": ha_client.last_update.isoformat() if ha_client.last_update else None,
                "cached_entities": len(ha_client.states)
            }
            
            # Get home status
            home_status = await ha_client.get_home_status()
            status["home_assistant"]["home_status"] = home_status
        else:
            status["home_assistant"] = {"connected": False}
        
        # AI Providers status
        if ai_engine:
            for name, provider in ai_engine.providers.items():
                health = await provider.health_check()
                status["ai_providers"][name] = health
        
        # Memory system stats
        if memory_system:
            # Get basic stats (would need to implement this method)
            status["memory_stats"] = {
                "initialized": True,
                "type": "chromadb+sqlite"
            }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat_endpoint(request: Dict[str, Any]):
    """Chat endpoint for AI interactions."""
    try:
        message = request.get("message")
        user_id = request.get("user_id", "default")
        context = request.get("context")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")
        
        # Process message
        result = await ai_engine.process_message(message, user_id, context)
        
        return {
            "success": True,
            "response": result.get("response"),
            "provider": result.get("provider"),
            "actions": result.get("actions", []),
            "context_used": result.get("context_used"),
            "memories_used": result.get("memories_used"),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/home/status")
async def get_home_status():
    """Get Home Assistant status."""
    try:
        if not ha_client or not ha_client.is_connected:
            raise HTTPException(status_code=503, detail="Home Assistant not connected")
        
        status = await ha_client.get_home_status()
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting home status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/home/entities")
async def get_entities(entity_type: Optional[str] = None):
    """Get Home Assistant entities."""
    try:
        if not ha_client or not ha_client.is_connected:
            raise HTTPException(status_code=503, detail="Home Assistant not connected")
        
        states = await ha_client.get_states()
        
        if entity_type:
            # Filter by entity type
            filtered_states = {
                entity_id: state for entity_id, state in states.items()
                if entity_id.startswith(entity_type + ".")
            }
            states = filtered_states
        
        return {
            "success": True,
            "data": states,
            "count": len(states),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/home/call_service")
async def call_service(request: Dict[str, Any]):
    """Call Home Assistant service."""
    try:
        domain = request.get("domain")
        service = request.get("service")
        service_data = request.get("data", {})
        
        if not domain or not service:
            raise HTTPException(status_code=400, detail="Domain and service are required")
        
        if not ha_client or not ha_client.is_connected:
            raise HTTPException(status_code=503, detail="Home Assistant not connected")
        
        result = await ha_client.call_service(domain, service, service_data)
        
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calling service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/energy/status")
async def get_energy_status():
    """Get energy consumption and production status."""
    try:
        if not ha_client or not ha_client.is_connected:
            raise HTTPException(status_code=503, detail="Home Assistant not connected")
        
        energy_data = await ha_client.get_energy_data()
        
        return {
            "success": True,
            "data": energy_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting energy status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/status")
async def get_security_status():
    """Get security system status."""
    try:
        if not ha_client or not ha_client.is_connected:
            raise HTTPException(status_code=503, detail="Home Assistant not connected")
        
        security_data = await ha_client.get_security_status()
        
        return {
            "success": True,
            "data": security_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting security status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/search")
async def search_memories(query: str, user_id: Optional[str] = None, limit: int = 10):
    """Search memories."""
    try:
        if not memory_system:
            raise HTTPException(status_code=503, detail="Memory system not available")
        
        memories = await memory_system.search_memories(query, user_id, limit)
        
        return {
            "success": True,
            "data": memories,
            "count": len(memories),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/stats/{user_id}")
async def get_memory_stats(user_id: str, days: int = 30):
    """Get memory statistics for a user."""
    try:
        if not memory_system:
            raise HTTPException(status_code=503, detail="Memory system not available")
        
        stats = await memory_system.get_interaction_stats(user_id, days)
        
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proactive/suggestions")
async def get_proactive_suggestions():
    """Get proactive suggestions based on current context."""
    try:
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")
        
        # Get current context (would need to implement this)
        context = {}
        
        suggestions = await ai_engine.get_proactive_suggestions(context)
        
        return {
            "success": True,
            "data": suggestions,
            "count": len(suggestions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting proactive suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """Get current configuration (without sensitive data)."""
    try:
        settings = get_settings()
        
        # Return safe config only
        safe_config = {
            "app_name": settings.app_name,
            "version": settings.version,
            "ai_provider_order": settings.ai_provider_order,
            "telegram_language": settings.telegram_language,
            "memory_retention_days": settings.memory_retention_days,
            "proactive_notifications_enabled": settings.proactive_notifications_enabled,
            "proactive_sensitivity": settings.proactive_sensitivity,
            "energy_monitoring_enabled": settings.energy_monitoring_enabled,
            "behavior_analysis_enabled": settings.behavior_analysis_enabled,
            "routine_detection_enabled": settings.routine_detection_enabled
        }
        
        return {
            "success": True,
            "data": safe_config,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
