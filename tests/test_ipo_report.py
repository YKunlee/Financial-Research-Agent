from datetime import date
import pytest
from finresearch_agent.ipo import (
    normalize_status,
    normalize_ipo_record,
    build_hk_ipo_report,
    IpoEntry,
    IpoRisk,
)
from finresearch_agent.utils import get_iso_week_string


def test_normalize_status():
    assert normalize_status("Subscription Open") == "subscription_open"
    assert normalize_status("hearing passed") == "hearing_passed"
    assert normalize_status("Expected to list") == "expected_listing"
    assert normalize_status("unknown") is None


def test_normalize_ipo_record():
    raw = {
        "company_name": "Test Company",
        "status": "subscription_open",
        "listing_date": "2026-01-20",
        "industry": "Tech",
        "business_summary": "Doing things",
        "risks": [{"risk_type": "Market risk", "source": "prospectus"}]
    }
    norm = normalize_ipo_record(raw)
    assert norm["company_name"] == "Test Company"
    assert norm["status"] == "subscription_open"
    assert norm["expected_listing_date"] == date(2026, 1, 20)
    assert len(norm["key_risks"]) == 1
    assert norm["key_risks"][0].risk_type == "Market risk"


def test_build_hk_ipo_report():
    as_of = date(2026, 1, 20)
    week = get_iso_week_string(as_of)
    records = [
        {
            "name": "Company A",
            "ipo_status": "Hearing Passed",
            "industry": "Finance"
        },
        {
            "company": "Company B",
            "status": "subscription_upcoming",
            "expected_date": "2026-02-01"
        }
    ]
    
    report = build_hk_ipo_report(records, as_of_date=as_of, week=week)
    
    assert report.market == "HK"
    assert report.week == week
    assert len(report.ipos) == 2
    
    ipo_a = next(i for i in report.ipos if i.company_name == "Company A")
    assert ipo_a.status == "hearing_passed"
    assert ipo_a.industry == "Finance"
    
    ipo_b = next(i for i in report.ipos if i.company_name == "Company B")
    assert ipo_b.status == "subscription_upcoming"
    assert ipo_b.expected_listing_date == date(2026, 2, 1)


def test_ipo_report_serialization():
    entry = IpoEntry(
        company_name="Test",
        status="expected_listing",
        expected_listing_date=date(2026, 1, 20),
        industry="Misc",
        business_summary="Summary",
        key_risks=[IpoRisk(risk_type="Risk", source="announcement")],
        data_source="Source",
        as_of_date=date(2026, 1, 20)
    )
    data = entry.model_dump(mode="json")
    assert data["expected_listing_date"] == "2026-01-20"
    assert data["key_risks"][0]["source"] == "announcement"
