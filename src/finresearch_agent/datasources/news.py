from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests

from finresearch_agent.cache.base import JSONCache
from finresearch_agent.constants import DEFAULT_TTL_SECONDS
from finresearch_agent.datasources.base import NewsProvider


class NewsAPIProvider(NewsProvider):
    name = "newsapi"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("NewsAPI api_key is required")
        self._api_key = api_key

    def fetch_daily(self, symbol: str, day: date) -> list[dict]:
        # Stores raw text; query is intentionally simple.
        from_dt = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
        to_dt = datetime.combine(day, datetime.max.time()).replace(tzinfo=timezone.utc)
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": symbol,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 100,
            "apiKey": self._api_key,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        articles = payload.get("articles") or []
        return articles


@dataclass(frozen=True)
class NewsService:
    cache: JSONCache
    provider: NewsProvider
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def _key(self, symbol: str, day: date) -> str:
        return f"news:{symbol}:{day.isoformat()}"

    def get_daily(self, symbol: str, day: date) -> dict[str, Any]:
        key = self._key(symbol, day)
        hit = self.cache.get_json(key)
        if hit:
            return hit
        articles = self.provider.fetch_daily(symbol=symbol, day=day)
        now = datetime.now(tz=timezone.utc)
        payload = {
            "symbol": symbol,
            "date": day.isoformat(),
            "source": self.provider.name,
            "data_timestamp": now.isoformat(),
            "articles": articles,
        }
        self.cache.set_json(key, payload, ttl_seconds=self.ttl_seconds)
        return payload
