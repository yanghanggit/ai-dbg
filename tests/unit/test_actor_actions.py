"""六个行为系统：说话、等待、战场移动、进城、出城、城内移动。

每个动词只在它所属的层生效：说话与出城在据点里，战场移动与进城在地图上，城内移动
在据点内部，等待在两层都可用（地图上没有可告知的对象）。
"""

from typing import Type, TypeVar

from ai_srpg.entitas import ReactiveProcessor
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.systems.actor_enter_stage_system import ActorEnterStageSystem
from ai_srpg.game.systems.actor_exit_stage_system import ActorExitStageSystem
from ai_srpg.game.systems.actor_move_within_stage_system import (
    ActorMoveWithinStageSystem,
)
from ai_srpg.game.systems.actor_speak_system import ActorSpeakSystem
from ai_srpg.game.systems.actor_travel_system import ActorTravelSystem
from ai_srpg.game.systems.actor_wait_system import ActorWaitSystem
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
    BATTLEFIELD,
    CAMP,
    FIRE_ROOM,
    HERE,
    OTHER,
    TOWER,
    WANDERER,
    build_world,
    entity,
    heard,
    said,
)

_Processor = TypeVar("_Processor", bound=ReactiveProcessor)


def _system(system_type: Type[_Processor], game: SRPGGame) -> _Processor:
    system = system_type(game)
    system.activate()
    return system


###############################################################################
# 说话：只在据点里
###############################################################################
async def test_speak_reaches_the_local_stage_only() -> None:
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorSpeakSystem, game)

    actor.replace(ActorSpeakAction, "风变了。")
    await system.execute()

    assert heard(game, OTHER) == [f"{HERE}说：风变了。"]
    assert heard(game, CAMP) == [f"{HERE}说：风变了。"]
    assert heard(game, HERE) == []
    assert heard(game, WANDERER) == []
    assert heard(game, TOWER) == []


async def test_speak_on_the_map_is_not_a_thing() -> None:
    """地图不是场所：站在战场上说话，谁也不会听见，包括地图自己。"""
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorSpeakSystem, game)

    actor.replace(ActorSpeakAction, "有人吗？")
    await system.execute()

    assert heard(game, HERE) == []
    assert heard(game, BATTLEFIELD) == []


async def test_wait_on_the_map_tells_nobody() -> None:
    """地图上没有听众：战场上原地不动只是「这轮没动」，不产生任何广播。"""
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorWaitSystem, game)

    actor.replace(ActorWaitAction)
    await system.execute()

    assert heard(game, BATTLEFIELD) == []
    assert heard(game, HERE) == []


async def test_wait_tells_others_that_nothing_happened() -> None:
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorWaitSystem, game)

    actor.replace(ActorWaitAction)
    await system.execute()

    assert heard(game, OTHER) == [f"{HERE}留在原地。"]
    assert heard(game, CAMP) == [f"{HERE}留在原地。"]
    assert heard(game, HERE) == []


###############################################################################
# 战场移动：只改坐标，不改变所在层
###############################################################################
async def test_travel_moves_one_cell_on_the_map() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorTravelSystem, game)

    actor.replace(ActorTravelAction, 1, 2)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (1, 2)
    assert actor.get(ActorComponent).current_stage == BATTLEFIELD
    assert said(game, WANDERER) == [f"你从{BATTLEFIELD}(1,1)走到{BATTLEFIELD}(1,2)。"]
    assert heard(game, BATTLEFIELD) == [
        f"{WANDERER}离开了{BATTLEFIELD}(1,1)。",
        f"{WANDERER}来到了{BATTLEFIELD}(1,2)。",
    ]


async def test_travel_can_stop_on_a_settlement_cell() -> None:
    """兵临城下：走到据点格不算进城，still 站在地图上。"""
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorTravelSystem, game)

    actor.replace(ActorTravelAction, 2, 2)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (2, 2)
    assert actor.get(ActorComponent).current_stage == BATTLEFIELD


async def test_travel_rejects_non_adjacent_cells() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorTravelSystem, game)

    actor.replace(ActorTravelAction, 4, 4)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (1, 1)
    assert said(game, WANDERER) == []


async def test_travel_requires_being_on_the_map() -> None:
    """在据点里的人收到战场移动动作也不会动：层级不符的动作不生效。"""
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorTravelSystem, game)

    actor.replace(ActorTravelAction, 3, 3)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP
    assert not actor.has(PositionComponent)


###############################################################################
# 进城 / 出城：边界上的一对
###############################################################################
async def test_enter_requires_standing_on_the_settlement_cell() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    actor.replace(PositionComponent, 2, 2)
    system = _system(ActorEnterStageSystem, game)

    actor.replace(ActorEnterStageAction, CAMP)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP
    assert not actor.has(PositionComponent)
    # 离开发生在地图上：只有地图记下；据点里的人只看见他进来
    assert heard(game, BATTLEFIELD) == [f"{WANDERER}离开了{BATTLEFIELD}(2,2)。"]
    assert heard(game, OTHER) == [f"{WANDERER}来到了{CAMP}。"]
    assert said(game, WANDERER) == [f"你从{BATTLEFIELD}(2,2)走到{CAMP}。"]


async def test_enter_is_rejected_from_another_cell() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorEnterStageSystem, game)

    actor.replace(ActorEnterStageAction, CAMP)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == BATTLEFIELD
    assert said(game, WANDERER) == []


async def test_exit_lands_on_the_settlement_cell() -> None:
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorExitStageSystem, game)

    actor.replace(ActorExitStageAction)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == BATTLEFIELD
    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (2, 2)
    assert heard(game, OTHER) == [f"{HERE}离开了{CAMP}。"]
    assert heard(game, BATTLEFIELD) == [f"{HERE}来到了{BATTLEFIELD}(2,2)。"]
    assert said(game, HERE) == [f"你从{CAMP}走到{BATTLEFIELD}(2,2)。"]


async def test_exit_from_a_deeper_area_still_lands_on_the_settlement_cell() -> None:
    """据点对外只是一个节点：在里面走到再深，出城也是从据点那一格出去。"""
    game = build_world()
    actor = entity(game, HERE)
    actor.replace(ActorComponent, FIRE_ROOM)
    system = _system(ActorExitStageSystem, game)
    actor.replace(ActorExitStageAction)

    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (2, 2)
    assert actor.get(ActorComponent).current_stage == BATTLEFIELD


###############################################################################
# 城内移动：子区域与父区域
###############################################################################
async def test_move_within_goes_to_a_child_area() -> None:
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorMoveWithinStageSystem, game)

    actor.replace(ActorMoveWithinStageAction, FIRE_ROOM)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == FIRE_ROOM
    assert heard(game, OTHER) == [f"{HERE}离开了{CAMP}。"]
    assert heard(game, FIRE_ROOM) == [f"{HERE}来到了{FIRE_ROOM}。"]
    assert said(game, HERE) == [f"你从{CAMP}走到{FIRE_ROOM}。"]


async def test_move_within_goes_back_to_the_parent_area() -> None:
    game = build_world()
    actor = entity(game, OTHER)
    actor.replace(ActorComponent, FIRE_ROOM)
    system = _system(ActorMoveWithinStageSystem, game)

    actor.replace(ActorMoveWithinStageAction, CAMP)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP


async def test_move_within_cannot_leave_the_settlement() -> None:
    """去另一个据点不是城内移动：那是先出城、再上路的组合。"""
    game = build_world()
    actor = entity(game, HERE)
    system = _system(ActorMoveWithinStageSystem, game)

    actor.replace(ActorMoveWithinStageAction, TOWER)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP
    assert said(game, HERE) == []


async def test_move_within_requires_being_inside_a_settlement() -> None:
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorMoveWithinStageSystem, game)

    actor.replace(ActorMoveWithinStageAction, CAMP)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == BATTLEFIELD
    assert said(game, WANDERER) == []


###############################################################################
# 触发器语义：进入匹配集合（不是「同时添加两个组件」）
###############################################################################
async def test_replacing_the_action_triggers_again() -> None:
    """ActorComponent 早就在了，更新动作也会再触发一次。"""
    game = build_world()
    actor = entity(game, WANDERER)
    system = _system(ActorTravelSystem, game)

    actor.replace(ActorTravelAction, 1, 2)
    await system.execute()
    actor.replace(ActorTravelAction, 2, 2)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (2, 2)


async def test_action_mounted_before_activation_is_not_collected() -> None:
    """先挂动作再开收集器，这次变更不会进来——动作只活一次 pass 的前提。"""
    game = build_world()
    actor = entity(game, WANDERER)
    actor.replace(ActorTravelAction, 1, 2)
    system = _system(ActorTravelSystem, game)

    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (1, 1)
