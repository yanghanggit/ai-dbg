from typing import Any

"""广播「自我回显」规则的单测。

规则（写在 `DBGGame.broadcast_to_stage` 的 docstring 里）：
- 行动类广播：发起者另有更精确的自我记录时排除发起者（出牌有 `combat_decision` 决策记录）；
- 观察类广播：发起者对该事件没有其他记录时保留（过牌等）。

这里把两个代表性系统各钉一条，规则变动时会立刻失败。
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.models import (
    ActorComponent,
    Card,
    HandComponent,
    PartyMemberComponent,
    PlayCardsAction,
    StageComponent,
    TargetType,
)
from dungeon_support import install_combat


@pytest.fixture()
def context() -> Context:
    return Context()


_PLAY_MODULE = "ai_dbg.systems.play_cards_action_system"
_PASS_MODULE = "ai_dbg.systems.pass_turn_action_system"


def _make_card() -> Card:
    return Card(
        name="攻击",
        description="",
        cost=1,
        damage=5,
        hit_count=1,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )


def _make_actor(context: Context, name: str, card: Card) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, name)
    entity.add(HandComponent, name, [card])
    return entity


def _make_game(actor: Entity, stage: Entity) -> Any:
    game = MagicMock()
    game.ecs = actor._context
    game.entity_index = {}
    game.world.agent_memories = {}
    game.events = MagicMock()
    install_combat(
        game,
        action_order=[actor.name],
        current_actor=actor.name,
    )
    return game


def _make_stage(context: Context) -> Entity:
    stage = context.create_entity()
    stage._name = "场景.河湾芦苇丛"
    stage.add(StageComponent, stage.name)
    return stage


async def test_play_cards_broadcast_excludes_actor(context: Context) -> None:
    """出牌是行动类广播：出牌者已有决策记录，广播必须排除他本人。"""
    from ai_dbg.systems.play_cards_action_system import PlayCardsActionSystem

    card = _make_card()
    actor = _make_actor(context, "角色.无名", card)
    actor.add(PlayCardsAction, actor.name, card, ["怪物.渡口野狗"])
    stage = _make_stage(context)
    game = _make_game(actor, stage)

    with (
        patch(f"{_PLAY_MODULE}.get_current_turn_actor", return_value=actor.name),
        patch(f"{_PLAY_MODULE}.consume_turn_energy"),
        patch(f"{_PLAY_MODULE}.broadcast_to_stage") as mock_broadcast,
    ):
        await PlayCardsActionSystem(game).react([actor])

    # 出牌事实不再由本系统写（已折进 `combat_decision` 决策记录，见 PartyCombatDecisionSystem），
    # 因此这里只断言广播口径。
    # 广播：排除出牌者与场景实体
    broadcast_kwargs = mock_broadcast.call_args.kwargs
    assert broadcast_kwargs["exclude_entities"] == {actor, stage}


async def test_pass_turn_broadcast_keeps_actor(context: Context) -> None:
    """过牌是观察类广播：过牌者没有其他记录，必须保留他本人。"""
    from ai_dbg.models import PassTurnAction
    from ai_dbg.systems import pass_turn_action_system as pass_module

    card = _make_card()
    actor = _make_actor(context, "角色.无名", card)
    actor.add(PassTurnAction, actor.name)
    stage = _make_stage(context)
    game = _make_game(actor, stage)

    with (
        patch(f"{_PASS_MODULE}.get_current_turn_actor", return_value=actor.name),
        patch(f"{_PASS_MODULE}.get_turn_energy", return_value=2),
        patch(f"{_PASS_MODULE}.consume_turn_energy"),
        patch(f"{_PASS_MODULE}.broadcast_to_stage") as mock_broadcast,
    ):
        await pass_module.PassTurnActionSystem(game).react([actor])

    broadcast_kwargs = mock_broadcast.call_args.kwargs
    assert broadcast_kwargs["exclude_entities"] == {stage}
    assert actor not in broadcast_kwargs["exclude_entities"]

    # 过牌者不额外收到私发消息（唯一凭据就是那条广播）
    assert not game.world.agent_memories
