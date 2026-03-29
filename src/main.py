#!/usr/bin/env python3
"""
HomeMind AI Assistant - Main Application
Advanced AI-powered Home Assistant integration with proactive capabilities.
"""

import asyncio
import logging
import sys
from datetime import datetime
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

    # Camera security monitoring con Gemini Vision
    asyncio.create_task(camera_security_monitor())
    logger.info("📹 Camera security monitoring avviato")


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


async def camera_security_monitor():
    """
    Loop di monitoraggio sicurezza camere con Gemini Vision.

    - Durante la finestra notturna (night_start → night_end): analizza ogni N minuti
    - Triggered da sensori di movimento: analisi immediata
    - Invia alert Telegram se Gemini rileva minacce (livello MEDIO o ALTO)
    - Genera report mattutino con riepilogo della notte
    """
    global settings, ha_client, ai_engine, telegram_bot

    # Tracciamento per evitare alert duplicati
    last_alert_times: dict = {}
    alert_cooldown_seconds = 300  # 5 minuti tra un alert e l'altro per la stessa camera
    night_events: list = []        # Registro eventi notturni per il report mattutino

    logger.info("📹 Camera security monitor avviato")

    while True:
        try:
            now = datetime.now()
            current_hour = now.hour

            # Determina se siamo in finestra notturna
            night_start = getattr(settings, "night_monitoring_start", 22)
            night_end = getattr(settings, "night_monitoring_end", 6)
            morning_report_hour = getattr(settings, "morning_report_hour", 7)

            in_night_window = (
                current_hour >= night_start or current_hour < night_end
            )

            # --- Report mattutino ---
            if current_hour == morning_report_hour and night_events:
                await _send_morning_report(night_events, telegram_bot)
                night_events.clear()

            # --- Recupera camere e sensori di movimento ---
            cameras = await ha_client.get_camera_entities()
            if not cameras:
                await asyncio.sleep(60)
                continue

            states = await ha_client.get_states()
            motion_sensors = {
                eid: s for eid, s in states.items()
                if "motion" in eid.lower() or "movimento" in eid.lower()
            }

            # Determina quali camere analizzare
            cameras_to_analyze = []

            for cam in cameras:
                cam_id = cam["entity_id"]
                cam_slug = cam_id.replace("camera.", "")

                # Controlla se c'è un sensore di movimento abbinato
                motion_triggered = any(
                    cam_slug in mid and s.get("state") == "on"
                    for mid, s in motion_sensors.items()
                )

                if motion_triggered:
                    cameras_to_analyze.append((cam_id, "motion"))
                elif in_night_window:
                    cameras_to_analyze.append((cam_id, "scheduled"))

            # --- Analizza le camere selezionate ---
            for camera_entity, trigger in cameras_to_analyze:
                # Cooldown: evita alert ripetuti
                last_alert = last_alert_times.get(camera_entity, 0)
                seconds_since_last = (now - datetime.fromtimestamp(last_alert)).total_seconds() if last_alert else 9999
                if seconds_since_last < alert_cooldown_seconds:
                    continue

                # Snapshot
                image_bytes = await ha_client.get_camera_snapshot(camera_entity)
                if not image_bytes:
                    continue

                # Analisi Gemini Vision
                analysis = await ai_engine.analyze_camera_for_security(camera_entity, image_bytes)

                threat_level = analysis.get("threat_level", "none")
                logger.info(
                    f"📹 {camera_entity} [{trigger}] → rischio={threat_level} | "
                    f"{analysis.get('summary', '')[:80]}"
                )

                # Aggiungi al registro notturno
                night_events.append({
                    "time": now.strftime("%H:%M"),
                    "camera": camera_entity,
                    "trigger": trigger,
                    "threat_level": threat_level,
                    "summary": analysis.get("summary", ""),
                })

                # Invia alert se minaccia rilevata (medio o alto)
                if threat_level in ("medium", "high") and telegram_bot:
                    await telegram_bot.send_security_alert(camera_entity, analysis, image_bytes)
                    last_alert_times[camera_entity] = now.timestamp()

            # Sleep: ogni 2 minuti di notte, ogni 5 di giorno
            sleep_seconds = 120 if in_night_window else 300
            await asyncio.sleep(sleep_seconds)

        except Exception as e:
            logger.error(f"Errore camera_security_monitor: {e}")
            await asyncio.sleep(60)


async def _send_morning_report(events: list, telegram_bot):
    """Invia il report mattutino riepilogativo della notte."""
    if not telegram_bot or not events:
        return

    try:
        total = len(events)
        threats = [e for e in events if e["threat_level"] in ("medium", "high")]
        motion_events = [e for e in events if e["trigger"] == "motion"]

        lines = [
            f"🌅 *Report Notturno HomeMind AI*",
            f"_{datetime.now().strftime('%d/%m/%Y')}_\n",
            f"📊 *Riepilogo:*",
            f"• Analisi totali: {total}",
            f"• Movimenti rilevati: {len(motion_events)}",
            f"• Allerte sicurezza: {len(threats)}\n",
        ]

        if threats:
            lines.append("🚨 *Eventi degni di nota:*")
            for e in threats[:5]:  # Max 5 eventi
                emoji = "🔴" if e["threat_level"] == "high" else "🟠"
                cam_name = e["camera"].replace("camera.", "").replace("_", " ").title()
                lines.append(f"{emoji} {e['time']} — {cam_name}: {e['summary']}")
        else:
            lines.append("✅ *Nessun evento sospetto rilevato stanotte.*")

        lines.append(f"\n_Generato da HomeMind AI con Gemini Vision_")

        await telegram_bot.application.bot.send_message(
            chat_id=telegram_bot.settings.telegram_chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
        logger.info(f"📋 Report mattutino inviato ({total} eventi, {len(threats)} allerte)")

    except Exception as e:
        logger.error(f"Errore invio report mattutino: {e}")


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
