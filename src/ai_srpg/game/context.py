"""
SRPG 游戏业务上下文。

`SRPGGame` 保存一次游戏运行所需的世界状态、ECS context、玩家身份、领域事件出口
与唯一 pipeline；ECS context 内部维护实体名称索引。用户会话历史由房间单独持有，
不属于这里。
所有游戏领域操作都以模块函数的形式接收 `SRPGGame`，不再把行为挂在这个对象上。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional

from ..entitas import (
    ComponentResolver,
    Context,
    ContextData,
    Entity,
    load_context,
)
from ..models import WorldState
from .events import DomainEventSink, NullEventSink

if TYPE_CHECKING:
    from ..entitas import ProcessorPipeline


#################################################################################################################################################
class ECSContext(Context):
    """游戏层 ECS 上下文：在基础 Context 上维护实体名称索引。

    名称索引是游戏层的派生数据，不应该暴露给业务代码；创建、销毁、按名称查找
    与快照恢复都通过本类的方法完成。
    """

    def __init__(self) -> None:
        super().__init__()
        self._entity_index: Dict[str, Entity] = {}

    def create_entity(self, name: str = "") -> Entity:
        """创建实体；提供 name 时同时写入名称索引。"""
        entity = super().create_entity()
        if name:
            self.register_entity(entity, name)
        return entity

    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体，并移除其名称索引。"""
        super().destroy_entity(entity)
        if self._entity_index.get(entity.name) is entity:
            self._entity_index.pop(entity.name, None)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """按名称查找实体；索引缺失时回退扫描 context。"""
        indexed = self._entity_index.get(name)
        if indexed is not None:
            return indexed
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None

    def register_entity(self, entity: Entity, name: Optional[str] = None) -> None:
        """把实体登记到名称索引；可选地同时设置实体名称。"""
        if name is not None:
            entity.name = name
        self._entity_index[entity.name] = entity

    def restore(
        self, data: ContextData, resolve_type: ComponentResolver
    ) -> Dict[str, Entity]:
        """从名称键控的 ContextData 恢复实体，并同步名称索引。"""
        restored = load_context(self, data, resolve_type)
        self._entity_index.update(restored)
        return restored


#################################################################################################################################################
@dataclass
class SRPGGame:
    """SRPG（Strategy RPG）的一次游戏运行上下文。"""

    name: str
    player_name: str
    player_actor: str
    world: WorldState
    ecs: ECSContext = field(default_factory=ECSContext)
    events: DomainEventSink = field(default_factory=NullEventSink)
    pipeline: ProcessorPipeline = field(init=False)

    def __repr__(self) -> str:
        return f"<SRPGGame name={self.name!r} player={self.player_name!r} entities={self.ecs.entity_count}>"
