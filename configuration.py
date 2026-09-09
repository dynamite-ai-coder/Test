import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "")

PUBLIC_URL = os.getenv("PUBLIC_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

MIN_SIZE_BYTES = int(os.getenv("MIN_SIZE_BYTES", str(10 * 1024 * 1024)))
MAX_SIZE_BYTES = int(os.getenv("MAX_SIZE_BYTES", str(4 * 1024 * 1024 * 1024)))

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/tg_downloads")
DATA_DIR = os.getenv("DATA_DIR", "/data")

TERABOX_NDUS = os.getenv("TERABOX_NDUS", "")
TERABOX_APP_ID = os.getenv("TERABOX_APP_ID", "250528")
TERABOX_UPLOAD_ID = os.getenv("TERABOX_UPLOAD_ID", "")
TERABOX_JS_TOKEN = os.getenv("TERABOX_JS_TOKEN", "")
TERABOX_BROWSER_ID = os.getenv("TERABOX_BROWSER_ID", "")
TERABOX_REMOTE_DIR = os.getenv("TERABOX_REMOTE_DIR", "/")

WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "1"))

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
]


def validate_config():
    missing = []
    for var in REQUIRED_VARS:
        val = os.getenv(var)
        if not val:
            missing.append(var)
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return True
