"""Riconoscimento targhe per HomeMind AI — integrazione con PlateRecognizer."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import Event, callback
from homeassistant.helpers.event import async_track_state_change_event

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from . import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)

_DEDUP_WINDOW_S = 30
_CONFIDENCE_THRESHOLD = 0.75
_KNOWN_PLATE_MIN_COUNT = 3
_KNOWN_PLATE_DAYS = 30
_SCAN_DELAY_S = 1.0
_RETRY_DELAY_S = 1.5

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS plate_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,
    confidence REAL NOT NULL,
    camera TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    known INTEGER NOT NULL DEFAULT 0
)
"""


class PlateRecognitionManager:
    """Gestisce il riconoscimento targhe tramite PlateRecognizer."""

    def __init__(self, coordinator: HomeMindCoordinator) -> None:
        self._coord = coordinator
        self._hass: HomeAssistant = coordinator.hass
        self._db_path: str = self._hass.config.path("homemind_plates.db")
        self._unsub_listeners: list = []
        self._last_seen: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def async_init(self) -> None:
        """Inizializza il database e i listener per i sensori veicolo."""
        await self._hass.async_add_executor_job(self._init_db)

        vehicle_sensors: list[str] = getattr(self._coord, "vehicle_sensors", [])
        if not vehicle_sensors:
            _LOGGER.debug("PlateRecognition: nessun sensore veicolo configurato")
            return

        self._unsub_listeners = [
            async_track_state_change_event(
                self._hass, [sensor], self._on_vehicle_detected
            )
            for sensor in vehicle_sensors
        ]
        _LOGGER.info(
            "PlateRecognition: inizializzato con %d sensori veicolo",
            len(vehicle_sensors),
        )

    def stop(self) -> None:
        """Rimuove tutti i listener attivi."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        _LOGGER.debug("PlateRecognition: fermato")

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #

    def _init_db(self) -> None:
        """Crea la tabella se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    def _store_detection(
        self, plate: str, confidence: float, camera: str, known: bool
    ) -> None:
        """Salva un rilevamento nel database."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO plate_detections (plate, confidence, camera, timestamp, known) "
                "VALUES (?, ?, ?, ?, ?)",
                (plate, confidence, camera, datetime.now().isoformat(), int(known)),
            )
            conn.commit()
        finally:
            conn.close()

    def _query_plate_count(self, plate: str, days: int) -> int:
        """Conta le occorrenze di una targa negli ultimi N giorni."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM plate_detections WHERE plate = ? AND timestamp >= ?",
                (plate, cutoff),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def _fetch_recent(self, limit: int) -> list[dict[str, Any]]:
        """Recupera gli ultimi rilevamenti."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM plate_detections ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _fetch_stats(self) -> dict[str, Any]:
        """Statistiche sulle targhe rilevate."""
        conn = sqlite3.connect(self._db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM plate_detections"
            ).fetchone()[0]
            unique = conn.execute(
                "SELECT COUNT(DISTINCT plate) FROM plate_detections"
            ).fetchone()[0]
            known = conn.execute(
                "SELECT COUNT(DISTINCT plate) FROM plate_detections WHERE known = 1"
            ).fetchone()[0]
            cutoff_today = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            today = conn.execute(
                "SELECT COUNT(*) FROM plate_detections WHERE timestamp >= ?",
                (cutoff_today,),
            ).fetchone()[0]
            return {
                "total_detections": total,
                "unique_plates": unique,
                "known_plates": known,
                "detections_today": today,
            }
        finally:
            conn.close()

    def _fetch_count_today(self) -> int:
        """Conta i rilevamenti di oggi."""
        cutoff = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM plate_detections WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Public async query methods
    # ------------------------------------------------------------------ #

    async def get_recent_detections(self, limit: int = 10) -> list[dict[str, Any]]:
        """Restituisce gli ultimi rilevamenti."""
        return await self._hass.async_add_executor_job(self._fetch_recent, limit)

    async def get_plate_stats(self) -> dict[str, Any]:
        """Restituisce statistiche sui rilevamenti."""
        return await self._hass.async_add_executor_job(self._fetch_stats)

    async def get_detection_count_today(self) -> int:
        """Restituisce il conteggio rilevamenti di oggi."""
        return await self._hass.async_add_executor_job(self._fetch_count_today)

    # ------------------------------------------------------------------ #
    # Vehicle detection handler
    # ------------------------------------------------------------------ #

    @callback
    def _on_vehicle_detected(self, event: Event) -> None:
        """Callback quando un sensore veicolo passa a 'on'."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state != "on":
            return

        entity_id: str = event.data.get("entity_id", "")
        vehicle_sensors: list[str] = getattr(self._coord, "vehicle_sensors", [])
        alpr_entities: list[str] = getattr(self._coord, "alpr_entities", [])

        try:
            idx = vehicle_sensors.index(entity_id)
        except ValueError:
            _LOGGER.warning("PlateRecognition: sensore %s non in lista", entity_id)
            return

        if idx >= len(alpr_entities):
            _LOGGER.warning(
                "PlateRecognition: nessuna entità ALPR per indice %d (sensore %s)",
                idx,
                entity_id,
            )
            return

        alpr_entity = alpr_entities[idx]
        _LOGGER.debug(
            "PlateRecognition: veicolo rilevato su %s → scansione %s",
            entity_id,
            alpr_entity,
        )
        self._hass.async_create_task(
            self._scan_and_process(alpr_entity, entity_id)
        )

    # ------------------------------------------------------------------ #
    # Scan + process pipeline
    # ------------------------------------------------------------------ #

    async def _scan_and_process(self, alpr_entity: str, camera_sensor: str) -> None:
        """Attende, scansiona e processa il risultato. Retry una volta se sotto soglia."""
        plate, confidence = await self._trigger_and_read(alpr_entity)

        if plate and confidence >= _CONFIDENCE_THRESHOLD:
            await self._handle_plate(plate, confidence, alpr_entity, camera_sensor)
            return

        # Retry dopo 1.5s
        _LOGGER.debug(
            "PlateRecognition: primo tentativo insufficiente (plate=%s, conf=%.2f), retry",
            plate,
            confidence,
        )
        await asyncio.sleep(_RETRY_DELAY_S)
        plate, confidence = await self._trigger_and_read(alpr_entity)

        if plate and confidence >= _CONFIDENCE_THRESHOLD:
            await self._handle_plate(plate, confidence, alpr_entity, camera_sensor)
        else:
            _LOGGER.debug(
                "PlateRecognition: targa non riconosciuta con sufficiente confidenza "
                "dopo retry (plate=%s, conf=%.2f)",
                plate,
                confidence,
            )

    async def _trigger_and_read(self, alpr_entity: str) -> tuple[str | None, float]:
        """Triggera la scansione e legge il risultato dall'entità."""
        await asyncio.sleep(_SCAN_DELAY_S)

        try:
            await self._hass.services.async_call(
                "image_processing",
                "scan",
                {"entity_id": alpr_entity},
                blocking=True,
            )
        except Exception as exc:
            _LOGGER.error("PlateRecognition: errore scansione %s: %s", alpr_entity, exc)
            return None, 0.0

        state = self._hass.states.get(alpr_entity)
        if state is None:
            _LOGGER.warning("PlateRecognition: entità %s non trovata", alpr_entity)
            return None, 0.0

        vehicles: list[dict] = state.attributes.get("vehicles", [])
        if not vehicles:
            return None, 0.0

        # Prende il veicolo con la confidenza più alta
        best = max(vehicles, key=lambda v: v.get("score", 0.0))
        plate = best.get("plate", "")
        score = float(best.get("score", 0.0))
        return (plate.upper().strip() if plate else None, score)

    # ------------------------------------------------------------------ #
    # Plate handling
    # ------------------------------------------------------------------ #

    async def _handle_plate(
        self,
        plate: str,
        confidence: float,
        alpr_entity: str,
        camera_sensor: str,
    ) -> None:
        """Processa una targa riconosciuta: dedup, salva, evento, notifica."""
        now = time.monotonic()

        # Deduplicazione: stessa targa entro 30s = skip
        last_time = self._last_seen.get(plate)
        if last_time is not None and (now - last_time) < _DEDUP_WINDOW_S:
            _LOGGER.debug("PlateRecognition: targa %s ignorata (dedup %.0fs)", plate, now - last_time)
            return

        self._last_seen[plate] = now

        # Verifica se la targa è nota (vista 3+ volte negli ultimi 30 giorni)
        past_count = await self._hass.async_add_executor_job(
            self._query_plate_count, plate, _KNOWN_PLATE_DAYS
        )
        known = past_count >= _KNOWN_PLATE_MIN_COUNT

        # Salva nel database
        await self._hass.async_add_executor_job(
            self._store_detection, plate, confidence, alpr_entity, known
        )

        # Aggiorna stato sul coordinator
        self._coord.last_plate = plate
        self._coord.plates_today = await self.get_detection_count_today()

        _LOGGER.info(
            "PlateRecognition: targa %s (conf=%.2f, camera=%s, nota=%s)",
            plate,
            confidence,
            alpr_entity,
            known,
        )

        # Evento HA
        self._hass.bus.async_fire(
            "homemind_plate_detected",
            {
                "plate": plate,
                "confidence": confidence,
                "camera": alpr_entity,
                "sensor": camera_sensor,
                "known": known,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Notifica Telegram per targhe sconosciute
        if not known:
            bot = getattr(self._coord, "bot", None)
            if bot is not None:
                await bot.send_message(
                    f"🚗 *Targa sconosciuta rilevata*\n"
                    f"Targa: `{plate}`\n"
                    f"Confidenza: {confidence:.0%}\n"
                    f"Camera: {alpr_entity}\n"
                    f"Vista {past_count + 1} volta/e"
                )
