"""
Home Assistant Client - WebSocket and REST API integration.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp
import websockets

from core.config import Settings

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """Home Assistant WebSocket and REST client."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.websocket = None
        self.session = None
        self.is_connected = False
        self.subscription_id = 0
        self.states = {}
        self.last_update = None
        
    async def connect(self):
        """Connect to Home Assistant."""
        try:
            # Initialize HTTP session
            self.session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.settings.ha_token}"}
            )
            
            # Connect to WebSocket
            await self._connect_websocket()
            
            # Subscribe to state changes
            await self._subscribe_to_states()
            
            self.is_connected = True
            logger.info("✅ Connected to Home Assistant")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Home Assistant: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Home Assistant."""
        try:
            if self.websocket:
                await self.websocket.close()
            
            if self.session:
                await self.session.close()
            
            self.is_connected = False
            logger.info("✅ Disconnected from Home Assistant")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Home Assistant: {e}")
    
    async def _connect_websocket(self):
        """Connect to Home Assistant WebSocket."""
        ws_url = self.settings.ha_websocket_url or f"{self.settings.ha_url.replace('http', 'ws')}/api/websocket"
        
        self.websocket = await websockets.connect(ws_url)
        
        # Wait for auth required message
        auth_message = await self.websocket.recv()
        auth_data = json.loads(auth_message)
        
        if auth_data.get("type") == "auth_required":
            # Send auth
            await self.websocket.send(json.dumps({
                "type": "auth",
                "access_token": self.settings.ha_token
            }))
            
            # Wait for auth response
            auth_response = await self.websocket.recv()
            auth_result = json.loads(auth_response)
            
            if auth_result.get("type") != "auth_ok":
                raise ValueError("Authentication failed")
        
        logger.info("✅ WebSocket authenticated")
    
    async def _subscribe_to_states(self):
        """Subscribe to state changes."""
        subscribe_message = {
            "id": self.subscription_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }
        
        await self.websocket.send(json.dumps(subscribe_message))
        self.subscription_id += 1
        
        # Start background task to listen for state changes
        asyncio.create_task(self._listen_for_state_changes())
    
    async def _listen_for_state_changes(self):
        """Listen for state changes."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                if data.get("type") == "event":
                    event = data.get("event", {})
                    if event.get("event_type") == "state_changed":
                        await self._handle_state_change(event)
                        
        except Exception as e:
            logger.error(f"Error listening for state changes: {e}")
    
    async def _handle_state_change(self, event: Dict):
        """Handle state change event."""
        try:
            data = event.get("data", {})
            entity_id = data.get("entity_id")
            new_state = data.get("new_state")
            
            if entity_id and new_state:
                self.states[entity_id] = new_state
                self.last_update = datetime.now()
                
                logger.debug(f"State changed: {entity_id} = {new_state.get('state')}")
                
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
    
    async def get_state(self, entity_id: str) -> Optional[Dict]:
        """Get state of an entity."""
        try:
            # Check cached state first
            if entity_id in self.states:
                return self.states[entity_id]
            
            # Fetch from API
            url = f"{self.settings.ha_url}/api/states/{entity_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    state = await response.json()
                    self.states[entity_id] = state
                    return state
                else:
                    logger.error(f"Error getting state for {entity_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting state for {entity_id}: {e}")
            return None
    
    async def get_states(self) -> Dict[str, Dict]:
        """Get all states."""
        try:
            url = f"{self.settings.ha_url}/api/states"
            async with self.session.get(url) as response:
                if response.status == 200:
                    states = await response.json()
                    
                    # Update cache
                    for state in states:
                        entity_id = state.get("entity_id")
                        if entity_id:
                            self.states[entity_id] = state
                    
                    return {state.get("entity_id"): state for state in states}
                else:
                    logger.error(f"Error getting states: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting states: {e}")
            return {}
    
    async def call_service(self, domain: str, service: str, service_data: Optional[Dict] = None) -> Dict:
        """Call Home Assistant service."""
        try:
            url = f"{self.settings.ha_url}/api/services/{domain}/{service}"
            
            payload = service_data or {}
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Service called: {domain}.{service} with data: {payload}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Error calling service {domain}.{service}: {response.status} - {error_text}")
                    raise Exception(f"Service call failed: {error_text}")
                    
        except Exception as e:
            logger.error(f"Error calling service {domain}.{service}: {e}")
            raise
    
    async def get_home_status(self) -> Dict[str, Any]:
        """Get comprehensive home status."""
        try:
            states = await self.get_states()
            
            # Count people at home
            people_entities = [s for s in states.values() if s.get("entity_id", "").startswith("person.")]
            people_home = sum(1 for s in people_entities if s.get("state") == "home")
            
            # Get temperature sensors
            temp_entities = [s for s in states.values() if "temperature" in s.get("entity_id", "").lower()]
            avg_temp = 0
            if temp_entities:
                temps = [float(s.get("state", 0)) for s in temp_entities if s.get("state") and s.get("state") != "unknown"]
                if temps:
                    avg_temp = sum(temps) / len(temps)
            
            # Count lights on
            light_entities = [s for s in states.values() if s.get("entity_id", "").startswith("light.")]
            lights_on = sum(1 for s in light_entities if s.get("state") == "on")
            
            # Get power consumption
            power_sensors = [s for s in states.values() if "power" in s.get("entity_id", "").lower() and "W" in s.get("attributes", {}).get("unit_of_measurement", "")]
            total_power = 0
            for sensor in power_sensors:
                try:
                    power = float(sensor.get("state", 0))
                    total_power += power
                except (ValueError, TypeError):
                    continue
            
            # Get solar production
            solar_sensors = [s for s in states.values() if "solar" in s.get("entity_id", "").lower() and "W" in s.get("attributes", {}).get("unit_of_measurement", "")]
            solar_power = 0
            for sensor in solar_sensors:
                try:
                    power = float(sensor.get("state", 0))
                    solar_power += power
                except (ValueError, TypeError):
                    continue
            
            return {
                "people_home": people_home,
                "temperature": round(avg_temp, 1) if avg_temp else None,
                "lights_on": lights_on,
                "devices_active": len([s for s in states.values() if s.get("state") == "on"]),
                "power_consumption": round(total_power, 1) if total_power else None,
                "solar_production": round(solar_power, 1) if solar_power else None,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting home status: {e}")
            return {}
    
    async def get_energy_data(self) -> Dict[str, Any]:
        """Get energy consumption and production data."""
        try:
            states = await self.get_states()
            
            # Get energy consumption sensors
            energy_sensors = [s for s in states.values() if "energy" in s.get("entity_id", "").lower()]
            
            today_consumption = 0
            solar_production = 0
            battery_level = None
            
            for sensor in energy_sensors:
                entity_id = sensor.get("entity_id", "")
                state = sensor.get("state")
                
                if state and state != "unknown" and state != "unavailable":
                    try:
                        value = float(state)
                        
                        if "consumption" in entity_id and "today" in entity_id:
                            today_consumption = value
                        elif "solar" in entity_id and "production" in entity_id:
                            solar_production = value
                        elif "battery" in entity_id and "level" in entity_id:
                            battery_level = value
                            
                    except (ValueError, TypeError):
                        continue
            
            # Calculate estimated cost (assuming €0.25 per kWh)
            estimated_cost = today_consumption * 0.25
            
            return {
                "today_consumption": round(today_consumption, 2),
                "solar_production": round(solar_production, 2),
                "battery_level": round(battery_level, 1) if battery_level else None,
                "estimated_cost": round(estimated_cost, 2),
                "historical_average": round(today_consumption * 1.1, 2)  # Mock historical data
            }
            
        except Exception as e:
            logger.error(f"Error getting energy data: {e}")
            return {}
    
    async def get_security_status(self) -> Dict[str, Any]:
        """Get security system status."""
        try:
            states = await self.get_states()
            
            # Get alarm status
            alarm_entities = [s for s in states.values() if s.get("entity_id", "").startswith("alarm_control_panel.")]
            alarm_state = "unknown"
            if alarm_entities:
                alarm_state = alarm_entities[0].get("state", "unknown")
            
            # Get door sensors
            door_entities = [s for s in states.values() if "door" in s.get("entity_id", "").lower() or "contact" in s.get("entity_id", "").lower()]
            open_doors = [s for s in door_entities if s.get("state") == "on"]
            
            # Get window sensors
            window_entities = [s for s in states.values() if "window" in s.get("entity_id", "").lower()]
            open_windows = [s for s in window_entities if s.get("state") == "on"]
            
            # Get camera status
            camera_entities = [s for s in states.values() if s.get("entity_id", "").startswith("camera.")]
            active_cameras = [s for s in camera_entities if s.get("state") == "recording" or s.get("state") == "streaming"]
            
            # Get motion sensors
            motion_entities = [s for s in states.values() if "motion" in s.get("entity_id", "").lower()]
            last_motion = None
            for sensor in motion_entities:
                last_changed = sensor.get("last_changed")
                if last_changed and sensor.get("state") == "on":
                    if not last_motion or last_changed > last_motion:
                        last_motion = last_changed
            
            return {
                "alarm_state": alarm_state,
                "doors_status": f"{len(open_doors)} aperte" if open_doors else "Tutte chiuse",
                "windows_status": f"{len(open_windows)} aperte" if open_windows else "Tutte chiuse",
                "cameras_status": f"{len(active_cameras)} attive" if active_cameras else "Nessuna attiva",
                "last_motion": last_motion.split("T")[1] if last_motion else "Nessun movimento recente"
            }
            
        except Exception as e:
            logger.error(f"Error getting security status: {e}")
            return {}
    
    async def execute_action(self, action_type: str, params: Optional[Dict] = None) -> str:
        """Execute a Home Assistant action."""
        try:
            params = params or {}
            
            if action_type == "start_appliances":
                # Start high-consumption appliances during solar production
                await self.call_service("switch", "turn_on", {"entity_id": "switch.washing_machine"})
                await self.call_service("switch", "turn_on", {"entity_id": "switch.dishwasher"})
                return "Elettrodomestici avviati per utilizzare l'energia solare"
                
            elif action_type == "arm_alarm":
                # Arm alarm system
                await self.call_service("alarm_control_panel", "alarm_arm_away", {"entity_id": "alarm_control_panel.home_alarm"})
                return "Allarme armato in modalità away"
                
            elif action_type == "check_doors":
                # Check door status
                security_status = await self.get_security_status()
                return f"Stato porte: {security_status.get('doors_status', 'N/D')}"
                
            elif action_type == "weather":
                # Get weather information
                weather_entity = "weather.home"
                weather_state = await self.get_state(weather_entity)
                if weather_state:
                    temp = weather_state.get("attributes", {}).get("temperature")
                    condition = weather_state.get("state")
                    return f"Meteo attuale: {condition}, {temp}°C"
                return "Meteo non disponibile"
                
            elif action_type == "home_status":
                # Get comprehensive home status
                status = await self.get_home_status()
                return (
                    f"Persone a casa: {status.get('people_home', 'N/D')}\n"
                    f"Temperatura: {status.get('temperature', 'N/D')}°C\n"
                    f"Luci accese: {status.get('lights_on', 'N/D')}\n"
                    f"Consumo: {status.get('power_consumption', 'N/D')}W\n"
                    f"Produzione solare: {status.get('solar_production', 'N/D')}W"
                )
                
            else:
                return f"Azione non riconosciuta: {action_type}"
                
        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}")
            return f"Errore nell'esecuzione dell'azione {action_type}: {e}"
