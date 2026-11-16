from unittest.mock import MagicMock, patch

from ai_dbg.entitas import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.models import (
    ActorComponent,
    DungeonComponent,
    GearItem,
    HandComponent,
    InventoryComponent,
    PartyMemberComponent,
    PlayerComponent,
    StageComponent,
)
from ai_dbg.services.dungeon_combat_actions import activate_equip_gear
from dungeon_support import install_combat


def _make_game() -> tuple[MagicMock, Context, Entity]:
    context = Context()
    stage = context.create_entity()
    stage._name = "场景.测试"
    stage.add(StageComponent, stage.name)
    stage.add(DungeonComponent, stage.name)
    player = context.create_entity()
    player._name = "player"
    player.add(ActorComponent, player.name, stage.name)
    player.add(PlayerComponent, player.name)
    player.add(InventoryComponent, player.name, [])
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.world.agent_memories = {}
    game.events = MagicMock()
    install_combat(game, room_name=stage.name)
    return game, context, player


def _make_actor(context: Context, name: str, *, party: bool, hand: bool) -> Entity:
    actor = context.create_entity()
    actor._name = name
    actor.add(ActorComponent, name, "场景.测试")
    if party:
        actor.add(PartyMemberComponent, name)
    if hand:
        actor.add(HandComponent, name, [])
    return actor


def test_activate_equip_gear_rejects_non_party_actor() -> None:
    game, context, _ = _make_game()
    actor = _make_actor(context, "怪物.测试", party=False, hand=True)
    game.entity_index[actor.name] = actor

    with patch(
        "ai_dbg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="怪物.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is False
    assert "不是我方角色" in msg


def test_activate_equip_gear_rejects_missing_hand() -> None:
    game, context, _ = _make_game()
    actor = _make_actor(context, "角色.测试", party=True, hand=False)
    game.entity_index[actor.name] = actor

    with patch(
        "ai_dbg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="角色.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is False
    assert "缺少手牌组件" in msg


def test_activate_equip_gear_activates_action() -> None:
    game, context, player = _make_game()
    gear = GearItem(name="装备.测试", description="测试装备")
    player.get(InventoryComponent).items.append(gear)
    actor = _make_actor(context, "角色.测试", party=True, hand=True)
    game.entity_index[actor.name] = actor

    with patch(
        "ai_dbg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="角色.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is True
    assert "成功激活装备使用" in msg
    assert actor.has(
        __import__(
            "ai_dbg.models", fromlist=["EquipGearItemAction"]
        ).EquipGearItemAction
    )
