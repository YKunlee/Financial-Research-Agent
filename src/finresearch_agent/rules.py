# 定义第一版风险规则集 RISK_RULES_V1，并基于技术指标与风险指标生成带证据信息的 RiskFlag 列表和 RuleResults 结果对象。
from __future__ import annotations

import operator
from finresearch_agent.constants import RISK_RULES_VERSION
from finresearch_agent.models import RiskFlag, RuleResults


RISK_RULES_V1 = [
    {
        "code": "DRAWDOWN_HIGH",
        "severity": "high",
        "title": "Large peak-to-trough drawdown",
        "field": "technicals.max_drawdown",
        "op": "<=",
        "threshold": -0.2,
        "details": "Max drawdown at or below -20% over the available window.",
    },
    {
        "code": "VOLATILITY_HIGH",
        "severity": "medium",
        "title": "Elevated short-term volatility",
        "field": "technicals.volatility_20",
        "op": ">=",
        "threshold": 0.04,
        "details": "20-day return volatility at or above 4% (daily).",
    },
    {
        "code": "SHARPE_NEGATIVE",
        "severity": "medium",
        "title": "Negative short-term Sharpe",
        "field": "risk.sharpe_20",
        "op": "<",
        "threshold": 0.0,
        "details": "20-day Sharpe ratio below 0 indicates unfavorable risk-adjusted returns.",
    },
    {
        "code": "VAR_TAIL_RISK",
        "severity": "high",
        "title": "Large 1-day VaR (95%)",
        "field": "risk.var_95_20",
        "op": "<=",
        "threshold": -0.05,
        "details": "Historical 1-day VaR at 95% at or below -5% based on the last 20 returns.",
    },
]


def apply_risk_rules(technicals, risk) -> RuleResults:
    flags: list[RiskFlag] = []
    ctx = {"technicals": technicals.model_dump(mode="python"), "risk": risk.model_dump(mode="python")}
    for rule in RISK_RULES_V1:
        value = _get_field(ctx, rule["field"])
        if value is None:
            continue
        if _compare(float(value), rule["op"], float(rule["threshold"])):
            flags.append(
                RiskFlag(
                    code=rule["code"],
                    severity=rule["severity"],
                    title=rule["title"],
                    details=rule["details"],
                    evidence={"field": rule["field"], "value": value, "threshold": rule["threshold"]},
                )
            )

    return RuleResults(rule_version=RISK_RULES_VERSION, flags=flags)


def _get_field(ctx: dict, dotted: str):
    cur = ctx
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _compare(v: float, op: str, t: float) -> bool:
    ops = {
        "<=": operator.le,
        "<": operator.lt,
        ">=": operator.ge,
        ">": operator.gt,
        "==": operator.eq,
    }
    if op not in ops:
        raise ValueError(f"Unsupported op: {op}")
    return ops[op](v, t)
