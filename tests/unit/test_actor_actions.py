"""三个行动系统：说话、原地不动、移动到相邻格。

移动的模型是「战场格」：角色要么在据点里（坐标取据点所在的格），要么站在空地上
（用自己的坐标）。因此移动只有两个结果——进据点（摘掉自己的坐标），站空地（写下坐标）。
"""

from typing import Any, Dict, List

import pytest

from ai_srpg.entitas import Entity
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import build_from_blueprint
from ai_srpg.game.entities.queries import get_exits
from ai_srpg.game.memory import get_agent_memory
from ai_srpg.game.systems.actor_move_system import ActorMoveSystem
from ai_srpg.game.systems.actor_speak_system import ActorSpeakSystem
from ai_srpg.game.systems.actor_wait_system import ActorWaitSystem
from ai_srpg.llm import AgentLoopResult
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
    ActorMoveAction,
    ActorPlanAction,
    ActorSpeakAction,
    ActorWaitAction,
    AppearanceComponent,
    Blueprint,
    ChatMessage,
    GlobalStageComponent,
    Position,
    PositionComponent,
    StageBlueprint,
    StageComponent,
)

###############################################################################
# 5x5 战场：营地在 (2,2)，哨塔在相邻的 (3,2)
###############################################################################
BATTLEFIELD = "舞台.战场"
CAMP = "舞台.营地"
TOWER = "舞台.哨塔"
HERE = "角色.甲"
OTHER = "角色.乙"
SENTRY = "角色.丙"
WANDERER = "角色.丁"


def _actor(name: str, stage: str, cell: Position | None = None) -> ActorBlueprint:
    components: Dict[str, Dict[str, object]] = {
        ActorComponent.__name__: {"current_stage": stage},
        AppearanceComponent.__name__: {"base_body": f"{name}的样子"},
    }
    if cell is not None:
        components[PositionComponent.__name__] = {"x": cell.x, "y": cell.y}
    return ActorBlueprint(
        name=name, system_message=f"{name} 的设定", components=components
    )


def _stage(name: str, cell: Position | None = None) -> StageBlueprint:
    return StageBlueprint(
        name=name,
        system_message=f"{name} 的设定",
        components={StageComponent.__name__: {}},
        position=cell,
    )


def _game() -> SRPGGame:
    game = create_srpg_game(name="ActorActionTest")
    build_from_blueprint(
        game,
        Blueprint(
            name="ActorActionTest",
            campaign_setting="设定",
            global_rules="规则",
            stage_tree=StageBlueprint(
                name=BATTLEFIELD,
                system_message=f"{BATTLEFIELD} 的设定",
                components={
                    StageComponent.__name__: {},
                    GlobalStageComponent.__name__: {"width": 5, "height": 5},
                },
                children=[
                    _stage(CAMP, Position(x=2, y=2)),
                    _stage(TOWER, Position(x=3, y=2)),
                ],
            ),
            actors=[
                _actor(HERE, CAMP),
                _actor(OTHER, CAMP),
                _actor(SENTRY, TOWER),
                _actor(WANDERER, BATTLEFIELD, Position(x=1, y=1)),
            ],
            worlds=[],
        ),
    )
    return game


def _entity(game: SRPGGame, name: str) -> Entity:
    entity = game.get_entity_by_name(name)
    assert entity is not None
    return entity


def _spoken_to(game: SRPGGame, name: str) -> List[str]:
    """该角色收到的广播文本（跳过首条 system 设定）。"""
    return [
        message.content
        for message in _messages(game, name)
        if getattr(message, "agent_event", None) is not None
    ]


def _messages(game: SRPGGame, name: str) -> List[ChatMessage]:
    return list(get_agent_memory(game, _entity(game, name)).messages[1:])


def _contents(game: SRPGGame, name: str) -> List[str]:
    return [message.content for message in _messages(game, name)]


###############################################################################
# 说话与等待：只到同一处的在场者
###############################################################################
async def test_speak_reaches_the_local_stage_only() -> None:
    game = _game()
    actor = _entity(game, HERE)
    system = ActorSpeakSystem(game)
    system.activate()

    actor.replace(ActorSpeakAction, "风变了。")
    await system.execute()

    assert _spoken_to(game, OTHER) == [f"{HERE}说：风变了。"]
    assert _spoken_to(game, CAMP) == [f"{HERE}说：风变了。"]
    assert _spoken_to(game, HERE) == []
    assert _spoken_to(game, SENTRY) == []


async def test_wait_tells_others_that_nothing_happened() -> None:
    game = _game()
    actor = _entity(game, HERE)
    system = ActorWaitSystem(game)
    system.activate()

    actor.replace(ActorWaitAction)
    await system.execute()

    assert _spoken_to(game, OTHER) == [f"{HERE}留在原地。"]
    assert _spoken_to(game, CAMP) == [f"{HERE}留在原地。"]
    assert _spoken_to(game, HERE) == []


async def test_speaker_on_the_field_is_heard_by_neighbours() -> None:
    """站在空地上没有「在场者」，改按一格距离扩散，(1,1) 听得见营地里的人。"""
    game = _game()
    actor = _entity(game, WANDERER)
    system = ActorSpeakSystem(game)
    system.activate()

    actor.replace(ActorSpeakAction, "有人吗？")
    await system.execute()

    assert _spoken_to(game, HERE) == [f"{WANDERER}说：有人吗？"]
    assert _spoken_to(game, OTHER) == [f"{WANDERER}说：有人吗？"]
    assert _spoken_to(game, BATTLEFIELD) == [f"{WANDERER}说：有人吗？"]


###############################################################################
# 移动：只能去相邻格
###############################################################################
async def test_exits_are_the_eight_neighbouring_cells() -> None:
    game = _game()

    exits = get_exits(game, _entity(game, HERE))

    assert [(exit_.x, exit_.y) for exit_ in exits] == [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 3),
        (3, 1),
        (3, 2),
        (3, 3),
    ]
    assert {exit_.stage for exit_ in exits if exit_.stage is not None} == {TOWER}


async def test_moving_onto_empty_cell_gives_actor_a_cell() -> None:
    game = _game()
    actor = _entity(game, HERE)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 3, 3)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == BATTLEFIELD
    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (3, 3)
    # 自己只留自述那条；离开与到达分属两个舞台的记忆
    assert _contents(game, actor.name) == [f"你从{CAMP}走到{BATTLEFIELD}(3,3)。"]
    assert _spoken_to(game, CAMP) == [
        f"{HERE}离开了{CAMP}。",
        f"{HERE}来到了{BATTLEFIELD}(3,3)。",
    ]
    assert _spoken_to(game, BATTLEFIELD) == [f"{HERE}来到了{BATTLEFIELD}(3,3)。"]


async def test_moving_into_a_stage_drops_the_actors_own_cell() -> None:
    game = _game()
    actor = _entity(game, HERE)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 3, 2)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == TOWER
    assert not actor.has(PositionComponent)
    assert _spoken_to(game, SENTRY) == [f"{HERE}来到了{TOWER}。"]
    assert _spoken_to(game, TOWER) == [f"{HERE}来到了{TOWER}。"]
    assert _spoken_to(game, OTHER) == [f"{HERE}离开了{CAMP}。"]
    assert _spoken_to(game, CAMP) == [f"{HERE}离开了{CAMP}。"]


async def test_moving_between_cells_on_the_field() -> None:
    """空地上再走一步：坐标更新，起点与终点各一句。"""
    game = _game()
    actor = _entity(game, WANDERER)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 0, 1)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (0, 1)
    assert _contents(game, actor.name) == [
        f"你从{BATTLEFIELD}(1,1)走到{BATTLEFIELD}(0,1)。"
    ]


async def test_moving_onto_a_camp_cell_walks_into_it() -> None:
    """目标格上有据点，就是走进那个据点——(2,2) 是营地，所以人从空地进了营地。"""
    game = _game()
    actor = _entity(game, WANDERER)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 2, 2)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP
    assert not actor.has(PositionComponent)
    # 起点 (1,1) 离营地一格，营地的人既看见他走，也看见他进来
    assert _spoken_to(game, OTHER) == [
        f"{WANDERER}离开了{BATTLEFIELD}(1,1)。",
        f"{WANDERER}来到了{CAMP}。",
    ]


async def test_non_adjacent_target_is_ignored() -> None:
    game = _game()
    actor = _entity(game, HERE)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 0, 0)
    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP
    assert not actor.has(PositionComponent)
    assert _spoken_to(game, OTHER) == []
    assert _contents(game, actor.name) == []


async def test_replacing_the_action_triggers_again() -> None:
    """触发器是「实体进入匹配集合」：ActorComponent 早就在了，更新动作也会再触发。"""
    game = _game()
    actor = _entity(game, HERE)
    system = ActorMoveSystem(game)
    system.activate()

    actor.replace(ActorMoveAction, 3, 3)
    await system.execute()
    assert actor.get(ActorComponent).current_stage == BATTLEFIELD

    actor.replace(ActorMoveAction, 4, 3)
    await system.execute()

    position = actor.get(PositionComponent)
    assert (position.x, position.y) == (4, 3)


async def test_action_mounted_before_activation_is_not_collected() -> None:
    """反向约束：先挂动作再开收集器，这次变更不会进来——动作只活一次 pass 的前提。"""
    game = _game()
    actor = _entity(game, HERE)
    actor.replace(ActorMoveAction, 3, 3)
    system = ActorMoveSystem(game)
    system.activate()

    await system.execute()

    assert actor.get(ActorComponent).current_stage == CAMP


###############################################################################
# 计划与行为交接：工具挂动作，系统消费它
###############################################################################
async def test_plan_handlers_mount_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_srpg.game.systems.actor_plan_system import ActorPlanSystem

    calls: List[Dict[str, Any]] = []

    async def _fake(**kwargs: object) -> AgentLoopResult:
        calls.append(dict(kwargs))
        messages = kwargs["messages"]
        return AgentLoopResult(
            success=True,
            start_index=0,
            end_index=len(messages),  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        )

    monkeypatch.setattr("ai_srpg.game.systems.actor_plan_system.agent_loop", _fake)
    game = _game()
    actor = _entity(game, HERE)
    system = ActorPlanSystem(game)
    system.activate()
    actor.replace(ActorPlanAction)
    await system.execute()

    (call,) = calls
    handlers = call["handlers"]

    assert handlers["speak"](content="喂。") == "（已记下）"
    assert actor.get(ActorSpeakAction).content == "喂。"
    assert "忽略" in handlers["move"](x=3, y=3)
    assert not actor.has(ActorMoveAction)
