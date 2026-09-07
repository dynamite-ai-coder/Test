import aiosqlite
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS queue_items (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    result_file TEXT,
                    error_message TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            await db.commit()

    async def add_item(self, item_id: str, url: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO queue_items (id, url, status, created_at) VALUES (?, ?, 'PENDING', ?)",
                (item_id, url, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def update_item(self, item_id: str, **kwargs: Any) -> None:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [item_id]
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE queue_items SET {fields} WHERE id = ?", values)
            await db.commit()

    async def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM queue_items WHERE id = ?", (item_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_items_by_status(self, status: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM queue_items WHERE status = ? ORDER BY created_at", (status,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_items(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM queue_items ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_next_pending(self) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM queue_items WHERE status = 'PENDING' ORDER BY created_at LIMIT 1"
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def url_exists_active(self, url: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM queue_items WHERE url = ? AND status IN ('PENDING', 'PROCESSING', 'WAITING_FOR_RESPONSE', 'WAITING_FOR_FILE')",
                (url,),
            )
            row = await cursor.fetchone()
            return row[0] > 0

    async def remove_item(self, item_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM queue_items WHERE id = ?", (item_id,))
            await db.commit()

    async def clear_all(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM queue_items")
            await db.commit()

    async def get_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            stats: Dict[str, Any] = {}
            for status in ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "WAITING_FOR_RESPONSE", "WAITING_FOR_FILE"]:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM queue_items WHERE status = ?", (status,)
                )
                row = await cursor.fetchone()
                stats[status.lower()] = row[0]

            cursor = await db.execute("SELECT COUNT(*) FROM queue_items")
            row = await cursor.fetchone()
            stats["total"] = row[0]

            cursor = await db.execute(
                "SELECT url FROM queue_items WHERE status = 'PROCESSING' LIMIT 1"
            )
            row = await cursor.fetchone()
            stats["current_url"] = row[0] if row else None

            return stats

    async def add_history(self, item_id: str, action: str, details: str = "") -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO processing_history (item_id, action, timestamp, details) VALUES (?, ?, ?, ?)",
                (item_id, action, datetime.utcnow().isoformat(), details),
            )
            await db.commit()

    async def move_item(self, item_id: str, direction: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, created_at FROM queue_items WHERE status = 'PENDING' ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            items = [dict(r) for r in rows]

            idx = next((i for i, it in enumerate(items) if it["id"] == item_id), None)
            if idx is None:
                return False

            if direction == "up" and idx > 0:
                swap = items[idx - 1]
                await db.execute(
                    "UPDATE queue_items SET created_at = ? WHERE id = ?",
                    (items[idx]["created_at"], swap["id"]),
                )
                await db.execute(
                    "UPDATE queue_items SET created_at = ? WHERE id = ?",
                    (swap["created_at"], item_id),
                )
                await db.commit()
                return True
            elif direction == "down" and idx < len(items) - 1:
                swap = items[idx + 1]
                await db.execute(
                    "UPDATE queue_items SET created_at = ? WHERE id = ?",
                    (items[idx]["created_at"], swap["id"]),
                )
                await db.execute(
                    "UPDATE queue_items SET created_at = ? WHERE id = ?",
                    (swap["created_at"], item_id),
                )
                await db.commit()
                return True
            return False
