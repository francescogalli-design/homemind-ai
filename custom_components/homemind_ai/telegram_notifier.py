"""Telegram notification sender for HomeMind AI."""

import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends messages and photos via a Telegram bot."""

    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self._base = f"https://api.telegram.org/bot{token}"

    async def send_message(self, text: str) -> bool:
        """Send a plain text message (HTML parse mode supported)."""
        if not self.token or not self.chat_id:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text[:4096],
                        "parse_mode": "HTML",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        _LOGGER.error("Telegram sendMessage error %s: %s", resp.status, body[:200])
                    return resp.status == 200
        except Exception as err:
            _LOGGER.error("Telegram send_message failed: %s", err)
            return False

    async def send_photo(self, image_bytes: bytes, caption: str = "") -> bool:
        """Send a photo with optional caption."""
        if not self.token or not self.chat_id:
            return False
        try:
            form = aiohttp.FormData()
            form.add_field("chat_id", self.chat_id)
            form.add_field("caption", caption[:1024], content_type="text/plain")
            form.add_field("parse_mode", "HTML")
            form.add_field(
                "photo",
                image_bytes,
                filename="homemind_alert.jpg",
                content_type="image/jpeg",
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base}/sendPhoto",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        _LOGGER.error("Telegram sendPhoto error %s: %s", resp.status, body[:200])
                    return resp.status == 200
        except Exception as err:
            _LOGGER.error("Telegram send_photo failed: %s", err)
            return False

    async def check_connection(self) -> bool:
        """Verify the bot token is valid."""
        if not self.token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base}/getMe",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False
