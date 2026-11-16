from typing import Any

"""ActionCleanupSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.models import DrawCardsAction, FillDrawPileAction, PassTurnAction
from ai_dbg.systems.action_cleanup_system import ActionCleanupSystem
from ecs_testing import Position

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，使 Group 自动更新行为生效。"""
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> Any:
    """Mock DBGGame，将 get_group() 代理到真实 Context，避免初始化重量级 DBGGame。"""
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: Any) -> ActionCleanupSystem:
    return ActionCleanupSystem(mock_game)


# ---------------------------------------------------------------------------
# Helpers — positional args matching field declaration order in each Component
# ---------------------------------------------------------------------------

# DrawCardsAction(name)
_SPEAK_ARGS = ("alice",)
# PassTurnAction(name)
_WHISPER_ARGS = ("alice",)
# FillDrawPileAction(name)
_ANNOUNCE_ARGS = ("alice",)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestActionCleanupSystem:
    """ActionCleanupSystem.execute() 和 _verify_actions_cleanup() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_execute_empty_world(self, system: ActionCleanupSystem) -> None:
        """无实体时 execute() 应正常完成，不抛出任何异常。"""
        await system.execute()

    @pytest.mark.asyncio
    async def test_execute_removes_single_action_component(
        self, context: Context, system: ActionCleanupSystem
    ) -> None:
        """单实体持有一个动作组件，执行后该组件应被移除。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)

        await system.execute()

        assert not entity.has(DrawCardsAction)

    @pytest.mark.asyncio
    async def test_execute_removes_multiple_actions_from_same_entity(
        self, context: Context, system: ActionCleanupSystem
    ) -> None:
        """单实体同时持有多个动作组件，执行后应全部被移除。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)
        entity.add(PassTurnAction, *_WHISPER_ARGS)
        entity.add(FillDrawPileAction, *_ANNOUNCE_ARGS)

        await system.execute()

        assert not entity.has(DrawCardsAction)
        assert not entity.has(PassTurnAction)
        assert not entity.has(FillDrawPileAction)

    @pytest.mark.asyncio
    async def test_execute_removes_actions_from_multiple_entities(
        self, context: Context, system: ActionCleanupSystem
    ) -> None:
        """多个实体各持不同动作组件，执行后应全部被清除。"""
        entity_a = context.create_entity()
        entity_a.add(DrawCardsAction, *_SPEAK_ARGS)

        entity_b = context.create_entity()
        entity_b.add(PassTurnAction, *_WHISPER_ARGS)

        entity_c = context.create_entity()
        entity_c.add(FillDrawPileAction, *_ANNOUNCE_ARGS)

        await system.execute()

        assert not entity_a.has(DrawCardsAction)
        assert not entity_b.has(PassTurnAction)
        assert not entity_c.has(FillDrawPileAction)

    @pytest.mark.asyncio
    async def test_execute_preserves_non_action_components(
        self, context: Context, system: ActionCleanupSystem
    ) -> None:
        """实体同时持有动作组件与非动作组件，执行后非动作组件应保留。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)
        entity.add(Position, 1.0, 2.0)

        await system.execute()

        assert not entity.has(DrawCardsAction)
        assert entity.has(Position)
