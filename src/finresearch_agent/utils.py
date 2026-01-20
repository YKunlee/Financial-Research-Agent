# 提供 JSON 序列化规范化、时间与周/季度计算、收益率和收盘价处理、数值转换及字符串清洗等通用工具函数。
from __future__ import annotations

import json
import numpy as np
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


# --- JSON Utilities ---

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


# --- Datetime Utilities ---

def get_calendar_quarter(d: date) -> str:
    """获取指定日期的日历季度，格式为 YYYYQn"""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}"


def get_iso_week_string(d: date) -> str:
    """获取指定日期的 ISO 周字符串，格式为 YYYY-WW"""
    iso = d.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def parse_quarter_from_date_string(date_str: str) -> str | None:
    """从日期字符串（YYYY-MM-DD）解析季度"""
    try:
        y, m, _ = date_str.split("-")
        q = (int(m) - 1) // 3 + 1
        return f"{y}Q{q}"
    except (ValueError, IndexError):
        return None


# --- Math Utilities ---

def compute_returns(series: np.ndarray) -> np.ndarray:
    """计算收益率序列"""
    if series.size < 2:
        return np.array([], dtype=float)
    return series[1:] / series[:-1] - 1.0


def to_float(v: Any) -> float | None:
    """安全地将值转换为浮点数"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() == "none":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def get_closes_array(bars: Any, as_of: Any) -> np.ndarray:
    """从行情数据中提取截至指定日期的收盘价数组"""
    filtered = [b for b in bars if b.date <= as_of]
    filtered.sort(key=lambda b: b.date)
    return np.array([b.close for b in filtered], dtype=float)


# --- String Utilities ---

def safe_strip(value: Any) -> str | None:
    """安全地去除字符串首尾空格，若结果为空则返回 None"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return None
