#!/usr/bin/env python3
"""
Telegram Bot - komunikacja z tmlogbot API
Wyszukuje dane logowania (login:pass) dla podanych domen.
Wyszukiwanie równoległe - wszystkie domeny naraz.
"""

import os
import asyncio
import logging
import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from io import BytesIO

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TMLOG_API_URL = os.environ.get("TMLOG_API_URL", "https://tmlogbot.com/api")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot gotowy!\n\n"
        "Wyślij mi listę domen (po jednej w linii):\n"
        "example.com\nexample2.com\n\n"
        "Wszystkie wyszukiwania nastapią równolegle."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    domains = [d.strip() for d in text.splitlines() if d.strip()]

    if not domains:
        await update.message.reply_text("Nie podano żadnych domen.")
        return

    await update.message.reply_text(
        f"Przetwarzam {len(domains)} domen równolegle..."
    )

    tasks = [search_domain(domain) for domain in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for domain, result in zip(domains, results):
        if isinstance(result, Exception):
            await update.message.reply_text(f"{domain}: Błąd - {str(result)}")
            continue

        if isinstance(result, list) and len(result) > 0:
            content = "\n".join(result)
            line_count = len(result)
            bio = BytesIO(content.encode("utf-8"))
            filename = f"{domain}_{line_count}.txt"
            bio.name = filename

            await update.message.reply_document(
                document=bio,
                caption=f"Plik: {filename}\nLinii: {line_count}",
            )
        elif isinstance(result, str):
            await update.message.reply_text(f"{domain}: {result}")
        else:
            await update.message.reply_text(f"{domain}: Brak wyników")

    await update.message.reply_text("Zakończono przetwarzanie.")


async def search_domain(domain: str) -> list:
    """Wyszukuje dane logowania dla domeny przez tmlogbot API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TMLOG_API_URL}/search",
                json={"domain": domain},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if isinstance(data, dict) and "results" in data:
                        return data["results"]
                    elif isinstance(data, list):
                        return data
                    else:
                        return [str(data)]
                else:
                    return [f"API zwróciło status {response.status}"]

    except asyncio.TimeoutError:
        return ["Timeout - API nie odpowiada"]
    except aiohttp.ClientError:
        return ["Błąd połączenia z API"]
    except Exception as e:
        return [f"Nieoczekiwany błąd: {str(e)}"]


def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN nie jest ustawiony!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot uruchomiony...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
