"""领域事件：一个动作一个事件；位置变化说给三处听，但事件只发布一次。"""

from typing import Any, List

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_srpg.game.context import SRPGGame
from ai_srpg.game.events.sink import RecordingEventSink
from ai_srpg.game.systems.actor_enter_stage_system import ActorEnterStageSystem
from ai_srpg.game.systems.actor_exit_stage_system import ActorExitStageSystem
from ai_srpg.game.systems.actor_move_within_stage_system import (
    ActorMoveWithinStageSystem,
)
from ai_srpg.game.systems.actor_speak_system import ActorSpeakSystem
from ai_srpg.game.systems.actor_travel_system import ActorTravelSystem
from ai_srpg.game.systems.actor_wait_system import ActorWaitSystem
from ai_srpg.game.systems.stage_pulse_system import StagePulseSystem
from ai_srpg.models import (
    ActorEnteredStage,
    ActorEnterStageAction,
    ActorExitedStage,
    ActorExitStageAction,
    ActorMovedWithinStage,
    ActorMoveWithinStageAction,
    ActorSpeakAction,
    ActorSpoke,
    ActorTravelAction,
    ActorTraveled,
    ActorWaitAction,
    ActorWaited,
    AnyAgentEvent,
    NoneEvent,
    PositionComponent,
    StagePulse,
)
from world_fixture import (
    BATTLEFIELD,
    CAMP,
    FIRE_ROOM,
    HERE,
    OTHER,
    TOWER,
    WANDERER,
    build_world,
    entity,
    messages,
)

_EVENT: TypeAdapter[AnyAgentEvent] = TypeAdapter(AnyAgentEvent)


def _world() -> tuple[SRPGGame, RecordingEventSink]:
    sink = RecordingEventSink()
    return build_world(events=sink), sink


def _activate(game: SRPGGame, system_type: Any) -> Any:
    system = system_type(game)
    system.activate()
    return system


def _tags(game: SRPGGame, name: str) -> List[str]:
    """该实体记忆里每条人类消息的事件标记。"""
    return [
        str(getattr(message, "agent_event", "")) for message in messages(game, name)
    ]


###############################################################################
# 事件的形状
###############################################################################
def test_events_round_trip_through_the_union() -> None:
    """每种事件都能按 type 判别解析回自己，字段不丢。"""
    events: List[Any] = [
        StagePulse(message="在场", stage=CAMP, actors=(HERE, OTHER)),
        ActorSpoke(message="说了", actor=HERE, stage=CAMP, content="说了"),
        ActorWaited(message="没动", actor=HERE, stage=CAMP),
        ActorTraveled(message="走了", actor=WANDERER, stage=BATTLEFIELD, x=1, y=2),
        ActorEnteredStage(message="进城", actor=WANDERER, stage=CAMP),
        ActorExitedStage(message="出城", actor=HERE, stage=CAMP),
        ActorMovedWithinStage(
            message="挪了", actor=HERE, stage=CAMP, destination=FIRE_ROOM
        ),
        NoneEvent(message="兜底"),
    ]

    for event in events:
        parsed = _EVENT.validate_python(event.model_dump())
        assert parsed == event
        assert parsed.type == event.type


def test_unknown_field_is_rejected() -> None:
    """事件是契约：多一个字段就是写错了，不静默吞掉。"""
    with pytest.raises(ValidationError):
        ActorSpoke.model_validate(
            {"message": "x", "actor": HERE, "stage": CAMP, "content": "x", "extra": 1}
        )


###############################################################################
# 一个动作一个事件
###############################################################################
async def test_speak_publishes_what_was_said() -> None:
    game, sink = _world()
    system = _activate(game, ActorSpeakSystem)
    entity(game, HERE).replace(ActorSpeakAction, "风变了。")
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorSpoke)
    assert (event.actor, event.stage, event.content) == (HERE, CAMP, "风变了。")
    assert _tags(game, OTHER) == ["actor_spoke"]


async def test_travel_publishes_once_but_tells_three_places() -> None:
    """旧处、新处、自己各听到一句，但那只发生过一件事。"""
    game, sink = _world()
    system = _activate(game, ActorTravelSystem)

    entity(game, WANDERER).replace(ActorTravelAction, 1, 2)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorTraveled)
    assert (event.actor, event.stage, event.x, event.y) == (
        WANDERER,
        BATTLEFIELD,
        1,
        2,
    )
    # 地图上只有地图自己听见；他自己另有一句路程记录
    assert _tags(game, BATTLEFIELD) == ["actor_traveled", "actor_traveled"]
    assert _tags(game, WANDERER) == ["actor_traveled"]


async def test_enter_publishes_the_settlement_it_entered() -> None:
    game, sink = _world()
    actor = entity(game, WANDERER)
    actor.replace(PositionComponent, 2, 2)
    system = _activate(game, ActorEnterStageSystem)

    actor.replace(ActorEnterStageAction, CAMP)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorEnteredStage)
    assert (event.actor, event.stage) == (WANDERER, CAMP)
    assert _tags(game, CAMP) == ["actor_entered_stage"]


async def test_exit_publishes_the_settlement_it_left() -> None:
    game, sink = _world()
    system = _activate(game, ActorExitStageSystem)

    entity(game, HERE).replace(ActorExitStageAction)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorExitedStage)
    assert (event.actor, event.stage) == (HERE, CAMP)


async def test_move_within_publishes_destination_and_settlement() -> None:
    game, sink = _world()
    system = _activate(game, ActorMoveWithinStageSystem)

    entity(game, HERE).replace(ActorMoveWithinStageAction, FIRE_ROOM)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorMovedWithinStage)
    assert (event.actor, event.stage, event.destination) == (HERE, CAMP, FIRE_ROOM)


async def test_wait_inside_a_settlement_publishes_and_tells_others() -> None:
    game, sink = _world()
    system = _activate(game, ActorWaitSystem)

    entity(game, HERE).replace(ActorWaitAction)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorWaited)
    assert (event.actor, event.stage) == (HERE, CAMP)
    assert _tags(game, OTHER) == ["actor_waited"]


async def test_wait_on_the_map_publishes_but_tells_nobody() -> None:
    """地图上没有听众，但「这轮没动」仍是发生过的事。"""
    game, sink = _world()
    system = _activate(game, ActorWaitSystem)

    entity(game, WANDERER).replace(ActorWaitAction)
    await system.execute()

    (event,) = sink.events
    assert isinstance(event, ActorWaited)
    assert event.stage == BATTLEFIELD
    assert messages(game, BATTLEFIELD) == []
    assert messages(game, HERE) == []


async def test_pulse_publishes_who_is_present() -> None:
    game, sink = _world()

    await StagePulseSystem(game).execute()  # 每轮执行一次，不需要订阅触发器

    published = {
        event.stage: event for event in sink.events if isinstance(event, StagePulse)
    }
    assert isinstance(published[CAMP], StagePulse)
    assert sorted(published[CAMP].actors) == sorted([HERE, OTHER])
    assert isinstance(published[TOWER], StagePulse)
    assert published[TOWER].actors == ("角色.丙",)
    # 全局舞台没有在场者，不发布
    assert BATTLEFIELD not in published


###############################################################################
# 被拒绝的动作不产生事件
###############################################################################
async def test_rejected_action_publishes_nothing() -> None:
    game, sink = _world()
    system = _activate(game, ActorTravelSystem)

    entity(game, WANDERER).replace(ActorTravelAction, 4, 4)  # 不相邻
    await system.execute()

    assert sink.events == []
