"""PlayCardsArbitrationSystem 的静态结算测试。"""

from typing import Any, List

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.entities import create_entity
from ai_dbg.models import (
    ActorComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    HandComponent,
    PlayCardsAction,
    TargetType,
)
from ai_dbg.systems.play_cards_arbitration_system import PlayCardsArbitrationSystem
from dungeon_support import install_combat

_STAGE_NAME = "场景.测试"


def _make_actor(
    game: Any,
    name: str,
    *,
    hp: int = 20,
    hand: List[Card] | None = None,
) -> Entity:
    entity = create_entity(game, name)
    entity.add(ActorComponent, name, _STAGE_NAME)
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=hp, max_hp=hp))
    entity.add(HandComponent, name, hand or [])
    return entity


def _card(
    *,
    damage: int,
    hit_count: int = 1,
    target_type: TargetType = TargetType.SINGLE,
    description: str = "测试卡牌",
) -> Card:
    return Card(
        name="斩击",
        description=description,
        damage=damage,
        hit_count=hit_count,
        target_type=target_type,
    )


def _block_card(block: int) -> Card:
    return Card(
        name="盾",
        description="盾",
        block=block,
        target_type=TargetType.SELF,
    )


def _prepare_combat(game: Any) -> None:
    install_combat(game, room_name=_STAGE_NAME, action_order=[], current_actor=None)


@pytest.mark.asyncio
async def test_single_target_subtracts_block_per_hit(sample_game: Any) -> None:
    _prepare_combat(sample_game)
    actor = _make_actor(sample_game, "角色.无名")
    target = _make_actor(sample_game, "怪物.甲", hp=10, hand=[_block_card(4)])
    actor.add(PlayCardsAction, actor.name, _card(damage=5, hit_count=2), [target.name])

    await PlayCardsArbitrationSystem(sample_game).react([actor])

    assert target.get(CharacterStatsComponent).stats.hp == 8


@pytest.mark.asyncio
async def test_spread_uses_hit_assignment_counts(sample_game: Any) -> None:
    _prepare_combat(sample_game)
    actor = _make_actor(sample_game, "角色.无名")
    a = _make_actor(sample_game, "怪物.甲", hp=10)
    b = _make_actor(sample_game, "怪物.乙", hp=10, hand=[_block_card(1)])
    actor.add(
        PlayCardsAction,
        actor.name,
        _card(damage=2, hit_count=4, target_type=TargetType.SPREAD),
        [a.name, a.name, b.name],
    )

    await PlayCardsArbitrationSystem(sample_game).react([actor])

    assert a.get(CharacterStatsComponent).stats.hp == 6
    assert b.get(CharacterStatsComponent).stats.hp == 9


@pytest.mark.asyncio
async def test_hp_is_clamped_at_zero(sample_game: Any) -> None:
    _prepare_combat(sample_game)
    actor = _make_actor(sample_game, "角色.无名")
    target = _make_actor(sample_game, "怪物.甲", hp=3)
    actor.add(PlayCardsAction, actor.name, _card(damage=10), [target.name])

    await PlayCardsArbitrationSystem(sample_game).react([actor])

    assert target.get(CharacterStatsComponent).stats.hp == 0


@pytest.mark.asyncio
async def test_zero_damage_does_not_emit_stats_update(sample_game: Any) -> None:
    _prepare_combat(sample_game)
    actor = _make_actor(sample_game, "角色.无名")
    target = _make_actor(sample_game, "怪物.甲", hp=10, hand=[_block_card(5)])
    actor.add(PlayCardsAction, actor.name, _card(damage=2), [target.name])

    await PlayCardsArbitrationSystem(sample_game).react([actor])

    assert target.get(CharacterStatsComponent).stats.hp == 10
    messages = sample_game.world.agent_memories[target.name].messages
    assert not any(getattr(m, "stats_update", None) is not None for m in messages)


@pytest.mark.asyncio
async def test_broadcast_uses_card_description_as_static_narrative(
    sample_game: Any,
) -> None:
    _prepare_combat(sample_game)
    actor = _make_actor(sample_game, "角色.无名")
    target = _make_actor(sample_game, "怪物.甲", hp=10)
    actor.add(
        PlayCardsAction,
        actor.name,
        _card(damage=2, description="刀光划过。"),
        [target.name],
    )

    await PlayCardsArbitrationSystem(sample_game).react([actor])

    event = sample_game.events.events[-1]
    assert event.narrative == "刀光划过。"
    assert (
        event.combat_log == "[角色.无名|斩击→怪物.甲: 2−0=每击2 ×1击=2] HP:怪物.甲 10→8"
    )
