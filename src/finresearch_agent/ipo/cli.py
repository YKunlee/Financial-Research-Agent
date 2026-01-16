from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from finresearch_agent.config import get_settings
from finresearch_agent.ipo.agent import build_hk_ipo_report, iso_week_string
from finresearch_agent.utils import json_dumps


def _load_records(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(payload, list):
        return payload, {}
    if isinstance(payload, dict):
        if isinstance(payload.get("ipos"), list):
            return payload["ipos"], payload
        if isinstance(payload.get("records"), list):
            return payload["records"], payload
    raise ValueError("Input JSON must be a list, or an object containing 'ipos' (or 'records').")


def main() -> None:
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
    week = meta.get("week") or iso_week_string(as_of)

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
    main()

