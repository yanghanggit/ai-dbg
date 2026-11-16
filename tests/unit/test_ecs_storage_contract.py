"""ECS ↔ 存储契约测试。

护栏一（Step 1）：entitas 核心的句柄 / pools 语义不变。
护栏二（Stage C）：name-keyed 的 ``serialize_context`` / ``restore_context``
与 ``game.persistence`` 之间的接口契约。
"""

import json
import uuid
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from ai_dbg.entitas import Component, Context, Entity
from ai_dbg.game.entities import (
    create_entity,
    destroy_entity,
    get_entity_by_name,
    restore_context,
    serialize_context,
)
from ai_dbg.models import (
    COMPONENT_TYPES,
    IdentityComponent,
    create_component_type,
)


@pytest.fixture(autouse=True)
def _clean_dynamic_component_types() -> Iterator[None]:
    before = set(COMPONENT_TYPES.keys())
    yield
    for key in list(COMPONENT_TYPES.keys()):
        if key not in before:
            del COMPONENT_TYPES[key]


class _GameImpl:
    """最小 DBGGame 替身：只提供函数所需的 ecs 与 entity_index。"""

    def __init__(self) -> None:
        self.ecs = Context()
        self.entity_index: dict[str, Entity] = {}
        self.world = SimpleNamespace(agent_memories={})


def _new_game() -> Any:
    return _GameImpl()


def _new_id() -> str:
    return str(uuid.uuid4())


class TestContextDataSerialization:
    def test_serialize_context_orders_by_slot_index(self) -> None:
        source = _new_game()
        first = create_entity(source, "first")
        first.add(IdentityComponent, "first", 9, _new_id())
        second = create_entity(source, "second")
        second.add(IdentityComponent, "second", 2, _new_id())

        data = serialize_context(source)

        # 按 slot index（即创建顺序）导出，与 creation_order 字段无关
        assert list(data) == ["first", "second"]

    def test_destroyed_entity_is_not_serialized(self) -> None:
        manager = _new_game()

        dead = create_entity(manager, "dead")
        dead.add(IdentityComponent, "dead", 1, _new_id())
        destroy_entity(manager, dead)

        live = create_entity(manager, "live")
        live.add(IdentityComponent, "live", 2, _new_id())

        data = serialize_context(manager)

        assert list(data) == ["live"]

    def test_serialization_reads_components_via_public_api(self) -> None:
        manager = _new_game()
        entity = create_entity(manager, "probe")
        entity.add(IdentityComponent, "probe", 1, _new_id())

        items = entity.iter_component_items()
        assert [comp_type for comp_type, _ in items] == list(entity.component_types)
        assert entity.get_all_components() == tuple(comp for _, comp in items)


class TestNameIndexContract:
    def test_name_lookup_and_cleanup_on_destroy(self) -> None:
        manager = _new_game()
        entity = create_entity(manager, "keeper")
        entity.add(IdentityComponent, "keeper", 1, _new_id())

        assert get_entity_by_name(manager, "keeper") == entity

        destroy_entity(manager, entity)
        assert get_entity_by_name(manager, "keeper") is None

    def test_recreated_name_points_to_new_handle(self) -> None:
        manager = _new_game()
        first = create_entity(manager, "node")
        first.add(IdentityComponent, "node", 1, _new_id())
        destroy_entity(manager, first)

        second = create_entity(manager, "node")
        second.add(IdentityComponent, "node", 2, _new_id())

        assert get_entity_by_name(manager, "node") == second
        assert get_entity_by_name(manager, "node") != first


class TestIndexHandleContract:
    def test_context_entities_property_is_a_set_of_handles(self) -> None:
        manager = _new_game()
        entity = create_entity(manager, "solo")
        entity.add(IdentityComponent, "solo", 1, _new_id())

        assert isinstance(manager.ecs.entities, set)
        assert entity in manager.ecs.entities

    def test_group_entities_support_copy_for_safe_iteration(self) -> None:
        from ai_dbg.entitas import Matcher

        manager = _new_game()
        entity = create_entity(manager, "iter")
        entity.add(IdentityComponent, "iter", 1, _new_id())

        group = manager.ecs.get_group(Matcher(IdentityComponent))
        snapshot = group.entities.copy()
        # 修改世界不应影响快照
        destroy_entity(manager, entity)
        assert entity in snapshot
        assert entity not in group.entities

    def test_entity_handle_hashable_and_usable_in_sets(self) -> None:
        manager = _new_game()
        entity = create_entity(manager, "hash")
        entity.add(IdentityComponent, "hash", 1, _new_id())

        assert {entity} == {entity}
        assert isinstance(entity, Entity)


class TestContextSnapshotContract:
    """Stage B 护栏：name-keyed 的 serialize_context / restore_context。"""

    def test_context_snapshot_round_trip(self) -> None:
        tag_cls = create_component_type("SnapshotTag", value=(int, ...))

        source = _new_game()
        hero = create_entity(source, "hero")
        hero.add(IdentityComponent, "hero", 1, _new_id())

        goblin = create_entity(source, "goblin")
        goblin.add(IdentityComponent, "goblin", 2, _new_id())
        goblin.set(tag_cls, tag_cls.model_validate({"value": 7}))

        data = serialize_context(source)
        assert list(data) == ["hero", "goblin"]
        assert data["goblin"][tag_cls.__name__] == {"value": 7}

        # 走一遍 JSON（模拟落盘再读回）
        reloaded = json.loads(json.dumps(data))

        target = _new_game()
        restored = restore_context(target, reloaded)

        assert set(restored) == {"hero", "goblin"}
        assert get_entity_by_name(target, "hero") is restored["hero"]
        assert restored["hero"].get(IdentityComponent).creation_order == 1
        assert restored["goblin"].get(tag_cls).model_dump() == {"value": 7}

    def test_serialize_context_skips_unregistered_components(self) -> None:
        class Unregistered(Component):
            value: int

        manager = _new_game()
        entity = create_entity(manager, "probe")
        entity.add(IdentityComponent, "probe", 1, _new_id())
        entity.set(Unregistered, Unregistered(value=1))

        data = serialize_context(manager)

        assert "Unregistered" not in data["probe"]
        assert "IdentityComponent" in data["probe"]

    def test_restore_context_requires_empty_context(self) -> None:
        manager = _new_game()
        existing = create_entity(manager, "existing")
        existing.add(IdentityComponent, "existing", 1, _new_id())

        with pytest.raises(AssertionError, match="empty context"):
            restore_context(manager, {})
