"""测试状态机管理器功能"""
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from finresearch_agent.models import CompanyIdentity
from finresearch_agent.state import (
    LLMMessage,
    ResearchState,
    SnapshotMetadata,
    StateManager,
)


class TestResearchState:
    """测试 ResearchState 模型"""

    def test_init_empty_state(self):
        """测试创建空状态"""
        state = ResearchState()
        assert state.thread_id != ""
        assert state.query == ""
        assert state.target is None
        assert state.data_store == {}
        assert state.analytic_metrics == {}
        assert state.rules_violations == []
        assert state.messages == []

    def test_state_with_target(self):
        """测试带有目标的状态"""
        identity = CompanyIdentity(
            symbol="AAPL",
            market="US",
            company_name="Apple Inc.",
            matched_on="ticker",
            query="苹果",
        )
        state = ResearchState(query="苹果", target=identity)
        assert state.target.symbol == "AAPL"
        assert state.target.company_name == "Apple Inc."


class TestStateManager:
    """测试 StateManager 功能"""

    def test_init_state(self):
        """测试初始化状态"""
        manager = StateManager()
        state = manager.init_state(query="测试查询", thread_id="test-123")

        assert state.thread_id == "test-123"
        assert state.query == "测试查询"
        assert state.snapshot_metadata.step_index == 0
        assert state.snapshot_metadata.node_name == "init"

    def test_update_state(self):
        """测试更新状态"""
        manager = StateManager()
        manager.init_state(query="测试")

        # 更新单个字段
        identity = CompanyIdentity(
            symbol="AAPL",
            market="US",
            company_name="Apple Inc.",
            matched_on="ticker",
            query="苹果",
        )
        state = manager.update_state("target", identity)

        assert state.target.symbol == "AAPL"
        assert state.snapshot_metadata.step_index == 1

    def test_update_state_append(self):
        """测试追加到列表字段"""
        manager = StateManager()
        manager.init_state(query="测试")

        # 追加消息
        msg1 = LLMMessage(role="user", content="第一条消息")
        state1 = manager.update_state("messages", msg1, append=True)
        assert len(state1.messages) == 1

        msg2 = LLMMessage(role="assistant", content="第二条消息")
        state2 = manager.update_state("messages", msg2, append=True)
        assert len(state2.messages) == 2
        assert state2.messages[0].content == "第一条消息"
        assert state2.messages[1].content == "第二条消息"

    def test_save_and_list_checkpoints(self):
        """测试保存和列出检查点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(storage_backend=Path(tmpdir))
            state = manager.init_state(query="测试", thread_id="test-123")

            # 保存多个检查点
            cp1 = manager.save_checkpoint(node_name="step1")
            assert cp1 == "test-123:0"

            manager.update_state("query", "更新后的查询")  # step_index 变为 1
            cp2 = manager.save_checkpoint(node_name="step2")
            assert cp2 == "test-123:1"  # 修正期望值

            # 列出检查点
            checkpoints = manager.list_checkpoints()
            assert len(checkpoints) == 2
            assert checkpoints[0]["node_name"] == "step1"
            assert checkpoints[0]["step_index"] == 0
            assert checkpoints[1]["node_name"] == "step2"
            assert checkpoints[1]["step_index"] == 1

    def test_rollback(self):
        """测试状态回滚"""
        manager = StateManager()
        manager.init_state(query="初始查询", thread_id="test-123")  # step=0
        manager.save_checkpoint(node_name="checkpoint_0")  # 保存 step=0

        # 更新状态
        manager.update_state("query", "第一次更新")  # step=1
        manager.save_checkpoint(node_name="checkpoint_1")  # 保存 step=1

        manager.update_state("query", "第二次更新")  # step=2
        manager.save_checkpoint(node_name="checkpoint_2")  # 保存 step=2

        current = manager.get_state()
        assert current.query == "第二次更新"
        assert current.snapshot_metadata.step_index == 2  # 修正期望值

        # 回滚到步骤 1
        rolled_back = manager.rollback(step_index=1)  # 修正回滚目标
        assert rolled_back.query == "第一次更新"
        assert rolled_back.snapshot_metadata.step_index == 1

    def test_get_evidence_chain_for_rules(self):
        """测试获取规则违规的证据链"""
        manager = StateManager()
        manager.init_state(query="测试", thread_id="test-123")

        # 添加目标
        identity = CompanyIdentity(
            symbol="AAPL",
            market="US",
            company_name="Apple Inc.",
            matched_on="ticker",
            query="苹果",
        )
        manager.update_state("target", identity)

        # 添加数据
        manager.update_state("data_store", {"market_data": {"symbol": "AAPL", "bars": []}})

        # 添加指标
        manager.update_state("analytic_metrics", {"volatility": 0.35, "max_drawdown": -0.28})

        # 添加违规
        manager.update_state(
            "rules_violations",
            [{"code": "HIGH_VOLATILITY", "severity": "high", "title": "波动率过高"}],
        )

        # 获取证据链
        evidence = manager.get_evidence_chain("rules_violations")

        assert len(evidence["conclusion"]) == 1
        assert evidence["conclusion"][0]["code"] == "HIGH_VOLATILITY"
        assert evidence["supporting_metrics"]["volatility"] == 0.35
        assert evidence["raw_data"]["symbol"] == "AAPL"
        assert evidence["target"].symbol == "AAPL"

    def test_get_evidence_chain_for_metrics(self):
        """测试获取分析指标的证据链"""
        manager = StateManager()
        manager.init_state(query="测试", thread_id="test-123")

        identity = CompanyIdentity(
            symbol="AAPL",
            market="US",
            company_name="Apple Inc.",
            matched_on="ticker",
            query="苹果",
        )
        manager.update_state("target", identity)
        manager.update_state("data_store", {"market_data": {"symbol": "AAPL"}})
        manager.update_state("analytic_metrics", {"ma_20": 150.5})

        evidence = manager.get_evidence_chain("analytic_metrics")

        assert evidence["conclusion"]["ma_20"] == 150.5
        assert evidence["raw_data"]["symbol"] == "AAPL"
        assert evidence["target"].symbol == "AAPL"

    def test_persistence_to_json(self):
        """测试持久化到 JSON 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            manager = StateManager(storage_backend=storage_path)

            manager.init_state(query="测试持久化", thread_id="persist-123")
            checkpoint_id = manager.save_checkpoint(node_name="test_node")

            # 验证文件已创建
            checkpoint_file = storage_path / f"{checkpoint_id}.json"
            assert checkpoint_file.exists()

            # 加载检查点
            loaded_state = manager.load_checkpoint(checkpoint_id)
            assert loaded_state.query == "测试持久化"
            assert loaded_state.thread_id == "persist-123"
            assert loaded_state.snapshot_metadata.node_name == "test_node"

    def test_thread_safety(self):
        """测试线程安全（基础测试）"""
        import threading

        manager = StateManager()
        manager.init_state(query="测试线程安全", thread_id="thread-test")

        def update_query(value):
            manager.update_state("query", f"更新-{value}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=update_query, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证状态仍然有效
        state = manager.get_state()
        assert state is not None
        assert state.thread_id == "thread-test"

    def test_error_on_update_without_init(self):
        """测试未初始化时更新状态会报错"""
        manager = StateManager()
        with pytest.raises(ValueError, match="State not initialized"):
            manager.update_state("query", "测试")

    def test_error_on_rollback_invalid_step(self):
        """测试回滚到无效步骤会报错"""
        manager = StateManager()
        manager.init_state(query="测试", thread_id="test-123")
        manager.save_checkpoint()

        with pytest.raises(ValueError, match="No checkpoint found"):
            manager.rollback(step_index=999)


class TestLLMMessage:
    """测试 LLMMessage 模型"""

    def test_create_message(self):
        """测试创建消息"""
        msg = LLMMessage(role="user", content="测试消息", token_count=10)

        assert msg.role == "user"
        assert msg.content == "测试消息"
        assert msg.token_count == 10
        assert isinstance(msg.timestamp, datetime)

    def test_message_with_metadata(self):
        """测试带元数据的消息"""
        msg = LLMMessage(
            role="assistant",
            content="回复",
            metadata={"model": "gpt-4", "temperature": 0.7},
        )

        assert msg.metadata["model"] == "gpt-4"
        assert msg.metadata["temperature"] == 0.7


class TestSnapshotMetadata:
    """测试 SnapshotMetadata 模型"""

    def test_create_metadata(self):
        """测试创建元数据"""
        meta = SnapshotMetadata(
            step_index=5,
            node_name="compute_metrics",
            thread_id="test-123",
            total_tokens=1000,
            execution_time_ms=250.5,
        )

        assert meta.step_index == 5
        assert meta.node_name == "compute_metrics"
        assert meta.thread_id == "test-123"
        assert meta.total_tokens == 1000
        assert meta.execution_time_ms == 250.5
        assert meta.error is None

    def test_metadata_with_error(self):
        """测试带错误信息的元数据"""
        meta = SnapshotMetadata(
            step_index=3,
            node_name="fetch_data",
            thread_id="test-456",
            error="API 调用失败",
        )

        assert meta.error == "API 调用失败"
