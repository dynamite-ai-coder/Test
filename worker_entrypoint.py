import asyncio
import signal

from config import Config
from storage import Storage
from queue_manager import QueueManager
from telegram_client import TelegramClientManager
from downloader import Downloader
from control_bot import ControlBot
from worker import Worker
from logger import setup_logger

logger = setup_logger("worker_entrypoint")


async def main() -> None:
    config = Config.from_env()
    config.ensure_dirs()

    logger.info("Uruchamianie Workera...")

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
        await control_bot.start()
        await client.start()

        logger.info("Worker gotowy.")
        await worker.run()

    except Exception as e:
        logger.error(f"Krytyczny błąd workera: {e}")
    finally:
        await client.stop()
        await control_bot.stop()
        logger.info("Worker zamknięty.")


if __name__ == "__main__":
    asyncio.run(main())
