from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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

