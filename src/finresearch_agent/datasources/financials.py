from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from finresearch_agent.cache.base import JSONCache
from finresearch_agent.constants import DEFAULT_TTL_SECONDS
from finresearch_agent.datasources.base import FinancialsProvider
from finresearch_agent.models import FinancialQuarter


class AlphaVantageFinancialsProvider(FinancialsProvider):
    """
    Uses Alpha Vantage 'INCOME_STATEMENT' endpoint and selects a single quarter.
    Requires `ALPHAVANTAGE_API_KEY`. This is intentionally narrow and code-first.
    """

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
        # Alpha Vantage uses fiscalDateEnding like '2024-09-30'
        # We map 'YYYYQn' by quarter end month.
        target = quarter.strip().upper()
        chosen: dict[str, Any] | None = None
        for r in reports:
            fiscal = (r.get("fiscalDateEnding") or "").strip()
            if not fiscal:
                continue
            y, m, _ = fiscal.split("-")
            q = (int(m) - 1) // 3 + 1
            qid = f"{y}Q{q}"
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
                # Raw values only; keep strings -> numbers conversion minimal and explicit
                "totalRevenue": _to_num(chosen.get("totalRevenue")),
                "grossProfit": _to_num(chosen.get("grossProfit")),
                "netIncome": _to_num(chosen.get("netIncome")),
                "operatingCashflow": _to_num(chosen.get("operatingCashflow")),
            },
        )


def _to_num(v: Any) -> float | int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if not s or s.lower() == "none":
        return None
    try:
        i = int(s)
        return i
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


@dataclass(frozen=True)
class FinancialsService:
    cache: JSONCache
    provider: FinancialsProvider
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def _key(self, symbol: str, quarter: str) -> str:
        return f"financials:{symbol}:{quarter.upper()}"

    def get_quarter(self, symbol: str, quarter: str) -> FinancialQuarter:
        key = self._key(symbol, quarter)
        hit = self.cache.get_json(key)
        if hit:
            return FinancialQuarter.model_validate(hit)
        fq = self.provider.fetch_quarter(symbol=symbol, quarter=quarter)
        self.cache.set_json(key, fq.model_dump(mode="json"), ttl_seconds=self.ttl_seconds)
        return fq
