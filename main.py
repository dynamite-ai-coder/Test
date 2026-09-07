import asyncio
import signal
import sys

from config import Config
from storage import Storage
from queue_manager import QueueManager
from telegram_client import TelegramClientManager
from downloader import Downloader
from control_bot import ControlBot
from worker import Worker
from logger import setup_logger

logger = setup_logger("main")


async def main() -> None:
    config = Config.from_env()
    config.ensure_dirs()

    logger.info("Uruchamianie Telegram Automation System...")

    storage = Storage(config.db_path)
    await storage.init()

    queue = QueueManager(storage)
    client = TelegramClientManager(config)
    downloader = Downloader(config)
    control_bot = ControlBot(config, queue)
    worker = Worker(config, queue, client, downloader, control_bot)

    loop = asyncio.get_event_loop()

    def shutdown():
        logger.info("Zamykanie...")
        worker.control["stop"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        await client.start()
        await control_bot.start()

        logger.info("System gotowy. Worker uruchomiony.")
        await worker.run()

    except Exception as e:
        logger.error(f"Krytyczny błąd: {e}")
    finally:
        await client.stop()
        await control_bot.stop()
        logger.info("System zamknięty.")


if __name__ == "__main__":
    asyncio.run(main())
