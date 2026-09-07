#!/usr/bin/env python3
"""
Telegram Bot - komunikacja z tmlogbot API
Wyszukuje dane logowania (login:pass) dla podanych domen.
"""

import os
import re
import logging
import requests
from telegram import Update, InputFile
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
TMLOG_LOGIN = os.environ.get("TMLOG_LOGIN", "")
TMLOG_PASS = os.environ.get("TMLOG_PASS", "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot gotowy!\n\n"
        "Wyślij mi listę domen (po jednej w linii):\n"
        "example.com\nexample2.com\n\n"
        "Bot wyszuka dane logowania dla każdej domeny."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    domains = [d.strip() for d in text.splitlines() if d.strip()]

    if not domains:
        await update.message.reply_text("Nie podano żadnych domen.")
        return

    await update.message.reply_text(
        f"Przetwarzam {len(domains)} domen..."
    )

    results = []

    for domain in domains:
        await update.message.reply_text(f"Szukam: {domain}...")

        try:
            search_result = await search_domain(domain)
            results.append({
                "domain": domain,
                "data": search_result,
            })
        except Exception as e:
            logger.error(f"Błąd dla {domain}: {e}")
            results.append({
                "domain": domain,
                "data": f"Błąd: {str(e)}",
            })

    for result in results:
        domain = result["domain"]
        data = result["data"]

        if isinstance(data, list) and len(data) > 0:
            content = "\n".join(data)
            line_count = len(data)
            bio = BytesIO(content.encode("utf-8"))
            bio.name = f"{domain}.txt"

            await update.message.reply_document(
                document=bio,
                caption=f"Plik: {domain}.txt\nLinii: {line_count}",
            )
        elif isinstance(data, str):
            await update.message.reply_text(f"{domain}: {data}")
        else:
            await update.message.reply_text(f"{domain}: Brak wyników")

    await update.message.reply_text("Zakończono przetwarzanie.")


async def search_domain(domain: str) -> list:
    """Wyszukuje dane logowania dla domeny przez tmlogbot API."""
    try:
        response = requests.post(
            f"{TMLOG_API_URL}/search",
            json={
                "domain": domain,
                "login": TMLOG_LOGIN,
                "password": TMLOG_PASS,
            },
            timeout=60,
        )

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, dict) and "results" in data:
                return data["results"]
            elif isinstance(data, list):
                return data
            else:
                return [str(data)]

        else:
            return [f"API zwróciło status {response.status_code}"]

    except requests.exceptions.Timeout:
        return ["Timeout - API nie odpowiada"]
    except requests.exceptions.ConnectionError:
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
