"""计划系统：谁被计划、看到什么、工具只留痕不改世界。

计划是「想」：动作组件由调用方挂，系统只负责把这一刻的舞台与在场角色讲给角色听，
再把它的工具调用记下来。工具目前是空转的，所以世界状态不会变。
"""

from typing import Any, Dict, List

import pytest

from ai_srpg.entitas import Entity
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import build_from_blueprint
from ai_srpg.game.memory import get_agent_memory
from ai_srpg.game.systems.actor_plan_system import (
    ActorPlanSystem,
    actor_plan_prompt,
)
from ai_srpg.llm import AgentLoopResult
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
    ActorPlanAction,
    AppearanceComponent,
    Blueprint,
    EnvironmentComponent,
    GlobalStageComponent,
    HumanMessage,
    Position,
    StageBlueprint,
    StageComponent,
)
from ai_srpg.utils import get_prompt_builders

STAGE = "舞台.营地"
ACTOR = "角色.甲"
OTHER_ACTOR = "角色.乙"
BASE_ENVIRONMENT = "碎石浅坑，灰土，风从旧道来"
BASE_BODY = "瘦削，洗得发白的旧斗篷"
OTHER_BODY = "矮壮，右臂缠着脏布"


###############################################################################
def _actor(name: str, base_body: str) -> ActorBlueprint:
    return ActorBlueprint(
        name=name,
        system_message=f"{name} 的设定",
        components={
            ActorComponent.__name__: {"current_stage": STAGE},
            AppearanceComponent.__name__: {"base_body": base_body},
        },
    )


def _game() -> SRPGGame:
    game = create_srpg_game(name="PlanTest")
    build_from_blueprint(
        game,
        Blueprint(
            name="PlanTest",
            campaign_setting="设定",
            global_rules="规则",
            stage_tree=StageBlueprint(
                name="舞台.战场",
                system_message="舞台.战场 的设定",
                components={
                    StageComponent.__name__: {},
                    GlobalStageComponent.__name__: {"width": 5, "height": 5},
                },
                children=[
                    StageBlueprint(
                        name=STAGE,
                        system_message=f"{STAGE} 的设定",
                        components={
                            StageComponent.__name__: {},
                            EnvironmentComponent.__name__: {
                                "base_environment": BASE_ENVIRONMENT
                            },
                        },
                        position=Position(x=2, y=2),
                    )
                ],
            ),
            actors=[_actor(ACTOR, BASE_BODY), _actor(OTHER_ACTOR, OTHER_BODY)],
            worlds=[],
        ),
    )
    return game


def _activate(game: SRPGGame, *actor_names: str) -> ActorPlanSystem:
    """先开收集器再挂动作：动作的 ADDED 才是触发事件。"""
    system = ActorPlanSystem(game)
    system.activate()
    for name in actor_names:
        _entity(game, name).replace(ActorPlanAction)
    return system


def _entity(game: SRPGGame, name: str) -> Entity:
    entity = game.get_entity_by_name(name)
    assert entity is not None
    return entity


def _capture(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """替换 agent loop，记录每次调用拿到的参数。"""
    calls: List[Dict[str, Any]] = []

    async def _fake(**kwargs: Any) -> AgentLoopResult:
        calls.append(kwargs)
        messages = kwargs["messages"]
        messages.append(HumanMessage(content=kwargs["input_message"]))
        return AgentLoopResult(
            success=True,
            start_index=len(messages) - 1,
            end_index=len(messages),
            messages=messages,
        )

    monkeypatch.setattr("ai_srpg.game.systems.actor_plan_system.agent_loop", _fake)
    return calls


###############################################################################
# 谁被计划
###############################################################################
async def test_only_actors_with_action_are_planned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    assert [call["name"] for call in calls] == [f"plan:{ACTOR}"]


async def test_planned_actors_run_in_creation_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game, OTHER_ACTOR, ACTOR)

    await system.execute()

    assert [call["name"] for call in calls] == [
        f"plan:{ACTOR}",
        f"plan:{OTHER_ACTOR}",
    ]


async def test_without_action_nobody_is_planned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game)

    await system.execute()

    assert calls == []


###############################################################################
# 看到什么
###############################################################################
async def test_prompt_has_environment_and_every_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    (call,) = calls
    message = call["input_message"]
    assert f"当前舞台：{STAGE}" in message
    assert BASE_ENVIRONMENT in message
    assert ACTOR in message and BASE_BODY in message
    assert OTHER_ACTOR in message and OTHER_BODY in message


async def test_prompt_builder_is_registered() -> None:
    builders = get_prompt_builders()
    assert any(builder is actor_plan_prompt for builder in builders.values())


###############################################################################
# 只留痕，不改世界
###############################################################################
async def test_tools_are_speak_and_move(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    (call,) = calls
    assert [tool.function.name for tool in call["tools"]] == ["speak", "move"]


async def test_handlers_only_acknowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game()
    calls = _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    (call,) = calls
    handlers = call["handlers"]
    assert "尚未生效" in str(handlers["speak"](content="谁在那儿？"))
    assert "尚未生效" in str(handlers["move"](target="水边"))


async def test_plan_is_written_to_actor_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    memory = get_agent_memory(game, _entity(game, ACTOR))
    contents = [message.content for message in memory.messages]
    assert any("当前舞台" in content for content in contents)


async def test_plan_failure_leaves_the_actor_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """计划失败只等于本轮轮空：不抛给 pipeline，也不改世界。"""

    async def _boom(**kwargs: Any) -> AgentLoopResult:
        raise RuntimeError("boom")

    monkeypatch.setattr("ai_srpg.game.systems.actor_plan_system.agent_loop", _boom)
    game = _game()
    actor = _entity(game, ACTOR)
    system = _activate(game, ACTOR)

    await system.execute()

    assert actor.get(ActorComponent).current_stage == STAGE
    assert actor.get(AppearanceComponent).appearance == BASE_BODY


async def test_plan_leaves_world_state_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = _game()
    actor = _entity(game, ACTOR)
    _capture(monkeypatch)
    system = _activate(game, ACTOR)

    await system.execute()

    assert actor.get(ActorComponent).current_stage == STAGE
    assert actor.get(AppearanceComponent).appearance == BASE_BODY
