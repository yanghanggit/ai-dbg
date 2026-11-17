"""EquipGearItemActionSystem 单元测试：验证装备请求的解析、守卫与转化流程。"""

from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.combat.state import combat_round_view
from ai_dbg.game.context import ECSContext
from ai_dbg.models import (
    ActorComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
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
    context: ECSContext,
    name: str,
    *,
    party: bool = True,
    hand: bool = True,
) -> Entity:
    """创建当前行动者；请求本身挂在 player 上，不在 actor 上。"""
    if not any(e.name == "测试场景" for e in context.entities):
        stage = context.create_entity("测试场景")
        stage.add(StageComponent, "测试场景")
    entity = context.create_entity(name)
    entity.add(ActorComponent, name, "测试场景")
    entity.add(
        CharacterStatsComponent,
        name,
        CharacterStats(hp=10, max_hp=10, attack=1, defense=0, speed=0),
    )
    if party:
        entity.add(PartyMemberComponent, name)
    if hand:
        entity.add(HandComponent, name, [])
    return entity


def _make_player_entity(
    context: ECSContext, name: str, items: List[GearItem]
) -> Entity:
    """创建持有团队背包（InventoryComponent）的 player 实体。"""
    entity = context.create_entity(name)
    entity.add(InventoryComponent, name, list(items))
    entity.add(PlayerComponent, name)
    return entity


def _attach_request(player: Entity, item_name: str) -> None:
    player.add(EquipGearItemAction, player.name, item_name)


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
    install_combat(
        game,
        action_order=["角色.测试"],
        current_actor="角色.测试",
    )
    return game


@pytest.fixture()
def system(mock_game: Any) -> EquipGearItemActionSystem:
    return EquipGearItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_rejects_when_combat_not_ongoing(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        set_combat_state(mock_game, CombatState.COMPLETE)
        actor = _make_actor_entity(context, "角色.测试")
        player = _make_player_entity(context, "player", [_make_gear("装备.测试")])
        _attach_request(player, "装备.测试")

        with pytest.raises(ValueError, match="战斗未在进行中"):
            await system.react([player])

        assert actor.has(HandComponent)

    @pytest.mark.asyncio
    async def test_rejects_non_party_current_actor(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        _make_actor_entity(context, "角色.测试", party=False, hand=True)
        player = _make_player_entity(context, "player", [_make_gear("装备.测试")])
        _attach_request(player, "装备.测试")

        with pytest.raises(ValueError, match="不是我方角色"):
            await system.react([player])

    @pytest.mark.asyncio
    async def test_rejects_current_actor_without_hand(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        _make_actor_entity(context, "角色.测试", party=True, hand=False)
        player = _make_player_entity(context, "player", [_make_gear("装备.测试")])
        _attach_request(player, "装备.测试")

        with pytest.raises(ValueError, match="缺少手牌组件"):
            await system.react([player])

    @pytest.mark.asyncio
    async def test_rejects_missing_gear_in_inventory(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        _make_actor_entity(context, "角色.测试")
        player = _make_player_entity(context, "player", [])
        _attach_request(player, "装备.测试")

        with pytest.raises(ValueError, match="找不到装备"):
            await system.react([player])

    @pytest.mark.asyncio
    async def test_processes_multiple_requests_in_one_batch(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        """react 接收列表时用显式循环逐个处理，不依赖 entities[0]。"""
        actor = _make_actor_entity(context, "角色.测试")
        gear_a = _make_gear("装备.甲")
        gear_b = _make_gear("装备.乙")
        player = _make_player_entity(context, "player", [gear_a, gear_b])
        request_a = context.create_entity("请求.甲")
        request_b = context.create_entity("请求.乙")
        request_a.add(EquipGearItemAction, request_a.name, gear_a.name)
        request_b.add(EquipGearItemAction, request_b.name, gear_b.name)

        await system.react([request_a, request_b])

        assert player.get(InventoryComponent).items == []
        equipped_names = [item.name for item in actor.get(EquippedGearComponent).items]
        assert equipped_names == ["装备.甲", "装备.乙"]

    @pytest.mark.asyncio
    async def test_converts_gear_to_current_actor_hand(
        self,
        context: ECSContext,
        mock_game: Any,
        system: EquipGearItemActionSystem,
    ) -> None:
        gear = _make_gear("装备.测试")
        actor = _make_actor_entity(context, "角色.测试")
        player = _make_player_entity(context, "player", [gear])
        _attach_request(player, "装备.测试")
        latest_round_entity = current_round_entity(mock_game)
        generated = Card(name="斩击", description="x")
        with patch.object(system, "_materialize_cards", return_value=[generated]):
            await system.react([player])

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
