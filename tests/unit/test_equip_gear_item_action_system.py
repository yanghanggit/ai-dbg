"""EquipGearItemActionSystem 单元测试：验证 GearItem 转化为手牌的流程。"""

from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.game.combat.state import combat_round_view
from ai_dbg.models import (
    ActorComponent,
    Card,
    CombatState,
    EquipGearItemAction,
    EquippedGearComponent,
    GearItem,
    HandComponent,
    InventoryComponent,
    PartyMemberComponent,
    PlayerComponent,
    RoundEntryKind,
    StageComponent,
)
from ai_dbg.systems.equip_gear_item_action_system import EquipGearItemActionSystem
from dungeon_support import (
    current_round_entity,
    install_combat,
    set_combat_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gear(name: str) -> GearItem:
    return GearItem(
        name=name,
        description="测试装备",
        cards=[Card(name=name, description="测试装备", cost=1, damage=3)],
    )


def _make_actor_entity(
    context: Context,
    name: str,
    action_item: GearItem,
) -> Entity:
    """创建携带 HandComponent + PartyMemberComponent + EquipGearItemAction 的当前行动者。"""
    if not any(e.name == "测试场景" for e in context.entities):
        stage = context.create_entity()
        stage._name = "测试场景"
        stage.add(StageComponent, "测试场景")
    entity = context.create_entity()
    entity._name = name
    entity.add(HandComponent, name, [])
    entity.add(ActorComponent, name, "测试场景")
    entity.add(PartyMemberComponent, name)
    entity.add(EquipGearItemAction, name, action_item)
    return entity


def _make_player_entity(context: Context, name: str, items: List[GearItem]) -> Entity:
    """创建持有团队背包（InventoryComponent）的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    entity.add(PlayerComponent, name)
    return entity


def _setup_mock_game(mock_game: Any, player: Entity) -> Entity:
    del player
    return current_round_entity(mock_game)


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
    install_combat(game)
    return game


@pytest.fixture()
def system(mock_game: Any) -> EquipGearItemActionSystem:
    return EquipGearItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        set_combat_state(mock_game, CombatState.COMPLETE)
        gear = _make_gear("装备.测试")
        actor = _make_actor_entity(context, "角色.测试", gear)

        await system.react([actor])

        mock_game.get_player_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_converts_gear_to_hand_card(
        self,
        context: Context,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        gear = _make_gear("装备.测试")
        actor = _make_actor_entity(context, "角色.测试", gear)
        player = _make_player_entity(context, "player", [gear])
        latest_round_entity = _setup_mock_game(mock_game, player)
        generated = Card(name="斩击", description="x")
        with patch.object(system, "_materialize_cards", return_value=[generated]):
            await system.react([actor])

        # 移动语义：gear 从团队背包移除
        assert gear not in player.get(InventoryComponent).items
        # 装备登记到当前行动者
        assert actor.has(EquippedGearComponent)
        assert gear in actor.get(EquippedGearComponent).items
        # 生成的卡牌进入当前行动者手牌
        assert generated in actor.get(HandComponent).cards
        # 本回合装备使用结果被记入记录队列
        gear_entries = [
            entry
            for entry in combat_round_view(mock_game, latest_round_entity).entries
            if entry.kind == RoundEntryKind.GEAR
        ]
        assert len(gear_entries) == 1
        assert gear_entries[0].log
        assert gear_entries[0].narrative
        # 广播装备转化通知
        assert mock_game.world.agent_memories
