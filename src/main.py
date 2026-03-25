#!/usr/bin/env python3
"""
HomeMind AI Assistant - Main Application
Advanced AI-powered Home Assistant integration with proactive capabilities.
"""

import asyncio
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import Settings, get_settings
from core.ai_engine import AIEngine
from core.memory_system import MemorySystem
from core.context_manager import ContextManager
from integrations.homeassistant.client import HomeAssistantClient
from integrations.telegram.bot import TelegramBot
from web.api.routes import router as api_router
from analytics.energy_analyzer import EnergyAnalyzer
from analytics.behavior_predictor import BehaviorPredictor
from analytics.routine_detector import RoutineDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("homemind.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global components
settings: Settings = None
ai_engine: AIEngine = None
memory_system: MemorySystem = None
context_manager: ContextManager = None
ha_client: HomeAssistantClient = None
telegram_bot: TelegramBot = None
energy_analyzer: EnergyAnalyzer = None
behavior_predictor: BehaviorPredictor = None
routine_detector: RoutineDetector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global settings, ai_engine, memory_system, context_manager
    global ha_client, telegram_bot, energy_analyzer, behavior_predictor, routine_detector
    
    logger.info("🚀 Starting HomeMind AI Assistant...")
    
    try:
        # Initialize settings
        settings = get_settings()
        logger.info("✅ Configuration loaded")
        
        # Initialize core components
        memory_system = MemorySystem(settings)
        await memory_system.initialize()
        logger.info("✅ Memory system initialized")
        
        context_manager = ContextManager(memory_system)
        logger.info("✅ Context manager initialized")
        
        ai_engine = AIEngine(settings, memory_system, context_manager)
        await ai_engine.initialize()
        logger.info("✅ AI engine initialized")
        
        # Initialize Home Assistant client
        ha_client = HomeAssistantClient(settings)
        await ha_client.connect()
        logger.info("✅ Home Assistant connected")
        
        # Initialize Telegram bot
        if settings.telegram_bot_token:
            telegram_bot = TelegramBot(settings, ai_engine, ha_client, context_manager)
            await telegram_bot.start()
            logger.info("✅ Telegram bot started")
        
        # Initialize analytics components
        energy_analyzer = EnergyAnalyzer(ha_client, memory_system)
        behavior_predictor = BehaviorPredictor(memory_system, context_manager)
        routine_detector = RoutineDetector(ha_client, memory_system)
        
        # Start background tasks
        asyncio.create_task(start_background_tasks())
        
        logger.info("🎉 HomeMind AI Assistant is ready!")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise
    finally:
        # Cleanup
        logger.info("🔄 Shutting down...")
        
        if telegram_bot:
            await telegram_bot.stop()
        
        if ha_client:
            await ha_client.disconnect()
        
        if memory_system:
            await memory_system.cleanup()
        
        logger.info("✅ Shutdown complete")


async def start_background_tasks():
    """Start background monitoring and analysis tasks."""
    global energy_analyzer, behavior_predictor, routine_detector, telegram_bot
    
    # Energy monitoring
    asyncio.create_task(energy_analyzer.start_monitoring())
    
    # Behavior analysis
    asyncio.create_task(behavior_predictor.start_analysis())
    
    # Routine detection
    asyncio.create_task(routine_detector.start_detection())
    
    # Proactive notifications
    if telegram_bot:
        asyncio.create_task(proactive_notification_loop())


async def proactive_notification_loop():
    """Background loop for proactive notifications."""
    global context_manager, telegram_bot, ai_engine
    
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            
            # Get current context
            context = await context_manager.get_current_context()
            
            # Check for proactive actions
            proactive_suggestions = await ai_engine.get_proactive_suggestions(context)
            
            for suggestion in proactive_suggestions:
                if suggestion.get("priority") == "high":
                    await telegram_bot.send_proactive_notification(suggestion)
                    
        except Exception as e:
            logger.error(f"Error in proactive notification loop: {e}")


# Create FastAPI app
app = FastAPI(
    title="HomeMind AI Assistant",
    description="Advanced AI-powered Home Assistant integration",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Mount static files
if Path("web/frontend/dist").exists():
    app.mount("/", StaticFiles(directory="web/frontend/dist", html=True), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "ai_engine": ai_engine is not None,
            "memory_system": memory_system is not None,
            "ha_client": ha_client is not None and ha_client.is_connected,
            "telegram_bot": telegram_bot is not None
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
