"""SRPG 游戏业务上下文。

`SRPGGame` 既是 ECS 上下文（继承 ``ECSContext``，实体创建/销毁/按名查找直接调用自身），
又是一次游戏运行的世界状态、玩家身份、领域事件出口与唯一 pipeline 的持有者。
用户会话历史由房间单独持有，不属于这里。
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
        player_name: str,
        player_actor: str,
        world: WorldState,
        events: Optional[DomainEventSink] = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.player_name = player_name
        self.player_actor = player_actor
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
        return f"<SRPGGame name={self.name!r} player={self.player_name!r} entities={self.entity_count}>"
