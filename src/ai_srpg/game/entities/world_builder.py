"""从蓝图构建世界、角色与舞台实体。"""

import uuid
from typing import List, Optional

from loguru import logger

from ...entitas import Entity
from ...models import (
    COMPONENT_TYPES,
    Actor,
    ActorComponent,
    AppearanceComponent,
    Blueprint,
    IdentityComponent,
    Stage,
    StageComponent,
    SystemMessage,
    World,
    WorldComponent,
    resolve_component_type,
)
from ..context import SRPGGame
from ..memory.access import add_system_message
from .player_binding import bind_player_actor
from .queries import get_actor_entity


def build_from_blueprint(
    srpg_game: SRPGGame,
    blueprint: Blueprint,
    *,
    user_name: str,
    player_actor: Optional[str] = None,
) -> None:
    """按蓝图创建并初始化新游戏世界，包括世界、角色和舞台。

    ``blueprint`` 是构建期输入，不写进任何运行时容器；``user_name`` 是玩家身份
    （来自会话/房间），``player_actor`` 缺省时取蓝图声明的受控角色。两者只在构建期
    使用，之后以 ECS 的 ``PlayerComponent`` 为准。
    """
    assert srpg_game.entity_count == 0, "游戏中有实体，不能创建新的游戏"

    _create_world_entities(srpg_game, blueprint.world_entities)
    create_actor_entities(
        srpg_game,
        [actor for stage in blueprint.stages for actor in stage.actors],
    )
    create_stage_entities(srpg_game, blueprint.stages)

    actor_name = player_actor or blueprint.player_actor
    bind_player_actor(srpg_game, user_name, actor_name)
    logger.info(f"玩家: {user_name} 选择控制: {actor_name}")


def _create_world_entities(
    srpg_game: SRPGGame, world_models: List[World]
) -> List[Entity]:
    """创建世界实体（全局规则管理器、叙事者）。"""
    world_entities: List[Entity] = []
    for world_model in world_models:
        world_entity = srpg_game.create_entity(world_model.name)
        world_entity.add(
            IdentityComponent,
            world_model.name,
            srpg_game.entity_naming.next_creation_order(),
            str(uuid.uuid4()),
        )
        world_entity.add(WorldComponent, world_model.name)

        assert (
            world_model.name in world_model.system_message
        ), f"world_model.system_message 缺少 {world_model.name} 的系统消息"
        add_system_message(
            srpg_game,
            world_entity,
            SystemMessage(content=world_model.system_message),
        )

        for comp_name, comp_data in world_model.components.items():
            comp_class = COMPONENT_TYPES.get(comp_name)
            assert comp_class is not None, f"未知组件类型: {comp_name}"
            world_entity.set(comp_class, comp_class(**comp_data))

        world_entities.append(world_entity)
    return world_entities


def create_actor_entities(
    srpg_game: SRPGGame, actor_models: List[Actor]
) -> List[Entity]:
    """创建蓝图声明的全部角色实体；谁被玩家控制由 ``PlayerComponent`` 决定。"""
    actor_entities: List[Entity] = []
    for actor_model in actor_models:
        actor_entity = srpg_game.create_entity(actor_model.name)
        actor_entity.add(
            IdentityComponent,
            actor_model.name,
            srpg_game.entity_naming.next_creation_order(),
            str(uuid.uuid4()),
        )
        actor_entity.add(ActorComponent, actor_model.name, "")

        assert (
            actor_model.name in actor_model.system_message
        ), f"actor_model.system_message 缺少 {actor_model.name} 的系统消息"
        add_system_message(
            srpg_game,
            actor_entity,
            SystemMessage(content=actor_model.system_message),
        )

        assert (
            actor_model.base_body != ""
        ), f"actor_model.base_body 不能为空: {actor_model.name}"
        actor_entity.add(
            AppearanceComponent,
            actor_model.name,
            actor_model.base_body,
            actor_model.base_body,
        )

        for comp_name, comp_data in actor_model.components.items():
            comp_class = COMPONENT_TYPES.get(comp_name)
            assert comp_class is not None, f"未知组件类型: {comp_name}"
            actor_entity.set(comp_class, comp_class(**comp_data))

        actor_entities.append(actor_entity)
    return actor_entities


def create_stage_entities(
    srpg_game: SRPGGame, stage_models: List[Stage]
) -> List[Entity]:
    """创建舞台实体，并建立角色与舞台的关联关系。"""
    stage_entities: List[Entity] = []
    for stage_model in stage_models:
        stage_entity = srpg_game.create_entity(stage_model.name)
        stage_entity.add(
            IdentityComponent,
            stage_model.name,
            srpg_game.entity_naming.next_creation_order(),
            str(uuid.uuid4()),
        )
        stage_entity.add(StageComponent, stage_model.name)

        assert stage_model.name in stage_model.system_message
        add_system_message(
            srpg_game,
            stage_entity,
            SystemMessage(content=stage_model.system_message),
        )

        for comp_name, comp_data in stage_model.components.items():
            comp_class = resolve_component_type(comp_name, comp_data)
            stage_entity.set(comp_class, comp_class(**comp_data))

        for actor_model in stage_model.actors:
            actor_entity = get_actor_entity(srpg_game, actor_model.name)
            assert actor_entity is not None, f"找不到actor_entity: {actor_model.name}"
            actor_entity.replace(ActorComponent, actor_model.name, stage_model.name)

        stage_entities.append(stage_entity)
    return stage_entities
