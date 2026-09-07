import uuid
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from storage import Storage


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path


class QueueManager:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def add_url(self, url: str) -> tuple[bool, str]:
        normalized = normalize_url(url)

        if not self._is_valid_url(normalized):
            return False, f"Nieprawidłowy URL: {url}"

        exists = await self.storage.url_exists_active(normalized)
        if exists:
            return False, f"URL już istnieje w aktywnej kolejce: {normalized}"

        item_id = str(uuid.uuid4())[:8]
        await self.storage.add_item(item_id, normalized)
        return True, f"Dodano: {normalized} (ID: {item_id})"

    async def add_urls(self, urls: List[str]) -> List[str]:
        results = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            success, msg = await self.add_url(url)
            results.append(msg)
        return results

    async def get_next(self) -> Optional[Dict[str, Any]]:
        return await self.storage.get_next_pending()

    async def update_status(self, item_id: str, status: str, **kwargs: Any) -> None:
        await self.storage.update_item(item_id, status=status, **kwargs)

    async def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        return await self.storage.get_item(item_id)

    async def remove_item(self, item_id: str) -> bool:
        item = await self.storage.get_item(item_id)
        if item and item["status"] == "PROCESSING":
            return False
        await self.storage.remove_item(item_id)
        return True

    async def clear(self) -> None:
        await self.storage.clear_all()

    async def get_stats(self) -> Dict[str, Any]:
        return await self.storage.get_stats()

    async def get_all_items(self) -> List[Dict[str, Any]]:
        return await self.storage.get_all_items()

    async def move_up(self, item_id: str) -> bool:
        return await self.storage.move_item(item_id, "up")

    async def move_down(self, item_id: str) -> bool:
        return await self.storage.move_item(item_id, "down")

    def _is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
