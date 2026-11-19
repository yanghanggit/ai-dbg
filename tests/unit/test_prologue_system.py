"""``PrologueSystem`` 的不变量检查：角色必须站在存在的舞台上。"""

from typing import Any

import pytest

from ai_srpg.game.ecs_context import ECSContext
from ai_srpg.game.systems.prologue_system import PrologueSystem
from ai_srpg.models import ActorComponent, StageComponent


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


@pytest.fixture()
def game(context: ECSContext) -> Any:
    """ECSContext 已提供名称索引与 get_group，可直接当 SRPGGame 的替身。"""
    return context


def _make_stage(context: ECSContext, name: str) -> Any:
    entity = context.create_entity(name)
    entity.add(StageComponent)
    return entity


def _make_actor(context: ECSContext, name: str, stage_name: str) -> Any:
    entity = context.create_entity(name)
    entity.add(ActorComponent, stage_name)
    return entity


############################################################################################################
class TestActorsOnStage:
    async def test_passes_when_every_actor_is_placed(
        self, context: ECSContext, game: Any
    ) -> None:
        """正常局面：角色都在存在的舞台上，系统跑通。"""
        _make_stage(context, "舞台.甲")
        _make_actor(context, "角色.甲", "舞台.甲")
        _make_actor(context, "角色.乙", "舞台.甲")

        await PrologueSystem(game).execute()

    async def test_passes_without_any_actor(
        self, context: ECSContext, game: Any
    ) -> None:
        """空局（还没装配角色）不该被断言挡住。"""
        _make_stage(context, "舞台.甲")

        await PrologueSystem(game).execute()

    async def test_rejects_actor_without_stage(
        self, context: ECSContext, game: Any
    ) -> None:
        """``current_stage`` 为空即「不在场」，直接报错。"""
        _make_actor(context, "角色.甲", "")

        with pytest.raises(AssertionError, match="角色.甲"):
            await PrologueSystem(game).execute()

    async def test_rejects_actor_on_missing_stage(
        self, context: ECSContext, game: Any
    ) -> None:
        """``current_stage`` 指向不存在的舞台也要报错，而不是静默漏人。"""
        _make_actor(context, "角色.甲", "舞台.不存在")

        with pytest.raises(AssertionError, match="舞台.不存在"):
            await PrologueSystem(game).execute()
