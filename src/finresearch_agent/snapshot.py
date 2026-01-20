# 将公司身份、行情、财报与指标等组装成 AnalysisSnapshot，计算稳定的 analysis_id 哈希并在需要时持久化为 JSON 快照文件。
from __future__ import annotations

import hashlib
from pathlib import Path

from finresearch_agent.models import (
    AnalysisSnapshot,
    CompanyIdentity,
    FinancialQuarter,
    MarketData,
    RiskMetrics,
    RuleResults,
    TechnicalIndicators,
)
from finresearch_agent.utils import canonical_dumps, json_dumps


def build_snapshot(
    *,
    identity: CompanyIdentity,
    as_of,
    market_data: MarketData,
    financials: list[FinancialQuarter],
    technicals: TechnicalIndicators,
    risk: RiskMetrics,
    rules: RuleResults,
    persist_dir: str | Path | None = None,
) -> AnalysisSnapshot:
    data_timestamps = {
        "market_data": market_data.data_timestamp,
        "financials": max((f.data_timestamp for f in financials), default=market_data.data_timestamp),
    }
    algo_versions = {
        "metrics": technicals.algo_version,
        "risk": risk.algo_version,
        "rules": rules.rule_version,
    }

    seed = {
        "symbol": identity.symbol,
        "market": identity.market,
        "company_name": identity.company_name,
        "as_of": as_of,
        "data_timestamps": data_timestamps,
        "algo_versions": algo_versions,
        "identity": identity.model_dump(mode="json"),
        "market_data": market_data.model_dump(mode="json"),
        "financials": [f.model_dump(mode="json") for f in financials],
        "technicals": technicals.model_dump(mode="json"),
        "risk": risk.model_dump(mode="json"),
        "rules": rules.model_dump(mode="json"),
    }
    analysis_id = _hash_seed(seed)

    snapshot = AnalysisSnapshot(
        analysis_id=analysis_id,
        symbol=identity.symbol,
        market=identity.market,
        company_name=identity.company_name,
        as_of=as_of,
        data_timestamps=data_timestamps,
        algo_versions=algo_versions,
        identity=identity,
        market_data=market_data,
        financials=financials,
        technicals=technicals,
        risk=risk,
        rules=rules,
    )

    if persist_dir is not None:
        _persist_snapshot(snapshot, persist_dir)

    return snapshot


def _hash_seed(seed: dict) -> str:
    canon = canonical_dumps(seed).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _persist_snapshot(snapshot: AnalysisSnapshot, persist_dir: str | Path) -> None:
    p = Path(persist_dir)
    p.mkdir(parents=True, exist_ok=True)
    out = p / f"{snapshot.analysis_id}.json"
    if out.exists():
        return
    out.write_text(json_dumps(snapshot.model_dump(mode="json")), encoding="utf-8")
