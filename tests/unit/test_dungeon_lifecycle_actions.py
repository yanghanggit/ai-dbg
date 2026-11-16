"""
Unit tests for src/ai_dbg/services/dungeon_advance_action.py
and src/ai_dbg/services/dungeon_exit_action.py

覆盖 ECS 化后的状态守卫：
  - 没有当前房间时拒绝推进 / 退出
  - 没有下一房间时拒绝推进
  - 非战斗房间（opening）可直接推进 / 退出，无需初始化状态位
"""

from typing import Any

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.entities import create_entity
from ai_dbg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    DungeonRoomType,
    LobbyComponent,
    PartyMemberComponent,
    SpoilsComponent,
    StageComponent,
)
from ai_dbg.services.dungeon_advance_action import advance_dungeon
from ai_dbg.services.dungeon_exit_action import exit_dungeon
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


def _make_party_member(game: Any, name: str, stage_name: str) -> Entity:
    entity = create_entity(game, name)
    entity.add(ActorComponent, name, stage_name)
    entity.add(
        CharacterStatsComponent,
        name,
        CharacterStats(hp=3, max_hp=10, attack=1, defense=1),
    )
    entity.add(PartyMemberComponent, name)
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
        member = _make_party_member(sample_game, "hero", "room0")

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
        member = _make_party_member(sample_game, "hero", "room0")

        ok, _ = await advance_dungeon(sample_game)

        assert ok is True
        assert member.get(ActorComponent).current_stage == "room1"

    async def test_advancing_into_non_combat_room_clears_stale_spoils(
        self, sample_game: Any
    ) -> None:
        """进入非战斗房间时自动清理上一轮残留的奖励状态。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        _make_opening_room(sample_game, "room1", 1)
        set_current_room(sample_game, room0)
        member = _make_party_member(sample_game, "hero", "room0")
        member.add(SpoilsComponent, "hero", [], [])

        ok, _ = await advance_dungeon(sample_game)

        assert ok is True
        assert not member.has(SpoilsComponent)


# ---------------------------------------------------------------------------
# exit_dungeon
# ---------------------------------------------------------------------------


class TestExitDungeonGuards:
    def test_rejects_when_no_current_room(self, sample_game: Any) -> None:
        """没有当前房间标记时拒绝退出。"""
        make_dungeon_entity(sample_game)
        _make_opening_room(sample_game, "room0", 0)

        ok, msg = exit_dungeon(sample_game)

        assert ok is False
        assert "尚未进入" in msg

    def test_exits_opening_room_without_initialization_flag(
        self, sample_game: Any
    ) -> None:
        """非战斗房间无需初始化状态位即可退出并恢复队伍成员到大厅。"""
        make_dungeon_entity(sample_game)
        room0 = _make_opening_room(sample_game, "room0", 0)
        set_current_room(sample_game, room0)
        _make_lobby_entity(sample_game, "lobby")
        member = _make_party_member(sample_game, "hero", "room0")

        ok, _ = exit_dungeon(sample_game)

        assert ok is True
        # 队伍标记被移除
        assert not member.has(PartyMemberComponent)
        # 成员已被传送回大厅
        actor_comp = member.get(ActorComponent)
        assert actor_comp is not None
        assert actor_comp.current_stage == "lobby"
