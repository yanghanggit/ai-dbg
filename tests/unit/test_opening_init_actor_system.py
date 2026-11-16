from typing import Any

"""OpeningInitActorSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.models import (
    ActorComponent,
    AppearanceComponent,
    CharacterStats,
    CharacterStatsComponent,
    DeckComponent,
    MonsterComponent,
    PartyMemberComponent,
)
from ai_dbg.systems.opening_init_actor_system import (
    OpeningInitActorSystem,
    OtherActorInfo,
    _build_other_actors_info,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: Context,
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
        entity.add(PartyMemberComponent, name)
    if is_monster:
        entity.add(MonsterComponent, name)
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> Any:
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.world.agent_memories = {}
    game.events = MagicMock()
    return game


@pytest.fixture()
def system(mock_game: Any) -> OpeningInitActorSystem:
    return OpeningInitActorSystem(mock_game)


# ---------------------------------------------------------------------------
# _build_other_actors_info
# ---------------------------------------------------------------------------


def test_format_other_actors_info_empty() -> None:
    assert _build_other_actors_info([]) == "无"


def test_format_other_actors_info_contains_name_camp_appearance() -> None:
    info = OtherActorInfo(other_name="游侠", appearance="披着绿色斗篷", camp="友方")
    result = _build_other_actors_info([info])
    assert "游侠" in result
    assert "友方" in result
    assert "披着绿色斗篷" in result


# ---------------------------------------------------------------------------
# _build_opening_init_prompt
# ---------------------------------------------------------------------------


# def test_build_opening_init_prompt_contains_key_fields() -> None:
#     stats = CharacterStats(hp=8, max_hp=20, attack=6, defense=4)
#     result = _build_opening_init_prompt(
#         stage_name="入口石室",
#         environment="潮湿阴冷的洞口",
#         other_actors_info=[],
#         actor_stats=stats,
#     )
#     assert "入口石室" in result
#     assert "潮湿阴冷的洞口" in result
#     assert "8/20" in result
#     assert "6" in result  # attack
#     assert "4" in result  # defense


# ---------------------------------------------------------------------------
# _inject_opening_scene_environment
# ---------------------------------------------------------------------------


def test_inject_opening_scene_environment_injects_human_and_ai_messages(
    context: Context, mock_game: Any, system: OpeningInitActorSystem
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

    # 每条 human 消息都携带开场场景标记
    for actor in (actor_a, actor_b):
        human_message = next(
            m
            for m in mock_game.world.agent_memories[actor.name].messages
            if m.type == "human"
        )
        assert human_message.content != ""
        assert getattr(human_message, "opening_initialization", None) == "入口石室"


def test_inject_opening_scene_environment_skips_already_injected_actor(
    context: Context, mock_game: Any, system: OpeningInitActorSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)

    # 已有同场景标记，应跳过注入
    mock_game.filter_messages.return_value = [object()]

    system._inject_opening_scene_environment(
        actor_entities={actor},
        stage_name="入口石室",
        environment="潮湿阴冷的洞口",
    )

    mock_game.add_human_message.assert_not_called()
    mock_game.add_ai_message.assert_not_called()


# ---------------------------------------------------------------------------
# _add_generate_deck_actions
# ---------------------------------------------------------------------------


# def test_add_generate_deck_actions_adds_action_to_party_only(
#     context: Context, mock_game: Any, system: OpeningInitActorSystem
# ) -> None:
#     ally = _make_actor(context, "勇者", is_ally=True)
#     monster = _make_actor(context, "哥布林", is_monster=True)

#     party_group = MagicMock()
#     party_group.entities = {ally}

#     mock_game.get_group.return_value = party_group

#     system._add_generate_deck_actions()

#     # 只为队伍添加；怪物牌库改由战斗管道生成
#     assert ally.has(GenerateDeckAction)
#     assert not monster.has(GenerateDeckAction)
#     mock_game.get_group.assert_called_once()
