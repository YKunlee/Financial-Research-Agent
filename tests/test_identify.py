from __future__ import annotations

import json
from pathlib import Path

import pytest

from finresearch_agent.identify import CompanyResolver


def test_company_resolver_ticker_name_alias(tmp_path: Path):
    companies = tmp_path / "companies.csv"
    companies.write_text(
        "symbol,market,company_name,aliases\nAAPL,NASDAQ,Apple Inc.,apple\n", encoding="utf-8"
    )
    aliases = tmp_path / "aliases.json"
    aliases.write_text(json.dumps({"apple computer": "AAPL"}), encoding="utf-8")

    r = CompanyResolver(companies, aliases)

    a = r.resolve("AAPL")
    assert a.symbol == "AAPL" and a.market == "NASDAQ"
    assert a.matched_on == "ticker"

    b = r.resolve("Apple Inc.")
    assert b.symbol == "AAPL"
    assert b.matched_on == "company_name"

    c = r.resolve("apple computer")
    assert c.symbol == "AAPL"
    assert c.matched_on == "alias"

    with pytest.raises(LookupError):
        r.resolve("UnknownCo")
