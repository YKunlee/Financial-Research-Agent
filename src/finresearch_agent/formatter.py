# 根据 AnalysisSnapshot 与解释文本生成 CLI 文本视图和结构化 JSON 结果，供终端展示或下游系统消费。
from __future__ import annotations

from finresearch_agent.models import AnalysisSnapshot


def risk_level_from_flags(snapshot: AnalysisSnapshot) -> str:
    severities = {f.severity for f in snapshot.rules.flags}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def format_result(snapshot: AnalysisSnapshot, explanation: str) -> dict:
    facts = {
        "analysis_id": snapshot.analysis_id,
        "symbol": snapshot.symbol,
        "market": snapshot.market,
        "company_name": snapshot.company_name,
        "as_of": snapshot.as_of.isoformat(),
        "risk_level": risk_level_from_flags(snapshot),
        "algo_versions": snapshot.algo_versions,
        "data_timestamps": {k: v.isoformat() for k, v in snapshot.data_timestamps.items()},
        "risk_flags": [f.model_dump(mode="json") for f in snapshot.rules.flags],
        "snapshot": snapshot.model_dump(mode="json"),
    }
    return {"facts": facts, "explanation": explanation}


def format_cli(snapshot: AnalysisSnapshot, explanation: str) -> str:
    risk_level = risk_level_from_flags(snapshot)
    snapshot_path = f"snapshots/{snapshot.analysis_id}.json"
    lines = [
        f"symbol={snapshot.symbol} market={snapshot.market} as_of={snapshot.as_of.isoformat()}",
        f"risk_level={risk_level} analysis_id={snapshot.analysis_id}",
        f"versions={snapshot.algo_versions}",
        "",
        f"Facts (structured): {snapshot_path}",
        "",
        "Explanation:",
        explanation.strip(),
    ]
    return "\n".join(lines)
