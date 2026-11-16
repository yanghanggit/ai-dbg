"""战斗/回合实体生命周期单测。"""

from typing import Any

from ai_dbg.entitas import Matcher
from ai_dbg.game.combat.state import (
    combat_rounds,
    combat_view,
    complete_combat,
    create_combat,
    create_combat_round,
    current_combat_round,
    destroy_combat,
    mark_combat_retreated,
    transition_combat_to_ongoing,
    transition_combat_to_post_combat,
)
from ai_dbg.models import (
    CombatComponent,
    CombatResult,
    CombatRoundComponent,
    CombatState,
    CombatStateComponent,
    CurrentCombatRoundComponent,
)
from ai_dbg.services.dungeon_teardown_action import teardown_dungeon
from dungeon_support import (
    make_dungeon_entity,
    make_room_entity,
    set_current_room,
)


def _room_and_combat(game: Any) -> tuple[Any, Any]:
    make_dungeon_entity(game)
    room = make_room_entity(game, name="场景.测试", index=0)
    set_current_room(game, room)
    combat = create_combat(game, room)
    return room, combat


def test_create_combat_links_room_and_initializes_state(sample_game: Any) -> None:
    room, combat = _room_and_combat(sample_game)

    assert room.has(CombatComponent)
    assert room.get(CombatComponent).combat_name == combat.name
    assert combat.get(CombatStateComponent).state == CombatState.INITIALIZATION


def test_round_lifecycle_keeps_only_one_current_marker(sample_game: Any) -> None:
    _, combat = _room_and_combat(sample_game)
    first = create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.无名"],
        current_actor="角色.无名",
    )
    assert current_combat_round(sample_game, combat) == first

    second = create_combat_round(
        sample_game,
        combat,
        index=2,
        action_order=["角色.无名"],
        current_actor="角色.无名",
    )

    assert current_combat_round(sample_game, combat) == second
    assert not first.has(CurrentCombatRoundComponent)
    assert [round_entity.name for round_entity in combat_rounds(sample_game, combat)] == [
        first.name,
        second.name,
    ]
    assert [round_view.index for round_view in combat_view(sample_game, combat).rounds] == [
        1,
        2,
    ]


def test_combat_state_transitions_update_the_single_component(sample_game: Any) -> None:
    _, combat = _room_and_combat(sample_game)

    transition_combat_to_ongoing(combat)
    assert combat.get(CombatStateComponent).state == CombatState.ONGOING

    mark_combat_retreated(combat)
    assert combat.get(CombatStateComponent).retreated is True

    complete_combat(combat, CombatResult.WIN)
    state = combat.get(CombatStateComponent)
    assert state.state == CombatState.COMPLETE
    assert state.result == CombatResult.WIN

    transition_combat_to_post_combat(combat)
    assert combat.get(CombatStateComponent).state == CombatState.POST_COMBAT


def test_destroy_combat_removes_rounds_and_room_marker(sample_game: Any) -> None:
    room, combat = _room_and_combat(sample_game)
    create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=[],
        current_actor=None,
    )
    combat_name = combat.name

    destroy_combat(sample_game, combat)

    assert not room.has(CombatComponent)
    assert not sample_game.ecs.get_group(Matcher(all_of=[CombatRoundComponent])).entities
    assert combat_name not in sample_game.entity_index


def test_teardown_dungeon_cascades_combat_entities(sample_game: Any) -> None:
    room, combat = _room_and_combat(sample_game)
    create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=[],
        current_actor=None,
    )

    teardown_dungeon(sample_game)

    assert sample_game.ecs.entity_count == 0
    assert sample_game.entity_index == {}
