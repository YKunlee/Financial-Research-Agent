from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finresearch_agent.models import AnalysisSnapshot

SNAPSHOTS_DIR = ROOT / "snapshots"


I18N: dict[str, dict[str, str]] = {
    "zh": {
        "page_title": "金融研究看板",
        "sidebar_title": "快照",
        "language": "语言",
        "language_zh": "中文",
        "language_en": "English",
        "source": "数据来源",
        "source_local": "本地 snapshots",
        "source_upload": "上传 JSON",
        "missing_snapshots_dir": "缺少 snapshots 目录：{path}",
        "no_snapshots": "未找到快照文件。",
        "snapshot_file": "选择快照文件",
        "upload_json": "上传 JSON",
        "hero_title": "金融研究看板",
        "hero_sub": "加载快照后可视化行情、指标与风险标记。",
        "hero_hint": "从侧边栏选择快照或上传 JSON 文件开始。",
        "renders_only": "本界面只渲染不可变快照数据，不会计算新增指标。",
        "parse_failed": "无法解析快照：{err}",
        "market": "市场",
        "as_of": "截止日期",
        "analysis_id": "分析 ID",
        "risk_level": "风险等级",
        "close": "收盘价",
        "ma20": "20日均线",
        "ma50": "50日均线",
        "vol20": "20日波动率",
        "mdd": "最大回撤",
        "sharpe20": "20日夏普",
        "var95_20": "VaR 95 (20日)",
        "metrics_version": "指标版本",
        "risk_version": "风险版本",
        "rules_version": "规则版本",
        "tab_market": "行情",
        "tab_risk": "风险与规则",
        "tab_financials": "财务",
        "tab_snapshot": "快照",
        "no_market_data": "该快照不包含行情数据。",
        "bars_to_display": "展示K线数量",
        "close_price": "收盘价走势",
        "volume": "成交量",
        "market_table": "行情表格",
        "source_caption": "来源：{source}",
        "risk_flags": "风险标记",
        "no_risk_flags": "该快照未触发任何风险标记。",
        "data_provenance": "数据溯源",
        "data_timestamps": "数据时间戳",
        "algo_versions": "算法版本",
        "no_financials": "该快照不包含财务数据。",
        "snapshot_json": "快照 JSON",
        "explanation": "解释",
        "no_explanation": "该 JSON 不包含解释文本。",
        "risk_low": "低",
        "risk_medium": "中",
        "risk_high": "高",
    },
    "en": {
        "page_title": "Financial Research Dashboard",
        "sidebar_title": "Snapshot",
        "language": "Language",
        "language_zh": "中文",
        "language_en": "English",
        "source": "Source",
        "source_local": "Local snapshots",
        "source_upload": "Upload JSON",
        "missing_snapshots_dir": "Missing snapshots directory: {path}",
        "no_snapshots": "No snapshots found.",
        "snapshot_file": "Snapshot file",
        "upload_json": "Upload JSON",
        "hero_title": "Financial Research Dashboard",
        "hero_sub": "Load a snapshot to visualize market data, metrics, and risk flags.",
        "hero_hint": "Select a snapshot from the sidebar or upload a JSON file to begin.",
        "renders_only": "This dashboard renders immutable snapshot data only. It does not compute new metrics.",
        "parse_failed": "Unable to parse snapshot: {err}",
        "market": "Market",
        "as_of": "As of",
        "analysis_id": "Analysis ID",
        "risk_level": "Risk Level",
        "close": "Close",
        "ma20": "MA 20",
        "ma50": "MA 50",
        "vol20": "Volatility 20d",
        "mdd": "Max Drawdown",
        "sharpe20": "Sharpe 20d",
        "var95_20": "VaR 95 20d",
        "metrics_version": "Metrics Version",
        "risk_version": "Risk Version",
        "rules_version": "Rules Version",
        "tab_market": "Market",
        "tab_risk": "Risk & Rules",
        "tab_financials": "Financials",
        "tab_snapshot": "Snapshot",
        "no_market_data": "No market data available in this snapshot.",
        "bars_to_display": "Bars to display",
        "close_price": "Close Price",
        "volume": "Volume",
        "market_table": "Market data table",
        "source_caption": "Source: {source}",
        "risk_flags": "Risk Flags",
        "no_risk_flags": "No risk flags triggered for this snapshot.",
        "data_provenance": "Data provenance",
        "data_timestamps": "Data timestamps",
        "algo_versions": "Algo versions",
        "no_financials": "No financials included in this snapshot.",
        "snapshot_json": "Snapshot JSON",
        "explanation": "Explanation",
        "no_explanation": "No explanation found in this JSON payload.",
        "risk_low": "low",
        "risk_medium": "medium",
        "risk_high": "high",
    },
}


def t(key: str, *, lang: str, **kwargs: Any) -> str:
    text = I18N.get(lang, I18N["en"]).get(key) or I18N["en"].get(key) or key
    return text.format(**kwargs)


def inject_style() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=Noto+Sans+SC:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --ink: #0f172a;
  --muted: #475569;
  --accent: #0f766e;
  --accent-soft: #e6f5f3;
  --panel: #ffffff;
  --bg: #f7f7f2;
  --risk-low: #1f8a70;
  --risk-medium: #f59f00;
  --risk-high: #e03131;
}
html, body, [class*="css"] {
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
  color: var(--ink);
}
.stApp {
  background: radial-gradient(1200px 600px at 10% -10%, #e7f0ff, transparent),
              radial-gradient(800px 500px at 95% 0%, #e9fff7, transparent),
              var(--bg);
}
.hero {
  background: linear-gradient(135deg, #ffffff 0%, #f4fbf9 100%);
  border: 1px solid #e6ecea;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
  animation: rise 600ms ease-out;
}
.hero-title {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 6px 0;
}
.hero-sub {
  color: var(--muted);
  font-size: 14px;
}
.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}
.badge.low { background: rgba(31, 138, 112, 0.12); color: var(--risk-low); }
.badge.medium { background: rgba(245, 159, 0, 0.12); color: var(--risk-medium); }
.badge.high { background: rgba(224, 49, 49, 0.12); color: var(--risk-high); }
.mono { font-family: 'IBM Plex Mono', monospace; }
@keyframes rise {
  from { transform: translateY(8px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
</style>
""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if "facts" in payload:
        facts = payload.get("facts") or {}
        snapshot = facts.get("snapshot")
        if snapshot is None and "snapshot" in payload:
            snapshot = payload.get("snapshot")
        if snapshot is None:
            raise ValueError("Missing snapshot in facts payload.")
        return snapshot, payload.get("explanation")
    if "snapshot" in payload and "analysis_id" not in payload:
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid snapshot payload.")
        return snapshot, payload.get("explanation")
    if "analysis_id" in payload:
        return payload, None
    raise ValueError("Unrecognized JSON structure.")


def risk_level_from_flags(flags: list[Any]) -> str:
    severities: set[str] = set()
    for flag in flags:
        if isinstance(flag, dict):
            severity = flag.get("severity")
        else:
            severity = getattr(flag, "severity", None)
        if severity:
            severities.add(severity)
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def to_market_df(snapshot: AnalysisSnapshot) -> pd.DataFrame:
    bars = [bar.model_dump(mode="json") for bar in snapshot.market_data.bars]
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return df


def format_value(value: float | int | None, decimals: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:.{decimals}f}"


def main() -> None:
    st.set_page_config(page_title="Financial Research Dashboard / 金融研究看板", layout="wide")
    inject_style()

    lang = st.sidebar.selectbox(
        "Language / 语言",
        options=["中文", "English"],
        index=0,
        key="lang_select",
    )
    lang_code = "zh" if lang == "中文" else "en"

    st.sidebar.title(t("sidebar_title", lang=lang_code))
    source_key = st.sidebar.radio(
        t("source", lang=lang_code),
        options=["local", "upload"],
        format_func=lambda v: t("source_local", lang=lang_code)
        if v == "local"
        else t("source_upload", lang=lang_code),
        horizontal=False,
        key="source_key",
    )

    payload: dict[str, Any] | None = None
    if source_key == "local":
        if not SNAPSHOTS_DIR.exists():
            st.sidebar.warning(
                t("missing_snapshots_dir", lang=lang_code, path=str(SNAPSHOTS_DIR))
            )
        files = sorted(SNAPSHOTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            st.sidebar.info(t("no_snapshots", lang=lang_code))
        else:
            selected = st.sidebar.selectbox(
                t("snapshot_file", lang=lang_code), files, format_func=lambda p: p.name
            )
            payload = load_payload(selected)
    else:
        uploaded = st.sidebar.file_uploader(t("upload_json", lang=lang_code), type=["json"])
        if uploaded is not None:
            payload = json.loads(uploaded.read().decode("utf-8"))

    if payload is None:
        st.markdown(
            f"""
<div class="hero">
  <div class="hero-title">{t("hero_title", lang=lang_code)}</div>
  <div class="hero-sub">{t("hero_sub", lang=lang_code)}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.info(t("hero_hint", lang=lang_code))
        st.stop()

    try:
        snapshot_dict, explanation = normalize_payload(payload)
        snapshot = AnalysisSnapshot.model_validate(snapshot_dict)
    except Exception as exc:  # noqa: BLE001 - present user-facing error
        st.error(t("parse_failed", lang=lang_code, err=str(exc)))
        st.stop()

    risk_level = risk_level_from_flags(snapshot.rules.flags)
    risk_text = (
        t("risk_high", lang=lang_code)
        if risk_level == "high"
        else t("risk_medium", lang=lang_code)
        if risk_level == "medium"
        else t("risk_low", lang=lang_code)
    )
    badge_html_localized = f'<span class="badge {risk_level}">{risk_text}</span>'

    st.markdown(
        f"""
<div class="hero">
  <div class="hero-title">{snapshot.company_name} <span class="mono">({snapshot.symbol})</span></div>
  <div class="hero-sub">{t("market", lang=lang_code)}: {snapshot.market} • {t("as_of", lang=lang_code)}: {snapshot.as_of.isoformat()} • {t("analysis_id", lang=lang_code)}: <span class="mono">{snapshot.analysis_id}</span></div>
  <div style="margin-top:10px;">{t("risk_level", lang=lang_code)}: {badge_html_localized}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.caption(t("renders_only", lang=lang_code))

    market_df = to_market_df(snapshot)
    latest_close = market_df["close"].iloc[-1] if not market_df.empty else None

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(t("close", lang=lang_code), format_value(latest_close, 2))
    col2.metric(t("ma20", lang=lang_code), format_value(snapshot.technicals.ma_20, 2))
    col3.metric(t("ma50", lang=lang_code), format_value(snapshot.technicals.ma_50, 2))
    col4.metric(t("vol20", lang=lang_code), format_value(snapshot.technicals.volatility_20, 6))
    col5.metric(t("mdd", lang=lang_code), format_value(snapshot.technicals.max_drawdown, 6))

    col6, col7, col8, col9, col10 = st.columns(5)
    col6.metric(t("sharpe20", lang=lang_code), format_value(snapshot.risk.sharpe_20, 4))
    col7.metric(t("var95_20", lang=lang_code), format_value(snapshot.risk.var_95_20, 6))
    col8.metric(t("metrics_version", lang=lang_code), snapshot.algo_versions.get("metrics", "—"))
    col9.metric(t("risk_version", lang=lang_code), snapshot.algo_versions.get("risk", "—"))
    col10.metric(t("rules_version", lang=lang_code), snapshot.algo_versions.get("rules", "—"))

    tabs = st.tabs(
        [
            t("tab_market", lang=lang_code),
            t("tab_risk", lang=lang_code),
            t("tab_financials", lang=lang_code),
            t("tab_snapshot", lang=lang_code),
        ]
    )

    with tabs[0]:
        if market_df.empty:
            st.warning(t("no_market_data", lang=lang_code))
        else:
            min_bars = min(20, len(market_df))
            bar_count = st.slider(
                t("bars_to_display", lang=lang_code),
                min_value=min_bars,
                max_value=len(market_df),
                value=min(120, len(market_df)),
            )
            view_df = market_df.tail(bar_count)

            st.subheader(t("close_price", lang=lang_code))
            st.line_chart(view_df["close"], height=320)
            st.caption(t("source_caption", lang=lang_code, source=snapshot.market_data.source))

            st.subheader(t("volume", lang=lang_code))
            st.bar_chart(view_df["volume"], height=220)

            with st.expander(t("market_table", lang=lang_code)):
                st.dataframe(view_df, use_container_width=True)

    with tabs[1]:
        if snapshot.rules.flags:
            st.subheader(t("risk_flags", lang=lang_code))
            for flag in snapshot.rules.flags:
                if flag.severity == "high":
                    st.error(f"{flag.title} ({flag.code})")
                elif flag.severity == "medium":
                    st.warning(f"{flag.title} ({flag.code})")
                else:
                    st.info(f"{flag.title} ({flag.code})")
                st.caption(flag.details)
                if flag.evidence:
                    st.json(flag.evidence)
        else:
            st.success(t("no_risk_flags", lang=lang_code))

        with st.expander(t("data_provenance", lang=lang_code)):
            st.write(t("data_timestamps", lang=lang_code))
            st.json({k: v.isoformat() for k, v in snapshot.data_timestamps.items()})
            st.write(t("algo_versions", lang=lang_code))
            st.json(snapshot.algo_versions)

    with tabs[2]:
        if not snapshot.financials:
            st.info(t("no_financials", lang=lang_code))
        else:
            rows = []
            for quarter in snapshot.financials:
                base = quarter.model_dump(mode="json")
                values = base.pop("values", {})
                rows.append({**base, **values})
            fin_df = pd.DataFrame(rows)
            st.dataframe(fin_df, use_container_width=True)

    with tabs[3]:
        st.subheader(t("snapshot_json", lang=lang_code))
        st.json(snapshot.model_dump(mode="json"))
        if explanation:
            st.subheader(t("explanation", lang=lang_code))
            st.write(explanation)
        else:
            st.info(t("no_explanation", lang=lang_code))


if __name__ == "__main__":
    main()
