import asyncio
import os
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Document

from config import Config
from logger import setup_logger

logger = setup_logger("telegram_client")


class TelegramClientManager:
    def __init__(self, config: Config):
        self.config = config
        self.target_chat_id: Optional[int] = None
        self._response_event = asyncio.Event()
        self._file_event = asyncio.Event()
        self._last_response: Optional[str] = None
        self._last_document_data: Optional[bytes] = None
        self._last_filename: Optional[str] = None
        self._waiting_for_selection = False
        self._client: Optional[TelegramClient] = None

    async def start(self) -> None:
        session_data = os.environ.get("TELETHON_SESSION", "")
        if not session_data:
            logger.error("Brak TELETHON_SESSION!")
            return

        session_path = "/tmp/telethon.session"
        with open(session_path, "wb") as f:
            f.write(bytes.fromhex(session_data))

        self._client = TelegramClient(
            session_path,
            self.config.telegram_api_id,
            self.config.telegram_api_hash,
        )

        await self._client.start()
        me = await self._client.get_me()
        logger.info(f"Telethon połączony: @{me.username}")

        self._client.add_event_handler(
            self._handle_new_message,
            events.NewMessage(from_users=self.config.target_bot_username),
        )

        await self._client.get_entity(self.config.target_bot_username)
        logger.info(f"Target bot: @{self.config.target_bot_username}")

    async def stop(self) -> None:
        if self._client:
            await self._client.disconnect()

    async def _handle_new_message(self, event):
        message = event.message
        text = message.text or ""
        document = message.document

        logger.info(f"Otrzymano od bota: {text[:100] if text else '(document)'}")

        if document:
            self._last_filename = None
            for attr in document.attributes:
                if hasattr(attr, "file_name"):
                    self._last_filename = attr.file_name
                    break
            self._last_filename = self._last_filename or "unknown"

            self._last_document_data = await message.download_media(file=bytes)
            self._file_event.set()
            logger.info(f"Otrzymano plik: {self._last_filename}")
            return

        if self._waiting_for_selection:
            self._last_response = text
            self._response_event.set()
            self._waiting_for_selection = False
            return

        self._last_response = text
        self._response_event.set()

    async def send_search(self, query: str) -> Optional[str]:
        self._response_event.clear()
        self._last_response = None

        command = f"/search {query}"
        logger.info(f"Wysyłanie: {command}")

        entity = await self._client.get_entity(self.config.target_bot_username)
        await self._client.send_message(entity, command)

        try:
            await asyncio.wait_for(
                self._response_event.wait(), timeout=self.config.bot_response_timeout
            )
            return self._last_response
        except asyncio.TimeoutError:
            logger.warning(f"Timeout odpowiedzi bota ({self.config.bot_response_timeout}s)")
            return None

    async def send_selection(self, text: str) -> Optional[str]:
        self._response_event.clear()
        self._last_response = None
        self._waiting_for_selection = True

        logger.info(f"Wysyłanie selekcji: {text}")

        entity = await self._client.get_entity(self.config.target_bot_username)
        await self._client.send_message(entity, text)

        try:
            await asyncio.wait_for(
                self._response_event.wait(), timeout=self.config.bot_response_timeout
            )
            return self._last_response
        except asyncio.TimeoutError:
            logger.warning("Timeout po selekcji")
            return None

    async def wait_for_file(self) -> Optional[tuple]:
        self._file_event.clear()
        self._last_document_data = None
        self._last_filename = None

        try:
            await asyncio.wait_for(
                self._file_event.wait(), timeout=self.config.file_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout pliku ({self.config.file_timeout}s)")
            return None

        if not self._last_document_data:
            return None

        return (self._last_filename or "unknown", self._last_document_data, 0)

    async def process_update(self, update: dict) -> None:
        pass

    def is_ready(self) -> bool:
        return self._client is not None and self._client.is_connected()
