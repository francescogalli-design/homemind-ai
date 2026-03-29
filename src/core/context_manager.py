"""
Context Manager - Manages real-time context and situational awareness.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .memory_system import MemorySystem

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages real-time context for proactive AI responses."""
    
    def __init__(self, memory_system: MemorySystem):
        self.memory_system = memory_system
        self.current_context = {}
        self.context_history = []
        self.last_update = None
        
    async def get_current_context(self) -> Dict[str, Any]:
        """Get comprehensive current context."""
        try:
            context = {
                "timestamp": datetime.now().isoformat(),
                "time_context": self._get_time_context(),
                "location_context": self._get_location_context(),
                "weather_context": await self._get_weather_context(),
                "energy_context": await self._get_energy_context(),
                "security_context": await self._get_security_context(),
                "people_context": await self._get_people_context(),
                "device_context": await self._get_device_context(),
                "routine_context": await self._get_routine_context(),
                "recent_interactions": await self._get_recent_interactions()
            }
            
            # Update stored context
            self.current_context = context
            self.last_update = datetime.now()
            
            # Store in history (keep last 24 hours)
            self.context_history.append({
                "timestamp": datetime.now().isoformat(),
                "context": context
            })
            
            # Cleanup old context
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.context_history = [
                entry for entry in self.context_history
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
            ]
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting current context: {e}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}
    
    def _get_time_context(self) -> Dict[str, Any]:
        """Get time-based context."""
        now = datetime.now()
        
        return {
            "hour": now.hour,
            "day_of_week": now.weekday(),  # 0=Monday, 6=Sunday
            "day_of_month": now.day,
            "month": now.month,
            "year": now.year,
            "is_weekend": now.weekday() >= 5,
            "is_holiday": self._is_holiday(now),
            "time_period": self._get_time_period(now.hour),
            "season": self._get_season(now.month)
        }
    
    def _get_location_context(self) -> Dict[str, Any]:
        """Get location-based context."""
        # This would integrate with GPS/position data
        return {
            "home": True,  # Assume we're at home
            "coordinates": None,  # Would be populated from HA
            "address": None,
            "city": None,
            "country": "Italy"
        }
    
    async def _get_weather_context(self) -> Dict[str, Any]:
        """Get weather context."""
        # This would integrate with weather APIs
        return {
            "temperature": 22,  # Mock data
            "condition": "partly_cloudy",
            "humidity": 65,
            "wind_speed": 10,
            "forecast": [
                {"day": "today", "high": 25, "low": 18, "condition": "partly_cloudy"},
                {"day": "tomorrow", "high": 27, "low": 19, "condition": "sunny"},
                {"day": "day_after", "high": 24, "low": 17, "condition": "rainy"}
            ]
        }
    
    async def _get_energy_context(self) -> Dict[str, Any]:
        """Get energy context."""
        # This would integrate with energy monitoring
        return {
            "current_consumption": 2500,  # Watts
            "solar_production": 1800,  # Watts
            "battery_level": 85,  # Percentage
            "grid_import": 700,  # Watts
            "grid_export": 0,  # Watts
            "daily_consumption": 12.5,  # kWh
            "daily_production": 8.2,  # kWh
            "cost_today": 3.13,  # Euros
            "is_peak_hour": self._is_peak_hour(),
            "solar_efficiency": 0.75  # Percentage
        }
    
    async def _get_security_context(self) -> Dict[str, Any]:
        """Get security context."""
        return {
            "alarm_state": "disarmed",
            "all_doors_closed": True,
            "all_windows_closed": True,
            "motion_detected": False,
            "last_motion": None,
            "cameras_active": 2,
            "night_mode": False,
            "vacation_mode": False,
            "trusted_users_present": True
        }
    
    async def _get_people_context(self) -> Dict[str, Any]:
        """Get people context."""
        return {
            "people_home": 2,
            "people_away": 0,
            "guests_present": False,
            "children_home": True,
            "adults_home": True,
            "sleeping": False,
            "last_arrival": datetime.now().isoformat(),
            "last_departure": (datetime.now() - timedelta(hours=8)).isoformat()
        }
    
    async def _get_device_context(self) -> Dict[str, Any]:
        """Get device context."""
        return {
            "total_devices": 45,
            "active_devices": 12,
            "lights_on": 3,
            "appliances_running": 2,
            "climate_control_active": True,
            "entertainment_active": False,
            "security_active": True,
            "automation_triggers_today": 8
        }
    
    async def _get_routine_context(self) -> Dict[str, Any]:
        """Get routine context."""
        return {
            "morning_routine_active": False,
            "evening_routine_active": False,
            "work_routine_active": True,
            "weekend_mode": False,
            "vacation_mode": False,
            "sleep_routine_active": False,
            "current_routine_confidence": 0.85,
            "predicted_next_action": "prepare_lunch",
            "routine_deviations": 0
        }
    
    async def _get_recent_interactions(self) -> List[Dict]:
        """Get recent user interactions."""
        # This would get actual recent interactions from memory
        return [
            {
                "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
                "type": "command",
                "content": "Accendi luce salotto",
                "result": "success"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "type": "question",
                "content": "Quanto consuma la lavatrice?",
                "result": "provided_info"
            }
        ]
    
    def _get_time_period(self, hour: int) -> str:
        """Get time period descriptor."""
        if 5 <= hour < 8:
            return "early_morning"
        elif 8 <= hour < 12:
            return "morning"
        elif 12 <= hour < 14:
            return "lunch"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"
    
    def _get_season(self, month: int) -> str:
        """Get season based on month."""
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"
    
    def _is_holiday(self, date: datetime) -> bool:
        """Check if date is a holiday."""
        # This would integrate with a holiday calendar
        # For now, just check some common Italian holidays
        if date.month == 12 and date.day == 25:  # Christmas
            return True
        if date.month == 1 and date.day == 1:  # New Year
            return True
        if date.month == 8 and date.day == 15:  # Ferragosto
            return True
        return False
    
    def _is_peak_hour(self) -> bool:
        """Check if current time is peak energy hour."""
        hour = datetime.now().hour
        # Typical peak hours in Italy
        return (8 <= hour <= 11) or (18 <= hour <= 21)
    
    async def update_context_event(self, event_type: str, data: Dict[str, Any]):
        """Update context with specific event."""
        try:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add to current context
            if "recent_events" not in self.current_context:
                self.current_context["recent_events"] = []
            
            self.current_context["recent_events"].append(event)
            
            # Keep only last 10 events
            self.current_context["recent_events"] = self.current_context["recent_events"][-10:]
            
            # Trigger context refresh if significant event
            if event_type in ["person_arrival", "person_departure", "alarm_triggered", "power_outage"]:
                await self.get_current_context()
            
            logger.debug(f"Updated context with event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error updating context event: {e}")
    
    async def get_context_summary(self) -> str:
        """Get human-readable context summary."""
        try:
            context = await self.get_current_context()
            
            summary_parts = []
            
            # Time context
            time_ctx = context.get("time_context", {})
            time_period = time_ctx.get("time_period", "unknown").replace("_", " ")
            summary_parts.append(f"Sono le {datetime.now().strftime('%H:%M')} ({time_period})")
            
            # People context
            people_ctx = context.get("people_context", {})
            people_home = people_ctx.get("people_home", 0)
            summary_parts.append(f"Persone a casa: {people_home}")
            
            # Energy context
            energy_ctx = context.get("energy_context", {})
            consumption = energy_ctx.get("current_consumption", 0)
            solar = energy_ctx.get("solar_production", 0)
            summary_parts.append(f"Consumo: {consumption}W, Solare: {solar}W")
            
            # Security context
            security_ctx = context.get("security_context", {})
            alarm_state = security_ctx.get("alarm_state", "unknown")
            summary_parts.append(f"Allarme: {alarm_state}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error getting context summary: {e}")
            return "Contesto non disponibile"
    
    async def analyze_context_patterns(self, hours_back: int = 24) -> Dict[str, Any]:
        """Analyze patterns in context history."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            relevant_history = [
                entry for entry in self.context_history
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
            ]
            
            if not relevant_history:
                return {"patterns": [], "insights": []}
            
            patterns = []
            insights = []
            
            # Analyze energy patterns
            energy_values = [
                entry["context"].get("energy_context", {}).get("current_consumption", 0)
                for entry in relevant_history
            ]
            if energy_values:
                avg_consumption = sum(energy_values) / len(energy_values)
                max_consumption = max(energy_values)
                
                patterns.append({
                    "type": "energy",
                    "metric": "average_consumption",
                    "value": avg_consumption,
                    "unit": "W"
                })
                
                if max_consumption > avg_consumption * 2:
                    insights.append("Picchi di consumo rilevati nel periodo analizzato")
            
            # Analyze people patterns
            people_values = [
                entry["context"].get("people_context", {}).get("people_home", 0)
                for entry in relevant_history
            ]
            if people_values:
                avg_people = sum(people_values) / len(people_values)
                patterns.append({
                    "type": "people",
                    "metric": "average_people_home",
                    "value": avg_people,
                    "unit": "people"
                })
            
            return {
                "patterns": patterns,
                "insights": insights,
                "data_points": len(relevant_history),
                "period_hours": hours_back
            }
            
        except Exception as e:
            logger.error(f"Error analyzing context patterns: {e}")
            return {"patterns": [], "insights": [], "error": str(e)}
