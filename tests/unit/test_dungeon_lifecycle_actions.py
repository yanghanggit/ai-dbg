"""
副本生命周期动作单测。

覆盖：
  - 没有当前房间时拒绝推进 / 退出
  - 没有下一房间时拒绝推进
  - 非战斗房间（opening）可直接推进 / 退出
  - 退出动作恢复玩家并触发 teardown
"""

from typing import Any

import pytest

from ai_srpg.entitas.entity import Entity
from ai_srpg.game.dungeon import get_dungeon_entity
from ai_srpg.game.entities import create_entity
from ai_srpg.game.pipelines.manager import RPGGameProcessPipeline
from ai_srpg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    DungeonRoomType,
    ExitDungeonAction,
    LobbyComponent,
    PlayerComponent,
    StageComponent,
    TeardownDungeonAction,
)
from ai_srpg.services.dungeon_advance_action import advance_dungeon
from ai_srpg.services.dungeon_exit_action import activate_exit_dungeon
from ai_srpg.systems.action_cleanup_system import ActionCleanupSystem
from ai_srpg.systems.exit_dungeon_action_system import ExitDungeonActionSystem
from ai_srpg.systems.teardown_dungeon_action_system import (
    TeardownDungeonActionSystem,
)
from dungeon_support import (
    make_dungeon_entity,
    make_room_entity,
    set_current_room,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lobby_entity(game: Any, name: str) -> Entity:
    entity = create_entity(game, name)
    entity.add(StageComponent, name)
    entity.add(LobbyComponent, name)
    return entity


def _make_player(game: Any, name: str, stage_name: str) -> Entity:
    entity = create_entity(game, name)
    entity.add(ActorComponent, name, stage_name)
    entity.add(
        CharacterStatsComponent,
        name,
        CharacterStats(hp=3, max_hp=10, attack=1, defense=1),
    )
    entity.add(PlayerComponent, game.player_name)
    return entity


def _make_opening_room(game: Any, name: str, index: int) -> Entity:
    return make_room_entity(
        game,
        name=name,
        index=index,
        room_type=DungeonRoomType.OPENING,
    )


# ---------------------------------------------------------------------------
# advance_dungeon
# ---------------------------------------------------------------------------


class TestAdvanceDungeonGuards:
    async def test_rejects_when_no_current_room(self, sample_game: Any) -> None:
        """没有当前房间标记时拒绝推进。"""
        make_dungeon_entity(sample_game)
        _make_opening_room(sample_game, "room0", 0)

        ok, msg = await advance_dungeon(sample_game)

        assert ok is False
        assert "尚未进入" in msg

    async def test_rejects_when_no_next_room(self, sample_game: Any) -> None:
        """没有下一房间时拒绝推进。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        set_current_room(sample_game, room0)
        member = _make_player(sample_game, "hero", "room0")

        ok, msg = await advance_dungeon(sample_game)

        assert ok is False
        assert "通关" in msg
        assert member.get(ActorComponent).current_stage == "room0"

    async def test_advances_opening_room_without_initialization_flag(
        self, sample_game: Any
    ) -> None:
        """非战斗房间无需初始化状态位即可推进到下一关。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        _make_opening_room(sample_game, "room1", 1)
        set_current_room(sample_game, room0)
        member = _make_player(sample_game, "hero", "room0")

        ok, _ = await advance_dungeon(sample_game)

        assert ok is True
        assert member.get(ActorComponent).current_stage == "room1"


# ---------------------------------------------------------------------------
# ExitDungeonActionSystem
# ---------------------------------------------------------------------------


class TestExitDungeonActions:
    @pytest.mark.asyncio
    async def test_rejects_when_no_current_room(self, sample_game: Any) -> None:
        """没有当前房间标记时，退出 system 拒绝执行。"""
        make_dungeon_entity(sample_game)
        _make_opening_room(sample_game, "room0", 0)
        member = _make_player(sample_game, "hero", "room0")

        ok, _ = activate_exit_dungeon(sample_game)

        assert ok is True
        assert member.has(ExitDungeonAction)
        with pytest.raises(ValueError, match="尚未进入"):
            await ExitDungeonActionSystem(sample_game).react([member])

    @pytest.mark.asyncio
    async def test_exits_opening_room_and_requests_teardown(
        self, sample_game: Any
    ) -> None:
        """非战斗房间可直接退出、恢复玩家，并生成 teardown 动作。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        set_current_room(sample_game, room0)
        _make_lobby_entity(sample_game, "lobby")
        member = _make_player(sample_game, "hero", "room0")
        member.add(DeathComponent, "hero")

        ok, _ = activate_exit_dungeon(sample_game)
        assert ok is True

        await ExitDungeonActionSystem(sample_game).react([member])

        assert member.has(PlayerComponent)
        assert not member.has(DeathComponent)
        assert member.has(TeardownDungeonAction)
        actor_comp = member.get(ActorComponent)
        assert actor_comp.current_stage == "lobby"
        assert member.get(CharacterStatsComponent).stats.hp == 10
        assert get_dungeon_entity(sample_game) is not None

        await TeardownDungeonActionSystem(sample_game).react([member])

        assert get_dungeon_entity(sample_game) is None

    @pytest.mark.asyncio
    async def test_pipeline_runs_exit_action_through_teardown_and_cleanup(
        self, sample_game: Any
    ) -> None:
        """动作进入 pipeline 后，同一次 pass 完成退出、teardown 和动作清理。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        set_current_room(sample_game, room0)
        _make_lobby_entity(sample_game, "lobby")
        member = _make_player(sample_game, "hero", "room0")

        pipeline = RPGGameProcessPipeline()
        pipeline.add(ExitDungeonActionSystem(sample_game))
        pipeline.add(TeardownDungeonActionSystem(sample_game))
        pipeline.add(ActionCleanupSystem(sample_game))
        pipeline.activate_reactive_processors()

        ok, _ = activate_exit_dungeon(sample_game)
        assert ok is True

        await pipeline.process(None)

        assert get_dungeon_entity(sample_game) is None
        assert not member.has(ExitDungeonAction)
        assert not member.has(TeardownDungeonAction)
