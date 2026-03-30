"""Telegram Bot per HomeMind AI — polling, comandi e query AI contestuale."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from . import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """
    Bot Telegram con long-polling per HomeMind AI.

    Riceve messaggi in arrivo, li autentica per chat_id,
    li instrada a comandi built-in o a query AI contestuale.
    """

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
            _LOGGER.info("HomeMind: Telegram bot non avviato (token o chat_id mancanti)")
            return
        self._running = True
        self._task = self._hass.loop.create_task(self._poll_loop())
        _LOGGER.info("HomeMind: Telegram bot avviato (chat_id=%s)", self._chat_id)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    # ------------------------------------------------------------------ #
    # Invio messaggi (usato anche dal coordinator per alert)
    # ------------------------------------------------------------------ #

    async def send_message(self, text: str, chat_id: str | None = None) -> None:
        cid = chat_id or self._chat_id
        if not cid or not self._token:
            return
        # Telegram max 4096 chars per message
        for chunk in _split_message(text, 4000):
            session = async_get_clientsession(self._hass)
            try:
                await session.post(
                    f"{self._base}/sendMessage",
                    json={"chat_id": cid, "text": chunk, "parse_mode": "Markdown"},
                    timeout=aiohttp.ClientTimeout(total=15),
                )
            except Exception as exc:
                _LOGGER.error("Telegram sendMessage errore: %s", exc)

    async def send_photo(
        self, image_bytes: bytes, caption: str, chat_id: str | None = None
    ) -> None:
        cid = chat_id or self._chat_id
        if not cid or not self._token:
            return
        session = async_get_clientsession(self._hass)
        try:
            data = aiohttp.FormData()
            data.add_field("chat_id", cid)
            data.add_field("caption", caption[:1024])
            data.add_field("parse_mode", "Markdown")
            data.add_field(
                "photo", image_bytes, filename="snapshot.jpg", content_type="image/jpeg"
            )
            await session.post(
                f"{self._base}/sendPhoto",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        except Exception as exc:
            _LOGGER.error("Telegram sendPhoto errore: %s", exc)

    # ------------------------------------------------------------------ #
    # Polling loop
    # ------------------------------------------------------------------ #

    async def _drain_old_updates(self) -> int:
        """Scarica i messaggi in coda al riavvio per evitare di rielaborarli."""
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{self._base}/getUpdates",
                params={"offset": -1, "timeout": 0},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    updates = data.get("result", [])
                    if updates:
                        return updates[-1]["update_id"] + 1
        except Exception as exc:
            _LOGGER.debug("drain_old_updates: %s", exc)
        return 0

    async def _get_updates(self, offset: int) -> list[dict]:
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{self._base}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": '["message"]',
                },
                timeout=aiohttp.ClientTimeout(total=40),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", [])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.debug("getUpdates errore: %s", exc)
        return []

    async def _poll_loop(self) -> None:
        offset = await self._drain_old_updates()
        _LOGGER.debug("HomeMind bot: polling da offset %d", offset)

        while self._running:
            try:
                updates = await self._get_updates(offset)
                for upd in updates:
                    offset = upd["update_id"] + 1
                    await self._handle_update(upd)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.error("Telegram poll loop errore: %s", exc)
                await asyncio.sleep(5)

    # ------------------------------------------------------------------ #
    # Routing messaggi
    # ------------------------------------------------------------------ #

    async def _handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))

        # Auth: solo chat_id autorizzato
        if self._chat_id and chat_id != self._chat_id:
            _LOGGER.warning("HomeMind: messaggio ignorato da chat non autorizzata %s", chat_id)
            return

        text = (message.get("text") or "").strip()
        if not text:
            # Voce o media: non gestita in questa versione
            return

        _LOGGER.info("HomeMind Telegram [%s]: %s", chat_id, text[:60])
        await self._route(text, chat_id)

    async def _route(self, text: str, chat_id: str) -> None:
        lower = text.lower().strip()

        # ---- Comandi built-in ----
        if lower in ("/start", "/help", "/comandi", "aiuto", "help"):
            await self.send_message(self._help_text(), chat_id)
            return

        if lower in ("/stato", "stato casa", "com'è la casa", "come sta la casa", "stato"):
            await self._cmd_status(chat_id)
            return

        if lower in ("/camere", "lista camere", "quali telecamere", "telecamere"):
            await self._cmd_list_cameras(chat_id)
            return

        if lower in ("/sensori", "sensori movimento", "sensori"):
            await self._cmd_motion_sensors(chat_id)
            return

        if lower in ("/report", "genera report", "report sicurezza", "report notturno"):
            await self._coord.send_morning_report(force=True)
            await self.send_message("📊 Report di sicurezza generato.", chat_id)
            return

        if lower in ("/svuota", "svuota alert", "cancella alert"):
            self._coord.night_events.clear()
            self._coord.alerts_tonight = 0
            await self.send_message("🗑️ Alert notturni azzerati.", chat_id)
            return

        # ---- Analisi telecamera specifica ----
        cameras = await self._coord._get_cameras()
        for cam_id in cameras:
            cam_slug = cam_id.replace("camera.", "").replace("_", " ").lower()
            state = self._hass.states.get(cam_id)
            cam_friendly = ""
            if state:
                cam_friendly = state.attributes.get("friendly_name", "").lower()
            if (
                cam_slug in lower
                or cam_id.lower() in lower
                or (cam_friendly and cam_friendly in lower)
            ):
                await self._cmd_analyze_camera(cam_id, chat_id)
                return

        # ---- Analisi tutte le camere ----
        if (
            lower.startswith("/analizza")
            or ("analizza" in lower and "tutte" in lower)
            or lower in ("analizza camere", "analizza telecamere", "/camere_ai")
        ):
            await self._cmd_analyze_all(chat_id)
            return

        # ---- Query AI contestuale (default) ----
        await self._cmd_ai_query(text, chat_id)

    # ------------------------------------------------------------------ #
    # Handlers comandi
    # ------------------------------------------------------------------ #

    async def _cmd_status(self, chat_id: str) -> None:
        from .ha_context import build_home_context

        context = build_home_context(
            self._hass, cameras=await self._coord._get_cameras()
        )
        await self.send_message(context, chat_id)

    async def _cmd_list_cameras(self, chat_id: str) -> None:
        cameras = await self._coord._get_cameras()
        if not cameras:
            await self.send_message(
                "❌ Nessuna telecamera configurata.\n"
                "Vai in *Impostazioni → Integrazioni → HomeMind AI → Configura* "
                "per selezionare le telecamere.",
                chat_id,
            )
            return

        lines = ["📷 *Telecamere monitorate:*\n"]
        for cam_id in cameras:
            state = self._hass.states.get(cam_id)
            name = (
                state.attributes.get("friendly_name") or cam_id
                if state
                else cam_id
            )
            lines.append(f"• {name}")
        lines.append(f"\n💬 _Scrivi il nome di una telecamera per analizzarla._")
        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_motion_sensors(self, chat_id: str) -> None:
        sensors: list[str] = []
        for eid in self._hass.states.async_entity_ids("binary_sensor"):
            state = self._hass.states.get(eid)
            if not state:
                continue
            dc = state.attributes.get("device_class", "")
            if dc not in ("motion", "occupancy"):
                continue
            name = state.attributes.get("friendly_name") or eid
            icon = "🔴" if state.state == "on" else "🟢"
            label = "ATTIVO" if state.state == "on" else "inattivo"
            sensors.append(f"{icon} {name}: {label}")
        if not sensors:
            await self.send_message(
                "ℹ️ Nessun sensore di movimento (binary_sensor con device_class motion/occupancy) trovato.",
                chat_id,
            )
            return
        text = "📡 *Sensori movimento:*\n\n" + "\n".join(sensors)
        await self.send_message(text, chat_id)

    async def _cmd_analyze_all(self, chat_id: str) -> None:
        cameras = await self._coord._get_cameras()
        if not cameras:
            await self.send_message(
                "❌ Nessuna telecamera configurata. Impostala prima dalla UI.",
                chat_id,
            )
            return
        await self.send_message(
            f"🔍 Analizzo {len(cameras)} telecamera/e con Gemini Vision...", chat_id
        )
        for cam_id in cameras:
            await self._cmd_analyze_camera(cam_id, chat_id)

    async def _cmd_analyze_camera(self, cam_id: str, chat_id: str) -> None:
        state = self._hass.states.get(cam_id)
        cam_name = (
            state.attributes.get("friendly_name")
            or cam_id.replace("camera.", "").replace("_", " ").title()
            if state
            else cam_id
        )
        await self.send_message(f"🔍 Analizzo *{cam_name}*...", chat_id)

        result = await self._coord.analyze_single_camera(cam_id)
        if not result:
            await self.send_message(
                f"❌ Impossibile ottenere snapshot da *{cam_name}*.\n"
                "Verifica che la telecamera sia online.",
                chat_id,
            )
            return

        level = result.get("threat_level", "none")
        emoji = {"high": "🔴", "medium": "🟠", "low": "🟡", "none": "🟢"}.get(level, "⚪")

        lines = [
            f"📷 *{cam_name}*",
            "",
            f"{emoji} Rischio: *{level.upper()}*",
            f"🔍 {result.get('description', 'N/A')}",
        ]
        unusual = result.get("unusual", "")
        if unusual and unusual.lower() not in ("no", "nessuno", "nessuna", "niente"):
            lines.append(f"⚠️ Insolito: {unusual}")
        summary = result.get("summary", "")
        if summary:
            lines.append(f"\n💬 _{summary}_")

        await self.send_message("\n".join(lines), chat_id)

    async def _cmd_ai_query(self, question: str, chat_id: str) -> None:
        from .ha_context import build_home_context
        from .ai_provider import ask_gemini

        await self.send_message("🤔 Sto elaborando...", chat_id)

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
    # Help
    # ------------------------------------------------------------------ #

    def _help_text(self) -> str:
        return (
            "🏠 *HomeMind AI — Comandi*\n\n"
            "📊 `/stato` — Stato completo della casa\n"
            "📷 `/camere` — Elenco telecamere monitorate\n"
            "🔍 `/analizza` — Analisi AI di tutte le telecamere\n"
            "📡 `/sensori` — Stato sensori di movimento\n"
            "📋 `/report` — Report sicurezza notturno\n"
            "🗑️ `/svuota` — Azzera alert notturni\n"
            "❓ `/help` — Questo messaggio\n\n"
            "💬 *Oppure scrivi qualsiasi domanda!*\n"
            "_Esempi:_\n"
            "• Chi c'è in casa adesso?\n"
            "• Le finestre sono chiuse?\n"
            "• Cosa vedi dalla camera ingresso?\n"
            "• Luci accese?\n"
            "• Stato allarme?"
        )


# ------------------------------------------------------------------ #
# Utility
# ------------------------------------------------------------------ #

def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Suddivide testo lungo in chunk per Telegram."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunk = text[:max_len]
        # Taglia a newline se possibile
        cut = chunk.rfind("\n")
        if cut > max_len // 2:
            chunk = text[:cut]
        chunks.append(chunk)
        text = text[len(chunk):]
    return chunks
