"""按玩家身份查角色的单元测试。

一局里可以有多个玩家，因此查询必须按 ``PlayerComponent.user_name`` 定位——
这正是多人阶段最容易写错的地方（取「第一个玩家」在单人下看起来是对的）。
"""

from typing import Any

import pytest

from ai_srpg.game.ecs_context import ECSContext
from ai_srpg.game.entities import get_player_actor_name, get_player_entity
from ai_srpg.models import ActorComponent, PlayerComponent

############################################################################################################


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


@pytest.fixture()
def game(context: ECSContext) -> Any:
    """只用到 get_group，因此用真实 Context 代理它，不构造 SRPGGame。"""
    stub = type("GameStub", (), {})()
    stub.get_group = context.get_group
    return stub


def _make_actor(context: ECSContext, name: str, user_name: str = "") -> Any:
    entity = context.create_entity(name)
    entity.add(ActorComponent, name, "")
    if user_name:
        entity.replace(PlayerComponent, user_name)
    return entity


############################################################################################################
class TestPlayerQueries:
    def test_returns_the_player_actor(self, context: ECSContext, game: Any) -> None:
        """单个玩家：返回他的角色名与实体。"""
        actor = _make_actor(context, "角色.甲", "alice")

        assert get_player_actor_name(game, "alice") == "角色.甲"
        assert get_player_entity(game, "alice") is actor

    def test_each_player_gets_their_own_actor(
        self, context: ECSContext, game: Any
    ) -> None:
        """多人：各查各的，与创建顺序无关。"""
        _make_actor(context, "角色.甲", "alice")
        _make_actor(context, "角色.乙", "bob")

        assert get_player_actor_name(game, "alice") == "角色.甲"
        assert get_player_actor_name(game, "bob") == "角色.乙"

    def test_non_player_actors_are_ignored(
        self, context: ECSContext, game: Any
    ) -> None:
        """同一舞台的非玩家角色不会被误认成某个玩家的角色。"""
        _make_actor(context, "角色.甲", "alice")
        _make_actor(context, "角色.路人")

        assert get_player_actor_name(game, "alice") == "角色.甲"
        assert get_player_entity(game, "bob") is None

    def test_unknown_player_returns_none(self, context: ECSContext, game: Any) -> None:
        """还没分到角色的玩家返回 None，而不是借用别人的角色。"""
        _make_actor(context, "角色.甲", "alice")

        assert get_player_actor_name(game, "bob") is None
        assert get_player_entity(game, "bob") is None

    def test_no_players_returns_none(self, game: Any) -> None:
        """场上没有玩家角色时返回 None。"""
        assert get_player_actor_name(game, "alice") is None

    def test_duplicate_binding_is_reported(
        self, context: ECSContext, game: Any
    ) -> None:
        """同一玩家绑定多个角色属状态损坏，直接报错而不是静默取一个。"""
        _make_actor(context, "角色.甲", "alice")
        _make_actor(context, "角色.乙", "alice")

        with pytest.raises(ValueError, match="角色.甲"):
            get_player_entity(game, "alice")
