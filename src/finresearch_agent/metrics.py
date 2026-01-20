from __future__ import annotations

from datetime import date
import numpy as np

from finresearch_agent.constants import METRICS_ALGO_VERSION, RISK_ALGO_VERSION
from finresearch_agent.models import MarketData, TechnicalIndicators, RiskMetrics
from finresearch_agent.utils import compute_returns, get_closes_array


def compute_technical_indicators(market_data: MarketData, as_of: date) -> TechnicalIndicators:
    closes = get_closes_array(market_data.bars, as_of)

    ma_20 = _sma(closes, 20)
    ma_50 = _sma(closes, 50)
    volatility_20 = _volatility(closes, 20)
    max_drawdown = _max_drawdown(closes)

    return TechnicalIndicators(
        algo_version=METRICS_ALGO_VERSION,
        as_of=as_of,
        ma_20=ma_20,
        ma_50=ma_50,
        volatility_20=volatility_20,
        max_drawdown=max_drawdown,
    )


def compute_risk_metrics(market_data: MarketData, as_of: date) -> RiskMetrics:
    closes = get_closes_array(market_data.bars, as_of)
    r = compute_returns(closes)

    sharpe_20 = _sharpe(r, 20)
    var_95_20 = _historical_var(r, 20, alpha=0.05)

    return RiskMetrics(
        algo_version=RISK_ALGO_VERSION,
        as_of=as_of,
        sharpe_20=sharpe_20,
        var_95_20=var_95_20,
    )


def _sma(series: np.ndarray, window: int) -> float | None:
    if series.size < window:
        return None
    return float(series[-window:].mean())


def _volatility(series: np.ndarray, window: int) -> float | None:
    r = compute_returns(series)
    if r.size < window:
        return None
    return float(np.std(r[-window:], ddof=1))


def _max_drawdown(series: np.ndarray) -> float | None:
    if series.size < 2:
        return None
    running_max = np.maximum.accumulate(series)
    drawdowns = series / running_max - 1.0
    return float(drawdowns.min())


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
