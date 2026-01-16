from __future__ import annotations

from finresearch_agent.constants import RISK_RULES_VERSION
from finresearch_agent.models import RiskFlag, RuleResults
from finresearch_agent.rules.ruleset_v1 import RISK_RULES_V1


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
    if op == "<=":
        return v <= t
    if op == "<":
        return v < t
    if op == ">=":
        return v >= t
    if op == ">":
        return v > t
    if op == "==":
        return v == t
    raise ValueError(f"Unsupported op: {op}")
