# 负责港股 IPO 相关数据的清洗规范化、风险与业务描述抽取（可选使用 LLM），并通过命令行生成周度结构化 IPO 报告 JSON。
from __future__ import annotations

import re
import json
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv

from finresearch_agent.config import Settings, get_settings
from finresearch_agent.utils import get_iso_week_string, json_dumps, safe_strip


# --- Models ---

class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IpoRisk(_Base):
    risk_type: str
    source: Literal["prospectus", "announcement"]


class IpoEntry(_Base):
    company_name: str
    status: str
    expected_listing_date: date | None = None
    industry: str = "Not disclosed"
    business_summary: str = "Not disclosed"
    key_risks: list[IpoRisk] = Field(default_factory=list)
    data_source: str
    as_of_date: date


class IpoReport(_Base):
    market: Literal["HK"]
    week: str  # YYYY-WW
    ipos: list[IpoEntry]
    disclaimer: str


# --- Normalization ---

_DATE_RE = re.compile(r"^(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})$")


def _parse_date_strict(value: str) -> date | None:
    m = _DATE_RE.match(value.strip())
    if not m:
        return None
    y = int(m.group("y"))
    mo = int(m.group("m"))
    d = int(m.group("d"))
    return date(y, mo, d)


def normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    raw = value.strip().lower().replace("-", "_").replace(" ", "_")
    raw = re.sub(r"_+", "_", raw)

    mapping = {
        "subscription_open": "subscription_open",
        "open_for_subscription": "subscription_open",
        "opens_for_subscription": "subscription_open",
        "subscription_upcoming": "subscription_upcoming",
        "upcoming_subscription": "subscription_upcoming",
        "hearing_passed": "hearing_passed",
        "passed_hearing": "hearing_passed",
        "expected_listing": "expected_listing",
        "expected_to_list": "expected_listing",
        "listing_expected": "expected_listing",
    }
    if raw in mapping:
        return mapping[raw]
    allowed_like = {"subscription_open", "subscription_upcoming", "hearing_passed", "expected_listing"}
    return raw if raw in allowed_like else None


def normalize_risks(value: Any) -> list[IpoRisk]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    risks: list[IpoRisk] = []
    for item in value:
        if isinstance(item, IpoRisk):
            risks.append(item)
            continue
        if not isinstance(item, dict):
            continue
        risk_type = item.get("risk_type")
        source = item.get("source")
        if not isinstance(risk_type, str) or not risk_type.strip():
            continue
        if source not in {"prospectus", "announcement"}:
            continue
        risks.append(IpoRisk(risk_type=risk_type.strip(), source=source))
    return risks


def normalize_ipo_record(record: dict[str, Any]) -> dict[str, Any]:
    company_name = (
        record.get("company_name")
        or record.get("name")
        or record.get("issuer_name")
        or record.get("company")
        or ""
    )
    if not isinstance(company_name, str) or not company_name.strip():
        raise ValueError("Missing company_name.")

    expected_listing_date: date | None = None
    for key in ("expected_listing_date", "listing_date", "expected_list_date", "expected_date"):
        if key not in record:
            continue
        v = record.get(key)
        if isinstance(v, date):
            expected_listing_date = v
            break
        if isinstance(v, str):
            parsed = _parse_date_strict(v)
            if parsed is not None:
                expected_listing_date = parsed
                break

    normalized: dict[str, Any] = {
        "company_name": " ".join(company_name.strip().split()),
        "status": normalize_status(record.get("status") or record.get("ipo_status")),
        "expected_listing_date": expected_listing_date,
        "industry": record.get("industry") or record.get("sector"),
        "business_summary": record.get("business_summary"),
        "business_description": record.get("business_description"),
        "use_of_proceeds": record.get("use_of_proceeds"),
        "data_source": record.get("data_source") or record.get("source"),
    }

    normalized["key_risks"] = normalize_risks(record.get("key_risks") or record.get("risks"))
    return normalized


# --- LLM Extraction ---

def enrich_entry_from_excerpts(entry: IpoEntry, *, raw: dict[str, Any], settings: Settings) -> IpoEntry:
    excerpts = _collect_excerpts(raw)
    if not excerpts or not settings.openai_api_key:
        return entry

    extracted = _extract_structured(excerpts, settings)
    if not extracted:
        return entry

    industry = extracted.get("industry")
    business_summary = extracted.get("business_summary")
    risks = extracted.get("risks")

    update: dict[str, Any] = entry.model_dump()
    if isinstance(industry, str) and industry != "Not disclosed" and entry.industry == "Not disclosed":
        update["industry"] = industry
    if (
        isinstance(business_summary, str)
        and business_summary != "Not disclosed"
        and entry.business_summary == "Not disclosed"
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
    for key, target in [("prospectus_excerpt", "prospectus"), ("prospectus_excerpts", "prospectus"),
                        ("announcement_excerpt", "announcement"), ("announcement_excerpts", "announcement")]:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            out[target] = val.strip() if target not in out else out[target] + "\n\n" + val.strip()
        elif isinstance(val, list):
            text = "\n\n".join([s.strip() for s in val if isinstance(s, str) and s.strip()])
            if text:
                out[target] = text if target not in out else out[target] + "\n\n" + text
    return out


def _extract_structured(excerpts: dict[Literal["prospectus", "announcement"], str], settings: Settings) -> dict[str, Any] | None:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage
    from langchain_core.prompts import ChatPromptTemplate

    model = ChatOpenAI(
        api_key=settings.openai_api_key, 
        model=settings.openai_model, 
        temperature=0,
        timeout=60,
        max_retries=2
    )
    sys = SystemMessage(content=(
        "You extract fields for an HK IPO research report.\n"
        "Rules:\n- Use ONLY the provided text excerpts.\n- Do NOT add facts.\n"
        "- For each field, either output an EXACT quote copied from the excerpts, or 'Not disclosed'.\n"
        "- For risks, output only risk phrases that appear verbatim in the text.\n- Output must be strict JSON only.\n"
    ))
    prompt = ChatPromptTemplate.from_messages([
        sys, ("human", "Prospectus excerpt (may be empty):\n{prospectus}\n\nAnnouncement excerpt (may be empty):\n{announcement}\n\nReturn JSON:\n{{\n  \"industry\": string,\n  \"business_summary\": string,\n  \"use_of_proceeds\": string,\n  \"risks\": [ {{\"risk_type\": string, \"source\": \"prospectus\"|\"announcement\"}} ]\n}}\n")
    ])
    chain = prompt | model
    out = chain.invoke(
        {"prospectus": excerpts.get("prospectus", ""), "announcement": excerpts.get("announcement", "")},
        config={"timeout": 60}
    )
    text = getattr(out, "content", str(out)).strip()
    try:
        payload = json.loads(text)
    except Exception:
        return None

    _validate_extractive(payload, excerpts)
    risks: list[IpoRisk] = []
    for item in payload.get("risks", []) or []:
        if isinstance(item, dict):
            risk_type, source = item.get("risk_type"), item.get("source")
            if isinstance(risk_type, str) and risk_type != "Not disclosed" and source in {"prospectus", "announcement"} and risk_type in excerpts.get(source, ""):
                risks.append(IpoRisk(risk_type=risk_type, source=source))
    return {"industry": payload.get("industry"), "business_summary": payload.get("business_summary"), "use_of_proceeds": payload.get("use_of_proceeds"), "risks": risks}


def _validate_extractive(payload: dict[str, Any], excerpts: dict[str, str]) -> None:
    all_text = "\n\n".join(excerpts.values())
    for key in ("industry", "business_summary", "use_of_proceeds"):
        val = payload.get(key)
        if isinstance(val, str) and val != "Not disclosed" and val not in all_text:
            raise ValueError(f"Non-extractive value for {key}.")
    risks = payload.get("risks")
    if isinstance(risks, list):
        for item in risks:
            if isinstance(item, dict):
                rt, src = item.get("risk_type"), item.get("source")
                if isinstance(rt, str) and rt != "Not disclosed" and rt not in excerpts.get(src, ""):
                    raise ValueError("Non-extractive risk_type.")


# --- Report Building ---

DEFAULT_ALLOWED_STATUSES = {"subscription_open", "subscription_upcoming", "hearing_passed", "expected_listing"}

def build_hk_ipo_report(
    records: Iterable[dict[str, Any]],
    *,
    as_of_date: date,
    week: str,
    data_source_default: str = "Public disclosure",
    allowed_statuses: set[str] | None = None,
    settings: Settings | None = None,
    use_llm_extraction: bool = False,
) -> IpoReport:
    allowed = allowed_statuses or set(DEFAULT_ALLOWED_STATUSES)
    entries: list[IpoEntry] = []
    for raw in records:
        norm = normalize_ipo_record(raw)
        status = norm.get("status")
        if status is None or (allowed and status not in allowed):
            continue
        industry = safe_strip(norm.get("industry")) or "Not disclosed"
        business_summary = safe_strip(norm.get("business_summary")) or safe_strip(norm.get("business_description")) or "Not disclosed"
        entry = IpoEntry(
            company_name=norm["company_name"], status=status, expected_listing_date=norm.get("expected_listing_date"),
            industry=industry, business_summary=business_summary, key_risks=norm.get("key_risks") or [],
            data_source=safe_strip(norm.get("data_source")) or data_source_default, as_of_date=as_of_date
        )
        if use_llm_extraction and settings is not None:
            try:
                entry = enrich_entry_from_excerpts(entry, raw=raw, settings=settings)
            except Exception:
                pass
        entries.append(entry)
    return IpoReport(market="HK", week=week, ipos=entries, disclaimer="This information is based on public IPO disclosures and is for research purposes only.")


# --- CLI ---

def _load_records(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(payload, list):
        return payload, {}
    if isinstance(payload, dict):
        if isinstance(payload.get("ipos"), list):
            return payload["ipos"], payload
        if isinstance(payload.get("records"), list):
            return payload["records"], payload
    raise ValueError("Input JSON must be a list, or an object containing 'ipos' (or 'records').")


def ipo_main() -> None:
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(
        prog="finresearch-ipo",
        description="HK IPO research report generator (code-first; consumes provided calendar/details/excerpts).",
    )
    parser.add_argument("--input", required=True, help="Path to JSON input (list or {ipos:[...]}).")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="YYYY-MM-DD (default: today).")
    parser.add_argument("--data-source", default=None, help="Default data_source when missing.")
    parser.add_argument("--use-llm", action="store_true", help="Extract missing fields/risks from excerpts.")
    parser.add_argument("--output", default=None, help="Optional output JSON file path.")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records, meta = _load_records(payload)

    data_source_default = args.data_source or meta.get("data_source") or "Public disclosure"
    week = meta.get("week") or get_iso_week_string(as_of)

    report = build_hk_ipo_report(
        records,
        as_of_date=as_of,
        week=week,
        data_source_default=data_source_default,
        settings=settings,
        use_llm_extraction=bool(args.use_llm),
    )

    out_json = json_dumps(report.model_dump(mode="json"))
    if args.output:
        Path(args.output).write_text(out_json, encoding="utf-8")
    else:
        print(out_json)


if __name__ == "__main__":
    ipo_main()
