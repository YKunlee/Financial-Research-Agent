"""状态机管理器 (State Machine Manager)

模块职责：
- 管理金融研究 Agent 的完整状态流转
- 支持状态版本控制、检查点保存和回滚
- 实现证据链追溯，确保金融级可审计性
- 提供线程安全的状态持久化机制

核心功能：
1. ResearchState: 定义 Agent 认知状态的完整结构
2. StateManager: 管理状态转换、持久化和回溯
3. Checkpoint: 支持多版本状态快照
4. Evidence Chain: 反向追溯结论到原始数据

输入：
- 来自 identify.py 的公司实体
- 来自 datasources.py 的原始数据
- 来自 metrics.py 的计算结果
- 来自 rules.py 的规则检查结果
- 来自 llm.py 的 LLM 消息

输出：
- 可回溯的状态快照
- 完整的执行轨迹
- 证据链映射

架构角色：
作为 Agent 的"记忆系统"，记录每个决策节点的完整上下文，
支持调试、审计和状态恢复。类似 LangGraph 的 State 管理层。
"""
from __future__ import annotations

import hashlib
import threading
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

from finresearch_agent.models import (
    AnalysisSnapshot,
    CompanyIdentity,
    FinancialQuarter,
    MarketData,
    RiskMetrics,
    RuleResults,
    TechnicalIndicators,
)
from finresearch_agent.utils import canonical_dumps, json_dumps, json_loads


# ============================================================================
# 1. 核心状态模型 (State Schema)
# ============================================================================

class LLMMessage(BaseModel):
    """LLM 消息记录，类似 LangChain 的 Message"""
    model_config = ConfigDict(extra="forbid")
    
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    token_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SnapshotMetadata(BaseModel):
    """快照元数据"""
    model_config = ConfigDict(extra="forbid")
    
    timestamp: datetime = Field(default_factory=datetime.now)
    step_index: int
    node_name: str
    thread_id: str
    total_tokens: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None


class ResearchState(BaseModel):
    """研究状态的完整定义 - Agent 的认知状态"""
    model_config = ConfigDict(extra="forbid")
    
    # 核心字段
    thread_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str = ""  # 用户原始查询
    
    # Target: 识别出的公司实体
    target: CompanyIdentity | None = None
    
    # Data_Store: 原始未加工数据
    data_store: dict[str, Any] = Field(default_factory=dict)
    
    # Analytic_Metrics: 计算出的量化结果
    analytic_metrics: dict[str, Any] = Field(default_factory=dict)
    
    # Rules_Violations: 规则检查结果
    rules_violations: list[dict[str, Any]] = Field(default_factory=list)
    
    # Messages: LLM 交互轨迹
    messages: list[LLMMessage] = Field(default_factory=list)
    
    # Snapshot_Metadata: 元数据
    snapshot_metadata: SnapshotMetadata | None = None
    
    # 最终快照（向后兼容）
    final_snapshot: AnalysisSnapshot | None = None


# ============================================================================
# 2. 状态管理器 (State Manager)
# ============================================================================

class StateManager:
    """线程安全的状态管理器"""
    
    def __init__(self, storage_backend: str | Path | None = None, cache_backend: Any | None = None):
        """
        Args:
            storage_backend: JSON 存储路径或 Redis URL
            cache_backend: 可选的 JSONCache 实例（用于 Redis）
        """
        self._current_state: ResearchState | None = None
        self._checkpoints: dict[str, list[ResearchState]] = {}  # thread_id -> states
        self._lock = threading.RLock()
        self._storage_backend = Path(storage_backend) if storage_backend else None
        self._cache_backend = cache_backend
        
        if self._storage_backend and isinstance(self._storage_backend, Path):
            self._storage_backend.mkdir(parents=True, exist_ok=True)
    
    def init_state(self, query: str, thread_id: str | None = None) -> ResearchState:
        """初始化新状态"""
        with self._lock:
            state = ResearchState(
                query=query,
                thread_id=thread_id or str(uuid4()),
                snapshot_metadata=SnapshotMetadata(
                    step_index=0,
                    node_name="init",
                    thread_id=thread_id or str(uuid4())
                )
            )
            self._current_state = state
            return deepcopy(state)
    
    def update_state(self, key: str, value: Any, append: bool = False) -> ResearchState:
        """更新状态字段
        
        Args:
            key: 状态字段名
            append: 如果为 True，则追加到列表字段而非覆盖
        """
        with self._lock:
            if self._current_state is None:
                raise ValueError("State not initialized. Call init_state() first.")
            
            state_dict = self._current_state.model_dump()
            
            if append and key in ["messages", "rules_violations"]:
                if not isinstance(value, list):
                    value = [value]
                state_dict[key].extend(value)
            else:
                state_dict[key] = value
            
            # 更新 step_index
            if state_dict["snapshot_metadata"]:
                state_dict["snapshot_metadata"]["step_index"] += 1
                state_dict["snapshot_metadata"]["timestamp"] = datetime.now()
            
            self._current_state = ResearchState(**state_dict)
            return deepcopy(self._current_state)
    
    def get_state(self) -> ResearchState | None:
        """获取当前状态的副本"""
        with self._lock:
            return deepcopy(self._current_state) if self._current_state else None
    
    def save_checkpoint(self, node_name: str | None = None) -> str:
        """保存检查点
        
        Returns:
            checkpoint_id: 格式为 {thread_id}:{step_index}
        """
        with self._lock:
            if self._current_state is None:
                raise ValueError("No state to checkpoint")
            
            state = deepcopy(self._current_state)
            
            # 更新元数据
            if state.snapshot_metadata:
                if node_name:
                    state.snapshot_metadata.node_name = node_name
                state.snapshot_metadata.timestamp = datetime.now()
            
            # 存储到内存
            thread_id = state.thread_id
            if thread_id not in self._checkpoints:
                self._checkpoints[thread_id] = []
            self._checkpoints[thread_id].append(state)
            
            # 持久化
            step_index = state.snapshot_metadata.step_index if state.snapshot_metadata else 0
            checkpoint_id = f"{thread_id}:{step_index}"
            
            if self._storage_backend:
                self._persist_checkpoint(checkpoint_id, state)
            
            return checkpoint_id
    
    def rollback(self, step_index: int) -> ResearchState:
        """回滚到指定步骤
        
        Args:
            step_index: 目标步骤索引
            
        Returns:
            回滚后的状态
        """
        with self._lock:
            if self._current_state is None:
                raise ValueError("No current state")
            
            thread_id = self._current_state.thread_id
            checkpoints = self._checkpoints.get(thread_id, [])
            
            # 查找目标步骤
            target_state = None
            for state in checkpoints:
                if state.snapshot_metadata and state.snapshot_metadata.step_index == step_index:
                    target_state = state
                    break
            
            if target_state is None:
                raise ValueError(f"No checkpoint found for step {step_index}")
            
            self._current_state = deepcopy(target_state)
            return deepcopy(target_state)
    
    def get_evidence_chain(self, conclusion_key: str) -> dict[str, Any]:
        """获取证据链：从结论反向追溯到原始数据
        
        Args:
            conclusion_key: 结论字段键（如 'rules_violations', 'analytic_metrics'）
            
        Returns:
            包含完整证据链的字典
        """
        with self._lock:
            if self._current_state is None:
                return {}
            
            state = self._current_state
            evidence = {
                "conclusion": getattr(state, conclusion_key, None),
                "thread_id": state.thread_id,
                "query": state.query,
            }
            
            # 映射关系
            if conclusion_key == "rules_violations":
                evidence["supporting_metrics"] = state.analytic_metrics
                evidence["raw_data"] = state.data_store.get("market_data")
                evidence["target"] = state.target
            
            elif conclusion_key == "analytic_metrics":
                evidence["raw_data"] = state.data_store.get("market_data")
                evidence["target"] = state.target
            
            # 添加消息轨迹
            evidence["message_trace"] = [
                {"role": m.role, "timestamp": m.timestamp, "tokens": m.token_count}
                for m in state.messages
            ]
            
            return evidence
    
    def list_checkpoints(self, thread_id: str | None = None) -> list[dict[str, Any]]:
        """列出所有检查点"""
        with self._lock:
            tid = thread_id or (self._current_state.thread_id if self._current_state else None)
            if not tid:
                return []
            
            checkpoints = self._checkpoints.get(tid, [])
            return [
                {
                    "step_index": c.snapshot_metadata.step_index if c.snapshot_metadata else 0,
                    "node_name": c.snapshot_metadata.node_name if c.snapshot_metadata else "unknown",
                    "timestamp": c.snapshot_metadata.timestamp if c.snapshot_metadata else None,
                }
                for c in checkpoints
            ]
    
    def _persist_checkpoint(self, checkpoint_id: str, state: ResearchState) -> None:
        """持久化检查点"""
        if isinstance(self._storage_backend, Path):
            # JSON 文件存储
            safe_checkpoint_id = checkpoint_id.replace(":", "__")
            filepath = self._storage_backend / f"{safe_checkpoint_id}.json"
            filepath.write_text(
                json_dumps(state.model_dump(mode="json")),
                encoding="utf-8"
            )
        elif self._cache_backend:
            # Redis 存储
            key = f"checkpoint:{checkpoint_id}"
            self._cache_backend.set_json(key, state.model_dump(mode="json"), ttl_seconds=86400 * 7)
    
    def load_checkpoint(self, checkpoint_id: str) -> ResearchState:
        """从持久化存储加载检查点"""
        with self._lock:
            if isinstance(self._storage_backend, Path):
                safe_checkpoint_id = checkpoint_id.replace(":", "__")
                filepath = self._storage_backend / f"{safe_checkpoint_id}.json"
                if not filepath.exists() and safe_checkpoint_id != checkpoint_id:
                    # Backward compatible for POSIX checkpoints written with ":" in filename.
                    legacy = self._storage_backend / f"{checkpoint_id}.json"
                    if legacy.exists():
                        filepath = legacy
                if not filepath.exists():
                    raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found")
                data = json_loads(filepath.read_text(encoding="utf-8"))
                return ResearchState(**data)
            elif self._cache_backend:
                key = f"checkpoint:{checkpoint_id}"
                data = self._cache_backend.get_json(key)
                if data is None:
                    raise ValueError(f"Checkpoint {checkpoint_id} not found in cache")
                return ResearchState(**data)
            else:
                raise ValueError("No storage backend configured")


# ============================================================================
# 3. 向后兼容的快照构建函数
# ============================================================================

def build_snapshot(
    *,
    identity: CompanyIdentity,
    as_of,
    market_data: MarketData,
    financials: list[FinancialQuarter],
    technicals: TechnicalIndicators,
    risk: RiskMetrics,
    rules: RuleResults,
    persist_dir: str | Path | None = None,
    state_manager: StateManager | None = None,
) -> AnalysisSnapshot:
    """构建分析快照（保持向后兼容）
    
    Args:
        state_manager: 可选的状态管理器，用于同步更新状态
    """
    data_timestamps = {
        "market_data": market_data.data_timestamp,
        "financials": max((f.data_timestamp for f in financials), default=market_data.data_timestamp),
    }
    algo_versions = {
        "metrics": technicals.algo_version,
        "risk": risk.algo_version,
        "rules": rules.rule_version,
    }

    seed = {
        "symbol": identity.symbol,
        "market": identity.market,
        "company_name": identity.company_name,
        "as_of": as_of,
        "data_timestamps": data_timestamps,
        "algo_versions": algo_versions,
        "identity": identity.model_dump(mode="json"),
        "market_data": market_data.model_dump(mode="json"),
        "financials": [f.model_dump(mode="json") for f in financials],
        "technicals": technicals.model_dump(mode="json"),
        "risk": risk.model_dump(mode="json"),
        "rules": rules.model_dump(mode="json"),
    }
    analysis_id = _hash_seed(seed)

    snapshot = AnalysisSnapshot(
        analysis_id=analysis_id,
        symbol=identity.symbol,
        market=identity.market,
        company_name=identity.company_name,
        as_of=as_of,
        data_timestamps=data_timestamps,
        algo_versions=algo_versions,
        identity=identity,
        market_data=market_data,
        financials=financials,
        technicals=technicals,
        risk=risk,
        rules=rules,
    )

    if persist_dir is not None:
        _persist_snapshot(snapshot, persist_dir)
    
    # 如果提供了状态管理器，同步更新状态
    if state_manager:
        state_manager.update_state("final_snapshot", snapshot)
        state_manager.save_checkpoint(node_name="snapshot_built")

    return snapshot


def _hash_seed(seed: dict) -> str:
    canon = canonical_dumps(seed).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _persist_snapshot(snapshot: AnalysisSnapshot, persist_dir: str | Path) -> None:
    p = Path(persist_dir)
    p.mkdir(parents=True, exist_ok=True)
    out = p / f"{snapshot.analysis_id}.json"
    if out.exists():
        return
    out.write_text(json_dumps(snapshot.model_dump(mode="json")), encoding="utf-8")
