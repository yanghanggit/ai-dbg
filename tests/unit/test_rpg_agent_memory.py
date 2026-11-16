from ai_dbg.game.game_entities import (
    create_entity,
)

"""
Tests for DBGGame memory message management methods:
  - add_human_message
  - add_ai_message
  - reset_agent_memory
  - filter_messages
  - remove_messages
  - remove_message_range
  - replace_span
"""

from typing import Any, List

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.game_memory import (
    KEEP_ON_COMPACT_ATTR,
    REPLACED_MESSAGES_ATTR,
    add_ai_message,
    add_human_message,
    add_system_message,
    compact_agent_memory,
    filter_messages,
    find_marked_span,
    get_agent_memory,
    remove_message_range,
    remove_messages,
    replace_span,
    reset_agent_memory,
)
from ai_dbg.models import AIMessage, ChatMessage, HumanMessage, SystemMessage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game(sample_game: Any) -> Any:
    """Alias for sample_game — a fully-constructed DBGGame with no blueprint entities."""
    return sample_game


@pytest.fixture
def actor(game: Any) -> Entity:
    """Create a named entity inside the game."""
    return create_entity(game, "TestActor")


@pytest.fixture
def second_actor(game: Any) -> Entity:
    """Create a second named entity for multi-entity tests."""
    return create_entity(game, "OtherActor")


# ---------------------------------------------------------------------------
# add_human_message
# ---------------------------------------------------------------------------


class TestAddHumanMessage:
    def test_basic(self, game: Any, actor: Entity) -> None:
        """Message is appended; content and type are correct."""
        add_human_message(game, actor, HumanMessage(content="hello"))

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, HumanMessage)
        assert msg.content == "hello"

    def test_kwargs_stored_as_extra_fields(self, game: Any, actor: Entity) -> None:
        """Extra kwargs are attached to the message via Pydantic extra='allow'."""
        add_human_message(
            game,
            actor,
            HumanMessage(
                content="planning prompt",
                agent_event="planning",
                broadcast_stage="full prompt text",
            ),
        )

        msgs = get_agent_memory(game, actor).messages
        msg = msgs[0]
        assert isinstance(msg, HumanMessage)
        assert getattr(msg, "agent_event") == "planning"
        assert getattr(msg, "broadcast_stage") == "full prompt text"

    def test_multiple_messages_preserve_order(self, game: Any, actor: Entity) -> None:
        """Multiple adds are appended in insertion order."""
        add_human_message(game, actor, HumanMessage(content="first"))
        add_human_message(game, actor, HumanMessage(content="second"))
        add_human_message(game, actor, HumanMessage(content="third"))

        msgs = get_agent_memory(game, actor).messages
        assert [m.content for m in msgs] == ["first", "second", "third"]

    def test_different_entities_have_independent_memories(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """Messages for different entities do not bleed into each other."""
        add_human_message(game, actor, HumanMessage(content="for actor"))
        add_human_message(game, second_actor, HumanMessage(content="for other"))

        assert len(get_agent_memory(game, actor).messages) == 1
        assert len(get_agent_memory(game, second_actor).messages) == 1
        assert get_agent_memory(game, actor).messages[0].content == "for actor"
        assert get_agent_memory(game, second_actor).messages[0].content == "for other"


# ---------------------------------------------------------------------------
# add_ai_message
# ---------------------------------------------------------------------------


class TestAddAiMessage:
    def test_basic(self, game: Any, actor: Entity) -> None:
        """AIMessage is appended; content and type are correct."""
        ai_msg = AIMessage(content="AI reply")
        add_ai_message(game, actor, ai_msg)

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 1
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].content == "AI reply"

    def test_empty_content_allowed(self, game: Any, actor: Entity) -> None:
        """纯 tool_calls 的 AI 消息正文为空是合法的（不抛断言），照常写入记忆。"""
        add_ai_message(game, actor, AIMessage(content=""))

        assert get_agent_memory(game, actor).messages[-1].content == ""

    def test_unregistered_tag_raises(self, game: Any, actor: Entity) -> None:
        """未登记的记忆标记直接失败，避免拼错后静默失去审计信息。"""
        with pytest.raises(AssertionError):
            add_human_message(game, actor, HumanMessage(content="x", no_such_tag=1))

    # def test_non_ai_message_raises(self, game: Any, actor: Entity) -> None:
    #     """Passing a non-AIMessage triggers AssertionError (isinstance guard)."""
    #     with pytest.raises(AssertionError):
    #         add_ai_message(game, actor, HumanMessage(content="oops"))

    def test_kwargs_set_as_attributes(self, game: Any, actor: Entity) -> None:
        """Extra fields set on AIMessage at construction are stored."""
        ai_msg = AIMessage(content="with tag", agent_event="test_tag")
        add_ai_message(game, actor, ai_msg)

        msgs = get_agent_memory(game, actor).messages
        assert getattr(msgs[0], "agent_event") == "test_tag"

    def test_same_message_object_is_stored(self, game: Any, actor: Entity) -> None:
        """The exact message object passed is the one stored (identity check)."""
        ai_msg = AIMessage(content="identity check")
        add_ai_message(game, actor, ai_msg)

        assert get_agent_memory(game, actor).messages[0] is ai_msg


# ---------------------------------------------------------------------------
# reset_agent_memory
# ---------------------------------------------------------------------------


class TestResetAgentMemory:
    def _seed(self, game: Any, actor: Entity) -> None:
        """Seed a system prompt plus some accumulated facts (dangerous-op target)."""
        add_system_message(game, actor, SystemMessage(content="you are a persona"))
        add_human_message(game, actor, HumanMessage(content="fact 1"))
        add_ai_message(game, actor, AIMessage(content="reply 1"))
        add_human_message(game, actor, HumanMessage(content="fact 2"))

    def test_keeps_only_system_message(self, game: Any, actor: Entity) -> None:
        """Only the leading SystemMessage survives the reset."""
        self._seed(game, actor)
        reset_agent_memory(game, actor)

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 1
        assert isinstance(msgs[0], SystemMessage)
        assert msgs[0].content == "you are a persona"

    def test_resets_context_usage_ratio(self, game: Any, actor: Entity) -> None:
        """context_usage_ratio is zeroed because the context is gone."""
        self._seed(game, actor)
        get_agent_memory(game, actor).context_usage_ratio = 0.83

        reset_agent_memory(game, actor)
        assert get_agent_memory(game, actor).context_usage_ratio == 0.0

    def test_empty_memory_raises(self, game: Any, actor: Entity) -> None:
        """Resetting an empty memory is refused (nothing to anchor the persona)."""
        with pytest.raises(AssertionError):
            reset_agent_memory(game, actor)

    def test_first_message_not_system_raises(self, game: Any, actor: Entity) -> None:
        """If the leading message is not a SystemMessage, reset is refused."""
        add_human_message(game, actor, HumanMessage(content="not a persona"))
        with pytest.raises(AssertionError):
            reset_agent_memory(game, actor)

    def test_idempotent_after_reset(self, game: Any, actor: Entity) -> None:
        """Calling reset again on an already-reset memory is a no-op, not an error."""
        self._seed(game, actor)
        reset_agent_memory(game, actor)
        reset_agent_memory(game, actor)

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 1
        assert isinstance(msgs[0], SystemMessage)

    def test_empty_sequence_equivalent_to_purge(self, game: Any, actor: Entity) -> None:
        """Explicit [] behaves like the default: only the system prompt remains."""
        self._seed(game, actor)
        reset_agent_memory(game, actor, [])

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 1
        assert isinstance(msgs[0], SystemMessage)

    def test_new_messages_replace_tail(self, game: Any, actor: Entity) -> None:
        """Passing new_messages replaces messages[1:] entirely."""
        self._seed(game, actor)
        replacement: list[ChatMessage] = [
            HumanMessage(content="replacement 1"),
            AIMessage(content="replacement 2"),
        ]
        reset_agent_memory(game, actor, replacement)

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 3
        assert isinstance(msgs[0], SystemMessage)
        assert [m.content for m in msgs[1:]] == ["replacement 1", "replacement 2"]

    def test_compact_agent_memory_delegates(self, game: Any, actor: Entity) -> None:
        """compact_agent_memory 以「摘要」重制记忆（无保留项时等于 reset 一条）。"""
        self._seed(game, actor)
        summary = HumanMessage(content="compressed summary")
        compact_agent_memory(game, actor, summary)

        msgs = get_agent_memory(game, actor).messages
        assert len(msgs) == 2
        assert isinstance(msgs[0], SystemMessage)
        assert msgs[1] is summary
        assert get_agent_memory(game, actor).context_usage_ratio == 0.0

    def test_compact_agent_memory_keeps_failure_notices(
        self, game: Any, actor: Entity
    ) -> None:
        """带 KEEP_ON_COMPACT_ATTR 的失败说明必须原样保留在摘要之后。"""
        self._seed(game, actor)
        notice = HumanMessage(content="本次结算未完成", **{KEEP_ON_COMPACT_ATTR: True})
        add_human_message(game, actor, notice)
        add_human_message(game, actor, HumanMessage(content="普通消息"))

        summary = HumanMessage(content="compressed summary")
        compact_agent_memory(game, actor, summary)

        msgs = get_agent_memory(game, actor).messages
        assert isinstance(msgs[0], SystemMessage)
        assert msgs[1] is summary
        assert msgs[2] is notice
        assert len(msgs) == 3


# ---------------------------------------------------------------------------
# filter_messages
# ---------------------------------------------------------------------------


class TestFilterMessages:
    def test_predicate_false_returns_empty(self, game: Any, actor: Entity) -> None:
        """Predicate returning False for every message returns []."""
        add_human_message(
            game, actor, HumanMessage(content="msg", agent_event="planning")
        )
        result = filter_messages(
            game, actor, predicate=lambda msg, index, messages: False
        )
        assert result == []

    def test_matches_custom_kwarg(self, game: Any, actor: Entity) -> None:
        """Finds a message that has the specified extra field."""
        add_human_message(
            game, actor, HumanMessage(content="planning msg", agent_event="TestActor")
        )
        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "TestActor"
            ),
        )
        assert len(result) == 1
        assert result[0].content == "planning msg"

    def test_no_match_returns_empty(self, game: Any, actor: Entity) -> None:
        """Returns [] when no message matches the predicate."""
        add_human_message(
            game, actor, HumanMessage(content="msg", agent_event="planning")
        )
        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "NonExistent"
            ),
        )
        assert result == []

    def test_attribute_not_present_returns_empty(
        self, game: Any, actor: Entity
    ) -> None:
        """Returns [] when no message has the requested attribute at all."""
        add_human_message(game, actor, HumanMessage(content="plain msg"))
        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "no_such_attr", None) is not None
            ),
        )
        assert result == []

    def test_multiple_matches(self, game: Any, actor: Entity) -> None:
        """All matching messages are returned."""
        add_human_message(
            game, actor, HumanMessage(content="round 1", agent_event="TestActor")
        )
        add_human_message(
            game, actor, HumanMessage(content="round 2", agent_event="TestActor")
        )
        add_human_message(
            game, actor, HumanMessage(content="other", agent_event="OtherActor")
        )

        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "TestActor"
            ),
        )
        assert len(result) == 2
        contents = {m.content for m in result}
        assert contents == {"round 1", "round 2"}

    def test_reverse_order_true_returns_newest_first(
        self, game: Any, actor: Entity
    ) -> None:
        """Default reverse_order=True: most-recently-added message is first."""
        add_human_message(
            game, actor, HumanMessage(content="older", agent_event="TestActor")
        )
        add_human_message(
            game, actor, HumanMessage(content="newer", agent_event="TestActor")
        )

        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "TestActor"
            ),
            reverse_order=True,
        )
        assert result[0].content == "newer"

    def test_reverse_order_false_returns_oldest_first(
        self, game: Any, actor: Entity
    ) -> None:
        """reverse_order=False: oldest message is first."""
        add_human_message(
            game, actor, HumanMessage(content="older", agent_event="TestActor")
        )
        add_human_message(
            game, actor, HumanMessage(content="newer", agent_event="TestActor")
        )

        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "TestActor"
            ),
            reverse_order=False,
        )
        assert result[0].content == "older"

    def test_multi_field_predicate(self, game: Any, actor: Entity) -> None:
        """Predicate can combine multiple conditions — partial match is not enough."""
        add_human_message(
            game,
            actor,
            HumanMessage(
                content="full match",
                agent_event="TestActor",
                broadcast_stage="prompt",
            ),
        )
        add_human_message(
            game,
            actor,
            HumanMessage(
                content="partial only",
                agent_event="TestActor",
            ),
        )

        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (
                getattr(msg, "agent_event", None) == "TestActor"
                and getattr(msg, "broadcast_stage", None) == "prompt"
            ),
        )
        assert len(result) == 1
        assert result[0].content == "full match"

    def test_index_and_messages_available(self, game: Any, actor: Entity) -> None:
        """Predicate receives the original index and the full message list."""
        add_human_message(game, actor, HumanMessage(content="first"))
        add_human_message(game, actor, HumanMessage(content="second"))
        add_human_message(game, actor, HumanMessage(content="third"))

        # 只保留原始索引为 1 且消息列表长度为 3 的消息
        result = filter_messages(
            game,
            actor,
            predicate=lambda msg, index, messages: (index == 1 and len(messages) == 3),
        )
        assert len(result) == 1
        assert result[0].content == "second"


# ---------------------------------------------------------------------------
# remove_messages
# ---------------------------------------------------------------------------


class TestRemoveMessages:
    def test_empty_input_returns_zero(self, game: Any, actor: Entity) -> None:
        """Passing an empty list returns 0 and leaves the message list unchanged."""
        add_human_message(game, actor, HumanMessage(content="keep me"))
        count = remove_messages(game, actor, [])
        assert count == 0
        assert len(get_agent_memory(game, actor).messages) == 1

    def test_removes_existing_message(self, game: Any, actor: Entity) -> None:
        """A message that is in the message list is removed; return value is 1."""
        add_human_message(game, actor, HumanMessage(content="to remove"))
        msg = get_agent_memory(game, actor).messages[0]

        count = remove_messages(game, actor, [msg])
        assert count == 1
        assert msg not in get_agent_memory(game, actor).messages

    def test_removes_multiple_messages(self, game: Any, actor: Entity) -> None:
        """Multiple messages are removed and the correct count is returned."""
        add_human_message(game, actor, HumanMessage(content="msg1"))
        add_human_message(game, actor, HumanMessage(content="msg2"))
        add_human_message(game, actor, HumanMessage(content="keep"))

        msgs = get_agent_memory(game, actor).messages
        to_remove = [msgs[0], msgs[1]]

        count = remove_messages(game, actor, to_remove)
        assert count == 2
        remaining = get_agent_memory(game, actor).messages
        assert len(remaining) == 1
        assert remaining[0].content == "keep"

    def test_not_in_memory_returns_zero(self, game: Any, actor: Entity) -> None:
        """Passing a message that was never in the memory returns 0."""
        add_human_message(game, actor, HumanMessage(content="keep"))
        foreign = HumanMessage(content="not in memory")

        count = remove_messages(game, actor, [foreign])
        assert count == 0
        assert len(get_agent_memory(game, actor).messages) == 1


# ---------------------------------------------------------------------------
# remove_message_range
# ---------------------------------------------------------------------------


class TestRemoveMessageRange:
    def _fill(self, game: Any, actor: Entity, n: int = 5) -> List[Any]:
        """Helper: add n HumanMessages and return all message objects."""
        for i in range(n):
            add_human_message(game, actor, HumanMessage(content=f"msg{i}"))
        return list(get_agent_memory(game, actor).messages)

    def test_same_message_raises(self, game: Any, actor: Entity) -> None:
        """begin == end triggers AssertionError."""
        msgs = self._fill(game, actor, 3)
        with pytest.raises(AssertionError):
            remove_message_range(game, actor, msgs[1], msgs[1])

    def test_basic_range_length(self, game: Any, actor: Entity) -> None:
        """Returned list length equals end_index - begin_index + 1."""
        msgs = self._fill(game, actor, 5)
        deleted = remove_message_range(game, actor, msgs[1], msgs[3])
        assert len(deleted) == 3  # indices 1, 2, 3

    def test_preserves_messages_outside_range(self, game: Any, actor: Entity) -> None:
        """Messages before begin and after end are kept."""
        msgs = self._fill(game, actor, 5)
        remove_message_range(game, actor, msgs[1], msgs[3])

        remaining = get_agent_memory(game, actor).messages
        assert len(remaining) == 2
        assert remaining[0] is msgs[0]
        assert remaining[1] is msgs[4]

    def test_returns_deleted_message_objects(self, game: Any, actor: Entity) -> None:
        """Return value contains the exact message objects that were deleted."""
        msgs = self._fill(game, actor, 5)
        deleted = remove_message_range(game, actor, msgs[1], msgs[3])

        assert deleted[0] is msgs[1]
        assert deleted[1] is msgs[2]
        assert deleted[2] is msgs[3]

    def test_memory_size_after_removal(self, game: Any, actor: Entity) -> None:
        """Memory shrinks by exactly the number of deleted messages."""
        msgs = self._fill(game, actor, 5)
        deleted = remove_message_range(game, actor, msgs[0], msgs[2])
        assert len(deleted) == 3
        assert len(get_agent_memory(game, actor).messages) == 2


# ---------------------------------------------------------------------------
# find_marked_span
# ---------------------------------------------------------------------------


class TestFindMarkedSpan:
    def test_returns_span_for_marked_region(self, game: Any, actor: Entity) -> None:
        add_human_message(game, actor, HumanMessage(content="start", loop_id="L1"))
        add_ai_message(game, actor, AIMessage(content="mid"))
        add_human_message(game, actor, HumanMessage(content="end", loop_id_end="L1"))

        span = find_marked_span(game, actor, "loop_id", "L1", end_attr="loop_id_end")

        assert span is not None
        assert (span.start_index, span.end_index) == (0, 2)
        assert span.messages == get_agent_memory(game, actor).messages

    def test_missing_value_returns_none(self, game: Any, actor: Entity) -> None:
        add_human_message(game, actor, HumanMessage(content="x"))
        assert (
            find_marked_span(game, actor, "loop_id", "L1", end_attr="loop_id_end")
            is None
        )


# ---------------------------------------------------------------------------
# replace_span
# ---------------------------------------------------------------------------


class TestReplaceSpan:
    def _fill(self, game: Any, actor: Entity, n: int = 5) -> List[Any]:
        for i in range(n):
            add_human_message(game, actor, HumanMessage(content=f"msg{i}"))
        return list(get_agent_memory(game, actor).messages)

    def test_replaces_half_open_interval(self, game: Any, actor: Entity) -> None:
        """[start, end) 被 new_messages 替换，区间外的消息原样保留。"""
        msgs = self._fill(game, actor, 5)
        summary = HumanMessage(content="总结", loop_id="L1")

        replaced = replace_span(game, actor, 1, 3, [summary])

        assert replaced == [msgs[1], msgs[2]]
        remaining = get_agent_memory(game, actor).messages
        assert [m.content for m in remaining] == ["msg0", "总结", "msg3", "msg4"]
        assert remaining[1] is summary

    def test_empty_replacement_deletes_interval(self, game: Any, actor: Entity) -> None:
        """new_messages 为空即回滚删除 [start, end)。"""
        msgs = self._fill(game, actor, 5)

        replaced = replace_span(game, actor, 1, 4, [])

        assert replaced == [msgs[1], msgs[2], msgs[3]]
        remaining = get_agent_memory(game, actor).messages
        assert [m.content for m in remaining] == ["msg0", "msg4"]

    def test_empty_interval_is_noop(self, game: Any, actor: Entity) -> None:
        """空区间（start == end）不删除任何东西。"""
        self._fill(game, actor, 3)
        replaced = replace_span(game, actor, 1, 1, [])
        assert replaced == []
        assert len(get_agent_memory(game, actor).messages) == 3

    def test_dump_attr_records_removed_messages(self, game: Any, actor: Entity) -> None:
        """传 dump_attr 时，被删整段结构化 dump 到最后一条新消息上。"""
        add_human_message(game, actor, HumanMessage(content="m0"))
        get_agent_memory(game, actor).messages.append(
            AIMessage(
                content="",
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {"name": "get_entity_stats", "arguments": "{}"},
                        }
                    ]
                },
            )
        )
        add_human_message(game, actor, HumanMessage(content="m2"))
        summary = HumanMessage(content="总结")

        replace_span(game, actor, 1, 3, [summary], dump_attr=REPLACED_MESSAGES_ATTR)

        dumped = getattr(summary, REPLACED_MESSAGES_ATTR)
        assert [d["type"] for d in dumped] == ["ai", "human"]
        assert (
            dumped[0]["additional_kwargs"]["tool_calls"][0]["function"]["name"]
            == "get_entity_stats"
        )
        assert dumped[1]["content"] == "m2"

    def test_no_dump_without_attr(self, game: Any, actor: Entity) -> None:
        """不传 dump_attr 时不外挂任何属性。"""
        self._fill(game, actor, 3)
        summary = HumanMessage(content="总结")
        replace_span(game, actor, 1, 3, [summary])
        assert not hasattr(summary, REPLACED_MESSAGES_ATTR)

    def test_dump_skipped_when_replacement_empty(
        self, game: Any, actor: Entity
    ) -> None:
        """回滚删除（new_messages 为空）时无挂载目标，不报错、不留 dump。"""
        self._fill(game, actor, 3)
        replace_span(game, actor, 1, 3, [], dump_attr=REPLACED_MESSAGES_ATTR)
        assert [m.content for m in get_agent_memory(game, actor).messages] == ["msg0"]

    def test_dump_strips_nested_same_attr(self, game: Any, actor: Entity) -> None:
        """再次压缩一条自带 dump 的消息时，嵌套的同名字段被剔除，避免层层膨胀。"""
        self._fill(game, actor, 3)  # msg0, msg1, msg2
        inner = HumanMessage(content="inner")
        replace_span(game, actor, 0, 2, [inner], dump_attr=REPLACED_MESSAGES_ATTR)
        assert hasattr(inner, REPLACED_MESSAGES_ATTR)

        # 此时记忆为 [inner(带 dump), msg2]；再把 inner 压缩进 outer
        outer = HumanMessage(content="outer")
        replace_span(game, actor, 0, 1, [outer], dump_attr=REPLACED_MESSAGES_ATTR)

        dumped = getattr(outer, REPLACED_MESSAGES_ATTR)
        assert len(dumped) == 1
        assert dumped[0]["content"] == "inner"
        assert REPLACED_MESSAGES_ATTR not in dumped[0]
