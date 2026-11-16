"""实体上下文操作：创建、销毁、查询、索引与序列化。"""

import copy
import uuid
from typing import Dict, List, Optional, Set, Type

from loguru import logger

from ..entitas import (
    Component,
    ContextData,
    Entity,
    Matcher,
    dump_context,
    dump_entities,
    load_context,
)
from ..models import (
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
from .dbg_game import DBGGame
from .game_memory import add_system_message, remove_agent_memory


###############################################################################################################################################
def _is_persistable_component(comp_type: Type[Component]) -> bool:
    """组件类型是否已注册（只有注册过的组件才会被整体序列化）。"""
    return COMPONENT_TYPES.get(comp_type.__name__) is not None


###############################################################################################################################################
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


###############################################################################################################################################
def create_entity(dbg_game: DBGGame, name: str) -> Entity:
    """创建并注册一个新实体。"""
    entity = dbg_game.ecs.create_entity()
    entity.name = str(name)
    dbg_game.entity_index[name] = entity
    return entity


###############################################################################################################################################
def destroy_entity(dbg_game: DBGGame, entity: Entity) -> None:
    """销毁实体：先清理 LLM 记忆与名称索引，再从 ECS 销毁。"""
    logger.debug(f"destroy_entity: {entity.name}")
    remove_agent_memory(dbg_game, entity)
    dbg_game.entity_index.pop(entity.name, None)
    dbg_game.ecs.destroy_entity(entity)


###############################################################################################################################################
def serialize_entities(dbg_game: DBGGame, entities: Set[Entity]) -> ContextData:
    """将实体集合导出为 name-keyed 的 ContextData（只含已注册组件）。"""
    ordered = sorted(entities, key=lambda entity: entity.index)
    return dump_entities(ordered, component_filter=_is_persistable_component)


###############################################################################################################################################
def serialize_context(dbg_game: DBGGame) -> ContextData:
    """将整个 ECS context 导出为 name-keyed 的 ContextData（只含已注册组件）。"""
    return dump_context(dbg_game.ecs, component_filter=_is_persistable_component)


###############################################################################################################################################
def restore_context(dbg_game: DBGGame, data: ContextData) -> Dict[str, Entity]:
    """从 name-keyed 的 ContextData 还原 ECS context，并重建名称索引。"""
    restored = load_context(dbg_game.ecs, data, resolve_component_type)
    dbg_game.entity_index.update(restored)
    return restored


###############################################################################################################################################
def get_world_entity(dbg_game: DBGGame, world_name: str) -> Optional[Entity]:
    """通过世界名称获取世界实体。"""
    entity = get_entity_by_name(dbg_game, world_name)
    if entity is not None and entity.has(WorldComponent):
        return entity
    return None


###############################################################################################################################################
def get_entity_by_name(dbg_game: DBGGame, name: str) -> Optional[Entity]:
    """通过名称获取实体；索引缺失时回退扫描 ECS（便于测试与旧快照）。"""
    indexed = dbg_game.entity_index.get(name, None)
    if indexed is not None:
        return indexed
    for entity in dbg_game.ecs.entities:
        if entity.name == name:
            return entity
    return None


###############################################################################################################################################
def get_stage_entity(dbg_game: DBGGame, stage_name: str) -> Optional[Entity]:
    """通过场景名称获取场景实体。"""
    entity = get_entity_by_name(dbg_game, stage_name)
    if entity is not None and entity.has(StageComponent):
        return entity
    return None


###############################################################################################################################################
def get_actor_entity(dbg_game: DBGGame, actor_name: str) -> Optional[Entity]:
    """通过角色名称获取角色实体。"""
    entity = get_entity_by_name(dbg_game, actor_name)
    if entity is not None and entity.has(ActorComponent):
        return entity
    return None


###############################################################################################################################################
def resolve_stage_entity(dbg_game: DBGGame, entity: Entity) -> Optional[Entity]:
    """解析并返回 Stage 实体。"""
    if entity.has(StageComponent):
        return entity
    elif entity.has(ActorComponent):
        actor_comp = entity.get(ActorComponent)
        return get_stage_entity(dbg_game, actor_comp.current_stage)

    assert False, f"无法解析 Stage 实体，传入的实体既不是 Stage 也不是 Actor: {entity}"
    return None


###############################################################################################################################################
def get_player_entity(dbg_game: DBGGame) -> Optional[Entity]:
    """获取玩家实体。"""
    player_entities = dbg_game.ecs.get_group(Matcher(all_of=[PlayerComponent])).entities
    assert len(player_entities) == 1, "There should be exactly one player entity."
    return next(iter(player_entities), None)


###############################################################################################################################################
def get_actors_in_stage(
    dbg_game: DBGGame, entity: Entity, matcher: Optional[Matcher] = None
) -> Set[Entity]:
    """获取指定场景上匹配 matcher 的 Actor 实体。"""
    stage_entity = resolve_stage_entity(dbg_game, entity)
    assert stage_entity is not None, f"entity = {entity}"

    all_of = list(matcher.all_of) if matcher is not None and matcher.all_of else []
    if ActorComponent not in all_of:
        all_of.append(ActorComponent)

    actor_matcher = Matcher(
        all_of=all_of,
        any_of=matcher.any_of if matcher is not None else None,
        none_of=matcher.none_of if matcher is not None else None,
    )

    ret: Set[Entity] = set()
    candidate_entities = dbg_game.ecs.get_group(actor_matcher).entities
    for candidate_entity in candidate_entities:
        candidate_stage_entity = resolve_stage_entity(dbg_game, candidate_entity)
        assert (
            candidate_stage_entity is not None
        ), f"candidate_entity = {candidate_entity}"
        if candidate_stage_entity != stage_entity:
            continue
        ret.add(candidate_entity)

    return ret


###############################################################################################################################################
def is_actor_in_lobby_stage(dbg_game: DBGGame, actor_entity: Entity) -> bool:
    """判断 Actor 是否在大厅/营地场景中。"""
    assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
    stage_entity = resolve_stage_entity(dbg_game, actor_entity)
    assert stage_entity is not None, "stage_entity is None"
    assert not (
        stage_entity.has(LobbyComponent) and stage_entity.has(DungeonComponent)
    ), "stage_entity has both LobbyComponent and DungeonComponent!"
    return stage_entity.has(LobbyComponent)


###############################################################################################################################################
def is_actor_in_dungeon_stage(dbg_game: DBGGame, actor_entity: Entity) -> bool:
    """判断 Actor 是否在副本场景中。"""
    assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
    stage_entity = resolve_stage_entity(dbg_game, actor_entity)
    assert stage_entity is not None, "stage_entity is None"
    assert not (
        stage_entity.has(DungeonComponent) and stage_entity.has(LobbyComponent)
    ), "stage_entity has both DungeonComponent and LobbyComponent!"
    return stage_entity.has(DungeonComponent)


###############################################################################################################################################
def get_actors_by_stage(dbg_game: DBGGame) -> Dict[Entity, List[Entity]]:
    """获取所有场景到 Actor 的分组映射。"""
    ret: Dict[Entity, List[Entity]] = {}
    actor_entities = dbg_game.ecs.get_group(Matcher(all_of=[ActorComponent])).entities
    for actor_entity in actor_entities:
        stage_entity = resolve_stage_entity(dbg_game, actor_entity)
        assert stage_entity is not None, f"actor_entity = {actor_entity}"
        ret.setdefault(stage_entity, []).append(actor_entity)

    stage_entities = dbg_game.ecs.get_group(Matcher(all_of=[StageComponent])).entities
    for stage_entity in stage_entities:
        if stage_entity not in ret:
            ret.setdefault(stage_entity, [])
    return ret


###############################################################################################################################################
def get_actors_by_stage_as_names(dbg_game: DBGGame) -> Dict[str, List[str]]:
    """获取所有场景到 Actor 的分组映射（名称版本）。"""
    ret: Dict[str, List[str]] = {}
    for stage_entity, actor_entities in get_actors_by_stage(dbg_game).items():
        ret[stage_entity.name] = [actor_entity.name for actor_entity in actor_entities]
    return ret


###############################################################################################################################################
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

    assert dbg_game.player_session.name.strip() != "", "玩家名字不能为空"
    assert dbg_game.player_session.actor.strip() != "", "玩家角色不能为空"
    player_actor_entity = get_actor_entity(dbg_game, dbg_game.player_session.actor)
    assert (
        player_actor_entity is not None
    ), f"找不到玩家角色实体: {dbg_game.player_session.actor}"
    assert not player_actor_entity.has(PlayerComponent)
    player_actor_entity.replace(PlayerComponent, dbg_game.player_session.name)
    logger.info(
        f"玩家: {dbg_game.player_session.name} 选择控制: {dbg_game.player_session.actor}"
    )
    assert player_actor_entity.has(
        InventoryComponent
    ), "玩家角色实体必须有 InventoryComponent"


###############################################################################################################################################
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


###############################################################################################################################################
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


###############################################################################################################################################
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
