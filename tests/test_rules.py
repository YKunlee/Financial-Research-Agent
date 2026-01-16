from __future__ import annotations

from datetime import date

from finresearch_agent.models import RiskMetrics, TechnicalIndicators
from finresearch_agent.rules.engine import apply_risk_rules


def test_rules_are_versioned_and_structured():
    technicals = TechnicalIndicators(
        algo_version="metrics_v1.0.0",
        as_of=date(2025, 1, 1),
        ma_20=None,
        ma_50=None,
        volatility_20=0.05,
        max_drawdown=-0.25,
    )
    risk = RiskMetrics(
        algo_version="risk_v1.0.0", as_of=date(2025, 1, 1), sharpe_20=-0.1, var_95_20=-0.06
    )
    out = apply_risk_rules(technicals, risk)
    assert out.rule_version == "risk_rules_v1"
    assert len(out.flags) >= 1
    assert all(isinstance(f.code, str) and f.evidence for f in out.flags)
