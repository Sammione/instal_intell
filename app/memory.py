"""Short-term conversation memory: remembers the last product(s) per user."""
from __future__ import annotations

import threading
import time

from .config import settings


class ConversationMemory:
    def __init__(self, ttl_seconds: int | None = None):
        self.ttl = ttl_seconds or settings.memory_ttl_seconds
        self._store: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["ts"] > self.ttl]
        for k in expired:
            del self._store[k]

    def get_last_products(self, user_id: str) -> list[str]:
        with self._lock:
            self._cleanup()
            entry = self._store.get(user_id)
            return list(entry["product_ids"]) if entry else []

    def set_last_products(self, user_id: str, product_ids: list[str]) -> None:
        if not product_ids:
            return
        with self._lock:
            self._store[user_id] = {"product_ids": list(product_ids), "ts": time.time()}

    def clear(self, user_id: str) -> None:
        with self._lock:
            self._store.pop(user_id, None)
