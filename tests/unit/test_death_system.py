"""`DeathSystem` 单测：当前行动者在自己回合内死亡时，回合指针必须推进以跳过它。

回归背景：回合指针只在过牌时推进，而过牌会拒绝死亡角色；若当前行动者因反伤自杀 /
神器后仲裁等在自己回合内死亡，无人能触发重算，本回合会永久卡死。
"""

from typing import Dict, List, cast
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.combat.state import combat_round_view
from ai_dbg.game.context import ECSContext
from ai_dbg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
)
from ai_dbg.systems.death_system import DeathSystem
from dungeon_support import current_round_entity, install_combat


def _make_actor(context: ECSContext, name: str, hp: int, max_hp: int = 10) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "dungeon")
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=hp, max_hp=max_hp))
    return entity


def _make_game(
    entities: Dict[str, Entity],
    action_order: List[str],
    current_actor: str,
) -> MagicMock:
    context = cast(ECSContext, next(iter(entities.values()))._context)
    game = MagicMock()
    game.ecs = context
    for entity in entities.values():
        context.register_entity(entity)
    game.world.agent_memories = {}
    game.events = MagicMock()

    install_combat(
        game,
        action_order=action_order,
        current_actor=current_actor,
    )

    return game


@pytest.mark.asyncio
async def test_current_actor_death_advances_pointer() -> None:
    context = ECSContext()
    dying = _make_actor(context, "角色.坏运气", hp=0)
    nxt = _make_actor(context, "角色.无名", hp=5)
    game = _make_game(
        {"角色.坏运气": dying, "角色.无名": nxt},
        ["角色.坏运气", "角色.无名"],
        "角色.坏运气",
    )

    await DeathSystem(game).execute()

    assert dying.has(DeathComponent)
    assert (
        combat_round_view(game, current_round_entity(game)).current_actor == "角色.无名"
    )
    # 死亡通知带结构化标记
    death_message = game.world.agent_memories["角色.坏运气"].messages[-1]
    assert death_message.death_notification == "角色.坏运气"


@pytest.mark.asyncio
async def test_non_current_actor_death_keeps_pointer() -> None:
    context = ECSContext()
    dying = _make_actor(context, "怪物.头狼", hp=0)
    current = _make_actor(context, "角色.坏运气", hp=5)
    game = _make_game(
        {"怪物.头狼": dying, "角色.坏运气": current},
        ["角色.坏运气", "怪物.头狼"],
        "角色.坏运气",
    )

    await DeathSystem(game).execute()

    assert dying.has(DeathComponent)
    assert (
        combat_round_view(game, current_round_entity(game)).current_actor
        == "角色.坏运气"
    )


@pytest.mark.asyncio
async def test_pointer_becomes_none_when_no_alive_actor_left() -> None:
    context = ECSContext()
    a = _make_actor(context, "角色.坏运气", hp=0)
    b = _make_actor(context, "角色.无名", hp=0)
    game = _make_game(
        {"角色.坏运气": a, "角色.无名": b},
        ["角色.坏运气", "角色.无名"],
        "角色.坏运气",
    )

    await DeathSystem(game).execute()

    assert combat_round_view(game, current_round_entity(game)).current_actor is None
