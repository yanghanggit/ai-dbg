"""实体查询：按名称/组件定位实体、舞台分组与归属判定。"""

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from ...entitas import Entity, Matcher
from ...models import (
    ActorComponent,
    ActorSummary,
    AppearanceComponent,
    GlobalStageComponent,
    PlayerComponent,
    PositionComponent,
    StageComponent,
    WorldComponent,
)
from ..context import SRPGGame


def get_actors_in_stage(
    srpg_game: SRPGGame, entity: Entity, matcher: Optional[Matcher] = None
) -> Set[Entity]:
    """获取指定舞台上匹配 matcher 的 Actor 实体。"""
    stage_entity = resolve_stage_entity(srpg_game, entity)
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
    candidate_entities = srpg_game.get_group(actor_matcher).entities
    for candidate_entity in candidate_entities:
        candidate_stage_entity = resolve_stage_entity(srpg_game, candidate_entity)
        assert (
            candidate_stage_entity is not None
        ), f"candidate_entity = {candidate_entity}"
        if candidate_stage_entity != stage_entity:
            continue
        ret.add(candidate_entity)

    return ret


def get_actors_by_stage(srpg_game: SRPGGame) -> Dict[Entity, List[Entity]]:
    """所有舞台到其上角色的映射，只含直接归属（不含子舞台里的人）。

    组查询走的是 ``set``（按对象哈希迭代），顺序不可预期；这里统一按实体创建顺序
    排序。舞台是父先子后建的，所以结果恰好是舞台树的先序，同一蓝图每次构建都一样。
    """
    ret: Dict[Entity, List[Entity]] = {}
    actor_entities = srpg_game.get_group(Matcher(all_of=[ActorComponent])).entities
    for actor_entity in sorted(actor_entities, key=lambda entity: entity.index):
        stage_entity = resolve_stage_entity(srpg_game, actor_entity)
        assert stage_entity is not None, f"actor_entity = {actor_entity}"
        ret.setdefault(stage_entity, []).append(actor_entity)

    stage_entities = srpg_game.get_group(Matcher(all_of=[StageComponent])).entities
    for stage_entity in stage_entities:
        ret.setdefault(stage_entity, [])

    return {stage: ret[stage] for stage in sorted(ret, key=lambda entity: entity.index)}


def get_actors_by_stage_as_names(srpg_game: SRPGGame) -> Dict[str, List[str]]:
    """获取所有舞台到 Actor 的分组映射（名称版本）。"""
    ret: Dict[str, List[str]] = {}
    for stage_entity, actor_entities in get_actors_by_stage(srpg_game).items():
        ret[stage_entity.name] = [actor_entity.name for actor_entity in actor_entities]
    return ret


def list_actor_summaries(srpg_game: SRPGGame) -> List[ActorSummary]:
    """所有角色的当前状态，按创建顺序（与快照重放一致）。"""
    actors = srpg_game.get_group(Matcher(all_of=[ActorComponent])).entities
    summaries: List[ActorSummary] = []
    for actor in sorted(actors, key=lambda entity: entity.index):
        summaries.append(
            ActorSummary(
                name=actor.name,
                stage=actor.get(ActorComponent).current_stage,
                player=(
                    actor.get(PlayerComponent).user_name
                    if actor.has(PlayerComponent)
                    else None
                ),
                appearance=(
                    actor.get(AppearanceComponent).appearance
                    if actor.has(AppearanceComponent)
                    else ""
                ),
            )
        )
    return summaries


class Cell(NamedTuple):
    """战场上的一格：坐标、格上的据点（如果有）、站在格上的角色。

    据点与站在格上的角色是平级的：一格可以只有空地，可以有据点，也可以有人就站在
    据点所在的那一格（兵临城下）。
    """

    x: int
    y: int
    stage: Optional[str] = None
    actors: Tuple[str, ...] = ()


############################################################################################################
def get_global_stage(srpg_game: SRPGGame, stage_name: str) -> Entity:
    """沿父链上溯到全局舞台（舞台树的根，自带网格）。"""
    entity = get_stage_entity(srpg_game, stage_name)
    assert entity is not None, f"找不到舞台实体: {stage_name}"
    while not entity.has(GlobalStageComponent):
        parent_name = entity.get(StageComponent).parent_stage
        assert parent_name is not None, f"{entity.name} 不在任何全局舞台之下"
        parent = get_stage_entity(srpg_game, parent_name)
        assert parent is not None, f"{entity.name} 的父舞台不存在: {parent_name}"
        entity = parent
    return entity


def is_on_map(srpg_game: SRPGGame, entity: Entity) -> bool:
    """这个实体是否站在战役地图上（而不是某个据点内部）。"""
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在舞台"
    return stage_entity.has(GlobalStageComponent)


def get_settlement(srpg_game: SRPGGame, entity: Entity) -> Optional[Entity]:
    """实体所属的据点：据点对外只是一个节点，就是全局舞台的直接子舞台。

    站在地图上返回 ``None``；无论在里面走到多深，返回的都是同一个据点根。
    """
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在舞台"
    if stage_entity.has(GlobalStageComponent):
        return None
    node = stage_entity
    while True:
        parent_name = node.get(StageComponent).parent_stage
        assert parent_name is not None, f"{node.name} 不在任何全局舞台之下"
        parent = get_stage_entity(srpg_game, parent_name)
        assert parent is not None, f"{node.name} 的父舞台不存在: {parent_name}"
        if parent.has(GlobalStageComponent):
            return node
        node = parent


def get_cell(srpg_game: SRPGGame, entity: Entity) -> Tuple[Entity, Tuple[int, int]]:
    """实体在战役地图上的位置：站在地图上用自己的坐标，在据点里用据点所在的格。"""
    if entity.has(PositionComponent):
        position = entity.get(PositionComponent)
        return _global_stage_of_entity(srpg_game, entity), (position.x, position.y)

    settlement = get_settlement(srpg_game, entity)
    assert settlement is not None, f"{entity.name} 站在地图上，却没有格子坐标"
    position = settlement.get(PositionComponent)
    global_stage = get_global_stage(srpg_game, settlement.name)
    return global_stage, (position.x, position.y)


def get_map_cells(srpg_game: SRPGGame, entity: Entity) -> List[Cell]:
    """地图上的相邻格；斜向也算相邻，与广播的距离口径一致。

    包含实体自己所在的那一格——「脚下有什么」决定能不能进城。
    """
    global_stage, (x, y) = get_cell(srpg_game, entity)
    grid = global_stage.get(GlobalStageComponent)

    by_cell: Dict[Tuple[int, int], Dict[str, object]] = {}
    for child in get_child_stages(srpg_game, global_stage.name):
        if not child.has(PositionComponent):
            continue
        position = child.get(PositionComponent)
        by_cell.setdefault((position.x, position.y), {})["stage"] = child.name

    for actor in get_actors_in_stage(srpg_game, global_stage):
        if not actor.has(PositionComponent) or actor.index == entity.index:
            continue
        position = actor.get(PositionComponent)
        entry = by_cell.setdefault((position.x, position.y), {})
        entry["actors"] = (*_actors_of(entry), actor.name)

    cells: List[Cell] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < grid.width and 0 <= ny < grid.height):
                continue
            entry = by_cell.get((nx, ny), {})
            cells.append(
                Cell(
                    x=nx,
                    y=ny,
                    stage=entry.get("stage"),  # type: ignore[arg-type]
                    actors=entry.get("actors", ()),  # type: ignore[arg-type]
                )
            )
    return sorted(cells)


def get_adjacent_stages(srpg_game: SRPGGame, entity: Entity) -> List[Entity]:
    """据点内部的可去区域：子区域与父区域。

    父区域是全局舞台时不在此列——那是「出城」，不是城内移动。
    """
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在舞台"
    assert not stage_entity.has(
        GlobalStageComponent
    ), f"{entity.name} 站在地图上，没有城内可去的区域"

    found = list(get_child_stages(srpg_game, stage_entity.name))
    parent_name = stage_entity.get(StageComponent).parent_stage
    assert parent_name is not None, f"{stage_entity.name} 不在任何全局舞台之下"
    parent = get_stage_entity(srpg_game, parent_name)
    assert parent is not None, f"{stage_entity.name} 的父舞台不存在: {parent_name}"
    if not parent.has(GlobalStageComponent):
        found.append(parent)
    return found


def get_stage_at_cell(
    srpg_game: SRPGGame, global_stage: Entity, cell: Tuple[int, int]
) -> Optional[Entity]:
    """某一格上的据点；空地上没有据点。"""
    for child in get_child_stages(srpg_game, global_stage.name):
        if not child.has(PositionComponent):
            continue
        position = child.get(PositionComponent)
        if (position.x, position.y) == cell:
            return child
    return None


def _actors_of(entry: Dict[str, object]) -> Tuple[str, ...]:
    """格子条目里已经记下的角色名。"""
    actors = entry.get("actors", ())
    assert isinstance(actors, tuple)
    return actors


def _global_stage_of_entity(srpg_game: SRPGGame, entity: Entity) -> Entity:
    """实体所在的全局舞台（角色站在空地上时，它的所在舞台就是全局舞台）。"""
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在舞台"
    return get_global_stage(srpg_game, stage_entity.name)


def get_child_stages(srpg_game: SRPGGame, stage_name: str) -> List[Entity]:
    """某舞台的直接子舞台，按创建顺序（即蓝图里声明的先后）返回。"""
    children = [
        entity
        for entity in srpg_game.get_group(Matcher(all_of=[StageComponent])).entities
        if entity.get(StageComponent).parent_stage == stage_name
    ]
    return sorted(children, key=lambda entity: entity.index)


def get_ancestor_stages(srpg_game: SRPGGame, stage_name: str) -> List[Entity]:
    """某舞台的祖先链，由近到远（父、祖父……），根舞台返回空列表。"""
    ancestors: List[Entity] = []
    entity = get_stage_entity(srpg_game, stage_name)
    assert entity is not None, f"找不到舞台实体: {stage_name}"
    parent_name = entity.get(StageComponent).parent_stage
    while parent_name is not None:
        parent = get_stage_entity(srpg_game, parent_name)
        assert parent is not None, f"舞台 {stage_name} 的父舞台不存在: {parent_name}"
        ancestors.append(parent)
        parent_name = parent.get(StageComponent).parent_stage
    return ancestors


def get_world_entity(srpg_game: SRPGGame, world_name: str) -> Optional[Entity]:
    """通过世界名称获取世界实体。"""
    entity = srpg_game.get_entity_by_name(world_name)
    if entity is not None and entity.has(WorldComponent):
        return entity
    return None


def get_stage_entity(srpg_game: SRPGGame, stage_name: str) -> Optional[Entity]:
    """通过舞台名称获取舞台实体。"""
    entity = srpg_game.get_entity_by_name(stage_name)
    if entity is not None and entity.has(StageComponent):
        return entity
    return None


def get_actor_entity(srpg_game: SRPGGame, actor_name: str) -> Optional[Entity]:
    """通过角色名称获取角色实体。"""
    entity = srpg_game.get_entity_by_name(actor_name)
    if entity is not None and entity.has(ActorComponent):
        return entity
    return None


def resolve_stage_entity(srpg_game: SRPGGame, entity: Entity) -> Optional[Entity]:
    """解析并返回 Stage 实体。"""
    if entity.has(StageComponent):
        return entity
    elif entity.has(ActorComponent):
        actor_comp = entity.get(ActorComponent)
        return get_stage_entity(srpg_game, actor_comp.current_stage)

    assert False, f"无法解析 Stage 实体，传入的实体既不是 Stage 也不是 Actor: {entity}"
    return None


def get_player_actor_name(srpg_game: SRPGGame, user_name: str) -> Optional[str]:
    """某玩家控制的角色名；该玩家尚未分到角色时返回 None。"""
    entity = get_player_entity(srpg_game, user_name)
    return entity.name if entity is not None else None


def get_player_entity(srpg_game: SRPGGame, user_name: str) -> Optional[Entity]:
    """某玩家控制的角色实体；该玩家尚未分到角色时返回 None。

    一局里可以有多个 ``PlayerComponent``（一人一个角色），因此必须按身份查，
    不能取「第一个玩家」。同一玩家绑定多个角色是状态损坏，直接报错。
    """
    players = srpg_game.get_group(Matcher(all_of=[PlayerComponent])).entities
    found = [
        entity
        for entity in players
        if entity.get(PlayerComponent).user_name == user_name
    ]
    if len(found) > 1:
        names = [entity.name for entity in found]
        raise ValueError(f"玩家 {user_name} 绑定了多个角色: {names}")
    return found[0] if found else None
