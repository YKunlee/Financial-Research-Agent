# HK IPO 报告（代码优先）

本项目新增 `finresearch-ipo`，用于在**不猜测、不臆造**的前提下，将你已经准备好的“香港 IPO 日历/公司信息/披露摘录”整理为结构化研究 JSON。

## 设计原则（与提示词约束对齐）
- 默认只消费输入数据，不抓取网页、不执行搜索。
- 不猜测 IPO 时间/发行价/估值等；缺失信息输出 `Not disclosed` 或 `null`。
- 输出为中立、事实性描述；不做投资建议。

## CLI 用法
从 JSON 文件生成报告（输出到 stdout 或 `--output`）：

`finresearch-ipo --input path/to/hk_ipos.json --as-of 2026-01-16`

可选参数：
- `--data-source`：当单条记录未提供 `data_source` 时的默认来源（默认 `Public disclosure`）
- `--use-llm`：当提供披露摘录时，尝试做“摘录式（extractive-only）”字段/风险抽取（需 `OPENAI_API_KEY`）
- `--output`：输出文件路径

## 输入格式
输入 JSON 支持两种形态：
1) 直接是数组：`[ { ... }, { ... } ]`
2) 对象包装：`{ "ipos": [ ... ], "data_source": "...", "week": "YYYY-WW" }`（也支持 `records` 作为数组字段名）

每条 IPO 记录至少需要：
- `company_name`：公司名称
- `status`：必须为以下之一（大小写/空格/连字符会做归一化）  
  `subscription_open` / `subscription_upcoming` / `hearing_passed` / `expected_listing`

可选字段（若缺失不会推断）：
- `expected_listing_date`：`YYYY-MM-DD`（严格解析；无法解析则置为 `null`）
- `industry`：行业；缺失输出 `Not disclosed`
- `business_summary` / `business_description`：业务概述；缺失输出 `Not disclosed`
- `risks` 或 `key_risks`：`[{ "risk_type": "...", "source": "prospectus|announcement" }]`

如需 `--use-llm`（摘录式抽取），可在单条记录中提供：
- `prospectus_excerpt` / `prospectus_excerpts`（字符串或字符串数组）
- `announcement_excerpt` / `announcement_excerpts`（字符串或字符串数组）

## 输出格式（最终 schema）
输出为：
- `market`: 固定 `HK`
- `week`: `YYYY-WW`
- `ipos`: IPO 条目数组，每条包含：`company_name/status/expected_listing_date/industry/business_summary/key_risks/data_source/as_of_date`
- `disclaimer`: 固定免责声明文本

## 实现位置
- 归一化：`src/finresearch_agent/ipo/normalize.py`
- 报告生成：`src/finresearch_agent/ipo/agent.py`
- CLI：`src/finresearch_agent/ipo/cli.py`
- 可选摘录式抽取：`src/finresearch_agent/ipo/llm_extract.py`
- 单测：`tests/test_ipo_report.py`

