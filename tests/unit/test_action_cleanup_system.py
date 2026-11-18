"""ActionCleanupSystem 单元测试。

动作组件按业务随时增删，因此这里用测试内定义的假动作组件 + 显式注册表传入，
不依赖任何具体玩法组件。
"""

from typing import Any, Dict, Type
from unittest.mock import MagicMock

import pytest

from ai_srpg.entitas import CleanupProcessor, ExecuteProcessor
from ai_srpg.entitas.components import Component
from ai_srpg.game.context import ECSContext
from ai_srpg.systems.action_cleanup_system import ActionCleanupSystem
from ecs_testing import Position

# ---------------------------------------------------------------------------
# 假动作组件与注册表
# ---------------------------------------------------------------------------


class SpeakAction(Component):
    """测试用动作组件：只携带发起者名字。"""

    name: str


class WhisperAction(Component):
    """测试用动作组件：只携带发起者名字。"""

    name: str


class AnnounceAction(Component):
    """测试用动作组件：只携带发起者名字。"""

    name: str


_TEST_ACTIONS: Dict[str, Type[Component]] = {
    "SpeakAction": SpeakAction,
    "WhisperAction": WhisperAction,
    "AnnounceAction": AnnounceAction,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> ECSContext:
    """提供真实 ECS Context，使 Group 自动更新行为生效。"""
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    """Mock SRPGGame，将 get_group() 代理到真实 Context，避免初始化重量级 SRPGGame。"""
    game = MagicMock()
    game.ecs = context
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: Any) -> ActionCleanupSystem:
    return ActionCleanupSystem(mock_game, _TEST_ACTIONS)


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
        entity.add(SpeakAction, "alice")

        await system.execute()

        assert not entity.has(SpeakAction)

    def test_cleanup_empty_world(self, system: ActionCleanupSystem) -> None:
        """无实体时 cleanup() 应正常完成，不抛出任何异常。"""
        system.cleanup()

    def test_cleanup_removes_single_action_component(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """单实体持有一个动作组件，执行后该组件应被移除。"""
        entity = context.create_entity()
        entity.add(SpeakAction, "alice")

        system.cleanup()

        assert not entity.has(SpeakAction)

    def test_cleanup_removes_multiple_actions_from_same_entity(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """单实体同时持有多个动作组件，执行后应全部被移除。"""
        entity = context.create_entity()
        entity.add(SpeakAction, "alice")
        entity.add(WhisperAction, "alice")
        entity.add(AnnounceAction, "alice")

        system.cleanup()

        assert not entity.has(SpeakAction)
        assert not entity.has(WhisperAction)
        assert not entity.has(AnnounceAction)

    def test_cleanup_removes_actions_from_multiple_entities(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """多个实体各持不同动作组件，执行后应全部被清除。"""
        entity_a = context.create_entity()
        entity_a.add(SpeakAction, "alice")

        entity_b = context.create_entity()
        entity_b.add(WhisperAction, "bob")

        entity_c = context.create_entity()
        entity_c.add(AnnounceAction, "carol")

        system.cleanup()

        assert not entity_a.has(SpeakAction)
        assert not entity_b.has(WhisperAction)
        assert not entity_c.has(AnnounceAction)

    def test_cleanup_preserves_non_action_components(
        self, context: ECSContext, system: ActionCleanupSystem
    ) -> None:
        """实体同时持有动作组件与非动作组件，执行后非动作组件应保留。"""
        entity = context.create_entity()
        entity.add(SpeakAction, "alice")
        entity.add(Position, 1.0, 2.0)

        system.cleanup()

        assert not entity.has(SpeakAction)
        assert entity.has(Position)
