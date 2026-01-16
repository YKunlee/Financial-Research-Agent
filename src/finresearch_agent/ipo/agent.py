from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from finresearch_agent.config import Settings
from finresearch_agent.ipo.models import IpoEntry, IpoReport
from finresearch_agent.ipo.normalize import normalize_ipo_record


DEFAULT_ALLOWED_STATUSES = {
    "subscription_open",
    "subscription_upcoming",
    "hearing_passed",
    "expected_listing",
}

_NOT_DISCLOSED = "Not disclosed"


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return None


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
        if status is None:
            continue
        if allowed and status not in allowed:
            continue

        data_source = _safe_text(norm.get("data_source")) or data_source_default

        industry = _safe_text(norm.get("industry")) or _NOT_DISCLOSED
        business_summary = (
            _safe_text(norm.get("business_summary"))
            or _safe_text(norm.get("business_description"))
            or _NOT_DISCLOSED
        )

        key_risks = norm.get("key_risks") or norm.get("risks") or []

        entry = IpoEntry(
            company_name=norm["company_name"],
            status=status,
            expected_listing_date=norm.get("expected_listing_date"),
            industry=industry,
            business_summary=business_summary,
            key_risks=key_risks,
            data_source=data_source,
            as_of_date=as_of_date,
        )

        if use_llm_extraction and settings is not None:
            try:
                from finresearch_agent.ipo.llm_extract import enrich_entry_from_excerpts

                entry = enrich_entry_from_excerpts(entry, raw=raw, settings=settings)
            except Exception:
                # Extraction is best-effort and must never block report generation.
                pass

        entries.append(entry)

    return IpoReport(
        market="HK",
        week=week,
        ipos=entries,
        disclaimer="This information is based on public IPO disclosures and is for research purposes only.",
    )


def iso_week_string(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-{iso.week:02d}"
