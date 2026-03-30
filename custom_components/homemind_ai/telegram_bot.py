"""Telegram Bot per HomeMind AI — polling, comandi, query AI contestuale."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from . import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)
_TG_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """Bot Telegram con long-polling per HomeMind AI."""

    def __init__(self, coordinator: "HomeMindCoordinator") -> None:
        self._coord = coordinator
        self._hass: "HomeAssistant" = coordinator.hass
        self._token: str = coordinator.telegram_token
        self._chat_id: str = str(coordinator.telegram_chat_id).strip()
        self._base = _TG_API.format(token=self._token)
        self._running = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if not self._token or not self._chat_id:
            return
        self._running = True
        self._task = self._hass.loop.create_task(self._poll_loop())
        _LOGGER.info("HomeMind: bot Telegram avviato (chat=%s)", self._chat_id)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    # ------------------------------------------------------------------ #
    # Invio — usato anche dal coordinator
    # ------------------------------------------------------------------ #

    async def send_message(self, text: str, chat_id: str | None = None) -> None:
        cid = chat_id or self._chat_id
        if not cid:
            return
        for chunk in _chunks(text, 4000):
            session = async_get_clientsession(self._hass)
            try:
                await session.post(
                    f"{self._base}/sendMessage",
                    json={"chat_id": cid, "text": chunk, "parse_mode": "Markdown"},
                    timeout=aiohttp.ClientTimeout(total=15),
                )
            except Exception as exc:
                _LOGGER.error("Telegram sendMessage: %s", exc)

    async def send_photo(
        self, image_bytes: bytes, caption: str, chat_id: str | None = None
    ) -> None:
        cid = chat_id or self._chat_id
        if not cid:
            return
        session = async_get_clientsession(self._hass)
        try:
            form = aiohttp.FormData()
            form.add_field("chat_id", cid)
            form.add_field("caption", caption[:1024])
            form.add_field("parse_mode", "Markdown")
            form.add_field("photo", image_bytes, filename="snapshot.jpg", content_type="image/jpeg")
            await session.post(
                f"{self._base}/sendPhoto",
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        except Exception as exc:
            _LOGGER.error("Telegram sendPhoto: %s", exc)

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #

    async def _drain_old_updates(self) -> int:
        """Salta messaggi accodati prima dell'avvio."""
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{self._base}/getUpdates",
                params={"offset": -1, "timeout": 0},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    updates = (await resp.json()).get("result", [])
                    if updates:
                        return updates[-1]["update_id"] + 1
        except Exception:
            pass
        return 0

    async def _get_updates(self, offset: int) -> list[dict]:
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{self._base}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": '["message"]'},
                timeout=aiohttp.ClientTimeout(total=40),
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("result", [])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.debug("getUpdates: %s", exc)
        return []

    async def _poll_loop(self) -> None:
        offset = await self._drain_old_updates()
        while self._running:
            try:
                for upd in await self._get_updates(offset):
                    offset = upd["update_id"] + 1
                    await self._handle_update(upd)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.error("Poll loop: %s", exc)
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict) -> None:
        msg = update.get("message")
        if not msg:
            return
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if self._chat_id and chat_id != self._chat_id:
            _LOGGER.warning("HomeMind: messaggio ignorato da chat %s", chat_id)
            return
        text = (msg.get("text") or "").strip()
        if not text:
            return
        _LOGGER.info("HomeMind bot: [%s] %s", chat_id, text[:60])
        await self._route(text, chat_id)

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #

    async def _route(self, text: str, chat_id: str) -> None:
        t = text.lower().strip()

        # Generali
        if t in ("/start", "/help", "/comandi"):
            await self.send_message(_help_text(), chat_id)
            return

        if t in ("/stato", "stato", "stato casa"):
            await self._cmd_stato(chat_id)
            return

        if t in ("/debug", "debug"):
            await self._cmd_debug(chat_id)
            return

        if t in ("/persone", "persone", "chi è in casa", "chi c'è in casa"):
            await self._cmd_persone(chat_id)
            return

        if t in ("/luci", "luci", "luci accese", "stato luci"):
            await self._cmd_luci(chat_id)
            return

        if t in ("/tapparelle", "tapparelle", "stato tapparelle", "cover"):
            await self._cmd_tapparelle(chat_id)
            return

        if t in ("/temperatura", "temperatura", "temperature", "termostati"):
            await self._cmd_temperatura(chat_id)
            return

        if t in ("/allarme", "allarme", "stato allarme"):
            await self._cmd_allarme(chat_id)
            return

        if t in ("/camere", "camere", "telecamere"):
            await self._cmd_lista_camere(chat_id)
            return

        if t in ("/sensori", "sensori", "sensori movimento"):
            await self._cmd_sensori(chat_id)
            return

        if t in ("/report", "report", "report sicurezza", "report notturno"):
            await self._coord.send_morning_report(force=True)
            return

        if t in ("/svuota", "svuota", "svuota alert"):
            self._coord.night_events.clear()
            self._coord.alerts_tonight = 0
            self._coord._notify_sensors()
            await self.send_message("Alert notturni azzerati.", chat_id)
            return

        # Analisi camera specifica per nome/entity
        cameras = await self._coord._get_all_cameras_raw()
        for cam_id in cameras:
            state = self._hass.states.get(cam_id)
            cam_friendly = (state.attributes.get("friendly_name", "") if state else "").lower()
            cam_slug = cam_id.replace("camera.", "").replace("_", " ").lower()
            if cam_slug in t or cam_id in t or (cam_friendly and cam_friendly in t):
                await self._cmd_analizza_camera(cam_id, chat_id)
                return

        # Analisi tutte le camere
        if "/analizza" in t or ("analizza" in t and any(k in t for k in ("camera", "telecamera", "tutte", "camere"))):
            await self._cmd_analizza_tutte(chat_id)
            return

        # Query AI contestuale (default per tutto il resto)
        await self._cmd_ai_query(text, chat_id)

    # ------------------------------------------------------------------ #
    # Comandi — stato casa
    # ------------------------------------------------------------------ #

    async def _cmd_stato(self, chat_id: str) -> None:
        """Stato sintetico della casa."""
        hass = self._hass
        now = datetime.now().strftime("%H:%M")

        lines = [f"*Casa · {now}*", ""]

        # Persone
        persons = hass.states.async_entity_ids("person")
        if persons:
            home = [_fname(hass, e) for e in persons if _state(hass, e) in ("home", "Home", "casa")]
            away = [_fname(hass, e) for e in persons if _state(hass, e) not in ("home", "Home", "casa")]
            if home:
                lines.append(f"In casa   {', '.join(home)}")
            if away:
                lines.append(f"Fuori     {', '.join(away)}")

        # Allarme
        alarms = hass.states.async_entity_ids("alarm_control_panel")
        if alarms:
            for eid in alarms:
                lines.append(f"Allarme   {_state(hass, eid)}")

        # Luci
        all_lights = hass.states.async_entity_ids("light")
        on_lights = [_fname(hass, e) for e in all_lights if _state(hass, e) == "on"]
        if on_lights:
            lines.append(f"Luci      {len(on_lights)} accese: {', '.join(on_lights[:4])}" +
                         (f" +{len(on_lights)-4}" if len(on_lights) > 4 else ""))
        else:
            lines.append("Luci      tutte spente")

        # Temperature
        temps = [
            f"{_fname(hass, e)} {_state(hass, e)}°"
            for e in hass.states.async_entity_ids("sensor")
            if _attr(hass, e, "device_class") == "temperature"
            and not any(s in _fname(hass, e).lower() for s in ("cpu", "gpu", "system"))
            and _state(hass, e) not in ("unavailable", "unknown")
        ]
        if temps:
            lines.append(f"Temp      {', '.join(temps[:3])}")

        # Tapparelle
        covers = hass.states.async_entity_ids("cover")
        if covers:
            open_c = [_fname(hass, e) for e in covers if _state(hass, e) == "open"]
            if open_c:
                lines.append(f"Tappar.   {', '.join(open_c[:3])} aperte")
            else:
                lines.append(f"Tappar.   tutte chiuse")

        # Telecamere
        cams = await self._coord._get_cameras()
        if cams:
            lines.append(f"Camere    {len(cams)} monitorate")

        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_persone(self, chat_id: str) -> None:
        hass = self._hass
        persons = hass.states.async_entity_ids("person")
        if not persons:
            await self.send_message("Nessuna entità person configurata in HA.", chat_id)
            return
        lines = ["*Persone*", ""]
        for eid in persons:
            state = hass.states.get(eid)
            if not state:
                continue
            name = state.attributes.get("friendly_name") or eid
            at_home = state.state in ("home", "Home", "casa")
            lines.append(f"{'In casa' if at_home else 'Fuori'}   {name}")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_luci(self, chat_id: str) -> None:
        hass = self._hass
        lights = hass.states.async_entity_ids("light")
        if not lights:
            await self.send_message("Nessuna luce configurata in HA.", chat_id)
            return
        on_lines, off_lines = [], []
        for eid in lights:
            s = hass.states.get(eid)
            if not s:
                continue
            name = s.attributes.get("friendly_name") or eid
            if s.state == "on":
                bri = s.attributes.get("brightness")
                pct = f" {int(bri/255*100)}%" if bri else ""
                on_lines.append(f"  {name}{pct}")
            else:
                off_lines.append(f"  {name}")
        lines = [f"*Luci · {len(on_lines)} accese / {len(off_lines)} spente*"]
        if on_lines:
            lines += ["", "Accese:"] + on_lines[:10]
        if off_lines:
            lines += ["", "Spente:"] + off_lines[:8]
            if len(off_lines) > 8:
                lines.append(f"  ... e altre {len(off_lines)-8}")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_tapparelle(self, chat_id: str) -> None:
        hass = self._hass
        covers = hass.states.async_entity_ids("cover")
        if not covers:
            await self.send_message("Nessuna tapparella/cover configurata in HA.", chat_id)
            return
        lines = ["*Tapparelle*", ""]
        for eid in covers:
            s = hass.states.get(eid)
            if not s:
                continue
            name = s.attributes.get("friendly_name") or eid
            pos = s.attributes.get("current_position")
            pos_str = f"{pos}%" if pos is not None else s.state
            lines.append(f"  {name}: {pos_str}")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_temperatura(self, chat_id: str) -> None:
        hass = self._hass
        temps, climates = [], []
        for eid in hass.states.async_entity_ids("sensor"):
            s = hass.states.get(eid)
            if not s or s.attributes.get("device_class") != "temperature":
                continue
            name = s.attributes.get("friendly_name") or eid
            if any(x in name.lower() for x in ("cpu", "gpu", "system", "board")):
                continue
            if s.state in ("unavailable", "unknown"):
                continue
            unit = s.attributes.get("unit_of_measurement", "°C")
            temps.append(f"  {name}: {s.state}{unit}")
        for eid in hass.states.async_entity_ids("climate"):
            s = hass.states.get(eid)
            if not s:
                continue
            name = s.attributes.get("friendly_name") or eid
            cur = s.attributes.get("current_temperature")
            setpt = s.attributes.get("temperature")
            detail = ""
            if cur is not None:
                detail = f" {cur}°C"
                if setpt is not None:
                    detail += f" → {setpt}°C"
            climates.append(f"  {name}: {s.state}{detail}")
        lines = ["*Temperature*"]
        if temps:
            lines += ["", "Sensori:"] + temps[:8]
        if climates:
            lines += ["", "Termostati:"] + climates[:5]
        if not temps and not climates:
            lines.append("\nNessun sensore temperatura rilevato.")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_allarme(self, chat_id: str) -> None:
        hass = self._hass
        alarms = hass.states.async_entity_ids("alarm_control_panel")
        if not alarms:
            await self.send_message("Nessun pannello allarme configurato in HA.", chat_id)
            return
        lines = ["*Allarme*", ""]
        for eid in alarms:
            s = hass.states.get(eid)
            if not s:
                continue
            name = s.attributes.get("friendly_name") or eid
            lines.append(f"  {name}: {s.state}")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_lista_camere(self, chat_id: str) -> None:
        all_cams = await self._coord._get_all_cameras_raw()
        active_cams = await self._coord._get_cameras()
        unsupported = self._coord._unsupported_cameras

        if not all_cams:
            await self.send_message(
                "Nessuna telecamera trovata in HA.\n\n"
                "Vai in Impostazioni → Integrazioni → HomeMind AI → Configura.",
                chat_id,
            )
            return

        lines = [f"*Telecamere · {len(active_cams)} attive*", ""]
        for cam_id in all_cams:
            s = self._hass.states.get(cam_id)
            name = (s.attributes.get("friendly_name") or cam_id) if s else cam_id
            if cam_id in unsupported:
                lines.append(f"  {name} — non supportata (camera virtuale)")
            else:
                lines.append(f"  {name}")
        lines.append("\nScrivi il nome per analizzarla, oppure /analizza per tutte.")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_sensori(self, chat_id: str) -> None:
        hass = self._hass
        sensors = []
        for eid in hass.states.async_entity_ids("binary_sensor"):
            s = hass.states.get(eid)
            if not s:
                continue
            dc = s.attributes.get("device_class", "")
            if dc not in ("motion", "occupancy"):
                continue
            name = s.attributes.get("friendly_name") or eid
            active = s.state == "on"
            sensors.append((active, name))
        if not sensors:
            await self.send_message("Nessun sensore di movimento (motion/occupancy) trovato.", chat_id)
            return
        sensors.sort(key=lambda x: not x[0])  # Attivi prima
        lines = ["*Sensori movimento*", ""]
        for active, name in sensors:
            lines.append(f"  {'ATTIVO' if active else 'inattivo'}   {name}")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_debug(self, chat_id: str) -> None:
        coord = self._coord
        cams_all = await coord._get_all_cameras_raw()
        cams_ok = await coord._get_cameras()
        motion_sensors = await coord._get_motion_sensors()

        lines = [
            "*HomeMind AI — Debug*",
            "",
            f"Versione    2.1.0",
            f"Stato API   {coord.api_health}",
            f"Modello     {coord.gemini_model}",
            f"Bot         {coord.bot_status}",
            f"Notte       {'attiva' if coord.night_mode == 'active' else 'inattiva'}  ({coord.night_start}:00–{coord.night_end}:00)",
            "",
            f"Camere tot  {len(cams_all)}",
            f"Camere ok   {len(cams_ok)}",
            f"Non supp.   {len(coord._unsupported_cameras)}",
            f"Sens. mov.  {len(motion_sensors)}",
            f"Alert nott. {coord.alerts_tonight}",
            "",
        ]
        if coord._unsupported_cameras:
            lines.append("*Camere escluse (virtuali):*")
            for cam_id in coord._unsupported_cameras:
                s = self._hass.states.get(cam_id)
                name = s.attributes.get("friendly_name", cam_id) if s else cam_id
                lines.append(f"  {name}")
            lines.append("")
        if coord.last_error:
            lines.append(f"*Ultimo errore:*\n{coord.last_error}")

        await self.send_message("\n".join(lines), chat_id)

    # ------------------------------------------------------------------ #
    # Analisi camere con foto
    # ------------------------------------------------------------------ #

    async def _cmd_analizza_tutte(self, chat_id: str) -> None:
        cameras = await self._coord._get_cameras()
        if not cameras:
            await self.send_message(
                "Nessuna telecamera supportata configurata.\n"
                "Usa /debug per vedere lo stato delle camere.",
                chat_id,
            )
            return
        await self.send_message(f"Analizzo {len(cameras)} telecamera/e...", chat_id)
        for cam_id in cameras:
            await self._cmd_analizza_camera(cam_id, chat_id)

    async def _cmd_analizza_camera(self, cam_id: str, chat_id: str) -> None:
        """Analizza camera e invia FOTO + analisi al bot."""
        hass = self._hass
        coord = self._coord
        state = hass.states.get(cam_id)
        cam_name = (
            state.attributes.get("friendly_name")
            or cam_id.replace("camera.", "").replace("_", " ").title()
        ) if state else cam_id

        # Prova snapshot prima (verifica che sia supportata)
        image_bytes = await coord._get_camera_snapshot(cam_id)
        if not image_bytes:
            if cam_id in coord._unsupported_cameras:
                await self.send_message(
                    f"*{cam_name}*\n\n"
                    "Camera non supportata — probabilmente una camera virtuale o slideshow. "
                    "Solo telecamere IP reali sono compatibili con l'analisi AI.",
                    chat_id,
                )
            else:
                await self.send_message(
                    f"*{cam_name}*\n\nSnapshot non disponibile. Verifica che la camera sia online.",
                    chat_id,
                )
            return

        # Analisi Gemini Vision (riusa lo snapshot già in cache)
        result = await coord.analyze_single_camera(cam_id)
        if not result:
            await self.send_message(f"*{cam_name}*\n\nAnalisi non disponibile.", chat_id)
            return

        level = result.get("threat_level", "none")
        ts = datetime.now().strftime("%H:%M")

        # Caption Apple-minimal (max 1024 chars per foto)
        caption_lines = [
            f"*{cam_name}*",
            "",
            result.get("description", ""),
        ]
        unusual = result.get("unusual", "")
        if unusual and unusual.lower() not in ("no", "nessuno", "nessuna", "niente", ""):
            caption_lines.append(unusual)
        caption_lines += [
            "",
            f"Rischio: {level.upper()} · {ts}",
        ]
        if result.get("summary"):
            caption_lines.append(f"_{result['summary']}_")
        if result.get("error"):
            caption_lines.append(f"\nErrore: {result['error']}")

        caption = "\n".join(caption_lines)

        # Invia FOTO + caption
        photo = coord._last_snapshots.get(cam_id, image_bytes)
        await self.send_photo(photo, caption[:1024], chat_id)

    # ------------------------------------------------------------------ #
    # Query AI contestuale
    # ------------------------------------------------------------------ #

    async def _cmd_ai_query(self, question: str, chat_id: str) -> None:
        from .ha_context import build_home_context
        from .ai_provider import ask_gemini

        await self.send_message("...", chat_id)

        context = build_home_context(
            self._hass, cameras=await self._coord._get_cameras()
        )
        session = async_get_clientsession(self._hass)
        answer = await ask_gemini(
            session=session,
            api_key=self._coord.api_key,
            model=self._coord.gemini_model,
            question=question,
            home_context=context,
        )
        await self.send_message(answer, chat_id)


# ------------------------------------------------------------------ #
# Testo help (Apple-minimal)
# ------------------------------------------------------------------ #

def _help_text() -> str:
    return (
        "*HomeMind AI*\n\n"
        "*Stato*\n"
        "/stato — Riepilogo casa\n"
        "/persone — Chi è in casa\n"
        "/luci — Stato luci\n"
        "/tapparelle — Posizione coperture\n"
        "/temperatura — Sensori e termostati\n"
        "/allarme — Pannello allarme\n\n"
        "*Sicurezza*\n"
        "/camere — Lista telecamere\n"
        "/analizza — Analisi AI di tutte le camere\n"
        "/sensori — Sensori di movimento\n"
        "/report — Report notturno\n"
        "/svuota — Azzera alert\n\n"
        "*Diagnostica*\n"
        "/debug — Stato API, modello, errori\n\n"
        "Oppure scrivi qualsiasi domanda sulla tua casa."
    )


# ------------------------------------------------------------------ #
# Utility helpers
# ------------------------------------------------------------------ #

def _chunks(text: str, size: int = 4000) -> list[str]:
    if len(text) <= size:
        return [text]
    parts = []
    while text:
        chunk = text[:size]
        cut = chunk.rfind("\n")
        if cut > size // 2:
            chunk = text[:cut]
        parts.append(chunk)
        text = text[len(chunk):]
    return parts


def _state(hass, eid: str) -> str:
    s = hass.states.get(eid)
    return s.state if s else "unavailable"


def _fname(hass, eid: str) -> str:
    s = hass.states.get(eid)
    if not s:
        return eid
    return s.attributes.get("friendly_name") or eid


def _attr(hass, eid: str, key: str):
    s = hass.states.get(eid)
    return s.attributes.get(key) if s else None
