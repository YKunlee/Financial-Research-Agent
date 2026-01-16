from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Prefer explicit 127.0.0.1 for WSL/Linux setups where Redis binds to loopback.
    # If you run the CLI on Windows but Redis is inside WSL2 bound to 127.0.0.1,
    # you must either run the CLI inside WSL or expose/forward the port and set REDIS_URL.
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    market_data_provider: str = os.getenv("MARKET_DATA_PROVIDER", "stooq")
    alphavantage_api_key: str | None = os.getenv("ALPHAVANTAGE_API_KEY") or None
    newsapi_key: str | None = os.getenv("NEWSAPI_KEY") or None


def get_settings() -> Settings:
    return Settings()
