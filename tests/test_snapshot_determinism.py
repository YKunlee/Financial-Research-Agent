from __future__ import annotations

from datetime import date, datetime, timezone

from finresearch_agent.models import (
    CompanyIdentity,
    FinancialQuarter,
    MarketBar,
    MarketData,
    RiskMetrics,
    RuleResults,
    TechnicalIndicators,
)
from finresearch_agent.snapshot.builder import build_snapshot


def test_analysis_id_is_stable_for_same_inputs(tmp_path):
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    identity = CompanyIdentity(
        symbol="AAPL", market="NASDAQ", company_name="Apple Inc.", matched_on="ticker", query="AAPL"
    )
    market = MarketData(
        symbol="AAPL",
        source="test",
        data_timestamp=ts,
        bars=[
            MarketBar(date=date(2025, 12, 30), open=1, high=1, low=1, close=100, volume=1),
            MarketBar(date=date(2025, 12, 31), open=1, high=1, low=1, close=110, volume=1),
        ],
    )
    technicals = TechnicalIndicators(
        algo_version="metrics_v1.0.0",
        as_of=date(2025, 12, 31),
        ma_20=None,
        ma_50=None,
        volatility_20=None,
        max_drawdown=-0.0909090909,
    )
    risk = RiskMetrics(algo_version="risk_v1.0.0", as_of=date(2025, 12, 31), sharpe_20=None, var_95_20=None)
    rules = RuleResults(rule_version="risk_rules_v1", flags=[])
    financials = [
        FinancialQuarter(
            symbol="AAPL",
            quarter="2025Q4",
            source="test",
            data_timestamp=ts,
            source_timestamp=None,
            values={"totalRevenue": 1},
        )
    ]

    s1 = build_snapshot(
        identity=identity,
        as_of=date(2025, 12, 31),
        market_data=market,
        financials=financials,
        technicals=technicals,
        risk=risk,
        rules=rules,
        persist_dir=tmp_path,
    )
    s2 = build_snapshot(
        identity=identity,
        as_of=date(2025, 12, 31),
        market_data=market,
        financials=financials,
        technicals=technicals,
        risk=risk,
        rules=rules,
        persist_dir=tmp_path,
    )
    assert s1.analysis_id == s2.analysis_id


def test_analysis_id_changes_when_inputs_change(tmp_path):
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    identity = CompanyIdentity(
        symbol="AAPL", market="NASDAQ", company_name="Apple Inc.", matched_on="ticker", query="AAPL"
    )
    market = MarketData(
        symbol="AAPL",
        source="test",
        data_timestamp=ts,
        bars=[MarketBar(date=date(2025, 12, 31), open=1, high=1, low=1, close=110, volume=1)],
    )
    rules = RuleResults(rule_version="risk_rules_v1", flags=[])
    base = dict(
        identity=identity,
        as_of=date(2025, 12, 31),
        market_data=market,
        financials=[],
        risk=RiskMetrics(algo_version="risk_v1.0.0", as_of=date(2025, 12, 31), sharpe_20=None, var_95_20=None),
        rules=rules,
        persist_dir=tmp_path,
    )
    s1 = build_snapshot(
        technicals=TechnicalIndicators(
            algo_version="metrics_v1.0.0",
            as_of=date(2025, 12, 31),
            ma_20=None,
            ma_50=None,
            volatility_20=None,
            max_drawdown=-0.1,
        ),
        **base,
    )
    s2 = build_snapshot(
        technicals=TechnicalIndicators(
            algo_version="metrics_v1.0.0",
            as_of=date(2025, 12, 31),
            ma_20=None,
            ma_50=None,
            volatility_20=None,
            max_drawdown=-0.2,
        ),
        **base,
    )
    assert s1.analysis_id != s2.analysis_id
