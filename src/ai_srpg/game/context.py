"""SRPG 游戏业务上下文。

`SRPGGame` 既是 ECS 上下文（继承 ``ECSContext``，实体创建/销毁/按名查找直接调用自身），
又是一次游戏运行的运行时状态（实体身份分配、agent 记忆）、领域事件出口与唯一 pipeline 的持有者。

玩家身份与当前控制角色属于玩家会话（``PlayerSession``）与蓝图（``Blueprint``），
不在此重复保存：构建世界时由调用方传入一次，之后以 ECS 的 ``PlayerComponent`` 为准。
"""

from typing import Optional

from loguru import logger

from ..entitas import Entity, ProcessorPipeline
from ..models import (
    SNAPSHOT_FORMAT_VERSION,
    AgentMemoryStore,
    ContextSnapshot,
    EntityNaming,
    resolve_component_type,
)
from .ecs_context import ECSContext
from .events.sink import DomainEventSink, NullEventSink


#################################################################################################################################################
class SRPGGame(ECSContext):
    """SRPG（Strategy RPG）的一次游戏运行上下文。"""

    def __init__(
        self,
        *,
        name: str,
        events: Optional[DomainEventSink] = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.entity_naming: EntityNaming = EntityNaming()
        self.agent_memory_store: AgentMemoryStore = AgentMemoryStore()
        self.events: DomainEventSink = events if events is not None else NullEventSink()
        # 由 `create_srpg_game` 装配后替换为空 pipeline 之上的真实流程。
        self.pipeline: ProcessorPipeline = ProcessorPipeline()

    def snapshot(self) -> ContextSnapshot:
        """导出当前 ECS 核心状态（实体与组件）。

        不包含 agent 记忆：记忆管理与 ECS 是平级系统，各自维护自己的快照。
        """
        return ContextSnapshot(
            game=self.name,
            entity_naming_counter=self.entity_naming.counter,
            entities=self.snapshot_entities(),
        )

    def restore_snapshot(self, snapshot: ContextSnapshot) -> None:
        """在空 context 上恢复快照。

        :raises ValueError: 格式版本或游戏名不匹配
        """
        if snapshot.format_version != SNAPSHOT_FORMAT_VERSION:
            raise ValueError(
                f"快照格式版本不匹配: {snapshot.format_version} != {SNAPSHOT_FORMAT_VERSION}"
            )
        if snapshot.game != self.name:
            raise ValueError(
                f"快照属于游戏 {snapshot.game!r}，不能恢复到 {self.name!r}"
            )

        self.restore(snapshot.entities, resolve_component_type)
        self.entity_naming = EntityNaming(snapshot.entity_naming_counter)

    def rollback(self, snapshot: ContextSnapshot) -> None:
        """清空当前状态并回到快照（用于运行失败后的回滚）。

        ``clear()`` 会让既有 group 与 reactive collector 失效，调用方必须随后
        重建 pipeline（``build_game_pipeline``）并重新 initialize。
        """
        self.clear()
        self.restore_snapshot(snapshot)

    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体：先清理它的 LLM 记忆，再从 ECS 销毁（名称索引同步移除）。"""
        logger.debug(f"destroy_entity: {entity.name}")
        self.agent_memory_store.remove(entity.name)
        super().destroy_entity(entity)

    def __repr__(self) -> str:
        return f"<SRPGGame name={self.name!r} entities={self.entity_count}>"
