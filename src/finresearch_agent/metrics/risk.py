from __future__ import annotations

from datetime import date

import numpy as np

from finresearch_agent.constants import RISK_ALGO_VERSION
from finresearch_agent.models import MarketData, RiskMetrics


def compute_risk_metrics(market_data: MarketData, as_of: date) -> RiskMetrics:
    bars = [b for b in market_data.bars if b.date <= as_of]
    bars.sort(key=lambda b: b.date)
    closes = np.array([b.close for b in bars], dtype=float)
    r = _returns(closes)

    sharpe_20 = _sharpe(r, 20)
    var_95_20 = _historical_var(r, 20, alpha=0.05)

    return RiskMetrics(
        algo_version=RISK_ALGO_VERSION,
        as_of=as_of,
        sharpe_20=sharpe_20,
        var_95_20=var_95_20,
    )


def _returns(series: np.ndarray) -> np.ndarray:
    if series.size < 2:
        return np.array([], dtype=float)
    return series[1:] / series[:-1] - 1.0


def _sharpe(returns: np.ndarray, window: int, risk_free_daily: float = 0.0) -> float | None:
    if returns.size < window:
        return None
    r = returns[-window:] - risk_free_daily
    std = np.std(r, ddof=1)
    if std == 0:
        return None
    mean = np.mean(r)
    return float(mean / std * np.sqrt(252.0))


def _historical_var(returns: np.ndarray, window: int, alpha: float) -> float | None:
    if returns.size < window:
        return None
    r = np.sort(returns[-window:])
    idx = int(np.floor(alpha * (r.size - 1)))
    return float(r[idx])
