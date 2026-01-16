from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


def _default(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        if isinstance(o, datetime) and o.tzinfo is None:
            o = o.replace(tzinfo=timezone.utc)
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default, ensure_ascii=False)


def json_loads(s: str) -> Any:
    return json.loads(s)


def _stable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _stable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 12)
    return obj


def canonical_dumps(obj: Any) -> str:
    stable = _stable(obj)
    return json.dumps(stable, default=_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
