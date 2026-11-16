from typing import Any

"""PickSpoilsActionSystem / SpoilsComponent 两队列语义单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.models import (
    ActorComponent,
    Card,
    DeckComponent,
    PickSpoilsAction,
    SpoilRewardKind,
    SpoilsComponent,
)
from ai_dbg.systems.pick_spoils_action_system import PickSpoilsActionSystem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str) -> Card:
    return Card(name=name, description=f"{name} 的描述", source="角色.无名")


def _make_actor(
    context: Context,
    name: str,
    candidate_cards: list[Card],
    claimed_cards: list[Card] | None = None,
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "")
    entity.add(DeckComponent, name, [])
    entity.add(
        SpoilsComponent,
        name,
        candidate_cards,
        claimed_cards if claimed_cards is not None else [],
    )
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
    game.player_session = MagicMock()
    return game


@pytest.fixture()
def system(mock_game: Any) -> PickSpoilsActionSystem:
    return PickSpoilsActionSystem(mock_game)


# ---------------------------------------------------------------------------
# SpoilsComponent 数据模型
# ---------------------------------------------------------------------------


def test_spoils_claimed_defaults_to_empty_queue() -> None:
    comp = SpoilsComponent(name="勇者", candidate_cards=[])
    assert comp.claimed_cards == []


# ---------------------------------------------------------------------------
# 领取：两队列迁移
# ---------------------------------------------------------------------------


async def test_pick_moves_card_from_cards_to_claimed(
    context: Context, mock_game: Any, system: PickSpoilsActionSystem
) -> None:
    cards = [_make_card("斩击"), _make_card("格挡"), _make_card("突进")]
    actor = _make_actor(context, "勇者", cards)
    actor.add(PickSpoilsAction, "勇者", SpoilRewardKind.CARD, cards[1])

    await system.react([actor])

    spoils = actor.get(SpoilsComponent)
    deck = actor.get(DeckComponent)

    # candidate_cards 出队一张；claimed_cards 入队同一对象
    assert spoils.candidate_cards == [cards[0], cards[2]]
    assert spoils.claimed_cards == [cards[1]]
    assert deck.cards == [cards[1]]

    # 牌库变化要写给本人（不广播）：一条带 spoils_pick 标记的自我状态说明
    message = mock_game.world.agent_memories[actor.name].messages[-1]
    assert message.content.startswith("# 你收下了战利品")
    assert "格挡" in message.content
    assert "当前共 1 张" in message.content
    assert message.spoils_pick == "格挡"


async def test_pick_rejected_when_already_claimed(
    context: Context, mock_game: Any, system: PickSpoilsActionSystem
) -> None:
    already = _make_card("已领")
    pending = _make_card("斩击")
    actor = _make_actor(context, "勇者", [pending], claimed_cards=[already])
    actor.add(PickSpoilsAction, "勇者", SpoilRewardKind.CARD, pending)

    with pytest.raises(AssertionError):
        await system.react([actor])

    # 状态未被改动
    spoils = actor.get(SpoilsComponent)
    assert spoils.candidate_cards == [pending]
    assert spoils.claimed_cards == [already]
    assert actor.get(DeckComponent).cards == []


async def test_pick_rejected_when_card_not_in_queue(
    context: Context, mock_game: Any, system: PickSpoilsActionSystem
) -> None:
    stray = _make_card("不在队列")
    actor = _make_actor(context, "勇者", [_make_card("斩击")])
    actor.add(PickSpoilsAction, "勇者", SpoilRewardKind.CARD, stray)

    with pytest.raises(AssertionError):
        await system.react([actor])
