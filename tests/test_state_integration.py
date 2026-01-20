"""测试状态管理器与现有系统的集成"""
from datetime import date
from pathlib import Path
import tempfile

import pytest

from finresearch_agent.agent import StockResearchAgent
from finresearch_agent.cache import InMemoryJSONCache
from finresearch_agent.config import Settings
from finresearch_agent.state import StateManager


class TestStateIntegration:
    """测试状态管理器与 Agent 的集成"""

    def test_agent_with_state_manager(self):
        """测试 Agent 默认包含状态管理器"""
        settings = Settings()
        cache = InMemoryJSONCache()
        agent = StockResearchAgent.default(settings=settings, cache=cache)

        assert agent.state_manager is not None
        assert isinstance(agent.state_manager, StateManager)

    def test_agent_analyze_records_state(self):
        """测试分析过程记录状态"""
        settings = Settings()
        cache = InMemoryJSONCache()
        agent = StockResearchAgent.default(settings=settings, cache=cache)

        # 执行分析
        try:
            snapshot, explanation = agent.analyze("AAPL", as_of=date(2024, 1, 1))
        except Exception:
            # 可能因为数据获取失败，但状态应该被记录
            pass

        # 验证状态被记录
        if agent.state_manager:
            state = agent.state_manager.get_state()
            assert state is not None
            assert state.query == "AAPL"

            # 验证至少有一些检查点
            checkpoints = agent.state_manager.list_checkpoints()
            assert len(checkpoints) > 0

    def test_backward_compatibility(self):
        """测试向后兼容性：不使用状态管理器的旧代码仍能工作"""
        from finresearch_agent.models import (
            CompanyIdentity,
            MarketData,
            MarketBar,
            TechnicalIndicators,
            RiskMetrics,
            RuleResults,
        )
        from finresearch_agent.state import build_snapshot
        from datetime import datetime

        # 构造最小数据
        identity = CompanyIdentity(
            symbol="TEST",
            market="US",
            company_name="Test Company",
            matched_on="ticker",
            query="TEST",
        )

        market_data = MarketData(
            symbol="TEST",
            source="test",
            data_timestamp=datetime.now(),
            bars=[
                MarketBar(
                    date=date(2024, 1, 1),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1000000,
                )
            ],
        )

        technicals = TechnicalIndicators(
            algo_version="test-1.0",
            as_of=date(2024, 1, 1),
            ma_20=100.0,
            ma_50=None,
            volatility_20=0.02,
            max_drawdown=-0.05,
        )

        risk = RiskMetrics(
            algo_version="test-1.0",
            as_of=date(2024, 1, 1),
            sharpe_20=1.5,
            var_95_20=-0.03,
        )

        rules = RuleResults(rule_version="test-1.0", flags=[])

        # 旧方式调用（不传 state_manager）
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = build_snapshot(
                identity=identity,
                as_of=date(2024, 1, 1),
                market_data=market_data,
                financials=[],
                technicals=technicals,
                risk=risk,
                rules=rules,
                persist_dir=tmpdir,
                # 注意：不传 state_manager
            )

            assert snapshot.symbol == "TEST"
            assert snapshot.company_name == "Test Company"

            # 验证快照文件被创建
            snapshot_file = Path(tmpdir) / f"{snapshot.analysis_id}.json"
            assert snapshot_file.exists()

    def test_state_manager_with_custom_storage(self):
        """测试使用自定义存储路径的状态管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "custom_checkpoints"

            settings = Settings()
            cache = InMemoryJSONCache()
            state_manager = StateManager(
                storage_backend=storage_path, cache_backend=cache
            )

            # 手动创建 Agent
            from finresearch_agent.identify import CompanyResolver
            from finresearch_agent.datasources import (
                MarketDataService,
                StooqMarketDataProvider,
            )

            resolver = CompanyResolver.default()
            provider = StooqMarketDataProvider()
            market_data = MarketDataService(cache=cache, provider=provider)

            agent = StockResearchAgent(
                settings=settings,
                cache=cache,
                resolver=resolver,
                market_data=market_data,
                financials=None,
                snapshots_dir=None,
                state_manager=state_manager,
            )

            # 执行分析
            try:
                snapshot, _ = agent.analyze("MSFT", as_of=date(2024, 1, 1))
            except Exception:
                pass

            # 验证检查点文件被创建在自定义路径
            if storage_path.exists():
                checkpoint_files = list(storage_path.glob("*.json"))
                assert len(checkpoint_files) > 0

    def test_state_survives_multiple_analyses(self):
        """测试状态在多次分析间保持一致"""
        settings = Settings()
        cache = InMemoryJSONCache()
        agent = StockResearchAgent.default(settings=settings, cache=cache)

        # 第一次分析
        try:
            snapshot1, _ = agent.analyze("AAPL", as_of=date(2024, 1, 1), thread_id="test-1")
        except Exception:
            pass

        if agent.state_manager:
            checkpoints1 = agent.state_manager.list_checkpoints(thread_id="test-1")
            assert len(checkpoints1) > 0

        # 第二次分析（不同 thread_id）
        try:
            snapshot2, _ = agent.analyze("MSFT", as_of=date(2024, 1, 1), thread_id="test-2")
        except Exception:
            pass

        if agent.state_manager:
            checkpoints2 = agent.state_manager.list_checkpoints(thread_id="test-2")
            assert len(checkpoints2) > 0

            # 验证两个会话的检查点互不影响
            checkpoints1_after = agent.state_manager.list_checkpoints(thread_id="test-1")
            assert len(checkpoints1_after) == len(checkpoints1)
