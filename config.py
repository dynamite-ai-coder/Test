import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    telegram_bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    target_bot_username: str = ""
    allowed_user_ids: List[int] = field(default_factory=list)
    download_dir: str = "./downloads"
    result_dir: str = "./results"
    db_path: str = "./data/queue.db"
    max_retries: int = 3
    bot_response_timeout: int = 60
    file_timeout: int = 180
    max_file_size: int = 50 * 1024 * 1024
    allowed_extensions: List[str] = field(default_factory=lambda: [".txt", ".csv", ".json"])

    @classmethod
    def from_env(cls) -> "Config":
        raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
        allowed = [int(uid.strip()) for uid in raw_ids.split(",") if uid.strip()]

        raw_exts = os.environ.get("ALLOWED_EXTENSIONS", ".txt,.csv,.json")
        extensions = [e.strip() for e in raw_exts.split(",") if e.strip()]

        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_api_id=int(os.environ.get("TELEGRAM_API_ID", "0")),
            telegram_api_hash=os.environ.get("TELEGRAM_API_HASH", ""),
            target_bot_username=os.environ.get("TARGET_BOT_USERNAME", ""),
            allowed_user_ids=allowed,
            download_dir=os.environ.get("DOWNLOAD_DIR", "./downloads"),
            result_dir=os.environ.get("RESULT_DIR", "./results"),
            db_path=os.environ.get("DB_PATH", "./data/queue.db"),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            bot_response_timeout=int(os.environ.get("BOT_RESPONSE_TIMEOUT", "60")),
            file_timeout=int(os.environ.get("FILE_TIMEOUT", "180")),
            max_file_size=int(os.environ.get("MAX_FILE_SIZE", str(50 * 1024 * 1024))),
            allowed_extensions=extensions,
        )

    def ensure_dirs(self) -> None:
        for d in [self.download_dir, self.result_dir, os.path.dirname(self.db_path)]:
            os.makedirs(d, exist_ok=True)

    def is_authorized(self, user_id: int) -> bool:
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids
