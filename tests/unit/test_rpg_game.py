"""
Unit tests for game lifecycle/entity/memory/broadcast functions

覆盖范围（不重复 test_rpg_agent_memory.py 中已有的用例）：
  - get_agent_memory
  - destroy_entity（含 agent_memories 清理）
  - add_system_message
  - flush_entities / restore_from_snapshot
  - notify_entities
  - broadcast_to_stage
  - exit / initialize（冒烟测试）
"""

import uuid
from typing import Any

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.entities import (
    create_entity,
    destroy_entity,
    get_entity_by_name,
)
from ai_dbg.game.lifecycle import (
    exit_game,
    initialize_game,
)
from ai_dbg.game.memory import (
    add_human_message,
    add_system_message,
    get_agent_memory,
)
from ai_dbg.game.messaging import (
    broadcast_to_stage,
    notify_entities,
)
from ai_dbg.game.persistence import (
    flush_entities,
    restore_from_snapshot,
)
from ai_dbg.models import (
    ActorComponent,
    HumanMessage,
    IdentityComponent,
    NoneEvent,
    StageComponent,
    SystemMessage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(game: Any, stage_name: str) -> Entity:
    """创建带 StageComponent 的场景实体。"""
    entity: Entity = create_entity(game, stage_name)
    entity.add(StageComponent, stage_name)
    return entity


def _make_actor(game: Any, actor_name: str, current_stage_name: str) -> Entity:
    """创建带 ActorComponent 的角色实体。"""
    entity: Entity = create_entity(game, actor_name)
    entity.add(ActorComponent, actor_name, current_stage_name)
    return entity


def _make_entity_with_identity(game: Any, name: str, order: int) -> Entity:
    """创建带 IdentityComponent 的实体（flush_entities 排序所需）。"""
    entity: Entity = create_entity(game, name)
    entity.add(IdentityComponent, name, order, str(uuid.uuid4()))
    return entity


def _agent_event(message: str = "hello") -> NoneEvent:
    return NoneEvent(message=message)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game(sample_game: Any) -> Any:
    return sample_game


@pytest.fixture
def actor(game: Any) -> Entity:
    return create_entity(game, "Actor_A")


@pytest.fixture
def second_actor(game: Any) -> Entity:
    return create_entity(game, "Actor_B")


# ---------------------------------------------------------------------------
# get_agent_memory
# ---------------------------------------------------------------------------


class TestGetAgentMemory:
    def test_creates_memory_on_first_access(self, game: Any, actor: Entity) -> None:
        """首次访问不存在的实体时，自动创建 AgentMemory。"""
        assert actor.name not in game.world.agent_memories
        memory = get_agent_memory(game, actor)
        assert memory is not None
        assert actor.name in game.world.agent_memories

    def test_returns_same_object_on_repeated_call(
        self, game: Any, actor: Entity
    ) -> None:
        """同一实体重复调用返回同一对象（identity）。"""
        memory1 = get_agent_memory(game, actor)
        memory2 = get_agent_memory(game, actor)
        assert memory1 is memory2

    def test_memory_name_matches_entity(self, game: Any, actor: Entity) -> None:
        """返回的 AgentMemory.name 与实体名称一致。"""
        memory = get_agent_memory(game, actor)
        assert memory.name == actor.name

    def test_different_entities_have_independent_memories(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """不同实体各自拥有独立的 AgentMemory 对象。"""
        memory_a = get_agent_memory(game, actor)
        memory_b = get_agent_memory(game, second_actor)
        assert memory_a is not memory_b
        assert memory_a.name != memory_b.name


# ---------------------------------------------------------------------------
# destroy_entity
# ---------------------------------------------------------------------------


class TestDestroyEntity:
    def test_destroy_removes_from_name_index(self, game: Any, actor: Entity) -> None:
        """销毁后 get_entity_by_name 返回 None。"""
        destroy_entity(game, actor)
        assert get_entity_by_name(game, actor.name) is None

    def test_destroy_cleans_up_agent_memories(self, game: Any, actor: Entity) -> None:
        """销毁时，world.agent_memories 中对应 key 被移除。"""
        get_agent_memory(game, actor)  # ensure memory exists
        assert actor.name in game.world.agent_memories
        destroy_entity(game, actor)
        assert actor.name not in game.world.agent_memories

    def test_destroy_entity_without_memory_ok(self, game: Any, actor: Entity) -> None:
        """没有 agent_memories 的实体销毁时不抛异常。"""
        assert actor.name not in game.world.agent_memories
        destroy_entity(game, actor)  # should not raise
        assert get_entity_by_name(game, actor.name) is None


# ---------------------------------------------------------------------------
# add_system_message
# ---------------------------------------------------------------------------


class TestAddSystemMessage:
    def test_basic_system_message(self, game: Any, actor: Entity) -> None:
        """成功添加 SystemMessage，内容与类型正确。"""
        add_system_message(game, actor, SystemMessage(content="system prompt"))
        messages = get_agent_memory(game, actor).messages
        assert len(messages) == 1
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == "system prompt"

    def test_system_message_not_first_raises(self, game: Any, actor: Entity) -> None:
        """memory 非空时调用 add_system_message 触发 AssertionError。"""
        add_human_message(game, actor, HumanMessage(content="already something here"))
        with pytest.raises(AssertionError):
            add_system_message(game, actor, SystemMessage(content="system prompt"))


# ---------------------------------------------------------------------------
# flush_entities / restore_from_snapshot
# ---------------------------------------------------------------------------


class TestFlushAndRestoreSnapshot:
    def test_flush_populates_entities_serialization(self, game: Any) -> None:
        """flush_entities 后 world.entities 非空。"""
        _make_entity_with_identity(game, "EntityX", 1)
        flush_entities(game)
        assert len(game.world.entities) > 0

    def test_restore_from_empty_raises(self, game: Any) -> None:
        """entities 为空时 restore_from_snapshot 触发 AssertionError。"""
        assert len(game.world.entities) == 0
        with pytest.raises(AssertionError):
            restore_from_snapshot(game)

    def test_restore_with_existing_entities_raises(self, game: Any) -> None:
        """游戏中已有实体时 restore_from_snapshot 触发 AssertionError。"""
        entity = _make_entity_with_identity(game, "EntityY", 1)
        flush_entities(game)
        # Now entities exist AND serialization is non-empty → should raise
        with pytest.raises(AssertionError):
            restore_from_snapshot(game)

    def test_flush_then_restore_round_trip(self, game: Any) -> None:
        """flush → 销毁所有实体 → restore：实体可通过名称找回。"""
        e1 = _make_entity_with_identity(game, "EntityR1", 1)
        e2 = _make_entity_with_identity(game, "EntityR2", 2)

        # Flush: persist current state
        flush_entities(game)
        assert len(game.world.entities) == 2

        # Destroy all entities
        destroy_entity(game, e1)
        destroy_entity(game, e2)
        assert len(game.ecs.entities) == 0

        # Restore: recreate entities from snapshot
        restore_from_snapshot(game)
        assert get_entity_by_name(game, "EntityR1") is not None
        assert get_entity_by_name(game, "EntityR2") is not None


# ---------------------------------------------------------------------------
# notify_entities
# ---------------------------------------------------------------------------


class TestNotifyEntities:
    def test_notify_adds_message_to_all_entities(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """notify_entities 把事件消息添加给集合中的每个实体。"""
        event = _agent_event("broadcast")
        notify_entities(game, {actor, second_actor}, event)

        assert get_agent_memory(game, actor).messages[-1].content == "broadcast"
        assert get_agent_memory(game, second_actor).messages[-1].content == "broadcast"

    def test_notify_publishes_domain_event(self, game: Any, actor: Entity) -> None:
        """notify_entities 向领域事件出口发布事件。"""
        before = len(game.events.events)
        notify_entities(game, {actor}, _agent_event("event1"))
        assert len(game.events.events) == before + 1

    def test_notify_stamps_event_type_without_broadcast_stage(
        self, game: Any, actor: Entity
    ) -> None:
        """私发消息只盖 agent_event 标记，不盖 broadcast_stage（不是全场景广播）。"""
        notify_entities(game, {actor}, _agent_event("private note"))

        message: Any = get_agent_memory(game, actor).messages[-1]
        assert message.agent_event == "none"
        assert not hasattr(message, "broadcast_stage")

    def test_notify_empty_set_still_publishes(self, game: Any) -> None:
        """实体集合为空时，领域事件仍会发布。"""
        before = len(game.events.events)
        notify_entities(game, set(), _agent_event("empty broadcast"))
        assert len(game.events.events) == before + 1

    def test_domain_events_accumulate_in_order(self, game: Any, actor: Entity) -> None:
        """每次 notify_entities 都会追加一条领域事件。"""
        before = list(game.events.events)
        notify_entities(game, {actor}, _agent_event("seq test"))
        assert game.events.events == before + [_agent_event("seq test")]


# ---------------------------------------------------------------------------
# broadcast_to_stage
# ---------------------------------------------------------------------------


class TestBroadcastToStage:
    def test_broadcast_reaches_stage_and_actors(self, game: Any) -> None:
        """广播时，场景实体及其所有 actor 都收到消息。"""
        stage = _make_stage(game, "Stage_1")
        a1 = _make_actor(game, "NPC_1", "Stage_1")
        a2 = _make_actor(game, "NPC_2", "Stage_1")

        broadcast_to_stage(game, stage, _agent_event("stage msg"))

        assert get_agent_memory(game, stage).messages[-1].content == "stage msg"
        assert get_agent_memory(game, a1).messages[-1].content == "stage msg"
        assert get_agent_memory(game, a2).messages[-1].content == "stage msg"

    def test_broadcast_excludes_specified_entities(self, game: Any) -> None:
        """被排除的实体不收到广播消息。"""
        stage = _make_stage(game, "Stage_2")
        a1 = _make_actor(game, "NPC_3", "Stage_2")
        a2 = _make_actor(game, "NPC_4", "Stage_2")

        broadcast_to_stage(
            game, stage, _agent_event("exclusive"), exclude_entities={a2}
        )

        # a1 and stage get it, a2 is excluded
        assert get_agent_memory(game, a1).messages[-1].content == "exclusive"
        assert get_agent_memory(game, stage).messages[-1].content == "exclusive"
        assert len(get_agent_memory(game, a2).messages) == 0

    def test_broadcast_with_no_actors_reaches_stage_only(self, game: Any) -> None:
        """场景中无 actor 时，只有场景实体收到广播。"""
        stage = _make_stage(game, "Stage_3")
        other_stage = _make_stage(game, "Stage_other")  # must exist for actor resolve
        unrelated_actor = _make_actor(game, "NPC_5", "Stage_other")

        broadcast_to_stage(game, stage, _agent_event("empty stage msg"))

        assert get_agent_memory(game, stage).messages[-1].content == "empty stage msg"
        assert len(get_agent_memory(game, unrelated_actor).messages) == 0

    def test_broadcast_stamps_event_type_and_stage(self, game: Any) -> None:
        """广播消息盖两个标记：agent_event（事件类型）与 broadcast_stage（广播范围）。"""
        stage = _make_stage(game, "Stage_4")
        actor = _make_actor(game, "NPC_6", "Stage_4")
        event = NoneEvent(message="喊了一声")

        broadcast_to_stage(game, actor, event)

        for entity in (stage, actor):
            message: Any = get_agent_memory(game, entity).messages[-1]
            assert message.agent_event == "none"
            assert message.broadcast_stage == "Stage_4"

    def test_broadcast_asserts_on_entity_without_stage(self, game: Any) -> None:
        """传入没有 StageComponent 也没有 ActorComponent 的实体触发 AssertionError。"""
        plain_entity = create_entity(game, "PlainEntity")
        with pytest.raises(AssertionError):
            broadcast_to_stage(game, plain_entity, _agent_event("fail"))


# ---------------------------------------------------------------------------
# exit / initialize（冒烟测试）
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_exit_with_pipeline(self, game: Any) -> None:
        """exit() 关闭唯一 pipeline 时不抛异常。"""
        exit_game(game)  # should not raise

    async def test_initialize_with_pipeline(self, game: Any) -> None:
        """initialize() 激活唯一 pipeline 时不抛异常。"""
        await initialize_game(game)
