from __future__ import annotations

import re

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from finresearch_agent.config import Settings
from finresearch_agent.models import AnalysisSnapshot
from finresearch_agent.utils import json_dumps


def explain_snapshot(snapshot: AnalysisSnapshot, settings: Settings) -> str:
    if settings.openai_api_key:
        try:
            return _explain_with_openai(snapshot, settings)
        except Exception:
            # Last-resort fallback: deterministic explanation never computes new numbers.
            return _deterministic_explanation(snapshot)
    return _deterministic_explanation(snapshot)


def _explain_with_openai(snapshot: AnalysisSnapshot, settings: Settings) -> str:
    from langchain_openai import ChatOpenAI

    snapshot_json = json_dumps(snapshot.model_dump(mode="json"))
    model = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)

    sys = SystemMessage(
        content=(
            "You are an explain-only stock research assistant.\n"
            "Rules:\n"
            "- You MAY ONLY use the provided JSON snapshot.\n"
            "- Do NOT do any math or numeric estimation.\n"
            "- Do NOT introduce any new numeric values.\n"
            "- Prefer qualitative phrasing; avoid digits except for analysis_id and version strings.\n"
            "- Cite analysis_id and versions exactly as given.\n"
        )
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            sys,
            ("human", "Explain this analysis snapshot for a human reader:\n\n{snapshot_json}"),
        ]
    )
    chain = prompt | model
    out = chain.invoke({"snapshot_json": snapshot_json})
    text = getattr(out, "content", str(out)).strip()
    _validate_no_new_numbers(snapshot_json, text)
    _validate_required_citations(snapshot, text)
    return text


def _deterministic_explanation(snapshot: AnalysisSnapshot) -> str:
    parts: list[str] = []
    parts.append(
        f"analysis_id={snapshot.analysis_id}; "
        f"versions={snapshot.algo_versions.get('metrics')},{snapshot.algo_versions.get('risk')},"
        f"{snapshot.algo_versions.get('rules')}"
    )
    if not snapshot.rules.flags:
        parts.append("No deterministic risk rules were triggered based on the computed metrics in the snapshot.")
        return "\n".join(parts)

    parts.append("Triggered risk flags:")
    for f in snapshot.rules.flags:
        parts.append(f"- {f.severity.upper()}: {f.title} ({f.code})")
    parts.append("This explanation is derived only from the snapshot fields and rule outputs.")
    return "\n".join(parts)


_NUM_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.IGNORECASE)


def _validate_no_new_numbers(snapshot_json: str, response: str) -> None:
    allowed = set(_NUM_RE.findall(snapshot_json))
    found = set(_NUM_RE.findall(response))
    extra = found - allowed
    if extra:
        raise ValueError(f"LLM introduced numeric tokens not present in snapshot: {sorted(extra)[:10]}")


def _validate_required_citations(snapshot: AnalysisSnapshot, response: str) -> None:
    required = [
        snapshot.analysis_id,
        snapshot.algo_versions.get("metrics") or "",
        snapshot.algo_versions.get("risk") or "",
        snapshot.algo_versions.get("rules") or "",
    ]
    missing = [r for r in required if r and r not in response]
    if missing:
        raise ValueError("LLM response missing required citations (analysis_id/versions).")
