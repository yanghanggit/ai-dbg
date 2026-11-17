"""RoomInitSystem 单元测试：开场角色感知、战斗牌堆初始化与战斗状态切换。"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.context import ECSContext
from ai_dbg.models import (
    ActorComponent,
    AppearanceComponent,
    CharacterStats,
    CharacterStatsComponent,
    CombatResult,
    CombatState,
    CombatStateComponent,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    MonsterComponent,
    PlayerComponent,
)
from ai_dbg.systems.room_init_system import (
    OtherActorInfo,
    RoomInitSystem,
    _build_other_actors_info,
)


def _make_actor(
    context: ECSContext,
    name: str,
    *,
    is_ally: bool = False,
    is_monster: bool = False,
    appearance: str = "普通外观",
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "")
    entity.add(CharacterStatsComponent, name, CharacterStats())
    entity.add(AppearanceComponent, name, "base_body", appearance)
    entity.add(DeckComponent, name, [])
    if is_ally:
        entity.add(PlayerComponent, name)
    if is_monster:
        entity.add(MonsterComponent, name)
    return entity


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    game = MagicMock()
    game.ecs = context
    game.world.agent_memories = {}
    game.events = MagicMock()
    return game


@pytest.fixture()
def system(mock_game: Any) -> RoomInitSystem:
    return RoomInitSystem(mock_game)


def test_format_other_actors_info_empty() -> None:
    assert _build_other_actors_info([]) == "无"


def test_format_other_actors_info_contains_name_camp_appearance() -> None:
    info = OtherActorInfo(other_name="游侠", appearance="披着绿色斗篷", camp="友方")
    result = _build_other_actors_info([info])
    assert "游侠" in result
    assert "友方" in result
    assert "披着绿色斗篷" in result


def test_inject_opening_scene_environment_injects_human_and_ai_messages(
    context: ECSContext, mock_game: Any, system: RoomInitSystem
) -> None:
    actor_a = _make_actor(context, "勇者", is_ally=True)
    actor_b = _make_actor(context, "游侠", is_ally=True)

    system._inject_opening_scene_environment(
        actor_entities={actor_a, actor_b},
        stage_name="入口石室",
        environment="潮湿阴冷的洞口",
    )

    for actor in (actor_a, actor_b):
        messages = mock_game.world.agent_memories[actor.name].messages
        assert sum(1 for m in messages if m.type == "human") == 1
        assert sum(1 for m in messages if m.type == "ai") == 1
        human_message = next(m for m in messages if m.type == "human")
        assert human_message.content != ""
        assert getattr(human_message, "opening_initialization", None) == "入口石室"


def test_inject_opening_scene_environment_is_idempotent(
    context: ECSContext, mock_game: Any, system: RoomInitSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)

    for _ in range(2):
        system._inject_opening_scene_environment(
            actor_entities={actor},
            stage_name="入口石室",
            environment="潮湿阴冷的洞口",
        )

    messages = mock_game.world.agent_memories[actor.name].messages
    assert sum(1 for m in messages if m.type == "human") == 1
    assert sum(1 for m in messages if m.type == "ai") == 1


def test_initialize_piles_adds_all_piles(
    context: ECSContext, system: RoomInitSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)
    system._initialize_piles({actor})

    assert actor.has(DrawPileComponent)
    assert actor.has(DiscardPileComponent)
    assert actor.has(ExhaustPileComponent)
    assert actor.get(DrawPileComponent).cards == []


def test_transition_to_ongoing(context: ECSContext, system: RoomInitSystem) -> None:
    combat = context.create_entity()
    combat._name = "场景.测试#combat"
    combat.add(
        CombatStateComponent,
        "场景.测试#combat",
        "场景.测试",
        CombatState.INITIALIZATION,
        CombatResult.NONE,
        False,
    )

    system._transition_to_ongoing(combat)

    state = combat.get(CombatStateComponent)
    assert state.state == CombatState.ONGOING
    assert state.result == CombatResult.NONE
