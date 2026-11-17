from typing import Any

"""ActionCleanupSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas import CleanupProcessor, ExecuteProcessor
from ai_dbg.game.context import ECSContext
from ai_dbg.models import DrawCardsAction, FillDrawPileAction, PassTurnAction
from ai_dbg.systems.action_cleanup_system import ActionCleanupSystem
from ecs_testing import Position

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> ECSContext:
    """提供真实 ECS Context，使 Group 自动更新行为生效。"""
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    """Mock DBGGame，将 get_group() 代理到真实 Context，避免初始化重量级 DBGGame。"""
    game = MagicMock()
    game.ecs = context
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
    """ActionCleanupSystem 的 execute/cleanup 双入口测试。"""

    def test_implements_execute_and_cleanup_phases(
        self, system: ActionCleanupSystem
    ) -> None:
        """正常路径走 execute，异常兜底走 cleanup，两个接口都要实现。"""
        assert isinstance(system, ExecuteProcessor)
        assert isinstance(system, CleanupProcessor)

    @pytest.mark.asyncio
    async def test_execute_clears_actions(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """正常 execute 路径也应清理动作组件。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)

        await system.execute()

        assert not entity.has(DrawCardsAction)

    def test_cleanup_empty_world(self, system: ActionCleanupSystem) -> None:
        """无实体时 cleanup() 应正常完成，不抛出任何异常。"""
        system.cleanup()

    def test_cleanup_removes_single_action_component(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """单实体持有一个动作组件，执行后该组件应被移除。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)

        system.cleanup()

        assert not entity.has(DrawCardsAction)

    def test_cleanup_removes_multiple_actions_from_same_entity(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """单实体同时持有多个动作组件，执行后应全部被移除。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)
        entity.add(PassTurnAction, *_WHISPER_ARGS)
        entity.add(FillDrawPileAction, *_ANNOUNCE_ARGS)

        system.cleanup()

        assert not entity.has(DrawCardsAction)
        assert not entity.has(PassTurnAction)
        assert not entity.has(FillDrawPileAction)

    def test_cleanup_removes_actions_from_multiple_entities(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """多个实体各持不同动作组件，执行后应全部被清除。"""
        entity_a = context.create_entity()
        entity_a.add(DrawCardsAction, *_SPEAK_ARGS)

        entity_b = context.create_entity()
        entity_b.add(PassTurnAction, *_WHISPER_ARGS)

        entity_c = context.create_entity()
        entity_c.add(FillDrawPileAction, *_ANNOUNCE_ARGS)

        system.cleanup()

        assert not entity_a.has(DrawCardsAction)
        assert not entity_b.has(PassTurnAction)
        assert not entity_c.has(FillDrawPileAction)

    def test_cleanup_preserves_non_action_components(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """实体同时持有动作组件与非动作组件，执行后非动作组件应保留。"""
        entity = context.create_entity()
        entity.add(DrawCardsAction, *_SPEAK_ARGS)
        entity.add(Position, 1.0, 2.0)

        system.cleanup()

        assert not entity.has(DrawCardsAction)
        assert entity.has(Position)
