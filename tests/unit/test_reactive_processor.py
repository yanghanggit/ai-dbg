"""ReactiveProcessor 的行为测试：真实 Context + Collector 集成。"""

from typing import Dict, List, Set

import pytest

from ai_srpg.entitas import (
    Context,
    Entity,
    GroupEvent,
    Matcher,
    ReactiveProcessor,
)
from ecs_testing import Position


class _Reactive(ReactiveProcessor):
    def __init__(self, context: Context, *, removed: bool = False) -> None:
        self._removed = removed
        self.reacted: List[List[Entity]] = []
        self.rejected: Set[Entity] = set()
        super().__init__(context)

    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        event = GroupEvent.REMOVED if self._removed else GroupEvent.ADDED
        return {Matcher(Position): event}

    def filter(self, entity: Entity) -> bool:
        return entity not in self.rejected

    async def react(self, entities: List[Entity]) -> None:
        self.reacted.append(list(entities))


def test_reactive_processor_is_abstract() -> None:
    with pytest.raises(TypeError):
        ReactiveProcessor(Context())  # type: ignore[abstract]


async def test_activate_collects_added_entities() -> None:
    context = Context()
    processor = _Reactive(context)
    processor.activate()

    entity = context.create_entity()
    entity.add(Position, 1, 2)

    await processor.execute()

    assert processor.reacted == [[entity]]


async def test_deactivate_stops_collection() -> None:
    context = Context()
    processor = _Reactive(context)
    processor.activate()
    processor.deactivate()

    entity = context.create_entity()
    entity.add(Position, 1, 2)

    await processor.execute()

    assert processor.reacted == []


async def test_filter_rejects_entities() -> None:
    context = Context()
    processor = _Reactive(context)
    processor.activate()

    accepted = context.create_entity()
    accepted.add(Position, 1, 2)
    rejected = context.create_entity()
    rejected.add(Position, 3, 4)
    processor.rejected.add(rejected)

    await processor.execute()

    assert processor.reacted == [[accepted]]


async def test_clear_drops_pending_entities_without_reacting() -> None:
    context = Context()
    processor = _Reactive(context)
    processor.activate()

    entity = context.create_entity()
    entity.add(Position, 1, 2)
    processor.clear()

    await processor.execute()
    assert processor.reacted == []

    another = context.create_entity()
    another.add(Position, 3, 4)
    await processor.execute()
    assert processor.reacted == [[another]]


async def test_removed_trigger_collects_removals() -> None:
    context = Context()
    entity = context.create_entity()
    entity.add(Position, 1, 2)

    processor = _Reactive(context, removed=True)
    processor.activate()

    entity.remove(Position)
    await processor.execute()

    assert processor.reacted == [[entity]]


async def test_no_changes_does_not_react() -> None:
    context = Context()
    context.create_entity()
    processor = _Reactive(context)
    processor.activate()

    await processor.execute()

    assert processor.reacted == []
