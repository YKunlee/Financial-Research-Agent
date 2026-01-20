# 使用 Pydantic 定义公司、行情、财报、技术指标、风险指标、规则标记和完整分析快照等核心数据模型，约束字段类型与结构。
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyIdentity(_Base):
    symbol: str
    market: str
    company_name: str
    matched_on: Literal["ticker", "company_name", "alias"]
    query: str


class MarketBar(_Base):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketData(_Base):
    symbol: str
    source: str
    data_timestamp: datetime
    bars: list[MarketBar]


class FinancialQuarter(_Base):
    symbol: str
    quarter: str  # YYYYQn
    source: str
    data_timestamp: datetime
    source_timestamp: datetime | None = Field(
        default=None, description="Timestamp from the upstream source payload, if available."
    )
    values: dict[str, float | int | None] = Field(
        description="Raw financial values only; no derived metrics."
    )


class TechnicalIndicators(_Base):
    algo_version: str
    as_of: date
    ma_20: float | None
    ma_50: float | None
    volatility_20: float | None
    max_drawdown: float | None


class RiskMetrics(_Base):
    algo_version: str
    as_of: date
    sharpe_20: float | None
    var_95_20: float | None


class RiskFlag(_Base):
    code: str
    severity: Literal["low", "medium", "high"]
    title: str
    details: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class RuleResults(_Base):
    rule_version: str
    flags: list[RiskFlag]


class AnalysisSnapshot(_Base):
    analysis_id: str
    symbol: str
    market: str
    company_name: str
    as_of: date
    data_timestamps: dict[str, datetime]
    algo_versions: dict[str, str]
    identity: CompanyIdentity
    market_data: MarketData
    financials: list[FinancialQuarter] = Field(default_factory=list)
    technicals: TechnicalIndicators
    risk: RiskMetrics
    rules: RuleResults
