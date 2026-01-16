from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any

import pandas as pd
import requests

from finresearch_agent.cache.base import JSONCache
from finresearch_agent.constants import DEFAULT_TTL_SECONDS
from finresearch_agent.datasources.base import MarketDataProvider
from finresearch_agent.models import MarketBar, MarketData


class StooqMarketDataProvider(MarketDataProvider):
    name = "stooq"

    def _to_stooq_symbol(self, symbol: str) -> str:
        # Minimal mapping: treat plain tickers as US listings.
        return f"{symbol.lower()}.us"

    def fetch_daily(self, symbol: str, start: date, end: date) -> MarketData:
        stooq_symbol = self._to_stooq_symbol(symbol)
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        df = pd.read_csv(StringIO(resp.text))
        if df.empty:
            return MarketData(
                symbol=symbol,
                source=self.name,
                data_timestamp=datetime.now(tz=timezone.utc),
                bars=[],
            )

        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
        df.sort_values("Date", inplace=True)

        now = datetime.now(tz=timezone.utc)
        bars = [
            MarketBar(
                date=row["Date"],
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row.get("Volume") or 0),
            )
            for _, row in df.iterrows()
        ]
        return MarketData(symbol=symbol, source=self.name, data_timestamp=now, bars=bars)


@dataclass(frozen=True)
class MarketDataService:
    cache: JSONCache
    provider: MarketDataProvider
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def _key(self, symbol: str, day: date) -> str:
        return f"market_data:{symbol}:{day.isoformat()}"

    def get_daily_range(self, symbol: str, start: date, end: date, *, min_bars: int = 0) -> MarketData:
        days = pd.date_range(start=start, end=end, freq="D").date
        cached: list[MarketBar] = []
        timestamps: list[str] = []
        for d in days:
            hit = self.cache.get_json(self._key(symbol, d))
            if not hit:
                continue
            cached.append(
                MarketBar(
                    date=date.fromisoformat(hit["date"]),
                    open=float(hit["open"]),
                    high=float(hit["high"]),
                    low=float(hit["low"]),
                    close=float(hit["close"]),
                    volume=int(hit["volume"]),
                )
            )
            timestamps.append(hit["data_timestamp"])

        have_dates = {b.date for b in cached}
        if len(have_dates) >= max(min_bars, 1):
            cached.sort(key=lambda b: b.date)
            ts = max(timestamps) if timestamps else datetime.now(tz=timezone.utc).isoformat()
            return MarketData(
                symbol=symbol,
                source=self.provider.name,
                data_timestamp=datetime.fromisoformat(ts),
                bars=cached,
            )

        if len(have_dates) == 0:
            fetched = self.provider.fetch_daily(symbol=symbol, start=start, end=end)
            self._cache_bars(symbol, fetched)
            return fetched

        # Cache has some data but not enough for the requested analysis window: refresh the range.
        fetched = self.provider.fetch_daily(symbol=symbol, start=start, end=end)
        self._cache_bars(symbol, fetched)
        return fetched

    def _cache_bars(self, symbol: str, market_data: MarketData) -> None:
        ts = market_data.data_timestamp.isoformat()
        for bar in market_data.bars:
            val: dict[str, Any] = {
                "symbol": symbol,
                "date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "source": market_data.source,
                "data_timestamp": ts,
            }
            self.cache.set_json(self._key(symbol, bar.date), val, ttl_seconds=self.ttl_seconds)
