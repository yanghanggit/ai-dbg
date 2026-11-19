"""动作前置条件：玩家能做的与模型能做的，由同一个判据决定。"""

from ai_srpg.entitas import Entity
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities.action_rules import action_blocker
from ai_srpg.models import (
    ActorComponent,
    ActorEnterStageAction,
    ActorExitStageAction,
    ActorMoveWithinStageAction,
    ActorSpeakAction,
    ActorTravelAction,
    ActorWaitAction,
    PositionComponent,
)
from world_fixture import (
    CAMP,
    FIRE_ROOM,
    HERE,
    TOWER,
    WANDERER,
    build_world,
    entity,
)


def _blocker(game: SRPGGame, actor: Entity, action: object) -> str | None:
    return action_blocker(game, actor, action)  # type: ignore[arg-type]


###############################################################################
# 据点层
###############################################################################
def test_speak_is_allowed_inside_a_settlement() -> None:
    game = build_world()
    assert _blocker(game, entity(game, HERE), ActorSpeakAction(content="喂")) is None


def test_speak_is_refused_on_the_map() -> None:
    game = build_world()
    reason = _blocker(game, entity(game, WANDERER), ActorSpeakAction(content="喂"))
    assert reason is not None
    assert "地图不是场所" in reason


def test_wait_is_allowed_everywhere() -> None:
    game = build_world()
    assert _blocker(game, entity(game, HERE), ActorWaitAction()) is None
    assert _blocker(game, entity(game, WANDERER), ActorWaitAction()) is None


def test_exit_requires_being_inside_a_settlement() -> None:
    game = build_world()
    assert _blocker(game, entity(game, HERE), ActorExitStageAction()) is None
    assert _blocker(game, entity(game, WANDERER), ActorExitStageAction()) is not None


def test_move_within_only_accepts_adjacent_areas() -> None:
    game = build_world()
    actor = entity(game, HERE)

    assert (
        _blocker(game, actor, ActorMoveWithinStageAction(destination=FIRE_ROOM)) is None
    )
    assert (
        _blocker(game, actor, ActorMoveWithinStageAction(destination=TOWER)) is not None
    )


def test_move_within_is_refused_on_the_map() -> None:
    game = build_world()
    reason = _blocker(
        game, entity(game, WANDERER), ActorMoveWithinStageAction(destination=CAMP)
    )
    assert reason is not None


###############################################################################
# 地图层
###############################################################################
def test_travel_only_accepts_adjacent_cells() -> None:
    game = build_world()
    actor = entity(game, WANDERER)

    assert _blocker(game, actor, ActorTravelAction(cell_x=1, cell_y=2)) is None
    assert _blocker(game, actor, ActorTravelAction(cell_x=4, cell_y=4)) is not None


def test_travel_is_refused_inside_a_settlement() -> None:
    game = build_world()
    assert _blocker(game, entity(game, HERE), ActorTravelAction(cell_x=1, cell_y=2))


def test_enter_requires_standing_on_the_settlement_cell() -> None:
    game = build_world()
    actor = entity(game, WANDERER)

    assert _blocker(game, actor, ActorEnterStageAction(stage_name=CAMP)) is not None

    actor.replace(PositionComponent, 2, 2)
    assert _blocker(game, actor, ActorEnterStageAction(stage_name=CAMP)) is None


def test_enter_refuses_unknown_stage() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    actor.replace(PositionComponent, 2, 2)

    reason = _blocker(game, actor, ActorEnterStageAction(stage_name="舞台.不存在"))
    assert reason is not None


###############################################################################
# 层级与动作类型
###############################################################################
def test_speak_on_the_map_keeps_the_actor_unchanged() -> None:
    """守卫只在判断，不改状态。"""
    game = build_world()
    actor = entity(game, WANDERER)

    _blocker(game, actor, ActorSpeakAction(content="喂"))

    assert actor.get(ActorComponent).current_stage == "舞台.战场"
    assert actor.has(PositionComponent)
