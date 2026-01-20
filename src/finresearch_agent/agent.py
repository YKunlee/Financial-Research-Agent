# 实现端到端的股票研究代理 StockResearchAgent，负责公司识别、数据抓取、指标计算、风险规则评估与分析快照持久化。
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from finresearch_agent.cache import JSONCache
from finresearch_agent.config import Settings
from finresearch_agent.datasources import FinancialsService, MarketDataService, StooqMarketDataProvider
from finresearch_agent.identify import CompanyResolver
from finresearch_agent.llm import explain_snapshot
from finresearch_agent.metrics import compute_risk_metrics, compute_technical_indicators
from finresearch_agent.models import AnalysisSnapshot
from finresearch_agent.rules import apply_risk_rules
from finresearch_agent.state import build_snapshot, StateManager, LLMMessage
from finresearch_agent.utils import get_calendar_quarter


@dataclass(frozen=True)
class StockResearchAgent:
    settings: Settings
    cache: JSONCache
    resolver: CompanyResolver
    market_data: MarketDataService
    financials: FinancialsService | None = None
    snapshots_dir: Path | None = None
    state_manager: StateManager | None = None

    @classmethod
    def default(cls, *, settings: Settings, cache: JSONCache) -> "StockResearchAgent":
        resolver = CompanyResolver.default()
        provider = StooqMarketDataProvider()
        market_data = MarketDataService(cache=cache, provider=provider)
        # Path adjustment for src/finresearch_agent/agent.py
        snapshots_dir = Path(__file__).resolve().parents[2] / "snapshots"
        checkpoints_dir = Path(__file__).resolve().parents[2] / "checkpoints"
        state_manager = StateManager(storage_backend=checkpoints_dir, cache_backend=cache)
        return cls(
            settings=settings,
            cache=cache,
            resolver=resolver,
            market_data=market_data,
            financials=None,
            snapshots_dir=snapshots_dir,
            state_manager=state_manager,
        )

    def analyze(self, query: str, as_of: date, thread_id: str | None = None) -> tuple[AnalysisSnapshot, str]:
        """执行完整的股票分析流程，带有状态管理
        
        Args:
            query: 用户查询
            as_of: 分析日期
            thread_id: 可选的线程 ID，用于恢复之前的会话
        """
        # 步骤 1: 初始化状态
        if self.state_manager:
            state = self.state_manager.init_state(query=query, thread_id=thread_id)
            self.state_manager.save_checkpoint(node_name="init")
        
        # 步骤 2: 公司识别
        identity = self.resolver.resolve(query)
        if self.state_manager:
            self.state_manager.update_state("target", identity)
            self.state_manager.save_checkpoint(node_name="identify")

        # 步骤 3: 获取市场数据
        lookback_days = 180  # ensures enough trading days for MA(50) on most markets
        start = as_of - timedelta(days=lookback_days)
        market = self.market_data.get_daily_range(identity.symbol, start=start, end=as_of, min_bars=60)
        
        if self.state_manager:
            self.state_manager.update_state(
                "data_store",
                {"market_data": market.model_dump(mode="json")}
            )
            self.state_manager.save_checkpoint(node_name="fetch_market_data")

        # 步骤 4: 计算指标
        technicals = compute_technical_indicators(market, as_of=as_of)
        risk = compute_risk_metrics(market, as_of=as_of)
        
        if self.state_manager:
            self.state_manager.update_state(
                "analytic_metrics",
                {
                    "technicals": technicals.model_dump(mode="json"),
                    "risk": risk.model_dump(mode="json"),
                }
            )
            self.state_manager.save_checkpoint(node_name="compute_metrics")
        
        # 步骤 5: 规则检查
        rules = apply_risk_rules(technicals, risk)
        if self.state_manager:
            violations = [flag.model_dump(mode="json") for flag in rules.flags]
            self.state_manager.update_state("rules_violations", violations)
            self.state_manager.save_checkpoint(node_name="apply_rules")

        # 步骤 6: 获取财务数据（可选）
        financials = []
        if self.financials is not None:
            q = get_calendar_quarter(as_of)
            try:
                financials = [self.financials.get_quarter(identity.symbol, q)]
                if self.state_manager:
                    data_store = self.state_manager.get_state().data_store
                    data_store["financials"] = [f.model_dump(mode="json") for f in financials]
                    self.state_manager.update_state("data_store", data_store)
            except Exception:
                financials = []

        # 步骤 7: 构建快照
        snapshot = build_snapshot(
            identity=identity,
            as_of=as_of,
            market_data=market,
            financials=financials,
            technicals=technicals,
            risk=risk,
            rules=rules,
            persist_dir=self.snapshots_dir,
            state_manager=self.state_manager,
        )
        
        # 步骤 8: LLM 解释
        explanation = explain_snapshot(snapshot, self.settings)
        
        if self.state_manager:
            # 记录 LLM 交互
            self.state_manager.update_state(
                "messages",
                LLMMessage(
                    role="assistant",
                    content=explanation[:500],  # 截断以节省空间
                    metadata={"snapshot_id": snapshot.analysis_id}
                ),
                append=True
            )
            self.state_manager.save_checkpoint(node_name="llm_explain")
        
        return snapshot, explanation
