"""战斗/回合实体生命周期单测。"""

from typing import Any

from ai_dbg.entitas import Matcher
from ai_dbg.game.combat import consume_turn_energy, get_turn_energy
from ai_dbg.game.combat.state import (
    combat_rounds,
    combat_turns,
    combat_view,
    create_combat,
    current_combat_round,
    current_combat_turn,
)
from ai_dbg.game.entities import create_entity
from ai_dbg.models import (
    ActorComponent,
    CombatComponent,
    CombatResult,
    CombatRoundComponent,
    CombatState,
    CombatStateComponent,
    CombatTurnComponent,
    CombatTurnStatus,
    CurrentCombatRoundComponent,
    CurrentCombatTurnComponent,
    DeathComponent,
)
from ai_dbg.systems.combat_outcome_system import CombatOutcomeSystem
from ai_dbg.systems.combat_post_combat_transition_system import (
    CombatPostCombatTransitionSystem,
)
from ai_dbg.systems.pass_turn_action_system import PassTurnActionSystem
from ai_dbg.systems.retreat_action_system import RetreatActionSystem
from ai_dbg.systems.room_init_system import RoomInitSystem
from ai_dbg.systems.teardown_dungeon_action_system import (
    TeardownDungeonActionSystem,
)
from dungeon_support import (
    advance_current_turn,
    create_combat_round,
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
    assert [
        round_entity.name for round_entity in combat_rounds(sample_game, combat)
    ] == [
        first.name,
        second.name,
    ]
    assert [
        round_view.index for round_view in combat_view(sample_game, combat).rounds
    ] == [
        1,
        2,
    ]


def test_round_creates_ordered_turns(sample_game: Any) -> None:
    _, combat = _room_and_combat(sample_game)
    round_entity = create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.甲", "角色.乙"],
        current_actor="角色.甲",
    )

    turns = combat_turns(sample_game, round_entity)
    assert [
        turn_entity.get(CombatTurnComponent).actor_name for turn_entity in turns
    ] == ["角色.甲", "角色.乙"]
    assert [
        turn_entity.get(CombatTurnComponent).order_index for turn_entity in turns
    ] == [1, 2]
    current_turn = current_combat_turn(sample_game, combat)
    assert current_turn is not None
    assert current_turn.get(CombatTurnComponent).actor_name == "角色.甲"
    assert current_turn.has(CurrentCombatTurnComponent)
    assert get_turn_energy(current_turn) == 2
    consume_turn_energy(current_turn, 1)
    assert get_turn_energy(current_turn) == 1
    assert current_turn.get(CombatTurnComponent).energy == 1

    round_view = combat_view(sample_game, combat).latest_round
    assert round_view is not None
    assert round_view.action_order == ["角色.甲", "角色.乙"]
    assert round_view.completed_actors == []
    assert round_view.current_actor == "角色.甲"
    dumped = round_view.model_dump(mode="json")
    assert dumped["action_order"] == ["角色.甲", "角色.乙"]
    assert dumped["current_actor"] == "角色.甲"
    assert dumped["turns"][0]["actor_name"] == "角色.甲"
    assert dumped["turns"][0]["energy"] == 1


def test_turn_completion_advances_to_next_pending_turn(sample_game: Any) -> None:
    _, combat = _room_and_combat(sample_game)
    for actor_name in ("角色.甲", "角色.乙"):
        actor_entity = create_entity(sample_game, actor_name)
        actor_entity.replace(ActorComponent, actor_name, "场景.测试")
    round_entity = create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.甲", "角色.乙"],
        current_actor="角色.甲",
    )
    current_turn = current_combat_turn(sample_game, combat)
    assert current_turn is not None

    PassTurnActionSystem(sample_game)._mark_turn_completed(current_turn)
    next_turn = advance_current_turn(sample_game, round_entity)

    assert next_turn is not None
    assert next_turn.get(CombatTurnComponent).actor_name == "角色.乙"
    assert next_turn.get(CombatTurnComponent).status == CombatTurnStatus.PENDING
    round_view = combat_view(sample_game, combat).latest_round
    assert round_view is not None
    assert round_view.completed_actors == ["角色.甲"]
    assert round_view.current_actor == "角色.乙"


def test_advance_current_turn_skips_dead_and_clears_after_last(
    sample_game: Any,
) -> None:
    _, combat = _room_and_combat(sample_game)
    actors = {}
    for actor_name in ("角色.甲", "角色.乙", "角色.丙"):
        actor_entity = create_entity(sample_game, actor_name)
        actor_entity.replace(ActorComponent, actor_name, "场景.测试")
        actors[actor_name] = actor_entity
    actors["角色.乙"].replace(DeathComponent, "角色.乙")

    round_entity = create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.甲", "角色.乙", "角色.丙"],
        current_actor="角色.甲",
    )
    current_turn = current_combat_turn(sample_game, combat)
    assert current_turn is not None
    PassTurnActionSystem(sample_game)._mark_turn_completed(current_turn)

    next_turn = advance_current_turn(sample_game, round_entity)
    assert next_turn is not None
    assert next_turn.get(CombatTurnComponent).actor_name == "角色.丙"
    turns = combat_turns(sample_game, round_entity)
    assert turns[1].get(CombatTurnComponent).status == CombatTurnStatus.DEAD
    round_view = combat_view(sample_game, combat).latest_round
    assert round_view is not None
    assert round_view.completed_actors == ["角色.甲"]

    PassTurnActionSystem(sample_game)._mark_turn_completed(next_turn)
    assert advance_current_turn(sample_game, round_entity) is None
    assert current_combat_turn(sample_game, combat) is None


def test_combat_state_transitions_update_the_single_component(sample_game: Any) -> None:
    _, combat = _room_and_combat(sample_game)

    RoomInitSystem(sample_game)._transition_to_ongoing(combat)
    assert combat.get(CombatStateComponent).state == CombatState.ONGOING

    RetreatActionSystem(sample_game)._mark_combat_retreated(combat)
    assert combat.get(CombatStateComponent).retreated is True

    CombatOutcomeSystem(sample_game)._complete_combat(combat, CombatResult.WIN)
    state = combat.get(CombatStateComponent)
    assert state.state == CombatState.COMPLETE
    assert state.result == CombatResult.WIN

    CombatPostCombatTransitionSystem(sample_game)._transition_to_post_combat(combat)
    assert combat.get(CombatStateComponent).state == CombatState.POST_COMBAT


def test_destroy_combat_removes_rounds_and_room_marker(sample_game: Any) -> None:
    room, combat = _room_and_combat(sample_game)
    create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    combat_name = combat.name

    TeardownDungeonActionSystem(sample_game)._destroy_combat(combat)

    assert not room.has(CombatComponent)
    assert not sample_game.ecs.get_group(
        Matcher(all_of=[CombatRoundComponent])
    ).entities
    assert not sample_game.ecs.get_group(Matcher(all_of=[CombatTurnComponent])).entities
    assert sample_game.ecs.get_entity_by_name(combat_name) is None


async def test_teardown_dungeon_cascades_combat_entities(sample_game: Any) -> None:
    room, combat = _room_and_combat(sample_game)
    create_combat_round(
        sample_game,
        combat,
        index=1,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )

    await TeardownDungeonActionSystem(sample_game).react([room])

    assert sample_game.ecs.entity_count == 0
