from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from finresearch_agent.models import FinancialQuarter, MarketData


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> MarketData:
        raise NotImplementedError


class FinancialsProvider(ABC):
    name: str

    @abstractmethod
    def fetch_quarter(self, symbol: str, quarter: str) -> FinancialQuarter:
        raise NotImplementedError


class NewsProvider(ABC):
    name: str

    @abstractmethod
    def fetch_daily(self, symbol: str, day: date) -> list[dict]:
        raise NotImplementedError
