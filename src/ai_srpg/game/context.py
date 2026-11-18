"""SRPG 游戏业务上下文。

`SRPGGame` 既是 ECS 上下文（继承 ``ECSContext``，实体创建/销毁/按名查找直接调用自身），
又是一次游戏运行的世界状态、领域事件出口与唯一 pipeline 的持有者。

玩家身份与当前控制角色属于玩家会话（``PlayerSession``）与蓝图（``Blueprint``），
不在此重复保存：构建世界时由调用方传入一次，之后以 ECS 的 ``PlayerComponent`` 为准。
"""

from typing import Optional

from loguru import logger

from ..entitas import Entity, ProcessorPipeline
from ..models import WorldState
from .ecs_context import ECSContext
from .events.sink import DomainEventSink, NullEventSink


#################################################################################################################################################
class SRPGGame(ECSContext):
    """SRPG（Strategy RPG）的一次游戏运行上下文。"""

    def __init__(
        self,
        *,
        name: str,
        world: WorldState,
        events: Optional[DomainEventSink] = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.world = world
        self.events: DomainEventSink = events if events is not None else NullEventSink()
        # 由 `create_srpg_game` 装配后替换为空 pipeline 之上的真实流程。
        self.pipeline: ProcessorPipeline = ProcessorPipeline()

    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体：先清理它的 LLM 记忆，再从 ECS 销毁（名称索引同步移除）。"""
        logger.debug(f"destroy_entity: {entity.name}")
        self.world.agent_memories.pop(entity.name, None)
        super().destroy_entity(entity)

    def __repr__(self) -> str:
        return f"<SRPGGame name={self.name!r} entities={self.entity_count}>"
