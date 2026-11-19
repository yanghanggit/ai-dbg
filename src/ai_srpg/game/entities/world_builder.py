"""从蓝图构建实体。

装配期只做三件事：按名字建实体、把 ``system_message`` 写成 ``memories[0]``、
按 ``components`` 逐项挂组件。生成值（创建顺序、实体 ID）由引擎填，其余状态一律
来自内容侧的组件数据——因此这里没有跨实体查找，也没有中间态。
"""

import uuid
from typing import Optional, Type, Union

from loguru import logger

from ...entitas import Entity
from ...entitas.components import Component
from ...models import (
    ActorBlueprint,
    ActorComponent,
    Blueprint,
    IdentityComponent,
    StageBlueprint,
    StageComponent,
    SystemMessage,
    WorldBlueprint,
    WorldComponent,
    resolve_component_type,
)
from ..context import SRPGGame
from ..memory.access import add_system_message
from .player_binding import bind_player_actor

BlueprintEntity = Union[ActorBlueprint, StageBlueprint, WorldBlueprint]


###############################################################################################################################################
def build_from_blueprint(
    srpg_game: SRPGGame,
    blueprint: Blueprint,
    *,
    user_name: str,
    player_actor: Optional[str] = None,
) -> None:
    """按蓝图创建并初始化新游戏世界：世界、舞台、角色。

    ``blueprint`` 是构建期输入，不写进任何运行时容器；``user_name`` 是玩家身份
    （来自会话/房间）。``player_actor`` 指定本局该玩家控制哪个角色——蓝图不声明谁可玩，
    任何角色都能被接管；不指定则不绑定，进场后再认领。两者只在构建期使用，之后以 ECS
    的 ``PlayerComponent`` 为准。
    """
    assert srpg_game.entity_count == 0, "游戏中有实体，不能创建新的游戏"

    stage_names = {stage.name for stage in blueprint.stages}
    for world in blueprint.world_entities:
        _create_entity(srpg_game, world, WorldComponent, "世界")
    for stage in blueprint.stages:
        _create_entity(srpg_game, stage, StageComponent, "舞台")
    for actor in blueprint.actors:
        entity = _create_entity(srpg_game, actor, ActorComponent, "角色")
        _assert_actor_on_declared_stage(entity, stage_names)

    if player_actor is not None:
        bind_player_actor(srpg_game, user_name, player_actor)
        logger.info(f"玩家: {user_name} 选择控制: {player_actor}")


###############################################################################################################################################
def _create_entity(
    srpg_game: SRPGGame,
    model: BlueprintEntity,
    marker: Type[Component],
    kind: str,
) -> Entity:
    """按蓝图声明建一个实体；缺标记组件即视为内容写错。"""
    entity = srpg_game.create_entity(model.name)
    entity.add(
        IdentityComponent,
        srpg_game.entity_naming.next_creation_order(),
        str(uuid.uuid4()),
    )

    assert (
        model.name in model.system_message
    ), f"{kind} {model.name} 的系统消息缺少实体名"
    add_system_message(srpg_game, entity, SystemMessage(content=model.system_message))

    for comp_name, comp_data in model.components.items():
        comp_class = resolve_component_type(comp_name, comp_data)
        entity.set(comp_class, comp_class(**comp_data))

    assert entity.has(marker), f"{kind} {model.name} 缺少标记组件 {marker.__name__}"
    return entity


###############################################################################################################################################
def _assert_actor_on_declared_stage(entity: Entity, stage_names: set[str]) -> None:
    """角色的 ``current_stage`` 必须指向蓝图里声明过的舞台。"""
    current_stage = entity.get(ActorComponent).current_stage
    assert (
        current_stage in stage_names
    ), f"角色 {entity.name} 的所在舞台不存在: {current_stage}"


###############################################################################
__all__ = ["build_from_blueprint"]
