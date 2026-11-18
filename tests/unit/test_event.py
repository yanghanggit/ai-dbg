"""Event（观察者）工具测试。"""

from typing import Any, List

from ai_srpg.entitas import Event


def test_listeners_are_called_in_registration_order() -> None:
    event = Event()
    calls: List[str] = []

    event += lambda *args, **kwargs: calls.append("first")
    event += lambda *args, **kwargs: calls.append("second")

    event()

    assert calls == ["first", "second"]


def test_listener_receives_positional_and_keyword_arguments() -> None:
    event = Event()
    received: List[Any] = []

    def listener(entity: object, component: object, *, flag: bool) -> None:
        received.append((entity, component, flag))

    event += listener
    event("entity", "component", flag=True)

    assert received == [("entity", "component", True)]


def test_duplicate_listener_is_ignored() -> None:
    event = Event()
    calls: List[int] = []

    def listener() -> None:
        calls.append(1)

    event += listener
    event += listener
    event()

    assert calls == [1]
    assert len(event) == 1


def test_remove_listener_and_unknown_removal_is_noop() -> None:
    event = Event()
    calls: List[int] = []

    def listener() -> None:
        calls.append(1)

    event += listener
    event -= listener
    event -= listener
    event()

    assert calls == []


def test_listener_exception_does_not_block_others() -> None:
    event = Event()
    calls: List[str] = []

    def broken() -> None:
        raise RuntimeError("listener boom")

    event += broken
    event += lambda: calls.append("after")

    event()

    assert calls == ["after"]


def test_count_bool_repr_and_iteration_snapshot() -> None:
    event = Event()
    assert len(event) == 0
    assert not event
    assert event.listener_count == 0
    assert not event.has_listeners
    assert repr(event) == "Event(listeners=0)"

    first = lambda: None
    second = lambda: None
    event += first
    snapshot = list(event)
    event += second

    assert len(event) == 2
    assert event
    assert event.listener_count == 2
    assert event.has_listeners
    assert repr(event) == "Event(listeners=2)"
    assert snapshot == [first]


def test_clear_and_alternative_methods() -> None:
    event = Event()
    calls: List[int] = []

    def listener() -> None:
        calls.append(1)

    event.add_listener(listener)
    event.trigger()
    event.remove_listener(listener)
    event.trigger()
    event.clear()

    assert calls == [1]
    assert len(event) == 0
