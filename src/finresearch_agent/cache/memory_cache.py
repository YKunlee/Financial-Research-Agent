from __future__ import annotations

import time
from typing import Any

from finresearch_agent.cache.base import JSONCache


class InMemoryJSONCache(JSONCache):
    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}

    def get_json(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at and time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else 0.0
        self._store[key] = (expires_at, value)
