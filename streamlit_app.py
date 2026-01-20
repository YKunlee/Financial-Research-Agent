from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from datetime import date
from dotenv import load_dotenv

# Load .env file before importing config
load_dotenv()

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finresearch_agent.models import AnalysisSnapshot
from finresearch_agent.config import get_settings, Settings
from finresearch_agent.ipo import build_hk_ipo_report, IpoReport
from finresearch_agent.utils import get_iso_week_string
from finresearch_agent.datasources import NewsAPIProvider, NewsService
from finresearch_agent.cache import InMemoryJSONCache
from finresearch_agent.chat import append_message_dedup, dedupe_consecutive_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

SNAPSHOTS_DIR = ROOT / "snapshots"


I18N: dict[str, dict[str, str]] = {
    "zh": {
        "page_title": "金融研究看板",
        "sidebar_title": "導航",
        "nav_dashboard": "研究看板",
        "nav_ipo": "IPO 报告",
        "language": "語言",
        "language_zh": "繁體中文",
        "language_en": "English",
        "source": "數據來源",
        "source_local": "本地快照",
        "source_upload": "上傳 JSON",
        "missing_snapshots_dir": "缺少 snapshots 目錄：{path}",
        "no_snapshots": "未找到快照文件。",
        "snapshot_file": "選擇快照文件",
        "upload_json": "上傳 JSON",
        "hero_title": "金融研究看板",
        "hero_sub": "加載快照後可視化行情、指標與風險標記。",
        "hero_hint": "從側邊欄選擇快照或上傳 JSON 文件開始。",
        "renders_only": "本介面只渲染不可變快照數據，不會計算新增指標。",
        "parse_failed": "無法解析快照：{err}",
        "market": "市場",
        "as_of": "截止日期",
        "analysis_id": "分析 ID",
        "risk_level": "風險等級",
        "close": "收盤價",
        "ma20": "20日均線",
        "ma50": "50日均線",
        "vol20": "20日波動率",
        "mdd": "最大回撤",
        "sharpe20": "20日夏普",
        "var95_20": "VaR 95 (20日)",
        "metrics_version": "指標版本",
        "risk_version": "風險版本",
        "rules_version": "規則版本",
        "tab_market": "行情",
        "tab_risk": "風險與規則",
        "tab_financials": "財務",
        "tab_snapshot": "快照",
        "no_market_data": "該快照不包含行情數據。",
        "bars_to_display": "展示K線數量",
        "close_price": "收盤價走勢",
        "volume": "成交量",
        "market_table": "行情表格",
        "source_caption": "來源：{source}",
        "risk_flags": "風險標記",
        "no_risk_flags": "該快照未觸發任何風險標記。",
        "data_provenance": "數據溯源",
        "data_timestamps": "數據時間戳",
        "algo_versions": "算法版本",
        "no_financials": "該快照不包含財務數據。",
        "snapshot_json": "快照 JSON",
        "explanation": "解釋",
        "no_explanation": "该 JSON 不包含解释文本。",
        "risk_low": "低",
        "risk_medium": "中",
        "risk_high": "高",
        "ipo_header": "港股 IPO 研究报告",
        "ipo_input_section": "IPO 数据输入",
        "ipo_generate_btn": "生成报告",
        "ipo_use_llm": "使用 LLM 提取缺失字段与风险",
        "ipo_as_of": "报告日期",
        "ipo_week": "周份",
        "ipo_industry": "行业",
        "ipo_status": "状态",
        "ipo_expected_listing": "预计上市日期",
        "ipo_business_summary": "业务摘要",
        "ipo_key_risks": "关键风险",
        "ipo_disclaimer": "免责声明",
        "ipo_no_data": "请上传或选择 IPO 原始数据 JSON 以生成报告。",
        "ipo_parse_failed": "解析 IPO 数据失败：{err}",
        "ipo_chat_placeholder": "在此输入 IPO 相关信息或询问...",
        "ipo_source_label": "原始资料来源 (粘贴招股书摘录或新闻)",
        "ipo_parsing": "正在分析您的输入内容...",
        "ipo_no_info": "未发现足够的 IPO 信息。请输入更多详情，例如：'XX公司拟于XX日期上市，业务是...'。",
        "ipo_found_n": "成功解析出 {n} 条 IPO 记录。",
    },
    "en": {
        "page_title": "Financial Research Dashboard",
        "sidebar_title": "Navigation",
        "nav_dashboard": "Dashboard",
        "nav_ipo": "IPO Report",
        "language": "Language",
        "language_zh": "繁體中文",
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
        "ipo_header": "HK IPO Research Report",
        "ipo_input_section": "IPO Data Input",
        "ipo_generate_btn": "Generate Report",
        "ipo_use_llm": "Use LLM to extract missing fields & risks",
        "ipo_as_of": "As of Date",
        "ipo_week": "Week",
        "ipo_industry": "Industry",
        "ipo_status": "Status",
        "ipo_expected_listing": "Expected Listing",
        "ipo_business_summary": "Business Summary",
        "ipo_key_risks": "Key Risks",
        "ipo_disclaimer": "Disclaimer",
        "ipo_no_data": "Please upload or select IPO raw data JSON to generate report.",
        "ipo_parse_failed": "Failed to parse IPO data: {err}",
        "ipo_chat_placeholder": "Type IPO info or questions here...",
        "ipo_source_label": "Raw Source Text (Paste prospectus or news)",
        "ipo_parsing": "Analyzing your input...",
        "ipo_no_info": "Not enough IPO info found. Please provide more details.",
        "ipo_found_n": "Parsed {n} IPO records.",
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


def render_ipo_report(report: IpoReport, lang_code: str) -> None:
    st.markdown(f"## {t('ipo_header', lang=lang_code)}")
    st.caption(f"{t('market', lang=lang_code)}: {report.market} • {t('ipo_week', lang=lang_code)}: {report.week}")

    for entry in report.ipos:
        with st.expander(f"{entry.company_name} ({entry.status})", expanded=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.write(f"**{t('ipo_industry', lang=lang_code)}**: {entry.industry}")
                st.write(f"**{t('ipo_status', lang=lang_code)}**: {entry.status}")
            with col2:
                listing_date = entry.expected_listing_date.isoformat() if entry.expected_listing_date else "—"
                st.write(f"**{t('ipo_expected_listing', lang=lang_code)}**: {listing_date}")
                st.write(f"**{t('source', lang=lang_code)}**: {entry.data_source}")

            st.markdown(f"**{t('ipo_business_summary', lang=lang_code)}**")
            st.write(entry.business_summary)

            if entry.key_risks:
                st.markdown(f"**{t('ipo_key_risks', lang=lang_code)}**")
                for risk in entry.key_risks:
                    st.markdown(f"- **{risk.risk_type}** ({risk.source})")

    st.divider()
    st.caption(f"**{t('ipo_disclaimer', lang=lang_code)}**: {report.disclaimer}")


def extract_ipos_from_text(text: str, settings: Settings) -> list[dict[str, Any]]:
    if not settings.openai_api_key or not text.strip():
        return []

    model = ChatOpenAI(
        api_key=settings.openai_api_key, 
        model=settings.openai_model, 
        temperature=0,
        timeout=60,
        max_retries=2
    )
    sys_msg = SystemMessage(
        content=(
            "You are a financial data extractor. Extract HK IPO records from the provided text.\n"
            "Return a JSON list of objects, each containing:\n"
            "- company_name: string\n"
            "- status: 'subscription_open', 'subscription_upcoming', 'hearing_passed', or 'expected_listing'\n"
            "- expected_listing_date: 'YYYY-MM-DD' or null\n"
            "- industry: string or null\n"
            "- business_summary: string or null\n"
            "- prospectus_excerpt: string (verbatim quote from text about the company)\n"
            "- announcement_excerpt: string (verbatim quote from text about the IPO status/date)\n"
            "Rules:\n"
            "- If multiple companies are mentioned, return multiple objects.\n"
            "- Use ONLY facts from the text.\n"
            "- Output strictly valid JSON list only.\n"
        )
    )
    user_msg = HumanMessage(content=text)

    try:
        resp = model.invoke([sys_msg, user_msg], config={"timeout": 60})
        content = str(resp.content).strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception as e:
        st.error(f"LLM 調用失敗: {str(e)}")
        return []


def fetch_news_text_for_ipo(query: str, settings: Settings) -> str | None:
    """Search recent news for IPO information using NewsAPI.
    
    Searches the last 2 months with IPO-related keywords to maximize hit rate.
    """
    import requests
    from datetime import datetime, timedelta, timezone

    print(f"\n[NewsAPI] Starting search for: {query}")
    query = query.strip()
    if not query or not settings.newsapi_key:
        print("[NewsAPI] Skipped: No query or API key")
        return None

    # Build search query with IPO keywords for better relevance
    search_query = f"{query} IPO"
    
    # Search last 2 months instead of just today
    now = datetime.now(tz=timezone.utc)
    from_dt = now - timedelta(days=60)
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": search_query,
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sortBy": "relevancy",
        "pageSize": 10,
        "apiKey": settings.newsapi_key,
    }

    try:
        print(f"[NewsAPI] Requesting URL: {url} with params: {params}")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - present user-facing error
        print(f"[NewsAPI] Error: {exc}")
        st.info(f"News search failed: {exc}")
        return None

    articles = payload.get("articles") or []
    print(f"[NewsAPI] Found {len(articles)} articles with 'IPO' keyword")
    if not articles:
        # Fallback: try without "IPO" keyword
        print("[NewsAPI] Falling back to query without 'IPO' keyword")
        params["q"] = query
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            articles = payload.get("articles") or []
            print(f"[NewsAPI] Found {len(articles)} articles in fallback search")
        except Exception as exc:
            print(f"[NewsAPI] Fallback error: {exc}")
            pass

    if not articles:
        return None

    parts: list[str] = []
    for art in articles[:5]:
        title = (art.get("title") or "").strip()
        desc = (art.get("description") or "").strip()
        content = (art.get("content") or "").strip()
        url_str = (art.get("url") or "").strip()

        segments = []
        if title:
            segments.append(f"Title: {title}")
        if desc:
            segments.append(f"Description: {desc}")
        if content:
            segments.append(f"Content: {content}")
        if url_str:
            segments.append(f"URL: {url_str}")

        if segments:
            parts.append("\n".join(segments))

    result = "\n\n---\n\n".join(parts) if parts else None
    print(f"[NewsAPI] Returning {len(parts)} processed article segments (Total length: {len(result) if result else 0})")
    return result


def fetch_google_search_for_ipo(query: str, settings: Settings) -> str | None:
    """Search for IPO information using Google Custom Search API.
    
    Google search provides better coverage for Chinese company names and HK IPO news.
    """
    import requests

    print(f"\n[GoogleSearch] Starting search for: {query}")
    query = query.strip()
    if not query or not settings.google_api_key or not settings.google_cse_id:
        print("[GoogleSearch] Skipped: No query or API key/CSE ID")
        return None

    # Build search query with IPO keywords
    search_query = f"{query} IPO 招股 上市"
    
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": settings.google_api_key,
        "cx": settings.google_cse_id,
        "q": search_query,
        "num": 10,  # max 10 results per request
    }

    try:
        print(f"[GoogleSearch] Requesting URL: {url} with params: {params}")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - present user-facing error
        print(f"[GoogleSearch] Error: {exc}")
        st.info(f"Google search failed: {exc}")
        return None

    items = payload.get("items") or []
    print(f"[GoogleSearch] Found {len(items)} results")
    if not items:
        # Fallback: try simpler query
        print("[GoogleSearch] Falling back to simpler query")
        params["q"] = f"{query} IPO"
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("items") or []
            print(f"[GoogleSearch] Found {len(items)} results in fallback search")
        except Exception as exc:
            print(f"[GoogleSearch] Fallback error: {exc}")
            pass

    if not items:
        return None

    parts: list[str] = []
    for item in items[:5]:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        link = (item.get("link") or "").strip()

        segments = []
        if title:
            segments.append(f"Title: {title}")
        if snippet:
            segments.append(f"Snippet: {snippet}")
        if link:
            segments.append(f"URL: {link}")

        if segments:
            parts.append("\n".join(segments))

    result = "\n\n---\n\n".join(parts) if parts else None
    print(f"[GoogleSearch] Returning {len(parts)} processed result segments (Total length: {len(result) if result else 0})")
    return result


def fetch_web_search_for_ipo(query: str, settings: Settings) -> tuple[str | None, str]:
    """Search for IPO information using available search APIs.
    
    Tries Google first (better for Chinese), then falls back to NewsAPI.
    Returns (search_result_text, source_name).
    """
    # Try Google first (better for Chinese company names)
    if settings.google_api_key and settings.google_cse_id:
        result = fetch_google_search_for_ipo(query, settings)
        if result:
            return result, "Google"
    
    # Fallback to NewsAPI
    if settings.newsapi_key:
        result = fetch_news_text_for_ipo(query, settings)
        if result:
            return result, "NewsAPI"
    
    return None, ""


def main() -> None:
    st.set_page_config(page_title="Financial Research Dashboard / 金融研究看板", layout="wide")
    inject_style()

    lang = st.sidebar.selectbox(
        "Language / 語言",
        options=["繁體中文", "English"],
        index=0,
        key="lang_select",
    )
    lang_code = "zh" if lang == "繁體中文" else "en"

    st.sidebar.title(t("sidebar_title", lang=lang_code))

    nav_mode = st.sidebar.radio(
        "Menu",
        options=["dashboard", "ipo"],
        format_func=lambda v: t("nav_dashboard", lang=lang_code) if v == "dashboard" else t("nav_ipo", lang=lang_code),
        label_visibility="collapsed",
    )

    if nav_mode == "dashboard":
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
    else:
        # IPO Mode
        st.markdown(f"## {t('nav_ipo', lang=lang_code)}")
        
        if "ipo_messages" not in st.session_state:
            st.session_state["ipo_messages"] = []
        else:
            st.session_state["ipo_messages"] = dedupe_consecutive_messages(st.session_state["ipo_messages"])

        for msg in st.session_state["ipo_messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "report" in msg:
                    render_ipo_report(msg["report"], lang_code)

        query = st.chat_input(t("ipo_chat_placeholder", lang=lang_code))
        
        if query:
            # Normalize input: treat None as empty string
            q_str = query.strip()
            
            if not q_str:
                st.warning(t("ipo_no_info", lang=lang_code))
            else:
                st.session_state["ipo_messages"].append({"role": "user", "content": q_str})
                with st.chat_message("user"):
                    st.write(q_str)

                with st.chat_message("assistant"):
                    settings = get_settings()
                    as_of = date.today()
                    print(f"\n[Main] Processing IPO query: '{q_str}' (Source: Chat)")
                    
                    # Step 1: Web search (separate spinner)
                    news_text, search_source = None, ""
                    # Only perform web search if we have a short query (likely a company name)
                    # If input is very long, it's probably already a prospectus, skip search
                    if len(q_str) < 500:
                        with st.spinner("🔍 正在搜索相關資訊..." if lang_code == "zh" else "🔍 Searching..."):
                            news_text, search_source = fetch_web_search_for_ipo(q_str, settings)
                    else:
                        print(f"[Main] Query too long ({len(q_str)} chars), treating as prospectus, skipping web search")
                    
                    # Step 2: Display search results
                    if news_text:
                        print(f"[Main] Search SUCCESS via {search_source}. Results length: {len(news_text)}")
                        st.caption(f"✅ 從 {search_source} 找到相關資訊" if lang_code == "zh" else f"✅ Found info via {search_source}")
                        with st.expander("🔍 搜索結果" if lang_code == "zh" else "🔍 Search Results", expanded=True):
                            st.text(news_text[:3000] + "..." if len(news_text) > 3000 else news_text)
                    else:
                        print(f"[Main] Search EMPTY or FAILED")
                        has_search_api = settings.google_api_key or settings.newsapi_key
                        if has_search_api and len(q_str) < 500:
                            st.caption(f"⚠️ 未找到 '{q_str}' 的相關資訊" if lang_code == "zh" else f"⚠️ No web results for '{q_str}'")
                            with st.expander("🔍 搜索結果" if lang_code == "zh" else "🔍 Search Results", expanded=True):
                                st.write("搜索結果為空，請嘗試：" if lang_code == "zh" else "No results found. Try:")
                                st.write("1. 使用英文公司名或股票代碼" if lang_code == "zh" else "1. Use English company name or stock code")
                                st.write("2. 直接貼上招股書或新聞全文" if lang_code == "zh" else "2. Paste full prospectus or news article")
                        elif not has_search_api:
                            st.caption("⚠️ 未配置搜索 API，請在 .env 中設置 GOOGLE_API_KEY 和 GOOGLE_CSE_ID" if lang_code == "zh" else "⚠️ No search API configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID in .env")
                    
                    # Step 3: Build combined text for LLM
                    if news_text:
                        combined_text = f"Query: {q_str}\n\nWeb search results:\n{news_text}"
                    else:
                        combined_text = q_str
                    
                    print(f"[Main] Sending to LLM. Total prompt text length: {len(combined_text)}")
                    
                    # Step 4: LLM parsing (separate spinner)
                    with st.spinner("🧠 正在分析 IPO 資訊..." if lang_code == "zh" else "🧠 Analyzing IPO info..."):
                        records = extract_ipos_from_text(combined_text, settings)
                    
                    print(f"[Main] LLM found {len(records)} IPO records")
                    
                    # Step 5: Display results
                    if not records:
                        msg_content = t("ipo_no_info", lang=lang_code)
                        st.write(msg_content)
                        if news_text:
                            st.info("💡 已搜索到相關內容，但未能提取出 IPO 記錄。請直接貼上完整的招股書或新聞全文。" if lang_code == "zh" else "💡 Found related content but couldn't extract IPO records. Try pasting the full prospectus or news article.")
                        st.session_state["ipo_messages"] = append_message_dedup(
                            st.session_state["ipo_messages"],
                            role="assistant",
                            content=msg_content,
                        )
                    else:
                        week = get_iso_week_string(as_of)
                        report = build_hk_ipo_report(
                            records,
                            as_of_date=as_of,
                            week=week,
                            settings=settings,
                            use_llm_extraction=True
                        )
                        msg_content = t("ipo_found_n", lang=lang_code, n=len(report.ipos))
                        st.write(msg_content)
                        render_ipo_report(report, lang_code)
                        st.session_state["ipo_messages"] = append_message_dedup(
                            st.session_state["ipo_messages"],
                            role="assistant",
                            content=msg_content,
                            report=report,
                        )


if __name__ == "__main__":
    main()
