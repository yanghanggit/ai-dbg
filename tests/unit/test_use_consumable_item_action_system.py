"""UseConsumableItemActionSystem 单元测试。

重构后语义：使用消耗品 = 先移除队伍背包中该条消耗品（消耗其全部 count），
再把「每个内置卡牌 × count」物化为手牌（0 费、一次性、不叠加角色属性）。
扣库存失败则不物化、不广播。效果结算交给后续出牌仲裁。
"""

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.combat.state import (
    combat_round_view,
    combat_rounds,
    create_combat_round,
)
from ai_dbg.game.context import ECSContext
from ai_dbg.game.dungeon import current_combat_entity
from ai_dbg.models import (
    ActorComponent,
    Card,
    CombatState,
    ConsumableItem,
    HandComponent,
    InventoryComponent,
    PlayerComponent,
    RoundEntryKind,
    StageComponent,
    UseConsumableItemAction,
)
from ai_dbg.systems.use_consumable_item_action_system import (
    UseConsumableItemActionSystem,
)
from dungeon_support import (
    current_round_entity,
    install_combat,
    set_combat_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_consumable(
    name: str,
    *,
    count: int = 1,
    damage: int = 3,
    card_count: int = 1,
) -> ConsumableItem:
    cards = [
        Card(
            name=f"{name}{'' if card_count == 1 else f'·{i}'}",
            description="测试消耗品",
            cost=0,
            exhaust=True,
            damage=damage,
        )
        for i in range(card_count)
    ]
    return ConsumableItem(name=name, description="测试消耗品", cards=cards, count=count)


def _make_actor_entity(
    context: ECSContext,
    name: str,
    action_item: ConsumableItem,
) -> Entity:
    """创建携带 UseConsumableItemAction 的当前行动者实体（持有空手牌）。"""
    if not any(e.name == "stage" for e in context.entities):
        stage = context.create_entity()
        stage._name = "stage"
        stage.add(StageComponent, "stage")
    entity = context.create_entity()
    entity._name = name
    entity.add(HandComponent, name, [])
    entity.add(ActorComponent, name, "stage")
    entity.add(UseConsumableItemAction, name, action_item)
    return entity


def _make_player_entity(
    context: ECSContext, name: str, items: List[ConsumableItem]
) -> Entity:
    """创建持有队伍背包（InventoryComponent）的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    entity.add(PlayerComponent, name)
    return entity


def _setup_mock_dungeon(mock_game: Any, *, round_count: int = 1) -> Entity:
    """为 mock_game 配置进行中的战斗状态与最新回合。"""
    combat_entity = current_combat_entity(mock_game)
    existing_rounds = combat_rounds(mock_game, combat_entity)
    for index in range(len(existing_rounds) + 1, round_count + 1):
        create_combat_round(
            mock_game,
            combat_entity,
            index=index,
            action_order=[],
            current_actor=None,
        )
    return current_round_entity(mock_game)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    game = MagicMock()
    game.ecs = context
    game.world.agent_memories = {}
    game.events = MagicMock()
    install_combat(game)
    return game


@pytest.fixture()
def system(mock_game: Any) -> UseConsumableItemActionSystem:
    return UseConsumableItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------


class TestFilter:
    def test_true_when_action_and_hand_present(
        self, context: ECSContext, system: UseConsumableItemActionSystem
    ) -> None:
        item = _make_consumable("灼血药剂")
        actor = _make_actor_entity(context, "角色.无名", item)
        assert system.filter(actor) is True

    def test_false_when_hand_missing(
        self, context: ECSContext, system: UseConsumableItemActionSystem
    ) -> None:
        entity = context.create_entity()
        entity._name = "player"
        entity.add(UseConsumableItemAction, "player", _make_consumable("灼血药剂"))
        assert system.filter(entity) is False


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        set_combat_state(mock_game, CombatState.COMPLETE)
        item = _make_consumable("灼血药剂", count=2)
        actor = _make_actor_entity(context, "角色.无名", item)

        await system.react([actor])

        mock_game.broadcast_to_stage.assert_not_called()
        mock_game.resolve_stage_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_materializes_card_into_hand(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=1, damage=5)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        hand = actor.get(HandComponent)
        assert len(hand.cards) == 1
        card = hand.cards[0]
        assert card.name == "灼血药剂"
        assert card.damage == 5
        assert card.cost == 0
        assert card.exhaust is True
        assert card.retain is True  # 未打出时跨回合保留，避免重复生效
        assert card.source == "角色.无名"
        assert card.uuid != item.cards[0].uuid  # 物化为独立副本

    @pytest.mark.asyncio
    async def test_materializes_each_builtin_card_times_count(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """每个内置牌 × count：1 张内置牌 count=3 → 3 张手牌。"""
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=3)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        hand = actor.get(HandComponent)
        assert len(hand.cards) == 3
        assert len({c.uuid for c in hand.cards}) == 3  # 各自独立副本

    @pytest.mark.asyncio
    async def test_materializes_multi_card_times_count(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """2 张内置牌 count=2 → 共 4 张手牌。"""
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("组合卷轴", count=2, card_count=2)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        hand = actor.get(HandComponent)
        assert len(hand.cards) == 4

    @pytest.mark.asyncio
    async def test_consumes_whole_stack(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """一次使用移除整条库存（count=2 全部消耗），物化 2 张。"""
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=2)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 0  # 整条移除
        assert len(actor.get(HandComponent).cards) == 2

    @pytest.mark.asyncio
    async def test_inventory_item_removed_when_last_count(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("最后一瓶药", count=1)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 0

    @pytest.mark.asyncio
    async def test_records_round_log_like_gear(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=1)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        round_entity = current_round_entity(mock_game)
        consumable_entries = [
            entry
            for entry in combat_round_view(mock_game, round_entity).entries
            if entry.kind == RoundEntryKind.CONSUMABLE
        ]
        assert len(consumable_entries) == 1
        assert consumable_entries[0].log
        assert consumable_entries[0].narrative

    @pytest.mark.asyncio
    async def test_broadcasts_notice_to_stage(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game, round_count=3)
        item = _make_consumable("爆裂卷轴", count=2)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [item])
        await system.react([actor])

        actor_memory = mock_game.world.agent_memories[actor.name]
        message = actor_memory.messages[-1]
        assert "角色.无名" in message.content
        assert "爆裂卷轴" in message.content
        assert "3" in message.content

    @pytest.mark.asyncio
    async def test_does_not_materialize_when_item_not_in_inventory(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        """扣库存失败（背包中找不到目标道具）时不物化、不广播。"""
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=1)
        other_item = _make_consumable("其他道具", count=1)
        actor = _make_actor_entity(context, "角色.无名", item)
        player = _make_player_entity(context, "player", [other_item])
        mock_game.resolve_stage_entity.return_value = context.create_entity()

        await system.react([actor])

        inv = player.get(InventoryComponent)
        assert len(inv.items) == 1
        assert inv.items[0].name == "其他道具"
        assert len(actor.get(HandComponent).cards) == 0
        mock_game.broadcast_to_stage.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_when_multiple_entities_triggered(
        self,
        context: ECSContext,
        mock_game: Any,
        system: UseConsumableItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        item = _make_consumable("灼血药剂", count=1)
        actor_a = _make_actor_entity(context, "角色.无名", item)
        actor_b = _make_actor_entity(context, "角色.顾知秋", item)

        with pytest.raises(AssertionError):
            await system.react([actor_a, actor_b])
