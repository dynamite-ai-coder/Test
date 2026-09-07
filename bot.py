#!/usr/bin/env python3
"""
Telegram Bot @Multi_url_bot - komunikacja z TTM API (enginesearch.top)
Wyszukuje dane logowania (url:login:pass) dla podanych domen.
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
TTM_API_URL = os.environ.get("TTM_API_URL", "https://enginesearch.top")
TTM_TOKEN = os.environ.get("TTM_TOKEN", "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot gotowy!\n\n"
        "Wyślij mi listę domen (po jednej w linii):\n"
        "example.com\nexample2.com\n\n"
        "Wyszukam dane logowania (url:login:pass) dla każdej domeny."
    )


async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TTM_TOKEN:
        await update.message.reply_text("TTM_TOKEN nie jest ustawiony!")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TTM_API_URL}/limits",
                params={"token": TTM_TOKEN},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    await update.message.reply_text(
                        f"Pozostałe limity:\n"
                        f"ULP (search/login/password): {data.get('ulprequest', '?')}\n"
                        f"MAIL: {data.get('mailsrequest', '?')}"
                    )
                else:
                    await update.message.reply_text(f"Błąd API: status {response.status}")
    except Exception as e:
        await update.message.reply_text(f"Błąd: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    domains = [d.strip() for d in text.splitlines() if d.strip()]

    if not domains:
        await update.message.reply_text("Nie podano żadnych domen.")
        return

    if not TTM_TOKEN:
        await update.message.reply_text("TTM_TOKEN nie jest ustawiony!")
        return

    await update.message.reply_text(f"Przetwarzam {len(domains)} domen...")

    tasks = [search_domain(domain) for domain in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for domain, result in zip(domains, results):
        if isinstance(result, Exception):
            await update.message.reply_text(f"{domain}: Błąd - {str(result)}")
            continue

        status, lines = result

        if status == 200 and lines:
            content = "\n".join(lines)
            line_count = len(lines)
            bio = BytesIO(content.encode("utf-8"))
            filename = f"{domain}.txt"
            bio.name = filename

            await update.message.reply_document(
                document=bio,
                caption=f"Plik: {domain}.txt\nDomena: {domain}\nLinii: {line_count}",
            )
        elif status == 404:
            await update.message.reply_text(f"{domain}: Nie znaleziono wyników")
        elif status == 403:
            await update.message.reply_text(f"{domain}: Brak credits (ulprequest)")
        elif status == 401:
            await update.message.reply_text(f"{domain}: Nieprawidłowy token API")
        else:
            await update.message.reply_text(f"{domain}: Status {status}")

    await update.message.reply_text("Zakończono przetwarzanie.")


async def search_domain(domain: str) -> tuple:
    """Wyszukuje dane logowania dla domeny przez TTM API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TTM_API_URL}/search",
                params={"query": domain, "token": TTM_TOKEN},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
                    return (200, lines)
                else:
                    return (response.status, [])

    except asyncio.TimeoutError:
        raise TimeoutError("Timeout - API nie odpowiada")
    except aiohttp.ClientError as e:
        raise ConnectionError(f"Błąd połączenia: {str(e)}")


def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN nie jest ustawiony!")
        return

    if not TTM_TOKEN:
        logger.error("TTM_TOKEN nie jest ustawiony!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("limits", limits))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot uruchomiony...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
