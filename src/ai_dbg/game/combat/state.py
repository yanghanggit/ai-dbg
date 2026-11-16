"""战斗/回合/行动槽/回合记录实体的创建、查询、状态迁移与清理。"""

from typing import List, Optional

from ...entitas import Entity, Matcher
from ...models import (
    CombatComponent,
    CombatResult,
    CombatRoundComponent,
    CombatRoundEntryComponent,
    CombatRoundEntryView,
    CombatRoundView,
    CombatState,
    CombatStateComponent,
    CombatTurnComponent,
    CombatTurnStatus,
    CombatTurnView,
    CombatView,
    CurrentCombatRoundComponent,
    CurrentCombatTurnComponent,
    DeathComponent,
    RoundEntryKind,
)
from ..context import DBGGame
from ..entities import (
    create_entity,
    destroy_entity,
    get_actor_entity,
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
def combat_round_entries(dbg_game: DBGGame, round_entity: Entity) -> List[Entity]:
    """按记录序号返回指定回合的全部回合记录实体。"""
    entry_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CombatRoundEntryComponent])
    ).entities
    matched = [
        entry_entity
        for entry_entity in entry_entities
        if entry_entity.get(CombatRoundEntryComponent).round_name == round_entity.name
    ]
    return sorted(
        matched,
        key=lambda entry_entity: entry_entity.get(CombatRoundEntryComponent).index,
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
def _current_turn_for_round(
    dbg_game: DBGGame, round_entity: Entity
) -> Optional[Entity]:
    """返回指定回合当前标记的行动槽；没有时返回 None。"""
    current_turns = [
        turn_entity
        for turn_entity in combat_turns(dbg_game, round_entity)
        if turn_entity.has(CurrentCombatTurnComponent)
    ]
    assert len(current_turns) <= 1, "同一回合最多只能有一个当前行动槽"
    return next(iter(current_turns), None)


###############################################################################################################################################
def turn_name_for_actor(
    dbg_game: DBGGame, round_entity: Entity, actor_name: str
) -> Optional[str]:
    """返回该角色在当前回合对应的行动槽名；优先当前槽，否则取最后一个槽。"""
    current_turn = _current_turn_for_round(dbg_game, round_entity)
    if (
        current_turn is not None
        and current_turn.get(CombatTurnComponent).actor_name == actor_name
    ):
        return current_turn.name

    matched = [
        turn_entity
        for turn_entity in combat_turns(dbg_game, round_entity)
        if turn_entity.get(CombatTurnComponent).actor_name == actor_name
    ]
    return matched[-1].name if matched else None


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
def combat_round_entry_view(entry_entity: Entity) -> CombatRoundEntryView:
    """把回合记录实体投影成只读视图。"""
    entry_comp = entry_entity.get(CombatRoundEntryComponent)
    return CombatRoundEntryView(
        name=entry_comp.name,
        combat_name=entry_comp.combat_name,
        round_name=entry_comp.round_name,
        turn_name=entry_comp.turn_name,
        index=entry_comp.index,
        kind=entry_comp.kind,
        log=entry_comp.log,
        narrative=entry_comp.narrative,
    )


###############################################################################################################################################
def combat_round_view(dbg_game: DBGGame, round_entity: Entity) -> CombatRoundView:
    """把回合实体及其行动槽/记录实体投影成只读视图。"""
    round_comp = round_entity.get(CombatRoundComponent)
    return CombatRoundView(
        index=round_comp.index,
        is_completed=round_comp.is_completed,
        draw_completed=round_comp.draw_completed,
        turns=[
            combat_turn_view(turn_entity)
            for turn_entity in combat_turns(dbg_game, round_entity)
        ],
        entries=[
            combat_round_entry_view(entry_entity)
            for entry_entity in combat_round_entries(dbg_game, round_entity)
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
def _combat_round_entity_name(combat_name: str, index: int) -> str:
    return f"{combat_name}#round-{index}"


###############################################################################################################################################
def _combat_turn_entity_name(round_name: str, order_index: int) -> str:
    return f"{round_name}#turn-{order_index}"


###############################################################################################################################################
def _combat_round_entry_entity_name(round_name: str, index: int) -> str:
    return f"{round_name}#entry-{index}"


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
    """创建新回合及其行动槽，并把它标记为当前回合。"""
    existing_round = current_combat_round(dbg_game, combat_entity)
    if existing_round is not None:
        existing_round.remove(CurrentCombatRoundComponent)
        for turn_entity in combat_turns(dbg_game, existing_round):
            if turn_entity.has(CurrentCombatTurnComponent):
                turn_entity.remove(CurrentCombatTurnComponent)

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
    )
    round_entity.replace(CurrentCombatRoundComponent, round_name)

    for order_index, actor_name in enumerate(action_order, start=1):
        create_combat_turn(
            dbg_game,
            round_entity,
            actor_name=actor_name,
            order_index=order_index,
        )

    if current_actor is not None:
        current_turn = next(
            (
                turn_entity
                for turn_entity in combat_turns(dbg_game, round_entity)
                if turn_entity.get(CombatTurnComponent).actor_name == current_actor
            ),
            None,
        )
        assert current_turn is not None, f"行动顺序中没有当前行动者: {current_actor}"
        set_current_combat_turn(dbg_game, current_turn)

    return round_entity


###############################################################################################################################################
def create_combat_turn(
    dbg_game: DBGGame,
    round_entity: Entity,
    *,
    actor_name: str,
    order_index: int,
    status: CombatTurnStatus = CombatTurnStatus.PENDING,
    energy: int = 2,
) -> Entity:
    """创建回合内的一个行动槽实体。"""
    round_comp = round_entity.get(CombatRoundComponent)
    turn_name = _combat_turn_entity_name(round_entity.name, order_index)
    assert (
        get_entity_by_name(dbg_game, turn_name) is None
    ), f"行动槽实体已存在: {turn_name}"

    turn_entity = create_entity(dbg_game, turn_name)
    turn_entity.replace(
        CombatTurnComponent,
        turn_name,
        round_comp.combat_name,
        round_entity.name,
        actor_name,
        order_index,
        status,
        energy,
    )
    return turn_entity


###############################################################################################################################################
def set_current_combat_turn(dbg_game: DBGGame, turn_entity: Entity) -> None:
    """把指定行动槽设为当前行动槽；同一战斗只保留一个当前槽。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    assert (
        turn_comp.status == CombatTurnStatus.PENDING
    ), f"已结束的行动槽不能成为当前行动槽: {turn_entity.name}"

    combat_entity = get_entity_by_name(dbg_game, turn_comp.combat_name)
    assert combat_entity is not None, f"找不到战斗实体: {turn_comp.combat_name}"
    for round_entity in combat_rounds(dbg_game, combat_entity):
        for existing_turn in combat_turns(dbg_game, round_entity):
            if existing_turn.has(CurrentCombatTurnComponent):
                existing_turn.remove(CurrentCombatTurnComponent)

    turn_entity.replace(CurrentCombatTurnComponent, turn_entity.name)


###############################################################################################################################################
def advance_current_turn(dbg_game: DBGGame, round_entity: Entity) -> Optional[Entity]:
    """把当前行动槽推进到下一个可用槽；没有可用槽时移除当前标记。"""
    turn_entities = combat_turns(dbg_game, round_entity)
    current_turn = _current_turn_for_round(dbg_game, round_entity)
    start_index = 0
    if current_turn is not None:
        start_index = turn_entities.index(current_turn) + 1

    for turn_entity in turn_entities[start_index:]:
        turn_comp = turn_entity.get(CombatTurnComponent)
        if turn_comp.status != CombatTurnStatus.PENDING:
            continue

        actor_entity = get_actor_entity(dbg_game, turn_comp.actor_name)
        assert actor_entity is not None, f"找不到行动槽角色实体: {turn_comp.actor_name}"
        if actor_entity.has(DeathComponent):
            mark_turn_dead(turn_entity)
            continue

        set_current_combat_turn(dbg_game, turn_entity)
        return turn_entity

    if current_turn is not None:
        current_turn.remove(CurrentCombatTurnComponent)
    return None


###############################################################################################################################################
def create_combat_round_entry(
    dbg_game: DBGGame,
    round_entity: Entity,
    *,
    kind: RoundEntryKind,
    log: str,
    narrative: str,
    turn_name: Optional[str] = None,
) -> Entity:
    """创建一条回合记录实体；默认关联当前行动槽。"""
    round_comp = round_entity.get(CombatRoundComponent)
    entries = combat_round_entries(dbg_game, round_entity)
    index = entries[-1].get(CombatRoundEntryComponent).index + 1 if entries else 1
    entry_name = _combat_round_entry_entity_name(round_entity.name, index)

    if turn_name is None:
        current_turn = _current_turn_for_round(dbg_game, round_entity)
        turn_name = current_turn.name if current_turn is not None else None

    entry_entity = create_entity(dbg_game, entry_name)
    entry_entity.replace(
        CombatRoundEntryComponent,
        entry_name,
        round_comp.combat_name,
        round_entity.name,
        turn_name,
        index,
        kind,
        log,
        narrative,
    )
    return entry_entity


###############################################################################################################################################
def record_round_entry(
    dbg_game: DBGGame,
    round_entity: Entity,
    kind: RoundEntryKind,
    log: str,
    narrative: str,
    *,
    turn_name: Optional[str] = None,
) -> Entity:
    """向回合追加一条操作记录实体。"""
    return create_combat_round_entry(
        dbg_game,
        round_entity,
        kind=kind,
        log=log,
        narrative=narrative,
        turn_name=turn_name,
    )


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
# 回合/行动槽状态写入
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
    )


###############################################################################################################################################
def mark_turn_completed(turn_entity: Entity) -> None:
    """标记行动槽已完成（角色已过牌/交出行动权）。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    assert (
        turn_comp.status == CombatTurnStatus.PENDING
    ), f"只有待行动的行动槽可以完成: {turn_entity.name}"
    turn_entity.replace(
        CombatTurnComponent,
        turn_comp.name,
        turn_comp.combat_name,
        turn_comp.round_name,
        turn_comp.actor_name,
        turn_comp.order_index,
        CombatTurnStatus.COMPLETED,
        turn_comp.energy,
    )


###############################################################################################################################################
def mark_turn_dead(turn_entity: Entity) -> None:
    """标记行动槽对应的角色已死亡，后续推进应跳过它。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    turn_entity.replace(
        CombatTurnComponent,
        turn_comp.name,
        turn_comp.combat_name,
        turn_comp.round_name,
        turn_comp.actor_name,
        turn_comp.order_index,
        CombatTurnStatus.DEAD,
        turn_comp.energy,
    )


###############################################################################################################################################
# 清理
###############################################################################################################################################
def destroy_combat(dbg_game: DBGGame, combat_entity: Entity) -> None:
    """销毁战斗实体及其全部回合/行动槽/记录实体，并解除房间上的战斗标记。"""
    for round_entity in combat_rounds(dbg_game, combat_entity):
        for entry_entity in combat_round_entries(dbg_game, round_entity):
            destroy_entity(dbg_game, entry_entity)

        for turn_entity in combat_turns(dbg_game, round_entity):
            if turn_entity.has(CurrentCombatTurnComponent):
                turn_entity.remove(CurrentCombatTurnComponent)
            destroy_entity(dbg_game, turn_entity)

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
