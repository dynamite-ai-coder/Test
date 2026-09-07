import asyncio
from typing import Dict, Any

from config import Config
from queue_manager import QueueManager, extract_domain
from telegram_client import TelegramClientManager
from downloader import Downloader
from control_bot import ControlBot
from logger import setup_logger

logger = setup_logger("worker")


class Worker:
    def __init__(
        self,
        config: Config,
        queue: QueueManager,
        client: TelegramClientManager,
        downloader: Downloader,
        control_bot: ControlBot,
    ):
        self.config = config
        self.queue = queue
        self.client = client
        self.downloader = downloader
        self.control_bot = control_bot
        self.control: Dict[str, Any] = {"paused": False, "stop": False}

    async def run(self) -> None:
        self.control_bot.set_worker_control(self.control)
        self._keepalive_task = asyncio.create_task(self._keepalive())

        while True:
            if self.control.get("stop"):
                logger.info("Worker zatrzymany.")
                break

            if self.control.get("paused"):
                await asyncio.sleep(5)
                continue

            item = await self.queue.get_next()
            if not item:
                await asyncio.sleep(5)
                continue

            await self._process_item(item)

        self._keepalive_task.cancel()
        logger.info("Worker zakończony.")

    async def _keepalive(self) -> None:
        """Keep-alive - ping co 10 min żeby Render nie zasypiał."""
        while True:
            await asyncio.sleep(600)
            logger.info("Keep-alive ping")
            chat_id = self.control_bot.get_chat_id()
            if chat_id:
                try:
                    await self.control_bot.send_message(chat_id, "💓 Keep-alive")
                except Exception:
                    pass

    async def _process_item(self, item: Dict[str, Any]) -> None:
        item_id = item["id"]
        url = item["url"]
        domain = extract_domain(url)
        retry_count = item.get("retry_count", 0) or 0

        logger.info(f"Przetwarzanie: {url} (ID: {item_id})")

        await self.queue.update_status(
            item_id, "PROCESSING", started_at=_now()
        )
        await self._notify(f"🔄 Przetwarzanie: {domain}")

        if not self.client.is_ready():
            logger.error("Telegram client nie jest połączony")
            await self.queue.update_status(
                item_id, "FAILED", error_message="Client not connected", completed_at=_now()
            )
            return

        try:
            response = await self.client.send_search(domain)
            if response is None:
                raise Exception("Brak odpowiedzi od bota")

            logger.info(f"Odpowiedź bota: {response[:100]}")

            await self.queue.update_status(item_id, "WAITING_FOR_RESPONSE")

            selection = "login:pass"
            logger.info(f"Wysyłanie selekcji: {selection}")

            response2 = await self.client.send_selection(selection)
            if response2 is None:
                raise Exception("Brak odpowiedzi po selekcji")

            logger.info(f"Odpowiedź po selekcji: {response2[:100]}")

            await self.queue.update_status(item_id, "WAITING_FOR_FILE")

            file_result = await self.client.wait_for_file()
            if file_result is None:
                raise Exception("Nie otrzymano pliku")

            filename, data, msg_id = file_result
            logger.info(f"Otrzymano plik: {filename} ({len(data)} bytes)")

            valid = self.downloader.validate_file_source(
                expected_chat_id=self.client.target_chat_id,
                actual_chat_id=self.client.target_chat_id,
                filename=filename,
            )
            if not valid:
                raise Exception("Walidacja pliku nie powiodła się")

            filepath = await self.downloader.save_file(
                data=data,
                original_filename=filename,
                url=url,
                chat_id=self.client.target_chat_id,
                message_id=msg_id,
            )

            if not filepath:
                raise Exception("Nie udało się zapisać pliku")

            await self.queue.update_status(
                item_id, "COMPLETED", result_file=filepath, completed_at=_now()
            )

            await self._deliver_file(filepath, domain, filename)

            logger.info(f"Zakończono: {url}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout dla {url}")
            await self._handle_failure(item_id, url, "Timeout", retry_count)
        except Exception as e:
            logger.error(f"Błąd dla {url}: {e}")
            await self._handle_failure(item_id, url, str(e), retry_count)

    async def _handle_failure(
        self, item_id: str, url: str, error: str, retry_count: int
    ) -> None:
        if retry_count < self.config.max_retries:
            logger.info(f"Retry {retry_count + 1}/{self.config.max_retries} dla {url}")
            await self.queue.update_status(
                item_id,
                "PENDING",
                retry_count=retry_count + 1,
                error_message=error,
            )
        else:
            await self.queue.update_status(
                item_id,
                "FAILED",
                error_message=error,
                completed_at=_now(),
            )
            await self._notify(f"❌ Failed: {url} - {error}")

    async def _deliver_file(self, filepath: str, domain: str, original_name: str) -> None:
        chat_id = self.control_bot.get_chat_id()
        if not chat_id:
            logger.error("Brak chat_id do dostarczenia pliku")
            return

        caption = f"📁 {domain}\n📄 {original_name}"
        try:
            await self.control_bot.send_file(chat_id, filepath, caption)
            logger.info(f"Plik dostarczony do {chat_id}")
        except Exception as e:
            logger.error(f"Błąd dostarczania pliku: {e}")

    async def _notify(self, text: str) -> None:
        chat_id = self.control_bot.get_chat_id()
        if chat_id:
            try:
                await self.control_bot.send_message(chat_id, text)
            except Exception:
                pass


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()
