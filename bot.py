#!/usr/bin/env python3
"""
Telegram Bot - komunikacja z tmlogbot przez Telegram
Wyszukuje dane logowania (login:pass) dla podanych domen.
"""

import os
import asyncio
import logging
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
TMLOG_BOT_USERNAME = os.environ.get("TMLOG_BOT_USERNAME", "tmlogbot")
LOGIN_PASS = os.environ.get("LOGIN_PASS", "login:pass")

user_sessions = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot gotowy!\n\n"
        "Wyślij mi listę domen (po jednej w linii):\n"
        "example.com\nexample2.com\n\n"
        "Wyszukam dane logowania dla każdej domeny."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    domains = [d.strip() for d in text.splitlines() if d.strip()]

    if not domains:
        await update.message.reply_text("Nie podano żadnych domen.")
        return

    chat_id = update.message.chat_id
    user_sessions[chat_id] = {
        "domains": domains,
        "current": 0,
        "results": {},
        "waiting_for_response": False,
    }

    await update.message.reply_text(
        f"Przetwarzam {len(domains)} domen...\n"
        f"Rozpoczynam wyszukiwanie dla: {domains[0]}"
    )

    await search_next_domain(chat_id, context)


async def search_next_domain(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = user_sessions.get(chat_id)
    if not session or session["current"] >= len(session["domains"]):
        await finish_search(chat_id, context)
        return

    domain = session["domains"][session["current"]]
    session["waiting_for_response"] = True

    tmlog_chat_id = os.environ.get("TMLOG_CHAT_ID", "")

    if tmlog_chat_id:
        await context.bot.send_message(
            chat_id=int(tmlog_chat_id),
            text=f"/search {domain}"
        )
        logger.info(f"Wysłano /search {domain} do tmlogbot (chat: {tmlog_chat_id})")
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Wyszukiwanie: {domain}...\n"
                 f"(TMLOG_CHAT_ID nie ustawione - symulacja)"
        )
        session["results"][domain] = ["symulacja: login:pass"]
        session["current"] += 1
        session["waiting_for_response"] = False
        await asyncio.sleep(1)
        await search_next_domain(chat_id, context)


async def handle_tmlog_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    chat_id = update.message.chat_id

    for uid, session in user_sessions.items():
        if not session["waiting_for_response"]:
            continue

        domain = session["domains"][session["current"]]

        if "URL:login:pass" in text or "login:pass" in text:
            tmlog_chat_id = os.environ.get("TMLOG_CHAT_ID", "")
            if tmlog_chat_id:
                await context.bot.send_message(
                    chat_id=int(tmlog_chat_id),
                    text=LOGIN_PASS
                )
                logger.info(f"Wysłano {LOGIN_PASS} do tmlogbot")
            return

        if "plik" in text.lower() or "wynik" in text.lower() or "result" in text.lower():
            if domain not in session["results"]:
                session["results"][domain] = []
            session["results"][domain].append(text)

            if len(session["results"][domain]) >= 1:
                session["current"] += 1
                session["waiting_for_response"] = False
                await search_next_domain(uid, context)
            return


async def finish_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = user_sessions.get(chat_id)
    if not session:
        return

    await context.bot.send_message(chat_id=chat_id, text="Zakończono wyszukiwanie. Wysyłam pliki...")

    for domain, results in session["results"].items():
        if results:
            content = "\n".join(results)
            line_count = len(results)
            bio = BytesIO(content.encode("utf-8"))
            filename = f"{domain}.txt"
            bio.name = filename

            await context.bot.send_document(
                chat_id=chat_id,
                document=bio,
                caption=f"Plik: {filename}\nDomena: {domain}\nLinii: {line_count}",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{domain}: Brak wyników"
            )

    await context.bot.send_message(chat_id=chat_id, text="Wszystkie pliki wysłane.")
    del user_sessions[chat_id]


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
