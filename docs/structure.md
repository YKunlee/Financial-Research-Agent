# 项目结构说明

## 总览
本项目是“代码优先、可复现”的股票研究代理。核心思想：
- 所有数值指标由代码计算，LLM 只负责解释已有 JSON 结果。
- 数据先走缓存（Redis），再走外部数据源。
- 每次分析生成不可变快照 `analysis_id`，便于追溯和复现。

## 目录结构
```
Financial-Research-Agent/
  data/                     # 公司与别名基础数据
  docs/                     # 文档（含 HK IPO 报告说明）
  snapshots/                # 分析快照输出（JSON）
  src/finresearch_agent/    # 核心代码
  tests/                    # 单元测试
  README.md                 # 使用说明
  streamlit_app.py          # Streamlit 可视化界面
  .env.example              # 环境变量模板
  pyproject.toml            # 包配置
  requirements.txt          # 依赖列表
```

## 关键模块

### 模块设计初衷
| 模块名称 | 作用（为什么它存在？） |
| :--- | :--- |
| `datasources.py` | **多源数据整合**：对接专业金融 API 和财报数据，确保数据源头的权威性与实时性，而非依赖通用搜索。 |
| `ipo.py` | **深度专业逻辑**：内置金融行业分析模型，专门处理 HK IPO 等复杂且高度专业化的业务场景。 |
| `snapshot.py` | **可复现性（快照）**：保存分析时的瞬时数据证据，确保研究结论在任何时候都可追溯、可复现。 |
| `cache.py` | **性能与成本优化**：通过 Redis 缓存机制减少昂贵的外部 API 和 LLM 调用，提升系统响应速度。 |
| `rules.py` | **合规与风控护栏**：通过结构化规则强制 AI 遵守金融逻辑，防止产生误导性的投资建议。 |
| `metrics.py` | **质量监控与量化**：自动计算技术与风险指标，为 AI 的解释提供精确的量化事实依据。 |
| `identify.py` | **精准实体识别**：确保分析对象（公司/股票）的唯一性，避免因名称歧义导致的分析错误。 |
| `llm.py` | **受控的自然语言解释**：仅负责对计算结果进行“翻译”，严禁 LLM 自行计算或捏造数据。 |

### 1) 配置与常量
- `src/finresearch_agent/config.py`  
  读取 `REDIS_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 等配置。
- `src/finresearch_agent/constants.py`  
  版本号常量（`metrics_v1.0.0` / `risk_v1.0.0` / `risk_rules_v1`）和默认 TTL。

### 2) 公司识别（T1）
- `src/finresearch_agent/identify.py`  
  从 `data/companies.csv` + `data/aliases.json` 解析查询，输出 `symbol/market/company_name`。
  不使用 LLM 猜测。

### 3) 缓存（T2/T3/T6）
- `src/finresearch_agent/cache.py`  
  Redis JSON 缓存封装，所有数据先查缓存再查外部。

缓存 key 规范：
- 行情：`market_data:{symbol}:{date}`
- 财报：`financials:{symbol}:{quarter}`

### 4) 数据源（T2/T3/T6）
- `src/finresearch_agent/datasources.py`  
  默认 Stooq 行情日线，支持 Alpha Vantage 财报。

### 5) 指标与风险（T4/T5）
- `src/finresearch_agent/metrics.py`  
  计算技术指标（MA、波动率、最大回撤）与风险指标（Sharpe、历史 VaR）。

### 6) 规则引擎（T7）
- `src/finresearch_agent/rules.py`  
  风险规则定义与执行，输出结构化风险标记。

### 7) 快照（T8）
- `src/finresearch_agent/snapshot.py`  
  汇总输出，生成不可变 `analysis_id`，写入 `snapshots/`。

### 8) LLM 解释（T9）
- `src/finresearch_agent/llm.py`  
  LLM 只读 JSON 快照；校验“无新增数字”与“必须引用版本号/analysis_id”。
  无 `OPENAI_API_KEY` 时走本地确定性解释。

### 9) 对外接口（T10）
- `src/finresearch_agent/agent.py`  
  统一编排：识别 -> 拉行情 -> 计算 -> 规则 -> 快照 -> 解释。
- `src/finresearch_agent/cli.py`  
  CLI 入口：`finresearch --query "Apple" --as-of YYYY-MM-DD`
- `src/finresearch_agent/ipo.py`  
  HK IPO 报告：从准备好的日历/公司信息/摘录生成报告。
- `src/finresearch_agent/formatter.py`  
  输出格式（facts + explanation）。

## 分析流程（简化）
1) 解析公司/代码  
2) 拉取行情（缓存优先）  
3) 计算技术/风险指标  
4) 规则判定风险标记  
5) 生成快照 + `analysis_id`  
6) LLM 解释（仅解释，不计算）

## 快照示例
- 输出位置：`snapshots/{analysis_id}.json`  
- 包含字段：`identity / market_data / technicals / risk / rules / algo_versions / data_timestamps`

## 测试
`python -m pytest`
