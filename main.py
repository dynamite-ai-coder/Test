import asyncio
import signal
import os
from aiohttp import web

from config import Config
from storage import Storage
from queue_manager import QueueManager
from telegram_client import TelegramClientManager
from downloader import Downloader
from control_bot import ControlBot
from worker import Worker
from logger import setup_logger

logger = setup_logger("main")


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


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
        await control_bot.start()

        app = web.Application()
        app.router.add_get("/", health_handler)
        app.router.add_get("/health", health_handler)
        app.router.add_post("/telegram/webhook", control_bot.handle_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", "10000"))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"HTTP server na porcie {port}")

        await client.start()

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
