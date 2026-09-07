import os
from datetime import datetime
from typing import Optional

from config import Config
from logger import setup_logger

logger = setup_logger("downloader")


class Downloader:
    def __init__(self, config: Config):
        self.config = config
        os.makedirs(config.download_dir, exist_ok=True)
        os.makedirs(config.result_dir, exist_ok=True)

    async def save_file(
        self,
        data: bytes,
        original_filename: str,
        url: str,
        chat_id: int,
        message_id: int,
    ) -> Optional[str]:
        if len(data) > self.config.max_file_size:
            logger.warning(f"Plik za duży: {len(data)} bytes > {self.config.max_file_size}")
            return None

        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in self.config.allowed_extensions:
            logger.warning(f"Niedozwolone rozszerzenie: {ext}")
            return None

        domain = url.replace("https://", "").replace("http://", "").replace("/", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{domain}_{timestamp}{ext}"

        filepath = os.path.join(self.config.result_dir, safe_filename)

        try:
            with open(filepath, "wb") as f:
                f.write(data)
            logger.info(f"Plik zapisany: {filepath} ({len(data)} bytes)")
            return filepath
        except Exception as e:
            logger.error(f"Błąd zapisu pliku: {e}")
            return None

    def validate_file_source(
        self,
        expected_chat_id: int,
        actual_chat_id: int,
        filename: str,
    ) -> bool:
        if actual_chat_id != expected_chat_id:
            logger.warning(
                f"Nieprawidłowe chat_id: oczekiwano {expected_chat_id}, otrzymano {actual_chat_id}"
            )
            return False

        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.config.allowed_extensions:
            logger.warning(f"Niedozwolone rozszerzenie pliku: {ext}")
            return False

        return True
