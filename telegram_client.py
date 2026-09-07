import asyncio
from typing import Optional, Callable, Awaitable, Any

from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename

from config import Config
from logger import setup_logger

logger = setup_logger("telegram_client")


class TelegramClientManager:
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[TelegramClient] = None
        self.target_chat_id: Optional[int] = None
        self._response_event = asyncio.Event()
        self._file_event = asyncio.Event()
        self._last_response: Optional[str] = None
        self._last_document: Optional[Any] = None
        self._last_message_id: Optional[int] = None
        self._on_file_callback: Optional[Callable] = None
        self._waiting_for_selection = False

    async def start(self) -> None:
        self.client = TelegramClient(
            "session",
            self.config.telegram_api_id,
            self.config.telegram_api_hash,
        )
        await self.client.start()
        logger.info("Telegram client uruchomiony")

        target = await self.client.get_entity(self.config.target_bot_username)
        self.target_chat_id = target.id
        logger.info(f"Target bot: {self.config.target_bot_username} (ID: {self.target_chat_id})")

        self.client.add_event_handler(
            self._handle_new_message,
            events.NewMessage(from_users=self.target_chat_id),
        )

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        message = event.message
        text = message.text or ""

        logger.info(f"Otrzymano od bota: {text[:100]}...")

        if message.document:
            self._last_document = message.document
            self._last_message_id = message.id
            self._file_event.set()
            logger.info("Otrzymano plik")
            return

        if self._waiting_for_selection:
            self._last_response = text
            self._response_event.set()
            self._waiting_for_selection = False
            return

        self._last_response = text
        self._response_event.set()

    async def send_search(self, query: str) -> Optional[str]:
        if not self.client or not self.target_chat_id:
            logger.error("Client nie jest połączony")
            return None

        self._response_event.clear()
        self._last_response = None

        command = f"/search {query}"
        logger.info(f"Wysyłanie: {command}")
        await self.client.send_message(self.target_chat_id, command)

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=self.config.bot_response_timeout)
            return self._last_response
        except asyncio.TimeoutError:
            logger.warning(f"Timeout oczekiwania na odpowiedź bota ({self.config.bot_response_timeout}s)")
            return None

    async def send_selection(self, text: str) -> Optional[str]:
        if not self.client or not self.target_chat_id:
            return None

        self._response_event.clear()
        self._last_response = None
        self._waiting_for_selection = True

        logger.info(f"Wysyłanie selekcji: {text}")
        await self.client.send_message(self.target_chat_id, text)

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=self.config.bot_response_timeout)
            return self._last_response
        except asyncio.TimeoutError:
            logger.warning("Timeout oczekiwania na odpowiedź po selekcji")
            return None

    async def wait_for_file(self) -> Optional[tuple]:
        if not self.client:
            return None

        self._file_event.clear()
        self._last_document = None

        try:
            await asyncio.wait_for(self._file_event.wait(), timeout=self.config.file_timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout oczekiwania na plik ({self.config.file_timeout}s)")
            return None

        if not self._last_document:
            return None

        doc = self._last_document
        filename = "unknown"
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name
                break

        data = await self.client.download_media(doc, file=bytes)
        return (filename, data, self._last_message_id)

    def is_ready(self) -> bool:
        return self.client is not None and self.client.is_connected()
