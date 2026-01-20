# HK IPO 报告（代码优先）

本项目支持生成港股 IPO 研究报告，用于在**不猜测、不臆造**的前提下，将准备好的“香港 IPO 日历/公司信息/披露摘录”整理为结构化研究 JSON。

## 核心原则
- 不猜测 IPO 时间/发行价/估值等；缺失信息输出 `Not disclosed` 或 `null`。
- 逻辑由代码控制，LLM 仅用于从摘录中提取原文。

## 使用方法
CLI 调用：
```bash
finresearch-ipo --input path/to/hk_ipos.json --as-of 2026-01-16
```

输入 JSON 格式：
1) 列表形式：`[ { "company_name": "...", "status": "..." }, ... ]`
2) 对象包装：`{ "ipos": [ ... ], "data_source": "...", "week": "YYYY-WW" }`

每条 IPO 记录至少需要 `company_name` 和 `status`。

## 代码结构
- 归一化逻辑：`src/finresearch_agent/ipo.py`
- 报告生成：`src/finresearch_agent/ipo.py`
- CLI：`src/finresearch_agent/ipo.py`
- 单元测试：`tests/test_ipo_report.py`

## 数据字段说明
- `ipos`: IPO 条目数组，每条包含：`company_name/status/expected_listing_date/industry/business_summary/key_risks/data_source/as_of_date`
