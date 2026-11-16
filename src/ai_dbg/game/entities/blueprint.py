"""从蓝图构建世界、角色与场景实体。"""

import copy
import uuid
from typing import List, Optional

from loguru import logger

from ...entitas import Entity
from ...models import (
    COMPONENT_TYPES,
    Actor,
    ActorComponent,
    ActorType,
    AppearanceComponent,
    CharacterStatsComponent,
    DeckComponent,
    DungeonComponent,
    IdentityComponent,
    InventoryComponent,
    LobbyComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    Stage,
    StageComponent,
    StageType,
    SystemMessage,
    World,
    WorldComponent,
    resolve_component_type,
)
from ..context import DBGGame
from ..memory import add_system_message
from .repository import create_entity, get_actor_entity


def _assert_deck_sources(actor_name: str, deck_comp: Optional[DeckComponent]) -> None:
    """入口不变量：牌库中每张卡必须显式带 source，且 source 必须等于持有者。"""
    assert deck_comp is not None, f"{actor_name} 缺少 DeckComponent"
    for card in deck_comp.cards:
        assert (
            card.source.strip()
        ), f"{actor_name} 的卡「{card.name}」缺少 source：牌库中每张卡都必须显式设置 source（见 demo/world.py）"
        assert (
            card.source == actor_name
        ), f"{actor_name} 的卡「{card.name}」source={card.source!r} 与持有者不符：持久牌库中的卡 source 必须等于持有者名"


def build_from_blueprint(dbg_game: DBGGame) -> None:
    """创建并初始化新游戏世界，包括世界、角色和场景。"""
    assert len(dbg_game.world.entities) == 0, "游戏中有实体，不能创建新的游戏"
    if len(dbg_game.world.entities) > 0:
        logger.warning(
            f"游戏中有实体，不能创建新的游戏，entities = {dbg_game.world.entities}"
        )
        return

    _create_world_entities(dbg_game, dbg_game.world.blueprint.world_entities)
    create_actor_entities(
        dbg_game,
        [actor for stage in dbg_game.world.blueprint.stages for actor in stage.actors],
    )
    create_stage_entities(dbg_game, dbg_game.world.blueprint.stages)

    assert dbg_game.player_name.strip() != "", "玩家名字不能为空"
    assert dbg_game.player_actor.strip() != "", "玩家角色不能为空"
    player_actor_entity = get_actor_entity(dbg_game, dbg_game.player_actor)
    assert (
        player_actor_entity is not None
    ), f"找不到玩家角色实体: {dbg_game.player_actor}"
    assert not player_actor_entity.has(PlayerComponent)
    player_actor_entity.replace(PlayerComponent, dbg_game.player_name)
    logger.info(f"玩家: {dbg_game.player_name} 选择控制: {dbg_game.player_actor}")
    assert player_actor_entity.has(
        InventoryComponent
    ), "玩家角色实体必须有 InventoryComponent"


def _create_world_entities(
    dbg_game: DBGGame, world_models: List[World]
) -> List[Entity]:
    """创建世界实体（全局规则管理器、叙事者）。"""
    world_entities: List[Entity] = []
    for world_model in world_models:
        world_entity = create_entity(dbg_game, world_model.name)
        dbg_game.world.entity_counter += 1
        world_entity.add(
            IdentityComponent,
            world_model.name,
            dbg_game.world.entity_counter,
            str(uuid.uuid4()),
        )
        world_entity.add(WorldComponent, world_model.name)

        assert (
            world_model.name in world_model.system_message
        ), f"world_model.system_message 缺少 {world_model.name} 的系统消息"
        add_system_message(
            dbg_game,
            world_entity,
            SystemMessage(content=world_model.system_message),
        )

        for comp_name, comp_data in world_model.components.items():
            comp_class = COMPONENT_TYPES.get(comp_name)
            assert comp_class is not None, f"未知组件类型: {comp_name}"
            world_entity.set(comp_class, comp_class(**comp_data))

        world_entities.append(world_entity)
    return world_entities


def create_actor_entities(dbg_game: DBGGame, actor_models: List[Actor]) -> List[Entity]:
    """创建角色实体（玩家、NPC、敌人）。"""
    actor_entities: List[Entity] = []
    for actor_model in actor_models:
        actor_entity = create_entity(dbg_game, actor_model.name)
        dbg_game.world.entity_counter += 1
        actor_entity.add(
            IdentityComponent,
            actor_model.name,
            dbg_game.world.entity_counter,
            str(uuid.uuid4()),
        )
        actor_entity.add(ActorComponent, actor_model.name, "")

        assert (
            actor_model.name in actor_model.system_message
        ), f"actor_model.system_message 缺少 {actor_model.name} 的系统消息"
        add_system_message(
            dbg_game,
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
        actor_entity.add(
            CharacterStatsComponent,
            actor_model.name,
            copy.copy(actor_model.character_stats),
        )

        match actor_model.type:
            case ActorType.NPC:
                actor_entity.add(NPCComponent, actor_model.name)
            case ActorType.MONSTER:
                actor_entity.add(MonsterComponent, actor_model.name)
            case _:
                assert False, f"未知的 ActorType: {actor_model.type}"

        for comp_name, comp_data in actor_model.components.items():
            comp_class = COMPONENT_TYPES.get(comp_name)
            assert comp_class is not None, f"未知组件类型: {comp_name}"
            actor_entity.set(comp_class, comp_class(**comp_data))

        assert actor_entity.has(DeckComponent), "玩家角色实体必须有 DeckComponent"
        _assert_deck_sources(actor_entity.name, actor_entity.get(DeckComponent))
        actor_entities.append(actor_entity)
    return actor_entities


def create_stage_entities(dbg_game: DBGGame, stage_models: List[Stage]) -> List[Entity]:
    """创建场景实体，并建立角色与场景的关联关系。"""
    stage_entities: List[Entity] = []
    for stage_model in stage_models:
        stage_entity = create_entity(dbg_game, stage_model.name)
        dbg_game.world.entity_counter += 1
        stage_entity.add(
            IdentityComponent,
            stage_model.name,
            dbg_game.world.entity_counter,
            str(uuid.uuid4()),
        )
        stage_entity.add(StageComponent, stage_model.name)

        assert stage_model.name in stage_model.system_message
        add_system_message(
            dbg_game,
            stage_entity,
            SystemMessage(content=stage_model.system_message),
        )

        match stage_model.type:
            case StageType.DUNGEON:
                stage_entity.add(DungeonComponent, stage_model.name)
            case StageType.LOBBY:
                stage_entity.add(LobbyComponent, stage_model.name)
            case _:
                assert False, f"未知的 StageType: {stage_model.type}"

        for comp_name, comp_data in stage_model.components.items():
            comp_class = resolve_component_type(comp_name, comp_data)
            stage_entity.set(comp_class, comp_class(**comp_data))

        for actor_model in stage_model.actors:
            actor_entity = get_actor_entity(dbg_game, actor_model.name)
            assert actor_entity is not None, f"找不到actor_entity: {actor_model.name}"
            actor_entity.replace(ActorComponent, actor_model.name, stage_model.name)

        stage_entities.append(stage_entity)
    return stage_entities
