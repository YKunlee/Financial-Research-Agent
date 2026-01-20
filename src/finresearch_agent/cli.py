# 实现 finresearch 命令行工具入口，解析查询标的与日期等参数并调用 StockResearchAgent 执行分析并输出结果。
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from finresearch_agent.agent import StockResearchAgent
from finresearch_agent.cache import RedisJSONCache
from finresearch_agent.config import get_settings
from finresearch_agent.formatter import format_cli, format_result
from finresearch_agent.utils import json_dumps


def main() -> None:
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(prog="finresearch", description="Stock research agent (code-first).")
    parser.add_argument("--query", required=True, help="Ticker, company name, or alias.")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="YYYY-MM-DD (default: today).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON result.")
    parser.add_argument(
        "--snapshots-dir",
        default=str(Path.cwd() / "snapshots"),
        help="Directory to persist immutable analysis snapshots.",
    )
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    cache = RedisJSONCache(settings.redis_url)
    agent = StockResearchAgent.default(settings=settings, cache=cache)
    agent = StockResearchAgent(
        settings=agent.settings,
        cache=agent.cache,
        resolver=agent.resolver,
        market_data=agent.market_data,
        financials=agent.financials,
        snapshots_dir=Path(args.snapshots_dir),
    )

    snapshot, explanation = agent.analyze(args.query, as_of=as_of)
    if args.json:
        print(json_dumps(format_result(snapshot, explanation)))
    else:
        print(format_cli(snapshot, explanation))
