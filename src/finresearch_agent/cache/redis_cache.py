from __future__ import annotations

from typing import Any

import redis

from finresearch_agent.cache.base import JSONCache
from finresearch_agent.utils import json_dumps, json_loads


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
