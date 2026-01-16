from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from finresearch_agent.config import Settings
from finresearch_agent.ipo.models import IpoEntry, IpoRisk


_NotDisclosed = "Not disclosed"


def enrich_entry_from_excerpts(entry: IpoEntry, *, raw: dict[str, Any], settings: Settings) -> IpoEntry:
    excerpts = _collect_excerpts(raw)
    if not excerpts:
        return entry

    if not settings.openai_api_key:
        return entry

    extracted = _extract_structured(excerpts, settings)
    if not extracted:
        return entry

    industry = extracted.get("industry")
    business_summary = extracted.get("business_summary")
    risks = extracted.get("risks")

    update: dict[str, Any] = entry.model_dump()
    if isinstance(industry, str) and industry != _NotDisclosed and entry.industry == _NotDisclosed:
        update["industry"] = industry
    if (
        isinstance(business_summary, str)
        and business_summary != _NotDisclosed
        and entry.business_summary == _NotDisclosed
    ):
        update["business_summary"] = business_summary

    if isinstance(risks, list):
        merged = list(entry.key_risks)
        for r in risks:
            if isinstance(r, IpoRisk) and r not in merged:
                merged.append(r)
        update["key_risks"] = merged

    return IpoEntry.model_validate(update)


def _collect_excerpts(raw: dict[str, Any]) -> dict[Literal["prospectus", "announcement"], str]:
    out: dict[Literal["prospectus", "announcement"], str] = {}

    prospectus = raw.get("prospectus_excerpt") or raw.get("prospectus_excerpts")
    if isinstance(prospectus, str) and prospectus.strip():
        out["prospectus"] = prospectus.strip()
    elif isinstance(prospectus, list):
        text = "\n\n".join([s.strip() for s in prospectus if isinstance(s, str) and s.strip()])
        if text:
            out["prospectus"] = text

    announcement = raw.get("announcement_excerpt") or raw.get("announcement_excerpts")
    if isinstance(announcement, str) and announcement.strip():
        out["announcement"] = announcement.strip()
    elif isinstance(announcement, list):
        text = "\n\n".join([s.strip() for s in announcement if isinstance(s, str) and s.strip()])
        if text:
            out["announcement"] = text

    return out


def _extract_structured(
    excerpts: dict[Literal["prospectus", "announcement"], str], settings: Settings
) -> dict[str, Any] | None:
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)
    sys = SystemMessage(
        content=(
            "You extract fields for an HK IPO research report.\n"
            "Rules:\n"
            "- Use ONLY the provided text excerpts.\n"
            "- Do NOT add facts.\n"
            "- For each field, either output an EXACT quote copied from the excerpts, or 'Not disclosed'.\n"
            "- For risks, output only risk phrases that appear verbatim in the text.\n"
            "- Output must be strict JSON only.\n"
        )
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            sys,
            (
                "human",
                "Prospectus excerpt (may be empty):\n{prospectus}\n\n"
                "Announcement excerpt (may be empty):\n{announcement}\n\n"
                "Return JSON:\n"
                "{\n"
                '  \"industry\": string,\n'
                '  \"business_summary\": string,\n'
                '  \"use_of_proceeds\": string,\n'
                '  \"risks\": [ {\"risk_type\": string, \"source\": \"prospectus\"|\"announcement\"} ]\n'
                "}\n",
            ),
        ]
    )

    chain = prompt | model
    out = chain.invoke(
        {
            "prospectus": excerpts.get("prospectus", ""),
            "announcement": excerpts.get("announcement", ""),
        }
    )
    text = getattr(out, "content", str(out)).strip()

    try:
        payload = json.loads(text)
    except Exception:
        return None

    _validate_extractive(payload, excerpts)

    risks: list[IpoRisk] = []
    for item in payload.get("risks", []) or []:
        if not isinstance(item, dict):
            continue
        risk_type = item.get("risk_type")
        source = item.get("source")
        if (
            isinstance(risk_type, str)
            and risk_type != _NotDisclosed
            and source in {"prospectus", "announcement"}
            and risk_type in excerpts.get(source, "")
        ):
            risks.append(IpoRisk(risk_type=risk_type, source=source))

    return {
        "industry": payload.get("industry"),
        "business_summary": payload.get("business_summary"),
        "use_of_proceeds": payload.get("use_of_proceeds"),
        "risks": risks,
    }


def _validate_extractive(payload: dict[str, Any], excerpts: dict[str, str]) -> None:
    all_text = "\n\n".join(excerpts.values())

    for key in ("industry", "business_summary", "use_of_proceeds"):
        val = payload.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            raise ValueError(f"Invalid type for {key}.")
        if val == _NotDisclosed:
            continue
        if val not in all_text:
            raise ValueError(f"Non-extractive value for {key}.")

    risks = payload.get("risks")
    if risks is None:
        return
    if not isinstance(risks, list):
        raise ValueError("Invalid risks list.")
    for item in risks:
        if not isinstance(item, dict):
            raise ValueError("Invalid risk item.")
        risk_type = item.get("risk_type")
        source = item.get("source")
        if not isinstance(risk_type, str):
            raise ValueError("Invalid risk_type.")
        if risk_type == _NotDisclosed:
            continue
        if source not in {"prospectus", "announcement"}:
            raise ValueError("Invalid risk source.")
        if risk_type not in excerpts.get(source, ""):
            raise ValueError("Non-extractive risk_type.")

