"""游戏快照：ECS 与 agent 记忆的整块导出、恢复与回滚。"""

import uuid

import pytest

from ai_srpg.entitas import Component
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.lifecycle import rollback_game, snapshot_game
from ai_srpg.models import (
    MEMORY_SNAPSHOT_FORMAT_VERSION,
    SNAPSHOT_FORMAT_VERSION,
    ContextSnapshot,
    IdentityComponent,
    SystemMessage,
)


class _UnregisteredComponent(Component):
    """故意不注册，用于验证快照不会静默丢数据。"""

    value: int = 0


def _new_game(name: str = "Game1") -> SRPGGame:
    return create_srpg_game(name=name)


def _add_entity(game: SRPGGame, name: str) -> None:
    entity = game.create_entity(name)
    entity.add(
        IdentityComponent,
        name,
        game.entity_naming.next_creation_order(),
        str(uuid.uuid4()),
    )


def _remember(game: SRPGGame, name: str, content: str) -> None:
    game.agent_memory_store.get_or_create(name).messages.append(
        SystemMessage(content=content)
    )


def test_ecs_snapshot_roundtrip_into_fresh_game() -> None:
    game = _new_game()
    _add_entity(game, "角色.甲")
    _add_entity(game, "场景.营地")

    snapshot = game.ecs_snapshot()

    assert snapshot.format_version == SNAPSHOT_FORMAT_VERSION
    assert snapshot.game == "Game1"
    assert snapshot.entity_naming_counter == 2
    assert list(snapshot.entities) == ["角色.甲", "场景.营地"]

    restored = _new_game()
    restored.restore_ecs_snapshot(snapshot)

    assert restored.entity_count == 2
    assert restored.entity_naming.counter == 2
    assert restored.get_entity_by_name("角色.甲") is not None
    assert restored.serialize() == snapshot.entities


def test_ecs_snapshot_survives_json_roundtrip() -> None:
    game = _new_game()
    _add_entity(game, "角色.甲")

    snapshot = game.ecs_snapshot()
    revived = ContextSnapshot.model_validate_json(snapshot.model_dump_json())

    assert revived == snapshot


def test_ecs_snapshot_rejects_unregistered_component() -> None:
    game = _new_game()
    _add_entity(game, "角色.甲")
    game.get_entity_by_name("角色.甲").add(_UnregisteredComponent, 1)  # type: ignore[union-attr]

    with pytest.raises(ValueError, match="_UnregisteredComponent"):
        game.ecs_snapshot()


def test_rollback_ecs_discards_entities_created_after_snapshot() -> None:
    game = _new_game()
    _add_entity(game, "角色.甲")
    snapshot = game.ecs_snapshot()

    _add_entity(game, "角色.乙")
    assert game.entity_count == 2

    game.rollback_ecs(snapshot)

    assert game.entity_count == 1
    assert game.get_entity_by_name("角色.乙") is None
    assert game.get_entity_by_name("角色.甲") is not None
    assert game.entity_naming.counter == 1


def test_restore_rejects_foreign_game_or_version() -> None:
    snapshot = _new_game().ecs_snapshot()

    other = _new_game(name="Game2")
    with pytest.raises(ValueError, match="Game1"):
        other.restore_ecs_snapshot(snapshot)

    bad_version = snapshot.model_copy(update={"format_version": 999})
    target = _new_game()
    with pytest.raises(ValueError, match="版本"):
        target.restore_ecs_snapshot(bad_version)


def test_memory_snapshot_roundtrip_is_isolated_from_later_writes() -> None:
    game = _new_game()
    _remember(game, "角色.甲", "第一条")

    snapshot = game.memory_snapshot()
    assert snapshot.format_version == MEMORY_SNAPSHOT_FORMAT_VERSION

    _remember(game, "角色.甲", "第二条")
    _remember(game, "角色.乙", "不该留在快照里")

    game.restore_memory_snapshot(snapshot)

    memory = game.agent_memory_store.get("角色.甲")
    assert memory is not None
    assert [message.content for message in memory.messages] == ["第一条"]
    assert game.agent_memory_store.get("角色.乙") is None


async def test_rollback_game_restores_ecs_and_memory_together() -> None:
    game = _new_game()
    _add_entity(game, "角色.甲")
    _remember(game, "角色.甲", "旧记忆")

    snapshot = snapshot_game(game)
    pipeline_before = game.pipeline

    _add_entity(game, "角色.乙")
    _remember(game, "角色.甲", "新记忆")

    await rollback_game(game, snapshot)

    assert game.entity_count == 1
    assert game.get_entity_by_name("角色.乙") is None
    memory = game.agent_memory_store.get("角色.甲")
    assert memory is not None
    assert [message.content for message in memory.messages] == ["旧记忆"]
    assert game.pipeline is not pipeline_before
