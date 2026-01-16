from __future__ import annotations

import re
from datetime import date
from typing import Any

from finresearch_agent.ipo.models import IpoRisk


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

    # Allow already-normalized inputs outside our mapping.
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

