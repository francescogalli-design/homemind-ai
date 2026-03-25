"""
Telegram Bot Integration - Advanced conversational AI with proactive capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import tempfile
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import filters
import speech_recognition as sr
from pydub import AudioSegment

from core.config import Settings
from core.ai_engine import AIEngine
from integrations.homeassistant.client import HomeAssistantClient
from core.context_manager import ContextManager

logger = logging.getLogger(__name__)


class TelegramBot:
    """Advanced Telegram bot with voice support and proactive notifications."""
    
    def __init__(self, settings: Settings, ai_engine: AIEngine, 
                 ha_client: HomeAssistantClient, context_manager: ContextManager):
        self.settings = settings
        self.ai_engine = ai_engine
        self.ha_client = ha_client
        self.context_manager = context_manager
        self.application = None
        self.user_contexts = {}  # Store per-user conversation context
        
    async def start(self):
        """Start the Telegram bot."""
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram bot token not configured")
            return
        
        self.application = Application.builder().token(self.settings.telegram_bot_token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("briefing", self.cmd_briefing))
        self.application.add_handler(CommandHandler("energy", self.cmd_energy))
        self.application.add_handler(CommandHandler("security", self.cmd_security))
        self.application.add_handler(CommandHandler("memory", self.cmd_memory))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("✅ Telegram bot started")
    
    async def stop(self):
        """Stop the Telegram bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("✅ Telegram bot stopped")
    
    async def send_proactive_notification(self, suggestion: Dict[str, Any]):
        """Send proactive notification to user."""
        if not self.settings.telegram_chat_id:
            return
        
        try:
            # Create inline keyboard for actions
            keyboard = []
            for action in suggestion.get("actions", []):
                keyboard.append([InlineKeyboardButton(
                    f"🔹 {action.replace('_', ' ').title()}", 
                    callback_data=f"action_{action}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await self.application.bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=f"*{suggestion['title']}*\n\n{suggestion['message']}",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
            logger.info(f"📤 Sent proactive notification: {suggestion['title']}")
            
        except Exception as e:
            logger.error(f"Error sending proactive notification: {e}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = str(update.effective_user.id)
        
        welcome_message = (
            "🧠 *Benvenuto in HomeMind AI Assistant!*\n\n"
            "Sono il tuo assistente intelligente per Home Assistant. "
            "Posso aiutarti con:\n\n"
            "🏠 Controllo dispositivi e automazioni\n"
            "⚡ Analisi e ottimizzazione energetica\n"
            "🔒 Gestione sicurezza\n"
            "📊 Briefing e report personalizzati\n"
            "🎙️ Comandi vocali\n\n"
            "Prova a dirmi: *\"Accendi la luce del salotto\"* o *\"Com'è la situazione energetica?\"*\n\n"
            "Usa /help per vedere tutti i comandi."
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        
        # Initialize user context
        self.user_contexts[user_id] = {
            "last_interaction": datetime.now(),
            "conversation_history": [],
            "preferences": {}
        }
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "🤖 *Comandi disponibili:*\n\n"
            "/start - Messaggio di benvenuto\n"
            "/status - Stato generale della casa\n"
            "/briefing - Briefing personalizzato\n"
            "/energy - Analisi energetica\n"
            "/security - Stato sicurezza\n"
            "/memory - Gestione memoria\n\n"
            "💬 *Comandi naturali:*\n"
            "• \"Accendi la luce del salotto\"\n"
            "• \"Temperatura attuale?\"\n"
            "• \"Arma l'allarme\"\n"
            "• \"Consumi di oggi\"\n"
            "• \"Qualcuno è a casa?\"\n\n"
            "🎙️ *Puoi anche mandarmi messaggi vocali!*\n\n"
            "Scrivimi in italiano naturale, capirò cosa vuoi!"
        )
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        try:
            # Get home status from HA
            status = await self.ha_client.get_home_status()
            
            status_text = (
                f"🏠 *Stato della Casa - {datetime.now().strftime('%H:%M')}*\n\n"
                f"👥 Persone a casa: {status.get('people_home', 'N/D')}\n"
                f"🌡️ Temperatura: {status.get('temperature', 'N/D')}°C\n"
                f"💡 Luci accese: {status.get('lights_on', 0)}\n"
                f"🔌 Dispositivi attivi: {status.get('devices_active', 0)}\n"
                f"⚡ Consumo attuale: {status.get('power_consumption', 'N/D')}W\n"
                f"☀️ Produzione solare: {status.get('solar_production', 'N/D')}W\n"
            )
            
            await update.message.reply_text(status_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nel recupero dello stato: {e}")
    
    async def cmd_briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /briefing command."""
        try:
            # Get current context
            current_context = await self.context_manager.get_current_context()
            
            # Generate AI briefing
            result = await self.ai_engine.process_message(
                "Dammi un briefing completo della situazione attuale della casa",
                str(update.effective_user.id),
                current_context
            )
            
            await update.message.reply_text(
                f"📋 *Briefing Personalizzato*\n\n{result['response']}",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nel briefing: {e}")
    
    async def cmd_energy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /energy command."""
        try:
            energy_data = await self.ha_client.get_energy_data()
            
            energy_text = (
                f"⚡ *Analisi Energetica - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
                f"📊 Consumo odierno: {energy_data.get('today_consumption', 'N/D')} kWh\n"
                f"☀️ Produzione solare: {energy_data.get('solar_production', 'N/D')} kWh\n"
                f"🔋 Batteria: {energy_data.get('battery_level', 'N/D')}%\n"
                f"💰 Costo stimato: €{energy_data.get('estimated_cost', 'N/D')}\n"
                f"📈 Media storica: {energy_data.get('historical_average', 'N/D')} kWh\n"
            )
            
            await update.message.reply_text(energy_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nei dati energetici: {e}")
    
    async def cmd_security(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /security command."""
        try:
            security_status = await self.ha_client.get_security_status()
            
            security_text = (
                f"🔒 *Stato Sicurezza*\n\n"
                f"🚪 Allarme: {security_status.get('alarm_state', 'N/D')}\n"
                f"🪟 Porte: {security_status.get('doors_status', 'N/D')}\n"
                f"🚪 Finestre: {security_status.get('windows_status', 'N/D')}\n"
                f"📹 Telecamere: {security_status.get('cameras_status', 'N/D')}\n"
                f"👤 Ultimo movimento: {security_status.get('last_motion', 'N/D')}\n"
            )
            
            await update.message.reply_text(security_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nello stato sicurezza: {e}")
    
    async def cmd_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /memory command."""
        try:
            user_id = str(update.effective_user.id)
            
            # Get recent memories
            memories = await self.ai_engine.memory_system.get_recent_memories(user_id, limit=5)
            
            if not memories:
                await update.message.reply_text("🧠 Non ho ancora memorizzato informazioni su di te.")
                return
            
            memory_text = "🧠 *Memorie Recenti:*\n\n"
            for i, memory in enumerate(memories, 1):
                memory_text += f"{i}. {memory}\n"
            
            await update.message.reply_text(memory_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nella memoria: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages."""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        
        try:
            # Update user context
            self._update_user_context(user_id, message_text)
            
            # Get current context
            current_context = await self.context_manager.get_current_context()
            
            # Process with AI
            result = await self.ai_engine.process_message(message_text, user_id, current_context)
            
            # Send response
            await update.message.reply_text(
                f"💭 {result['response']}",
                parse_mode="Markdown"
            )
            
            # Execute any actions
            if result.get("actions"):
                await self._execute_actions(result["actions"], update)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("❌ Mi dispiace, ho riscontrato un errore. Riprova più tardi.")
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages."""
        user_id = str(update.effective_user.id)
        
        try:
            # Download voice file
            voice_file = await update.message.voice.get_file()
            
            # Convert to text
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
                await voice_file.download_to_drive(temp_file.name)
                
                # Convert OGG to WAV
                audio = AudioSegment.from_ogg(temp_file.name)
                wav_path = temp_file.name.replace(".ogg", ".wav")
                audio.export(wav_path, format="wav")
                
                # Transcribe
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language="it-IT")
                
                # Cleanup
                os.unlink(temp_file.name)
                os.unlink(wav_path)
            
            # Send transcription confirmation
            await update.message.reply_text(f"🎙️ Ho capito: \"{text}\"")
            
            # Process as text message
            update.message.text = text
            await self.handle_message(update, context)
            
        except Exception as e:
            logger.error(f"Error handling voice message: {e}")
            await update.message.reply_text("❌ Non ho capito il messaggio vocale. Riprova.")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages."""
        await update.message.reply_text("📸 Ho ricevuto la foto! Al momento posso solo analizzare messaggi di testo e vocali.")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()
        
        action = query.data.replace("action_", "")
        
        try:
            # Execute action
            result = await self.ha_client.execute_action(action)
            
            await query.edit_message_text(
                f"✅ Azione completata: {action}\n\n{result}",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Errore nell'azione {action}: {e}")
    
    def _update_user_context(self, user_id: str, message: str):
        """Update user conversation context."""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {
                "last_interaction": datetime.now(),
                "conversation_history": [],
                "preferences": {}
            }
        
        user_context = self.user_contexts[user_id]
        user_context["last_interaction"] = datetime.now()
        user_context["conversation_history"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        
        # Keep only last 10 messages
        user_context["conversation_history"] = user_context["conversation_history"][-10:]
    
    async def _execute_actions(self, actions: List[Dict], update: Update):
        """Execute Home Assistant actions."""
        for action in actions:
            try:
                result = await self.ha_client.execute_action(action["type"], action.get("params", {}))
                
                # Send action confirmation
                await update.message.reply_text(
                    f"✅ Eseguito: {action.get('description', action['type'])}",
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                await update.message.reply_text(f"❌ Errore azione {action['type']}: {e}")
