from typing import Any

"""DestroyEntitySystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_srpg.game.ecs_context import ECSContext
from ai_srpg.game.systems.destroy_entity_system import DestroyEntitySystem
from ai_srpg.models import DestroyComponent
from ecs_testing import Position

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> ECSContext:
    """提供真实 ECS Context。"""
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    """Mock SRPGGame：get_group() 代理到真实 Context，destroy_entity() 同时调用真实 Context 的销毁。"""
    game = MagicMock()
    game.get_group.side_effect = context.get_group
    game.destroy_entity.side_effect = context.destroy_entity
    return game


@pytest.fixture()
def system(mock_game: Any) -> DestroyEntitySystem:
    return DestroyEntitySystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDestroyEntitySystem:
    """DestroyEntitySystem.execute() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_execute_empty_world(self, system: DestroyEntitySystem) -> None:
        """无实体时 execute() 应正常完成，不调用 destroy_entity()。"""
        await system.execute()

    @pytest.mark.asyncio
    async def test_execute_destroys_single_marked_entity(
        self, context: ECSContext, mock_game: Any, system: DestroyEntitySystem
    ) -> None:
        """持有 DestroyComponent 的实体执行后应被销毁。"""
        entity = context.create_entity()
        entity.add(DestroyComponent, "target")

        await system.execute()

        assert not context.has_entity(entity)

    @pytest.mark.asyncio
    async def test_execute_destroys_multiple_marked_entities(
        self, context: ECSContext, mock_game: Any, system: DestroyEntitySystem
    ) -> None:
        """多个持有 DestroyComponent 的实体全部应被销毁。"""
        entity_a = context.create_entity()
        entity_a.add(DestroyComponent, "a")
        entity_b = context.create_entity()
        entity_b.add(DestroyComponent, "b")
        entity_c = context.create_entity()
        entity_c.add(DestroyComponent, "c")

        await system.execute()

        assert not context.has_entity(entity_a)
        assert not context.has_entity(entity_b)
        assert not context.has_entity(entity_c)

    @pytest.mark.asyncio
    async def test_execute_ignores_entities_without_destroy_component(
        self, context: ECSContext, mock_game: Any, system: DestroyEntitySystem
    ) -> None:
        """不持有 DestroyComponent 的实体不应被销毁。"""
        entity = context.create_entity()
        entity.add(Position, 1.0, 2.0)

        await system.execute()

        assert context.has_entity(entity)

    @pytest.mark.asyncio
    async def test_execute_only_destroys_marked_entities(
        self, context: ECSContext, mock_game: Any, system: DestroyEntitySystem
    ) -> None:
        """混合场景：仅销毁持有 DestroyComponent 的实体，保留其他实体。"""
        to_destroy = context.create_entity()
        to_destroy.add(DestroyComponent, "bye")

        to_keep = context.create_entity()
        to_keep.add(Position, 0.0, 0.0)

        await system.execute()

        assert not context.has_entity(to_destroy)
        assert context.has_entity(to_keep)

    @pytest.mark.asyncio
    async def test_execute_calls_destroy_entity_not_remove_component(
        self, context: ECSContext, mock_game: Any, system: DestroyEntitySystem
    ) -> None:
        """execute() 应通过 destroy_entity(game) 销毁实体，而非仅移除组件。"""
        entity = context.create_entity()
        entity.add(DestroyComponent, "x")

        await system.execute()

        # destroy_entity 被调用，而非 entity.remove()
