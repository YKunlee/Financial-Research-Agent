from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from finresearch_agent.cache.base import JSONCache
from finresearch_agent.config import Settings
from finresearch_agent.datasources.financials import FinancialsService
from finresearch_agent.datasources.market import MarketDataService, StooqMarketDataProvider
from finresearch_agent.identify.resolver import CompanyResolver
from finresearch_agent.llm.explainer import explain_snapshot
from finresearch_agent.metrics.risk import compute_risk_metrics
from finresearch_agent.metrics.technical import compute_technical_indicators
from finresearch_agent.models import AnalysisSnapshot
from finresearch_agent.rules.engine import apply_risk_rules
from finresearch_agent.snapshot.builder import build_snapshot


@dataclass(frozen=True)
class StockResearchAgent:
    settings: Settings
    cache: JSONCache
    resolver: CompanyResolver
    market_data: MarketDataService
    financials: FinancialsService | None = None
    snapshots_dir: Path | None = None

    @classmethod
    def default(cls, *, settings: Settings, cache: JSONCache) -> "StockResearchAgent":
        resolver = CompanyResolver.default()
        provider = StooqMarketDataProvider()
        market_data = MarketDataService(cache=cache, provider=provider)
        snapshots_dir = Path(__file__).resolve().parents[3] / "snapshots"
        return cls(
            settings=settings,
            cache=cache,
            resolver=resolver,
            market_data=market_data,
            financials=None,
            snapshots_dir=snapshots_dir,
        )

    def analyze(self, query: str, as_of: date) -> tuple[AnalysisSnapshot, str]:
        identity = self.resolver.resolve(query)

        lookback_days = 180  # ensures enough trading days for MA(50) on most markets
        start = as_of - timedelta(days=lookback_days)
        market = self.market_data.get_daily_range(identity.symbol, start=start, end=as_of, min_bars=60)

        technicals = compute_technical_indicators(market, as_of=as_of)
        risk = compute_risk_metrics(market, as_of=as_of)
        rules = apply_risk_rules(technicals, risk)

        financials = []
        if self.financials is not None:
            q = _calendar_quarter(as_of)
            try:
                financials = [self.financials.get_quarter(identity.symbol, q)]
            except Exception:
                financials = []

        snapshot = build_snapshot(
            identity=identity,
            as_of=as_of,
            market_data=market,
            financials=financials,
            technicals=technicals,
            risk=risk,
            rules=rules,
            persist_dir=self.snapshots_dir,
        )
        explanation = explain_snapshot(snapshot, self.settings)
        return snapshot, explanation


def _calendar_quarter(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}"
