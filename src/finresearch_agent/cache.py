from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import redis
from finresearch_agent.utils import json_dumps, json_loads


class JSONCache(ABC):
    @abstractmethod
    def get_json(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        raise NotImplementedError


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


class RedisJSONCache(JSONCache):
    def __init__(self, redis_url: str):
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get_json(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json_loads(raw)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._client.set(key, json_dumps(value), ex=int(ttl_seconds))

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False
