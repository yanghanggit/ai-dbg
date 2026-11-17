"""测试辅助：直接在 ECS 中构造副本/房间/战斗状态。"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from ai_dbg.entitas import Entity
from ai_dbg.game.combat.state import (
    combat_round_entries,
    combat_rounds,
    combat_turns,
    create_combat,
    current_combat_turn,
)
from ai_dbg.game.dungeon import (
    current_combat_entity,
    current_combat_round_entity,
    current_dungeon_combat,
)
from ai_dbg.game.entities import create_entity, get_entity_by_name
from ai_dbg.models import (
    CombatPassSnapshotComponent,
    CombatResult,
    CombatState,
    CombatStateComponent,
    CombatTurnComponent,
    CurrentDungeonRoomComponent,
    DungeonComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    DungeonRunComponent,
    StageComponent,
)
from ai_dbg.systems.combat_round_completion_system import CombatRoundCompletionSystem
from ai_dbg.systems.combat_round_start_system import CombatRoundStartSystem
from ai_dbg.systems.combat_turn_state import CombatTurnStateMixin
from ai_dbg.systems.draw_cards_action_system import DrawCardsActionSystem


def make_dungeon_entity(
    game: Any,
    *,
    name: str = "副本.测试",
    profile: str = "profile",
) -> Entity:
    """创建只带 DungeonRunComponent 的副本实体。"""
    entity = create_entity(game, name)
    entity.add(
        DungeonRunComponent,
        name,
        profile,
        datetime.now(timezone.utc),
        {},
    )
    return entity


def make_room_entity(
    game: Any,
    *,
    name: str,
    index: int,
    room_type: DungeonRoomType = DungeonRoomType.COMBAT,
    dungeon_name: str = "副本.测试",
) -> Entity:
    """创建房间实体（当前实现中房间实体就是对应 Stage 实体）。"""
    existing = get_entity_by_name(game, name)
    entity = existing if existing is not None else create_entity(game, name)
    entity.replace(StageComponent, name)
    entity.replace(DungeonComponent, name)
    entity.replace(
        DungeonRoomComponent,
        name,
        dungeon_name,
        index,
        room_type,
    )
    return entity


def set_current_room(game: Any, room: Entity) -> None:
    """把 room 标记为当前房间。"""
    room.replace(CurrentDungeonRoomComponent, room.name)


class _TurnStateAccess(CombatTurnStateMixin):
    """测试用迁移入口：直接复用 system 层 mixin。"""

    def __init__(self, game: Any) -> None:
        self._game = game


def advance_current_turn(game: Any, round_entity: Entity) -> Optional[Entity]:
    """测试辅助：复用生产 system 的行动槽推进逻辑。"""
    return _TurnStateAccess(game)._advance_current_turn(round_entity)


def create_combat_round(
    game: Any,
    combat_entity: Entity,
    *,
    index: int,
    action_order: Optional[List[str]],
    current_actor: Optional[str],
) -> Entity:
    """测试辅助：复用生产系统的回合创建逻辑。"""
    return CombatRoundStartSystem(game)._create_round(
        combat_entity,
        index=index,
        action_order=action_order or [],
        current_actor=current_actor,
    )


def install_combat(
    game: Any,
    *,
    room_name: str = "场景.测试",
    index: int = 0,
    dungeon_name: str = "副本.测试",
    state: CombatState = CombatState.ONGOING,
    rounds: int = 1,
    action_order: Optional[List[str]] = None,
    current_actor: Optional[str] = None,
    draw_completed: bool = True,
    is_completed: bool = False,
) -> Any:
    """创建战斗房间、战斗实体与若干回合，返回当前战斗只读视图。"""
    room = make_room_entity(
        game,
        name=room_name,
        index=index,
        room_type=DungeonRoomType.COMBAT,
        dungeon_name=dungeon_name,
    )
    set_current_room(game, room)
    combat_entity = create_combat(game, room, state=state)

    for round_index in range(1, rounds + 1):
        round_entity = create_combat_round(
            game,
            combat_entity,
            index=round_index,
            action_order=action_order or [],
            current_actor=current_actor,
        )
        if round_index == rounds:
            if draw_completed:
                DrawCardsActionSystem(game)._mark_round_draw_completed(round_entity)
            if is_completed:
                CombatRoundCompletionSystem(game)._mark_round_completed(round_entity)

    if state == CombatState.ONGOING:
        install_pass_snapshot(game)

    return current_dungeon_combat(game)


def install_pass_snapshot(game: Any) -> None:
    """测试辅助：模拟 CombatPassSnapshotSystem 建立的 pass 快照。"""
    combat_entity = current_combat_entity(game)
    turn_entity = current_combat_turn(game, combat_entity)
    if turn_entity is None:
        return

    turn_comp = turn_entity.get(CombatTurnComponent)
    turn_entity.replace(
        CombatPassSnapshotComponent,
        combat_entity.name,
        turn_comp.round_name,
        turn_entity.name,
        turn_comp.actor_name,
    )


def install_opening_room(
    game: Any,
    *,
    room_name: str = "场景.开场",
    index: int = 0,
    dungeon_name: str = "副本.测试",
) -> Entity:
    """把 room 设为当前开场房间。"""
    room = make_room_entity(
        game,
        name=room_name,
        index=index,
        room_type=DungeonRoomType.OPENING,
        dungeon_name=dungeon_name,
    )
    set_current_room(game, room)
    return room


def clear_current_room(game: Any) -> None:
    """移除当前房间标记。"""
    for entity in list(game.ecs.entities):
        if entity.has(CurrentDungeonRoomComponent):
            entity.remove(CurrentDungeonRoomComponent)


def append_combat_round(
    game: Any,
    *,
    action_order: Optional[List[str]] = None,
    current_actor: Optional[str] = None,
) -> Entity:
    """测试辅助：给当前战斗追加一个新回合。"""
    combat_entity = current_combat_entity(game)
    index = len(combat_rounds(game, combat_entity)) + 1
    return create_combat_round(
        game,
        combat_entity,
        index=index,
        action_order=action_order or [],
        current_actor=current_actor,
    )


def set_combat_state(
    game: Any,
    state: CombatState,
    *,
    result: CombatResult = CombatResult.NONE,
    retreated: bool = False,
) -> None:
    """测试辅助：直接改写当前战斗的状态组件。"""
    combat_entity = current_combat_entity(game)
    state_comp = combat_entity.get(CombatStateComponent)
    combat_entity.replace(
        CombatStateComponent,
        state_comp.name,
        state_comp.room_name,
        state,
        result,
        retreated,
    )


def current_round_entity(game: Any) -> Entity:
    """测试辅助：返回当前回合实体。"""
    round_entity = current_combat_round_entity(game)
    assert round_entity is not None, "当前战斗没有回合"
    return round_entity


def current_turn_entity(game: Any) -> Entity:
    """测试辅助：返回当前行动槽实体。"""
    turn_entity = current_combat_turn(game, current_combat_entity(game))
    assert turn_entity is not None, "当前战斗没有当前行动槽"
    return turn_entity


def current_round_turns(game: Any) -> List[Entity]:
    """测试辅助：返回当前回合的全部行动槽实体。"""
    return combat_turns(game, current_round_entity(game))


def current_round_entries(game: Any) -> List[Entity]:
    """测试辅助：返回当前回合的全部记录实体。"""
    return combat_round_entries(game, current_round_entity(game))
