from __future__ import annotations

from datetime import date

import pytest

from finresearch_agent.ipo.agent import build_hk_ipo_report, iso_week_string
from finresearch_agent.ipo.normalize import normalize_ipo_record, normalize_status


def test_normalize_status_mapping():
    assert normalize_status("Subscription Open") == "subscription_open"
    assert normalize_status("hearing-passed") == "hearing_passed"
    assert normalize_status("expected_to_list") == "expected_listing"
    assert normalize_status("unknown") is None


def test_normalize_ipo_record_date_strict():
    rec = normalize_ipo_record(
        {
            "company_name": " Example   Co ",
            "status": "subscription_open",
            "expected_listing_date": "2026-01-20",
        }
    )
    assert rec["company_name"] == "Example Co"
    assert rec["expected_listing_date"] == date(2026, 1, 20)


def test_build_hk_ipo_report_schema_and_defaults():
    as_of = date(2026, 1, 16)
    week = iso_week_string(as_of)
    report = build_hk_ipo_report(
        [
            {
                "company_name": "Alpha Ltd",
                "status": "Subscription Open",
                "expected_listing_date": "2026-01-20",
                "industry": "Retail",
                "business_description": "Retail operator focused on XYZ.",
                "risks": [{"risk_type": "Regulatory changes", "source": "prospectus"}],
                "data_source": "HKEX",
            },
            {
                "company_name": "Beta Ltd",
                "status": "withdrawn",
            },
            {
                "company_name": "Gamma Ltd",
                "status": "expected_listing",
            },
        ],
        as_of_date=as_of,
        week=week,
        data_source_default="Public disclosure",
    )

    assert report.market == "HK"
    assert report.week == week
    assert len(report.ipos) == 2  # withdrawn filtered out

    alpha = report.ipos[0]
    assert alpha.company_name == "Alpha Ltd"
    assert alpha.status == "subscription_open"
    assert alpha.expected_listing_date == date(2026, 1, 20)
    assert alpha.industry == "Retail"
    assert alpha.business_summary == "Retail operator focused on XYZ."
    assert alpha.key_risks[0].risk_type == "Regulatory changes"
    assert alpha.key_risks[0].source == "prospectus"
    assert alpha.data_source == "HKEX"
    assert alpha.as_of_date == as_of

    gamma = report.ipos[1]
    assert gamma.company_name == "Gamma Ltd"
    assert gamma.industry == "Not disclosed"
    assert gamma.business_summary == "Not disclosed"
    assert gamma.key_risks == []


def test_missing_company_name_raises():
    with pytest.raises(ValueError):
        normalize_ipo_record({"status": "expected_listing"})

