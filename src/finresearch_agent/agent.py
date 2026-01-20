# 实现端到端的股票研究代理 StockResearchAgent，负责公司识别、数据抓取、指标计算、风险规则评估与分析快照持久化。
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from finresearch_agent.cache import JSONCache
from finresearch_agent.config import Settings
from finresearch_agent.datasources import FinancialsService, MarketDataService, StooqMarketDataProvider
from finresearch_agent.identify import CompanyResolver
from finresearch_agent.llm import explain_snapshot
from finresearch_agent.metrics import compute_risk_metrics, compute_technical_indicators
from finresearch_agent.models import AnalysisSnapshot
from finresearch_agent.rules import apply_risk_rules
from finresearch_agent.snapshot import build_snapshot
from finresearch_agent.utils import get_calendar_quarter


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
        # Path adjustment for src/finresearch_agent/agent.py
        snapshots_dir = Path(__file__).resolve().parents[2] / "snapshots"
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
            q = get_calendar_quarter(as_of)
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
