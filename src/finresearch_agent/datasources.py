# 定义行情、财报和新闻等外部数据提供者抽象及带缓存的服务类，从第三方 API 抓取原始数据并转为统一的内部模型。
from __future__ import annotations

import pandas as pd
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any, Generic, TypeVar

from finresearch_agent.cache import JSONCache
from finresearch_agent.constants import DEFAULT_TTL_SECONDS
from finresearch_agent.models import FinancialQuarter, MarketBar, MarketData
from finresearch_agent.utils import parse_quarter_from_date_string, to_float

T = TypeVar("T")


# --- Base Provider & Service ---

class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> MarketData:
        raise NotImplementedError


class FinancialsProvider(ABC):
    name: str

    @abstractmethod
    def fetch_quarter(self, symbol: str, quarter: str) -> FinancialQuarter:
        raise NotImplementedError


class NewsProvider(ABC):
    name: str

    @abstractmethod
    def fetch_daily(self, symbol: str, day: date) -> list[dict]:
        raise NotImplementedError


@dataclass(frozen=True)
class BaseCachingService(Generic[T]):
    cache: JSONCache
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def _get_hit(self, key: str) -> dict | None:
        return self.cache.get_json(key)

    def _set_hit(self, key: str, value: Any) -> None:
        if hasattr(value, "model_dump"):
            data = value.model_dump(mode="json")
        else:
            data = value
        self.cache.set_json(key, data, ttl_seconds=self.ttl_seconds)


# --- Market Data ---

class StooqMarketDataProvider(MarketDataProvider):
    name = "stooq"

    def _to_stooq_symbol(self, symbol: str) -> str:
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
class MarketDataService(BaseCachingService[MarketData]):
    provider: MarketDataProvider | None = None

    def _key(self, symbol: str, day: date) -> str:
        return f"market_data:{symbol}:{day.isoformat()}"

    def get_daily_range(self, symbol: str, start: date, end: date, *, min_bars: int = 0) -> MarketData:
        days = pd.date_range(start=start, end=end, freq="D").date
        cached: list[MarketBar] = []
        timestamps: list[str] = []
        for d in days:
            hit = self._get_hit(self._key(symbol, d))
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

        fetched = self.provider.fetch_daily(symbol=symbol, start=start, end=end)
        self._cache_bars(symbol, fetched)
        return fetched

    def _cache_bars(self, symbol: str, market_data: MarketData) -> None:
        ts = market_data.data_timestamp.isoformat()
        for bar in market_data.bars:
            val = {
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
            self._set_hit(self._key(symbol, bar.date), val)


# --- Financials ---

class AlphaVantageFinancialsProvider(FinancialsProvider):
    name = "alphavantage"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("AlphaVantage api_key is required")
        self._api_key = api_key

    def fetch_quarter(self, symbol: str, quarter: str) -> FinancialQuarter:
        url = (
            "https://www.alphavantage.co/query"
            f"?function=INCOME_STATEMENT&symbol={symbol}&apikey={self._api_key}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        reports = payload.get("quarterlyReports") or []
        target = quarter.strip().upper()
        chosen: dict[str, Any] | None = None
        for r in reports:
            fiscal = (r.get("fiscalDateEnding") or "").strip()
            if not fiscal:
                continue
            qid = parse_quarter_from_date_string(fiscal)
            if qid == target:
                chosen = r
                break

        if not chosen:
            raise LookupError(f"Quarter {quarter} not found for {symbol} in Alpha Vantage payload")

        now = datetime.now(tz=timezone.utc)
        source_ts = chosen.get("fiscalDateEnding")
        return FinancialQuarter(
            symbol=symbol,
            quarter=target,
            source=self.name,
            data_timestamp=now,
            source_timestamp=datetime.fromisoformat(source_ts).replace(tzinfo=timezone.utc)
            if source_ts
            else None,
            values={
                "totalRevenue": to_float(chosen.get("totalRevenue")),
                "grossProfit": to_float(chosen.get("grossProfit")),
                "netIncome": to_float(chosen.get("netIncome")),
                "operatingCashflow": to_float(chosen.get("operatingCashflow")),
            },
        )


@dataclass(frozen=True)
class FinancialsService(BaseCachingService[FinancialQuarter]):
    provider: FinancialsProvider | None = None

    def _key(self, symbol: str, quarter: str) -> str:
        return f"financials:{symbol}:{quarter.upper()}"

    def get_quarter(self, symbol: str, quarter: str) -> FinancialQuarter:
        key = self._key(symbol, quarter)
        hit = self._get_hit(key)
        if hit:
            return FinancialQuarter.model_validate(hit)
        fq = self.provider.fetch_quarter(symbol=symbol, quarter=quarter)
        self._set_hit(key, fq)
        return fq


# --- News ---

class NewsAPIProvider(NewsProvider):
    name = "newsapi"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("NewsAPI api_key is required")
        self._api_key = api_key

    def fetch_daily(self, symbol: str, day: date) -> list[dict]:
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
class NewsService(BaseCachingService[dict]):
    provider: NewsProvider | None = None

    def _key(self, symbol: str, day: date) -> str:
        return f"news:{symbol}:{day.isoformat()}"

    def get_daily(self, symbol: str, day: date) -> dict[str, Any]:
        key = self._key(symbol, day)
        hit = self._get_hit(key)
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
        self._set_hit(key, payload)
        return payload
