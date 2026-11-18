"""ECS context 与序列化数据之间的转换。"""

from typing import Dict, Set, Type

from ...entitas import (
    Component,
    ContextData,
    Entity,
    dump_context,
    dump_entities,
)
from ...models import COMPONENT_TYPES, resolve_component_type
from ..context import SRPGGame


def _is_persistable_component(comp_type: Type[Component]) -> bool:
    """组件类型是否已注册（只有注册过的组件才会被整体序列化）。"""
    return COMPONENT_TYPES.get(comp_type.__name__) is not None


def serialize_entities(srpg_game: SRPGGame, entities: Set[Entity]) -> ContextData:
    """将实体集合导出为 name-keyed 的 ContextData（只含已注册组件）。"""
    ordered = sorted(entities, key=lambda entity: entity.index)
    return dump_entities(ordered, component_filter=_is_persistable_component)


def serialize_context(srpg_game: SRPGGame) -> ContextData:
    """将整个 ECS context 导出为 name-keyed 的 ContextData（只含已注册组件）。"""
    return dump_context(srpg_game.ecs, component_filter=_is_persistable_component)


def restore_context(srpg_game: SRPGGame, data: ContextData) -> Dict[str, Entity]:
    """从 name-keyed 的 ContextData 还原 ECS context，并重建名称索引。"""
    return srpg_game.ecs.restore(data, resolve_component_type)
