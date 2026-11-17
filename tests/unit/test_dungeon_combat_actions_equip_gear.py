"""activate_equip_gear 只负责发起装备使用请求。"""

from unittest.mock import MagicMock

from ai_dbg.entitas import Entity
from ai_dbg.game.context import ECSContext
from ai_dbg.models import EquipGearItemAction, InventoryComponent, PlayerComponent
from ai_dbg.services.dungeon_combat_actions import activate_equip_gear


def _make_game() -> tuple[MagicMock, ECSContext, Entity]:
    context = ECSContext()
    player = context.create_entity("player")
    player.add(PlayerComponent, player.name)
    player.add(InventoryComponent, player.name, [])
    game = MagicMock()
    game.ecs = context
    return game, context, player


def test_activate_equip_gear_only_attaches_request_to_player() -> None:
    game, _, player = _make_game()

    ok, message = activate_equip_gear(game, "装备.测试")

    assert ok is True
    assert "已发起装备使用" in message
    assert player.has(EquipGearItemAction)
    assert player.get(EquipGearItemAction).item_name == "装备.测试"


def test_activate_equip_gear_does_not_validate_inventory() -> None:
    """背包里有没有装备由 system 判断，发起层不拦截。"""
    game, _, player = _make_game()

    ok, _ = activate_equip_gear(game, "不存在的装备")

    assert ok is True
    assert player.has(EquipGearItemAction)
