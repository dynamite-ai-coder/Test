import os
import json
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from typing import Dict, Any, Optional

from config import Config
from queue_manager import QueueManager
from logger import setup_logger

logger = setup_logger("control_bot")


class ControlBot:
    def __init__(self, config: Config, queue: QueueManager):
        self.config = config
        self.queue = queue
        self.app: Optional[Application] = None
        self.worker_control: Optional[Dict[str, Any]] = None

    def set_worker_control(self, control: Dict[str, Any]) -> None:
        self.worker_control = control

    def set_client(self, client) -> None:
        self._client = client

    async def start(self) -> None:
        self._client = None
        self.app = Application.builder().token(self.config.telegram_bot_token).build()

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("add", self.cmd_add))
        self.app.add_handler(CommandHandler("addlist", self.cmd_addlist))
        self.app.add_handler(CommandHandler("queue", self.cmd_queue))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("clear", self.cmd_clear))
        self.app.add_handler(CommandHandler("cancel", self.cmd_cancel))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )

        await self.app.initialize()

        port = int(os.environ.get("PORT", "10000"))
        url = os.environ.get("RENDER_EXTERNAL_URL", f"https://{os.environ.get('RENDER_SERVICE_SLUG', 'localhost')}.onrender.com")

        await self.app.bot.set_webhook(
            url=f"{url}/telegram/webhook",
            allowed_updates=Update.ALL_TYPES,
        )
        logger.info(f"Webhook ustawiony: {url}/telegram/webhook")

    async def stop(self) -> None:
        if self.app:
            await self.app.shutdown()

    async def handle_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            update = Update.de_json(data, self.app.bot)

            if self._client:
                await self._client.process_update(update)

            await self.app.process_update(update)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
        return web.Response(text="OK")

    def _check_auth(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if not self.config.is_authorized(user_id):
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return

        keyboard = [
            [InlineKeyboardButton("➕ Add URL", callback_data="add_url")],
            [
                InlineKeyboardButton("📋 Queue", callback_data="queue"),
                InlineKeyboardButton("📊 Status", callback_data="status"),
            ],
            [
                InlineKeyboardButton("▶️ Start", callback_data="startqueue"),
                InlineKeyboardButton("⏸ Pause", callback_data="pause"),
                InlineKeyboardButton("⏹ Stop", callback_data="stop"),
            ],
            [InlineKeyboardButton("🗑 Clear Queue", callback_data="clear")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Telegram Automation Control Bot\n\n"
            "Wyślij /add <url> lub kliknij przycisk.",
            reply_markup=reply_markup,
        )

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return

        if not context.args:
            await update.message.reply_text("Użycie: /add <url>\n\nLub wyślij wiele URLi po jednej w linii.")
            return

        url = " ".join(context.args)
        urls = [u.strip() for u in url.splitlines() if u.strip()]
        if not urls:
            urls = [url]

        results = await self.queue.add_urls(urls)
        await update.message.reply_text("\n".join(results))

    async def cmd_addlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        await update.message.reply_text(
            "Wyślij listę URLi (po jednej w linii):\n\n"
            "https://example1.com\nhttps://example2.com"
        )

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        await self._show_queue(update)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        if self.worker_control:
            self.worker_control["paused"] = True
        await update.message.reply_text("⏸ Queue paused.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        if self.worker_control:
            self.worker_control["paused"] = False
        await update.message.reply_text("▶️ Queue resumed.")

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        if self.worker_control:
            self.worker_control["stop"] = True
        await update.message.reply_text("⏹ Worker stopped.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        stats = await self.queue.get_stats()
        total = stats.get("total", 0)
        completed = stats.get("completed", 0)
        progress = f"{completed} / {total}" if total > 0 else "0 / 0"

        worker_state = "STOPPED"
        if self.worker_control:
            if self.worker_control.get("stop"):
                worker_state = "STOPPED"
            elif self.worker_control.get("paused"):
                worker_state = "PAUSED"
            else:
                worker_state = "RUNNING"

        text = (
            f"📊 Status\n\n"
            f"Queue size: {stats.get('pending', 0) + stats.get('processing', 0)}\n"
            f"Completed: {completed}\n"
            f"Failed: {stats.get('failed', 0)}\n"
            f"Processing: {stats.get('current_url', 'None')}\n"
            f"Progress: {progress}\n"
            f"Worker: {worker_state}"
        )
        await update.message.reply_text(text)

    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        await self.queue.clear()
        await update.message.reply_text("🗑 Queue cleared.")

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await update.message.reply_text("Unauthorized user.")
            return
        if self.worker_control:
            self.worker_control["stop"] = True
        await update.message.reply_text("⏹ Worker cancelled.")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not self._check_auth(update):
            await query.answer("Unauthorized.", show_alert=True)
            return

        data = query.data

        if data == "add_url":
            await query.answer()
            await query.edit_message_text("Wyślij /add <url> lub wyślij listę URLi.")
        elif data == "queue":
            await query.answer()
            await self._show_queue_callback(query)
        elif data == "status":
            await query.answer()
            stats = await self.queue.get_stats()
            total = stats.get("total", 0)
            completed = stats.get("completed", 0)
            await query.edit_message_text(
                f"📊 Queue: {stats.get('pending', 0)} pending | "
                f"Done: {completed}/{total} | "
                f"Failed: {stats.get('failed', 0)}"
            )
        elif data == "startqueue":
            await query.answer()
            if self.worker_control:
                self.worker_control["paused"] = False
                self.worker_control["stop"] = False
            await query.edit_message_text("▶️ Worker started.")
        elif data == "pause":
            await query.answer()
            if self.worker_control:
                self.worker_control["paused"] = True
            await query.edit_message_text("⏸ Worker paused.")
        elif data == "stop":
            await query.answer()
            if self.worker_control:
                self.worker_control["stop"] = True
            await query.edit_message_text("⏹ Worker stopped.")
        elif data == "clear":
            await query.answer()
            await self.queue.clear()
            await query.edit_message_text("🗑 Queue cleared.")
        elif data.startswith("remove_"):
            item_id = data.replace("remove_", "")
            removed = await self.queue.remove_item(item_id)
            await query.answer("Removed." if removed else "Cannot remove active item.")
            if removed:
                await self._show_queue_callback(query)
        elif data.startswith("moveup_"):
            item_id = data.replace("moveup_", "")
            await self.queue.move_up(item_id)
            await query.answer()
            await self._show_queue_callback(query)
        elif data.startswith("movedown_"):
            item_id = data.replace("movedown_", "")
            await self.queue.move_down(item_id)
            await query.answer()
            await self._show_queue_callback(query)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            return

        text = update.message.text.strip()
        urls = [u.strip() for u in text.splitlines() if u.strip()]

        if len(urls) > 1 and any("://" in u or "." in u for u in urls):
            results = await self.queue.add_urls(urls)
            await update.message.reply_text(f"Dodano {len([r for r in results if r.startswith('Dodano')])} URLi.")
        elif len(urls) == 1:
            success, msg = await self.queue.add_url(urls[0])
            await update.message.reply_text(msg)

    async def _show_queue(self, update: Update) -> None:
        items = await self.queue.get_all_items()
        if not items:
            await update.message.reply_text("Kolejka jest pusta.")
            return

        lines = []
        for i, item in enumerate(items[:20], 1):
            status_icon = {
                "PENDING": "⏳",
                "PROCESSING": "🔄",
                "COMPLETED": "✅",
                "FAILED": "❌",
                "WAITING_FOR_RESPONSE": "⏳",
                "WAITING_FOR_FILE": "⏳",
            }.get(item["status"], "❓")
            lines.append(f"{i}. {status_icon} {item['url']} [{item['status']}]")

        keyboard = []
        for item in items[:10]:
            keyboard.append([
                InlineKeyboardButton(f"❌ {item['url'][:30]}", callback_data=f"remove_{item['id']}"),
                InlineKeyboardButton("↑", callback_data=f"moveup_{item['id']}"),
                InlineKeyboardButton("↓", callback_data=f"movedown_{item['id']}"),
            ])

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )

    async def _show_queue_callback(self, query) -> None:
        items = await self.queue.get_all_items()
        if not items:
            await query.edit_message_text("Kolejka jest pusta.")
            return

        lines = []
        for i, item in enumerate(items[:20], 1):
            status_icon = {
                "PENDING": "⏳",
                "PROCESSING": "🔄",
                "COMPLETED": "✅",
                "FAILED": "❌",
            }.get(item["status"], "❓")
            lines.append(f"{i}. {status_icon} {item['url']}")

        keyboard = []
        for item in items[:10]:
            keyboard.append([
                InlineKeyboardButton(f"❌ {item['url'][:30]}", callback_data=f"remove_{item['id']}"),
                InlineKeyboardButton("↑", callback_data=f"moveup_{item['id']}"),
                InlineKeyboardButton("↓", callback_data=f"movedown_{item['id']}"),
            ])

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )

    async def send_file(self, chat_id: int, filepath: str, caption: str) -> None:
        if self.app:
            with open(filepath, "rb") as f:
                await self.app.bot.send_document(chat_id=chat_id, document=f, caption=caption)

    async def send_message(self, chat_id: int, text: str) -> None:
        if self.app:
            await self.app.bot.send_message(chat_id=chat_id, text=text)

    def get_chat_id(self) -> Optional[int]:
        if self.config.allowed_user_ids:
            return self.config.allowed_user_ids[0]
        return None
