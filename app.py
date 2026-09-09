import os
import sys
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from configuration import (
    TELEGRAM_BOT_TOKEN,
    PUBLIC_URL,
    WEBHOOK_SECRET,
    DOWNLOAD_DIR,
    DATA_DIR,
    validate_config,
)
from database import init_db
from telegram_bot import process_update
from job_queue import start_worker


app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route(f"/webhook/{WEBHOOK_SECRET}" if WEBHOOK_SECRET else "/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(secret, WEBHOOK_SECRET):
            return jsonify({"error": "unauthorized"}), 403
    data = request.get_json(silent=True)
    if data:
        try:
            process_update(data)
        except Exception as e:
            print(f"[WEB] Error processing update: {e}")
    return jsonify({"ok": True})


def setup_webhook():
    if not PUBLIC_URL:
        print("[WEB] No PUBLIC_URL, using polling mode")
        return
    import requests
    webhook_url = f"{PUBLIC_URL.rstrip('/')}/webhook"
    if WEBHOOK_SECRET:
        webhook_url += f"/{WEBHOOK_SECRET}"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    try:
        r = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        result = r.json()
        if result.get("ok"):
            print(f"[WEB] Webhook set: {webhook_url}")
        else:
            print(f"[WEB] Webhook error: {result}")
    except Exception as e:
        print(f"[WEB] Webhook setup failed: {e}")


def main():
    print("[WEB] Starting Telegram → TeraBox")
    try:
        validate_config()
    except EnvironmentError as e:
        print(f"[WEB] CONFIG ERROR: {e}")
        sys.exit(1)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    start_worker()
    setup_webhook()
    port = int(os.getenv("PORT", "10000"))
    print(f"[WEB] Listening on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
