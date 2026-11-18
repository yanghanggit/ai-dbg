"""游戏层 ECS 上下文。

在 entitas 的 ``Context`` 之上维护「实体名 → 实体」索引：索引是游戏层的派生数据，
创建、销毁、按名称查找、快照序列化/恢复都通过本类的方法完成，业务代码不需要感知索引。
"""

from typing import Dict, Optional, Set, Type

from ..entitas import (
    Component,
    ComponentResolver,
    Context,
    ContextData,
    Entity,
    dump_context,
    dump_entities,
    load_context,
)
from ..models import COMPONENT_TYPES


def _is_persistable_component(comp_type: Type[Component]) -> bool:
    """组件类型是否已注册（只有注册过的组件才会被整体序列化）。"""
    return COMPONENT_TYPES.get(comp_type.__name__) is not None


#################################################################################################################################################
class ECSContext(Context):
    """游戏层 ECS 上下文：在基础 Context 上维护实体名称索引。"""

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

    def serialize(self, entities: Optional[Set[Entity]] = None) -> ContextData:
        """导出为 name-keyed 的 ContextData（只含已注册组件）。

        不传 ``entities`` 时导出整个 context；传入时只导出该实体集合，
        并按 slot index（创建顺序）排序，保证快照稳定。
        """
        if entities is None:
            return dump_context(self, component_filter=_is_persistable_component)
        ordered = sorted(entities, key=lambda entity: entity.index)
        return dump_entities(ordered, component_filter=_is_persistable_component)

    def restore(
        self, data: ContextData, resolve_type: ComponentResolver
    ) -> Dict[str, Entity]:
        """从名称键控的 ContextData 恢复实体，并同步名称索引。"""
        restored = load_context(self, data, resolve_type)
        self._entity_index.update(restored)
        return restored
