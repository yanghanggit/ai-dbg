"""CombatPassSnapshotSystem 单测：动作阶段快照的建立、刷新与兜底清理。"""

import json
from typing import Any

import pytest

from ai_srpg.game.dungeon import current_combat_entity
from ai_srpg.game.entities import create_entity
from ai_srpg.game.entities.serialization import serialize_context
from ai_srpg.models import (
    COMPONENT_TYPES,
    ActorComponent,
    CombatPassSnapshotComponent,
    CombatRoundComponent,
    CombatState,
    CurrentCombatTurnComponent,
)
from ai_srpg.systems.combat_pass_context import CombatPassContextMixin
from ai_srpg.systems.combat_pass_snapshot_system import CombatPassSnapshotSystem
from ai_srpg.systems.pass_turn_action_system import PassTurnActionSystem
from dungeon_support import (
    advance_current_turn,
    current_round_entity,
    current_turn_entity,
    install_combat,
    set_combat_state,
)


class _Queries(CombatPassContextMixin):
    """测试用查询入口：直接复用系统层的 ECS Matcher/Group 查询。"""

    def __init__(self, game: Any) -> None:
        self._game = game


def _drop_snapshot(sample_game: Any) -> None:
    entity = _Queries(sample_game)._pass_snapshot_entity_or_none()
    if entity is not None:
        entity.remove(CombatPassSnapshotComponent)


@pytest.mark.asyncio
async def test_creates_snapshot_at_action_stage(sample_game: Any) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲", "角色.乙"],
        current_actor="角色.甲",
    )
    _drop_snapshot(sample_game)

    await CombatPassSnapshotSystem(sample_game).execute()

    queries = _Queries(sample_game)
    snapshot = queries._pass_snapshot()
    turn_entity = queries._pass_turn()
    assert snapshot.actor_name == "角色.甲"
    assert snapshot.turn_name == turn_entity.name
    assert snapshot.round_name == current_round_entity(sample_game).name
    assert snapshot.combat_name == current_combat_entity(sample_game).name
    assert queries._pass_round().name == snapshot.round_name


@pytest.mark.asyncio
async def test_cleanup_removes_snapshot(sample_game: Any) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    system = CombatPassSnapshotSystem(sample_game)
    queries = _Queries(sample_game)
    assert queries._pass_snapshot_or_none() is not None

    system.cleanup()

    assert queries._pass_snapshot_or_none() is None


@pytest.mark.asyncio
async def test_no_snapshot_without_current_turn(sample_game: Any) -> None:
    install_combat(sample_game, action_order=["角色.甲"])

    await CombatPassSnapshotSystem(sample_game).execute()

    assert _Queries(sample_game)._pass_snapshot_or_none() is None


@pytest.mark.asyncio
async def test_execute_clears_stale_snapshot_when_combat_ended(
    sample_game: Any,
) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    set_combat_state(sample_game, CombatState.COMPLETE)
    queries = _Queries(sample_game)
    assert queries._pass_snapshot_or_none() is not None

    await CombatPassSnapshotSystem(sample_game).execute()

    assert queries._pass_snapshot_or_none() is None


@pytest.mark.asyncio
async def test_execute_refreshes_snapshot_after_turn_advance(
    sample_game: Any,
) -> None:
    for name in ("角色.甲", "角色.乙"):
        actor = create_entity(sample_game, name)
        actor.add(ActorComponent, name, "场景.测试")
    install_combat(
        sample_game,
        action_order=["角色.甲", "角色.乙"],
        current_actor="角色.甲",
    )
    system = CombatPassSnapshotSystem(sample_game)
    queries = _Queries(sample_game)
    await system.execute()
    assert queries._pass_snapshot().actor_name == "角色.甲"

    current_turn = current_turn_entity(sample_game)
    PassTurnActionSystem(sample_game)._mark_turn_completed(current_turn)
    advance_current_turn(sample_game, current_round_entity(sample_game))

    await system.execute()

    assert queries._pass_snapshot().actor_name == "角色.乙"
    assert queries._pass_turn().name != current_turn.name


@pytest.mark.asyncio
async def test_snapshot_is_transient_and_not_serialized(sample_game: Any) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    await CombatPassSnapshotSystem(sample_game).execute()

    assert "CombatPassSnapshotComponent" not in COMPONENT_TYPES
    dumped = json.dumps(serialize_context(sample_game), ensure_ascii=False)
    assert "CombatPassSnapshotComponent" not in dumped


@pytest.mark.asyncio
async def test_require_rejects_finished_snapshot_turn(sample_game: Any) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    current_turn = current_turn_entity(sample_game)
    PassTurnActionSystem(sample_game)._mark_turn_completed(current_turn)

    with pytest.raises(ValueError, match="已结束"):
        _Queries(sample_game)._pass_turn()


@pytest.mark.asyncio
async def test_require_rejects_snapshot_mismatch(sample_game: Any) -> None:
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )
    queries = _Queries(sample_game)
    snapshot = queries._pass_snapshot()
    queries._pass_snapshot_entity().replace(
        CombatPassSnapshotComponent,
        snapshot.combat_name,
        snapshot.round_name,
        snapshot.turn_name,
        "角色.乙",
    )

    with pytest.raises(ValueError, match="不一致"):
        queries._pass_turn()


def test_snapshot_matches_current_turn_after_install(sample_game: Any) -> None:
    """测试辅助 install_combat 也应模拟 pipeline 建立快照。"""
    install_combat(
        sample_game,
        action_order=["角色.甲"],
        current_actor="角色.甲",
    )

    queries = _Queries(sample_game)
    snapshot = queries._pass_snapshot()
    current_turn = next(
        entity
        for entity in sample_game.ecs.entities
        if entity.has(CurrentCombatTurnComponent)
    )
    round_comp = current_round_entity(sample_game).get(CombatRoundComponent)
    assert snapshot.turn_name == current_turn.name
    assert snapshot.round_name == round_comp.name
