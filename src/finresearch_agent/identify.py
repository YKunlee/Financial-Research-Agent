# 读取本地 companies.csv 和 aliases.json 文件，通过代码、公司名或别名解析查询字符串并返回标准化的 CompanyIdentity 标的信息。
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from finresearch_agent.models import CompanyIdentity


def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[\.\,\-\(\)'\"]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass(frozen=True)
class _CompanyRow:
    symbol: str
    market: str
    company_name: str
    aliases: tuple[str, ...]


class CompanyResolver:
    def __init__(self, companies_csv: str | Path, aliases_json: str | Path):
        self._companies_csv = Path(companies_csv)
        self._aliases_json = Path(aliases_json)
        self._by_symbol: dict[str, _CompanyRow] = {}
        self._by_name: dict[str, str] = {}
        self._by_alias: dict[str, str] = {}
        self._load()

    @classmethod
    def default(cls) -> "CompanyResolver":
        # Adjusting path since this is now at src/finresearch_agent/identify.py
        root = Path(__file__).resolve().parents[2]  # repo root
        return cls(root / "data" / "companies.csv", root / "data" / "aliases.json")

    def _load(self) -> None:
        with self._companies_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = (row.get("symbol") or "").strip().upper()
                market = (row.get("market") or "").strip()
                company_name = (row.get("company_name") or "").strip()
                aliases = (row.get("aliases") or "").strip()
                alias_list = tuple(a.strip() for a in aliases.split(",") if a.strip())
                company = _CompanyRow(
                    symbol=symbol, market=market, company_name=company_name, aliases=alias_list
                )
                self._by_symbol[symbol] = company
                self._by_name[_norm(company_name)] = symbol
                for a in alias_list:
                    self._by_alias[_norm(a)] = symbol

        if self._aliases_json.exists():
            with self._aliases_json.open("r", encoding="utf-8") as f:
                aliases = json.load(f)
            for k, v in aliases.items():
                self._by_alias[_norm(str(k))] = str(v).strip().upper()

    def resolve(self, query: str) -> CompanyIdentity:
        q = query.strip()
        if not q:
            raise ValueError("Empty query")

        q_upper = q.upper().strip()
        if q_upper in self._by_symbol:
            row = self._by_symbol[q_upper]
            return CompanyIdentity(
                symbol=row.symbol,
                market=row.market,
                company_name=row.company_name,
                matched_on="ticker",
                query=query,
            )

        qn = _norm(q)
        symbol = self._by_alias.get(qn)
        if symbol and symbol in self._by_symbol:
            row = self._by_symbol[symbol]
            return CompanyIdentity(
                symbol=row.symbol,
                market=row.market,
                company_name=row.company_name,
                matched_on="alias",
                query=query,
            )

        symbol = self._by_name.get(qn)
        if symbol and symbol in self._by_symbol:
            row = self._by_symbol[symbol]
            return CompanyIdentity(
                symbol=row.symbol,
                market=row.market,
                company_name=row.company_name,
                matched_on="company_name",
                query=query,
            )

        raise LookupError(f"Unknown company/ticker: {query!r}. Add it to data/companies.csv.")
