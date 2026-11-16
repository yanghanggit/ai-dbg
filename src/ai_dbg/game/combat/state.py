"""战斗/回合实体的创建、查询、状态迁移与清理。"""

from typing import List, Optional

from ...entitas import Entity, Matcher
from ...models import (
    CombatComponent,
    CombatResult,
    CombatRoundComponent,
    CombatRoundView,
    CombatState,
    CombatStateComponent,
    CombatView,
    CurrentCombatRoundComponent,
    RoundEntry,
    RoundEntryKind,
)
from ..context import DBGGame
from ..entities import create_entity, destroy_entity, get_entity_by_name


###############################################################################################################################################
# 查询
###############################################################################################################################################
def get_combat_entity_for_room(dbg_game: DBGGame, room_entity: Entity) -> Entity:
    """返回房间实体链接到的战斗实体。"""
    combat_comp = room_entity.get(CombatComponent)
    combat_entity = get_entity_by_name(dbg_game, combat_comp.combat_name)
    assert combat_entity is not None, f"找不到战斗实体: {combat_comp.combat_name}"
    assert combat_entity.has(
        CombatStateComponent
    ), f"{combat_comp.combat_name} 缺少 CombatStateComponent"
    return combat_entity


###############################################################################################################################################
def combat_rounds(dbg_game: DBGGame, combat_entity: Entity) -> List[Entity]:
    """按回合序号返回指定战斗的全部回合实体。"""
    round_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CombatRoundComponent])
    ).entities
    matched = [
        round_entity
        for round_entity in round_entities
        if round_entity.get(CombatRoundComponent).combat_name == combat_entity.name
    ]
    return sorted(
        matched,
        key=lambda round_entity: round_entity.get(CombatRoundComponent).index,
    )


###############################################################################################################################################
def current_combat_round(
    dbg_game: DBGGame, combat_entity: Entity
) -> Optional[Entity]:
    """返回指定战斗当前标记的回合实体；没有回合时返回 None。"""
    current_rounds = [
        round_entity
        for round_entity in combat_rounds(dbg_game, combat_entity)
        if round_entity.has(CurrentCombatRoundComponent)
    ]
    assert len(current_rounds) <= 1, "同一战斗最多只能有一个当前回合"
    return next(iter(current_rounds), None)


###############################################################################################################################################
def latest_combat_round(
    dbg_game: DBGGame, combat_entity: Entity
) -> Optional[Entity]:
    """返回指定战斗的最后一个回合实体；没有回合时返回 None。"""
    rounds = combat_rounds(dbg_game, combat_entity)
    return rounds[-1] if rounds else None


###############################################################################################################################################
def combat_round_view(round_entity: Entity) -> CombatRoundView:
    """把回合实体投影成只读视图。"""
    round_comp = round_entity.get(CombatRoundComponent)
    return CombatRoundView(
        index=round_comp.index,
        completed_actors=list(round_comp.completed_actors),
        action_order=list(round_comp.action_order),
        current_actor=round_comp.current_actor,
        is_completed=round_comp.is_completed,
        draw_completed=round_comp.draw_completed,
        entries=list(round_comp.entries),
    )


###############################################################################################################################################
def combat_view(dbg_game: DBGGame, combat_entity: Entity) -> CombatView:
    """把战斗实体及其回合实体投影成只读视图。"""
    state_comp = combat_entity.get(CombatStateComponent)
    return CombatView(
        name=state_comp.room_name,
        state=state_comp.state,
        result=state_comp.result,
        rounds=[
            combat_round_view(round_entity)
            for round_entity in combat_rounds(dbg_game, combat_entity)
        ],
        retreated=state_comp.retreated,
    )


###############################################################################################################################################
# 创建
###############################################################################################################################################
def _combat_entity_name(room_name: str) -> str:
    return f"{room_name}#combat"


###############################################################################################################################################
def _combat_round_entity_name(combat_name: str, index: int) -> str:
    return f"{combat_name}#round-{index}"


###############################################################################################################################################
def create_combat(
    dbg_game: DBGGame,
    room_entity: Entity,
    *,
    state: CombatState = CombatState.INITIALIZATION,
) -> Entity:
    """为战斗房间创建战斗实体；房间已有未初始化战斗时复用并推进到给定状态。"""
    if room_entity.has(CombatComponent):
        combat_comp = room_entity.get(CombatComponent)
        existing = get_entity_by_name(dbg_game, combat_comp.combat_name)
        assert existing is not None, f"找不到战斗实体: {combat_comp.combat_name}"
        assert existing.has(
            CombatStateComponent
        ), f"{combat_comp.combat_name} 缺少 CombatStateComponent"
        state_comp = existing.get(CombatStateComponent)
        assert (
            state_comp.state == CombatState.NONE
        ), f"{room_entity.name} 战斗已初始化，同一战斗房间不可重开"
        existing.replace(
            CombatStateComponent,
            state_comp.name,
            state_comp.room_name,
            state,
            state_comp.result,
            state_comp.retreated,
        )
        return existing

    combat_name = _combat_entity_name(room_entity.name)
    assert (
        get_entity_by_name(dbg_game, combat_name) is None
    ), f"战斗实体已存在: {combat_name}"

    combat_entity = create_entity(dbg_game, combat_name)
    combat_entity.replace(
        CombatStateComponent,
        combat_name,
        room_entity.name,
        state,
        CombatResult.NONE,
        False,
    )
    room_entity.replace(CombatComponent, room_entity.name, combat_name)
    return combat_entity


###############################################################################################################################################
def create_combat_round(
    dbg_game: DBGGame,
    combat_entity: Entity,
    *,
    index: int,
    action_order: List[str],
    current_actor: Optional[str],
) -> Entity:
    """创建新回合并把它标记为当前回合。"""
    existing_round = current_combat_round(dbg_game, combat_entity)
    if existing_round is not None:
        existing_round.remove(CurrentCombatRoundComponent)

    round_name = _combat_round_entity_name(combat_entity.name, index)
    assert (
        get_entity_by_name(dbg_game, round_name) is None
    ), f"回合实体已存在: {round_name}"

    round_entity = create_entity(dbg_game, round_name)
    round_entity.replace(
        CombatRoundComponent,
        round_name,
        combat_entity.name,
        index,
        False,
        False,
        list(action_order),
        [],
        current_actor,
        [],
    )
    round_entity.replace(CurrentCombatRoundComponent, round_name)
    return round_entity


###############################################################################################################################################
# 战斗状态迁移
###############################################################################################################################################
def transition_combat_to_ongoing(combat_entity: Entity) -> None:
    """将战斗状态从 INITIALIZATION 转换为 ONGOING。"""
    state_comp = combat_entity.get(CombatStateComponent)
    assert state_comp.state == CombatState.INITIALIZATION
    assert state_comp.result == CombatResult.NONE
    combat_entity.replace(
        CombatStateComponent,
        state_comp.name,
        state_comp.room_name,
        CombatState.ONGOING,
        state_comp.result,
        state_comp.retreated,
    )


###############################################################################################################################################
def complete_combat(combat_entity: Entity, result: CombatResult) -> None:
    """将战斗状态从 ONGOING 转换为 COMPLETE。"""
    state_comp = combat_entity.get(CombatStateComponent)
    assert state_comp.state == CombatState.ONGOING
    assert result in (CombatResult.WIN, CombatResult.LOSE)
    assert state_comp.result == CombatResult.NONE
    combat_entity.replace(
        CombatStateComponent,
        state_comp.name,
        state_comp.room_name,
        CombatState.COMPLETE,
        result,
        state_comp.retreated,
    )


###############################################################################################################################################
def transition_combat_to_post_combat(combat_entity: Entity) -> None:
    """将战斗状态从 COMPLETE 转换为 POST_COMBAT。"""
    state_comp = combat_entity.get(CombatStateComponent)
    assert state_comp.result in (CombatResult.WIN, CombatResult.LOSE)
    assert state_comp.state == CombatState.COMPLETE
    combat_entity.replace(
        CombatStateComponent,
        state_comp.name,
        state_comp.room_name,
        CombatState.POST_COMBAT,
        state_comp.result,
        state_comp.retreated,
    )


###############################################################################################################################################
def mark_combat_retreated(combat_entity: Entity) -> None:
    """标记本次战斗通过撤退结束。"""
    state_comp = combat_entity.get(CombatStateComponent)
    combat_entity.replace(
        CombatStateComponent,
        state_comp.name,
        state_comp.room_name,
        state_comp.state,
        state_comp.result,
        True,
    )


###############################################################################################################################################
# 回合状态写入
###############################################################################################################################################
def mark_round_completed(round_entity: Entity) -> None:
    """标记回合完成。"""
    round_comp = round_entity.get(CombatRoundComponent)
    round_entity.replace(
        CombatRoundComponent,
        round_comp.name,
        round_comp.combat_name,
        round_comp.index,
        True,
        round_comp.draw_completed,
        list(round_comp.action_order),
        list(round_comp.completed_actors),
        round_comp.current_actor,
        list(round_comp.entries),
    )


###############################################################################################################################################
def mark_round_draw_completed(round_entity: Entity) -> None:
    """标记回合抽牌阶段完成。"""
    round_comp = round_entity.get(CombatRoundComponent)
    round_entity.replace(
        CombatRoundComponent,
        round_comp.name,
        round_comp.combat_name,
        round_comp.index,
        round_comp.is_completed,
        True,
        list(round_comp.action_order),
        list(round_comp.completed_actors),
        round_comp.current_actor,
        list(round_comp.entries),
    )


###############################################################################################################################################
def append_round_completed_actor(round_entity: Entity, actor_name: str) -> None:
    """把角色名追加到回合的已完成行动者列表。"""
    round_comp = round_entity.get(CombatRoundComponent)
    round_entity.replace(
        CombatRoundComponent,
        round_comp.name,
        round_comp.combat_name,
        round_comp.index,
        round_comp.is_completed,
        round_comp.draw_completed,
        list(round_comp.action_order),
        [*round_comp.completed_actors, actor_name],
        round_comp.current_actor,
        list(round_comp.entries),
    )


###############################################################################################################################################
def set_round_current_actor(
    round_entity: Entity, actor_name: Optional[str]
) -> None:
    """设置回合当前行动者。"""
    round_comp = round_entity.get(CombatRoundComponent)
    round_entity.replace(
        CombatRoundComponent,
        round_comp.name,
        round_comp.combat_name,
        round_comp.index,
        round_comp.is_completed,
        round_comp.draw_completed,
        list(round_comp.action_order),
        list(round_comp.completed_actors),
        actor_name,
        list(round_comp.entries),
    )


###############################################################################################################################################
def record_round_entry(
    round_entity: Entity,
    kind: RoundEntryKind,
    log: str,
    narrative: str,
) -> None:
    """向回合追加一条操作记录。"""
    round_comp = round_entity.get(CombatRoundComponent)
    entry = RoundEntry(kind=kind, log=log, narrative=narrative)
    round_entity.replace(
        CombatRoundComponent,
        round_comp.name,
        round_comp.combat_name,
        round_comp.index,
        round_comp.is_completed,
        round_comp.draw_completed,
        list(round_comp.action_order),
        list(round_comp.completed_actors),
        round_comp.current_actor,
        [*round_comp.entries, entry],
    )


###############################################################################################################################################
# 清理
###############################################################################################################################################
def destroy_combat(dbg_game: DBGGame, combat_entity: Entity) -> None:
    """销毁战斗实体及其全部回合实体，并解除房间上的战斗标记。"""
    for round_entity in combat_rounds(dbg_game, combat_entity):
        if round_entity.has(CurrentCombatRoundComponent):
            round_entity.remove(CurrentCombatRoundComponent)
        destroy_entity(dbg_game, round_entity)

    room_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CombatComponent])
    ).entities.copy()
    for room_entity in room_entities:
        combat_comp = room_entity.get(CombatComponent)
        if combat_comp.combat_name == combat_entity.name:
            room_entity.remove(CombatComponent)

    destroy_entity(dbg_game, combat_entity)
