import requests
import os
from configuration import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID


API_BASE = "https://api.telegram.org/bot{}"


def _url(method):
    return f"{API_BASE.format(TELEGRAM_BOT_TOKEN)}/{method}"


def send_message(chat_id, text, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        r = requests.post(_url("sendMessage"), json=data, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[TELEGRAM] Error sending message: {e}")
        return None


def is_allowed(user_id):
    if ALLOWED_USER_ID == 0:
        return True
    return user_id == ALLOWED_USER_ID


def handle_start(chat_id, user_id):
    if not is_allowed(user_id):
        send_message(chat_id, "Access denied.")
        return
    send_message(chat_id, "Telegram → TeraBox Bot\n\nCommands:\n/start - Help\n/whoami - Your user ID\n/status - App status\n/jobs - Recent jobs\n/add @channel - Process channel\n/stop JOB_ID - Stop job")


def handle_help(chat_id, user_id):
    handle_start(chat_id, user_id)


def handle_whoami(chat_id, user_id):
    send_message(chat_id, f"Your user ID: {user_id}")


def handle_status(chat_id, user_id):
    if not is_allowed(user_id):
        send_message(chat_id, "Access denied.")
        return
    from database import get_running_jobs
    running = get_running_jobs()
    if running:
        j = running[0]
        send_message(chat_id, f"Worker: BUSY\nJob: {j['job_id']}\nChannel: {j['channel']}\nFiles found: {j['files_found']}\nUploaded: {j['files_uploaded']}\nFailed: {j['files_failed']}")
    else:
        send_message(chat_id, "Worker: IDLE\nNo active jobs.")


def handle_jobs(chat_id, user_id):
    if not is_allowed(user_id):
        send_message(chat_id, "Access denied.")
        return
    from database import get_user_jobs
    jobs = get_user_jobs(user_id)
    if not jobs:
        send_message(chat_id, "No jobs found.")
        return
    lines = []
    for j in jobs:
        lines.append(f"{j['job_id']} | {j['channel']} | {j['status']} | Found: {j['files_found']} | Uploaded: {j['files_uploaded']}")
    send_message(chat_id, "\n".join(lines))


def handle_add(chat_id, user_id, args):
    if not is_allowed(user_id):
        send_message(chat_id, "Access denied.")
        return
    if not args:
        send_message(chat_id, "Usage: /add @channel")
        return
    channel = args[0]
    if not channel.startswith("@"):
        send_message(chat_id, "Channel must start with @")
        return
    from database import create_job
    from job_queue import enqueue_job
    job_id = create_job(user_id, channel)
    enqueue_job(job_id, user_id, channel)
    send_message(chat_id, f"Job {job_id} created for {channel}")


def handle_stop(chat_id, user_id, args):
    if not is_allowed(user_id):
        send_message(chat_id, "Access denied.")
        return
    if not args:
        send_message(chat_id, "Usage: /stop JOB_ID")
        return
    job_id = args[0]
    from database import get_job, update_job
    job = get_job(job_id)
    if not job:
        send_message(chat_id, f"Job {job_id} not found.")
        return
    if job["status"] not in ("queued", "running"):
        send_message(chat_id, f"Job {job_id} is {job['status']}, cannot stop.")
        return
    update_job(job_id, status="stopped")
    send_message(chat_id, f"Job {job_id} stop requested.")


def process_update(update):
    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "")
    parts = text.split()
    if not parts:
        return
    cmd = parts[0].lower()
    args = parts[1:]
    if cmd == "/start":
        handle_start(chat_id, user_id)
    elif cmd == "/help":
        handle_help(chat_id, user_id)
    elif cmd == "/whoami":
        handle_whoami(chat_id, user_id)
    elif cmd == "/status":
        handle_status(chat_id, user_id)
    elif cmd == "/jobs":
        handle_jobs(chat_id, user_id)
    elif cmd == "/add":
        handle_add(chat_id, user_id, args)
    elif cmd == "/stop":
        handle_stop(chat_id, user_id, args)
