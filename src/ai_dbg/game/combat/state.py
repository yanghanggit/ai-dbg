"""战斗/回合/行动槽实体的创建与查询。"""

from typing import List, Optional

from ...entitas import Entity, Matcher
from ...models import (
    CombatComponent,
    CombatResult,
    CombatRoundComponent,
    CombatRoundView,
    CombatState,
    CombatStateComponent,
    CombatTurnComponent,
    CombatTurnView,
    CombatView,
    CurrentCombatRoundComponent,
    CurrentCombatTurnComponent,
)
from ..context import DBGGame
from ..entities import (
    create_entity,
    get_entity_by_name,
)


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
def combat_turns(dbg_game: DBGGame, round_entity: Entity) -> List[Entity]:
    """按行动槽顺序返回指定回合的全部行动槽实体。"""
    turn_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CombatTurnComponent])
    ).entities
    matched = [
        turn_entity
        for turn_entity in turn_entities
        if turn_entity.get(CombatTurnComponent).round_name == round_entity.name
    ]
    return sorted(
        matched,
        key=lambda turn_entity: turn_entity.get(CombatTurnComponent).order_index,
    )


###############################################################################################################################################
def current_combat_round(dbg_game: DBGGame, combat_entity: Entity) -> Optional[Entity]:
    """返回指定战斗当前标记的回合实体；没有回合时返回 None。"""
    current_rounds = [
        round_entity
        for round_entity in combat_rounds(dbg_game, combat_entity)
        if round_entity.has(CurrentCombatRoundComponent)
    ]
    assert len(current_rounds) <= 1, "同一战斗最多只能有一个当前回合"
    return next(iter(current_rounds), None)


###############################################################################################################################################
def current_combat_turn(dbg_game: DBGGame, combat_entity: Entity) -> Optional[Entity]:
    """返回指定战斗当前标记的行动槽实体；没有当前行动槽时返回 None。"""
    turn_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CombatTurnComponent])
    ).entities
    current_turns = [
        turn_entity
        for turn_entity in turn_entities
        if turn_entity.get(CombatTurnComponent).combat_name == combat_entity.name
        and turn_entity.has(CurrentCombatTurnComponent)
    ]
    assert len(current_turns) <= 1, "同一战斗最多只能有一个当前行动槽"
    return next(iter(current_turns), None)


###############################################################################################################################################
def current_turn_for_round(dbg_game: DBGGame, round_entity: Entity) -> Optional[Entity]:
    """返回指定回合当前标记的行动槽；没有时返回 None。"""
    current_turns = [
        turn_entity
        for turn_entity in combat_turns(dbg_game, round_entity)
        if turn_entity.has(CurrentCombatTurnComponent)
    ]
    assert len(current_turns) <= 1, "同一回合最多只能有一个当前行动槽"
    return next(iter(current_turns), None)


###############################################################################################################################################
def latest_combat_round(dbg_game: DBGGame, combat_entity: Entity) -> Optional[Entity]:
    """返回指定战斗的最后一个回合实体；没有回合时返回 None。"""
    rounds = combat_rounds(dbg_game, combat_entity)
    return rounds[-1] if rounds else None


###############################################################################################################################################
def combat_turn_view(turn_entity: Entity) -> CombatTurnView:
    """把行动槽实体投影成只读视图。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    return CombatTurnView(
        name=turn_comp.name,
        combat_name=turn_comp.combat_name,
        round_name=turn_comp.round_name,
        actor_name=turn_comp.actor_name,
        order_index=turn_comp.order_index,
        status=turn_comp.status,
        energy=turn_comp.energy,
        is_current=turn_entity.has(CurrentCombatTurnComponent),
    )


###############################################################################################################################################
def combat_round_view(dbg_game: DBGGame, round_entity: Entity) -> CombatRoundView:
    """把回合实体及其行动槽投影成只读视图。"""
    round_comp = round_entity.get(CombatRoundComponent)
    return CombatRoundView(
        index=round_comp.index,
        is_completed=round_comp.is_completed,
        draw_completed=round_comp.draw_completed,
        turns=[
            combat_turn_view(turn_entity)
            for turn_entity in combat_turns(dbg_game, round_entity)
        ],
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
            combat_round_view(dbg_game, round_entity)
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
