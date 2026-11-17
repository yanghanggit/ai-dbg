"""CombatHandCleanupSystem 与回合手牌结算的单元测试。"""

from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas import Entity
from ai_dbg.game.context import ECSContext
from ai_dbg.models import (
    Card,
    CombatState,
    DiscardPileComponent,
    DrawPileComponent,
    HandComponent,
)
from ai_dbg.systems.card_pile_common import HandSettlement
from ai_dbg.systems.combat_hand_cleanup_system import CombatHandCleanupSystem
from dungeon_support import install_combat


#######################################################################################################################################
def _make_card(name: str, *, retain: bool = False) -> Card:
    return Card(name=name, description="", retain=retain)


def _make_owner(
    context: ECSContext,
    *,
    name: str = "角色.测试",
    draw_cards: Optional[List[Card]] = None,
    discard_cards: Optional[List[Card]] = None,
    hand_cards: Optional[List[Card]] = None,
    retained_cards: Optional[List[Card]] = None,
) -> Entity:
    """创建带手牌 / 抽牌堆 / 弃牌堆 / 保留队列的测试实体。"""
    entity = context.create_entity(name)
    entity.add(
        DrawPileComponent,
        name,
        draw_cards or [],
        retained_cards or [],
    )
    entity.add(DiscardPileComponent, name, discard_cards or [])
    entity.add(HandComponent, name, hand_cards or [])
    return entity


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


def _make_game(context: ECSContext) -> Any:
    game = MagicMock()
    game.ecs = context
    game.world.agent_memories = {}
    game.events = MagicMock()
    return game


#######################################################################################################################################
class TestSettleHand:
    """CombatHandCleanupSystem._settle_hand() 的结算测试。"""

    def test_moves_discard_and_retained_cards(self, context: ECSContext) -> None:
        discarded = [_make_card("攻击"), _make_card("防守")]
        retained = [_make_card("守势", retain=True)]
        old_discard = [_make_card("旧牌")]
        old_retained = [_make_card("旧保留", retain=True)]
        draw_card = _make_card("抽牌")

        owner = _make_owner(
            context,
            draw_cards=[draw_card],
            discard_cards=old_discard,
            hand_cards=[*discarded, *retained],
            retained_cards=old_retained,
        )

        settlement = CombatHandCleanupSystem(_make_game(context))._settle_hand(owner)

        assert settlement == HandSettlement(
            owner=owner,
            discarded=tuple(discarded),
            retained=tuple(retained),
        )
        assert owner.get(DiscardPileComponent).cards == [*old_discard, *discarded]
        draw_pile = owner.get(DrawPileComponent)
        assert draw_pile.cards == [draw_card]
        assert draw_pile.retained_cards == [*old_retained, *retained]
        assert not owner.has(HandComponent)

    def test_empty_hand_still_removes_component(self, context: ECSContext) -> None:
        owner = _make_owner(context)
        old_discard = owner.get(DiscardPileComponent).cards

        settlement = CombatHandCleanupSystem(_make_game(context))._settle_hand(owner)

        assert settlement.discarded == ()
        assert settlement.retained == ()
        assert owner.get(DiscardPileComponent).cards == old_discard
        assert not owner.has(HandComponent)


#######################################################################################################################################
class TestCombatHandCleanupSystem:
    """CombatHandCleanupSystem.execute() 的状态守卫与清理测试。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_in_combat_room(self, context: ECSContext) -> None:
        owner = _make_owner(context, hand_cards=[_make_card("攻击")])
        game = _make_game(context)

        await CombatHandCleanupSystem(game).execute()

        assert owner.has(HandComponent)

    @pytest.mark.asyncio
    async def test_skips_when_round_not_completed(self, context: ECSContext) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.ONGOING, is_completed=False)
        owner = _make_owner(context, hand_cards=[_make_card("攻击")])

        await CombatHandCleanupSystem(game).execute()

        assert owner.has(HandComponent)

    @pytest.mark.asyncio
    async def test_skips_when_combat_is_post_combat(self, context: ECSContext) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.POST_COMBAT)
        owner = _make_owner(context, hand_cards=[_make_card("攻击")])

        await CombatHandCleanupSystem(game).execute()

        assert owner.has(HandComponent)

    @pytest.mark.asyncio
    async def test_cleans_when_round_completed(self, context: ECSContext) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.ONGOING, is_completed=True)
        owner = _make_owner(
            context,
            draw_cards=[_make_card("抽牌")],
            discard_cards=[_make_card("旧牌")],
            hand_cards=[
                _make_card("攻击"),
                _make_card("守势", retain=True),
            ],
        )

        await CombatHandCleanupSystem(game).execute()

        assert not owner.has(HandComponent)
        assert [card.name for card in owner.get(DiscardPileComponent).cards] == [
            "旧牌",
            "攻击",
        ]
        assert [card.name for card in owner.get(DrawPileComponent).retained_cards] == [
            "守势"
        ]
        assert owner.name in game.world.agent_memories
        assert (
            game.world.agent_memories[owner.name].messages[-1].content.splitlines()[0]
            == "# 回合结束 · 清手牌"
        )

    @pytest.mark.asyncio
    async def test_cleans_every_owner_with_hand(self, context: ECSContext) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.ONGOING, is_completed=True)
        first = _make_owner(
            context,
            name="角色.甲",
            hand_cards=[_make_card("甲牌")],
        )
        second = _make_owner(
            context,
            name="角色.乙",
            hand_cards=[_make_card("乙牌", retain=True)],
        )

        await CombatHandCleanupSystem(game).execute()

        assert all(not owner.has(HandComponent) for owner in (first, second))

    @pytest.mark.asyncio
    async def test_cleans_when_combat_completed_before_round_completion(
        self, context: ECSContext
    ) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.COMPLETE, is_completed=False)
        owner = _make_owner(context, hand_cards=[_make_card("攻击")])

        await CombatHandCleanupSystem(game).execute()

        assert not owner.has(HandComponent)

    @pytest.mark.asyncio
    async def test_empty_hand_does_not_write_memory(self, context: ECSContext) -> None:
        game = _make_game(context)
        install_combat(game, state=CombatState.ONGOING, is_completed=True)
        owner = _make_owner(context)

        await CombatHandCleanupSystem(game).execute()

        assert not owner.has(HandComponent)
        assert owner.name not in game.world.agent_memories
