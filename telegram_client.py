import asyncio
import aiohttp
from typing import Optional

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
        self._offset: int = 0
        self._polling_task: Optional[asyncio.Task] = None

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.config.telegram_bot_token}"

    async def start(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self._base_url}/getMe") as resp:
                data = await resp.json()
                if data.get("ok"):
                    bot_info = data["result"]
                    logger.info(f"Bot połączony: @{bot_info.get('username')}")
                else:
                    logger.error(f"Błąd połączenia z bot API: {data}")

        logger.info("Telegram client gotowy (webhook mode)")

    async def stop(self) -> None:
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

    async def _poll_updates(self) -> None:
        """Long polling - nasłuchuje odpowiedzi od ttmbot."""
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        "offset": self._offset,
                        "timeout": 30,
                    }
                    async with session.get(
                        f"{self._base_url}/getUpdates", params=params
                    ) as resp:
                        data = await resp.json()

                    if not data.get("ok"):
                        logger.warning(f"getUpdates error: {data}")
                        await asyncio.sleep(5)
                        continue

                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        await self._process_update(update)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def _process_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return

        text = message.get("text", "")
        document = message.get("document")

        logger.info(f"Otrzymano: {text[:100] if text else '(document)'}")

        if document:
            file_id = document["file_id"]
            file_name = document.get("file_name", "unknown")
            self._last_filename = file_name
            self._last_document_data = await self._download_file(file_id)
            self._file_event.set()
            logger.info(f"Otrzymano plik: {file_name}")
            return

        if self._waiting_for_selection:
            self._last_response = text
            self._response_event.set()
            self._waiting_for_selection = False
            return

        self._last_response = text
        self._response_event.set()

    async def _download_file(self, file_id: str) -> bytes:
        """Pobiera plik z Telegram Bot API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._base_url}/getFile", params={"file_id": file_id}
            ) as resp:
                data = await resp.json()

            if not data.get("ok"):
                raise Exception(f"getFile error: {data}")

            file_path = data["result"]["file_path"]
            url = f"https://api.telegram.org/file/bot{self.config.telegram_bot_token}/{file_path}"

            async with session.get(url) as resp:
                return await resp.read()

    async def send_search(self, query: str) -> Optional[str]:
        self._response_event.clear()
        self._last_response = None

        command = f"/search {query}"
        logger.info(f"Wysyłanie: {command}")

        await self._send_message(self.config.target_bot_username, command)

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
        await self._send_message(self.config.target_bot_username, text)

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

    async def _send_message(self, username: str, text: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._base_url}/getChat", params={"chat_id": f"@{username}"}
            ) as resp:
                data = await resp.json()

            if not data.get("ok"):
                logger.error(f"getChat error: {data}")
                return

            chat_id = data["result"]["id"]

            async with session.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            ) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    logger.error(f"sendMessage error: {result}")

    async def process_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return

        text = message.get("text", "")
        document = message.get("document")

        logger.info(f"Otrzymano (webhook): {text[:100] if text else '(document)'}")

        if document:
            file_id = document["file_id"]
            file_name = document.get("file_name", "unknown")
            self._last_filename = file_name
            self._last_document_data = await self._download_file(file_id)
            self._file_event.set()
            logger.info(f"Otrzymano plik: {file_name}")
            return

        if self._waiting_for_selection:
            self._last_response = text
            self._response_event.set()
            self._waiting_for_selection = False
            return

        self._last_response = text
        self._response_event.set()

    def is_ready(self) -> bool:
        return self._polling_task is not None and not self._polling_task.done()
