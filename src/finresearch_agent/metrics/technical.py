from __future__ import annotations

from datetime import date

import numpy as np

from finresearch_agent.constants import METRICS_ALGO_VERSION
from finresearch_agent.models import MarketData, TechnicalIndicators


def compute_technical_indicators(market_data: MarketData, as_of: date) -> TechnicalIndicators:
    bars = [b for b in market_data.bars if b.date <= as_of]
    bars.sort(key=lambda b: b.date)
    closes = np.array([b.close for b in bars], dtype=float)

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


def _sma(series: np.ndarray, window: int) -> float | None:
    if series.size < window:
        return None
    return float(series[-window:].mean())


def _returns(series: np.ndarray) -> np.ndarray:
    if series.size < 2:
        return np.array([], dtype=float)
    return series[1:] / series[:-1] - 1.0


def _volatility(series: np.ndarray, window: int) -> float | None:
    r = _returns(series)
    if r.size < window:
        return None
    return float(np.std(r[-window:], ddof=1))


def _max_drawdown(series: np.ndarray) -> float | None:
    if series.size < 2:
        return None
    running_max = np.maximum.accumulate(series)
    drawdowns = series / running_max - 1.0
    return float(drawdowns.min())
