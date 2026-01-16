# Financial-Research-Agent
Production-oriented, code-first Stock Research Agent with:

- Deterministic, versioned computations (no LLM math)
- Redis-backed caching for reproducible inputs/outputs
- Immutable, hash-addressed analysis snapshots (`analysis_id`)
- Explain-only LLM integration (LLM reads JSON snapshot only)

## Principles
- LLM does **not** compute numbers: all indicators/metrics are computed in code.
- Every analysis is reproducible: the snapshot is persisted as JSON and keyed by a hash of inputs + data + versions.
- Caching comes before external calls (Redis).

## Quickstart
1) Start Redis

Option A (Docker on the same machine):

`docker run -p 6379:6379 redis:7`

Option B (Redis inside WSL):

- If you run `finresearch` inside WSL and Redis is `127.0.0.1:6379`, set `REDIS_URL=redis://127.0.0.1:6379/0`.
- If you run `finresearch` on Windows but Redis is inside WSL2 and bound to `127.0.0.1`, Windows cannot reach it directly; either:
  - run `finresearch` inside WSL, or
  - reconfigure Redis to listen on `0.0.0.0` / set up port forwarding, then set `REDIS_URL` accordingly.

2) Install (example):

`pip install -e .`

3) Configure env:

`cp .env.example .env`

4) Run:

`finresearch --query "Apple" --as-of 2025-12-31`

Snapshots are written to `./snapshots/{analysis_id}.json` (default).

## HK IPO report
Generate a neutral, factual Hong Kong IPO report from provided (structured) IPO calendar / company details / prospectus excerpts:

`finresearch-ipo --input path/to/hk_ipos.json --as-of 2026-01-16`

Input JSON can be either:
- a list of IPO records, or
- an object with `ipos: [...]` (optionally with `data_source`).

Each record should include at least `company_name` and `status` (one of `subscription_open`, `subscription_upcoming`, `hearing_passed`, `expected_listing`). Optional fields include `expected_listing_date` (YYYY-MM-DD), `industry`, `business_description`, and `risks` (`[{risk_type, source}]`).

Optional LLM extraction (best-effort, extractive-only) is available when `OPENAI_API_KEY` is set:

`finresearch-ipo --input path/to/hk_ipos.json --use-llm`

See `docs/ipo.md` for the full input/output contract and constraints.

## Streamlit UI
Visualize snapshots with a lightweight dashboard:

1) Install Streamlit:

`pip install -e .`

2) Run the app:

`streamlit run streamlit_app.py`

3) Select a snapshot from `./snapshots/` or upload a JSON file.

The sidebar includes a `Language / 语言` switch for Chinese/English UI text.

## What’s implemented
- `T1` Identification: `data/companies.csv` + `data/aliases.json` (no LLM guessing)
- `T2` Market data + cache: Stooq provider + `market_data:{symbol}:{date}` Redis keys (TTL 24h)
- `T3` Financials + cache: quarter-keyed cache `financials:{symbol}:{quarter}` (provider pluggable)
- `T4` Technical indicators (versioned): MA, volatility, max drawdown (`metrics_v1.0.0`)
- `T5` Risk metrics (versioned): Sharpe, historical VaR (`risk_v1.0.0`)
- `T7` Declarative risk rules: versioned flags (`risk_rules_v1`)
- `T8` Snapshot: hash-based `analysis_id`, persisted JSON
- `T9` Explain-only: LangChain prompt + numeric-token guardrail + deterministic fallback
- `T10` Formatter: facts vs. explanation separation (`--json` for machine output)
