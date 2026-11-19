"""房间 TTL / 回收测试。"""

import asyncio
import time
from typing import cast

from ai_srpg.game.context import SRPGGame
from ai_srpg.session.registry import RoomRegistry
from ai_srpg.session.room import Room


class _FakePipeline:
    def __init__(self) -> None:
        self.shutdown_called = False

    def tear_down(self, observer: object = None) -> None:
        self.shutdown_called = True

    def clear_reactive_processors(self) -> None:
        pass


class _FakeGame:
    def __init__(self) -> None:
        self.exited = False
        self.pipeline = _FakePipeline()

    def exit(self) -> None:
        self.exited = True


async def test_reap_expired_removes_idle_room() -> None:
    server = RoomRegistry()
    room = await server.create_room("alice")
    game = _FakeGame()
    room._srpg_game = cast(SRPGGame, game)
    room._last_active_at = 0.0

    reaped = await server.reap_expired(ttl=10, now=time.monotonic())

    assert reaped == ["alice"]
    assert not server.has_room("alice")
    assert room.is_closed


async def test_reap_expired_keeps_active_room() -> None:
    server = RoomRegistry()
    room = await server.create_room("alice")
    room._last_active_at = time.monotonic()

    reaped = await server.reap_expired(ttl=10)

    assert reaped == []
    assert server.has_room("alice")
    assert not room.is_closed


async def test_reap_expired_skips_busy_room() -> None:
    server = RoomRegistry()
    room = await server.create_room("alice")
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with room.transaction():
            room._last_active_at = 0.0  # 标记为过期，但它仍处于忙状态
            started.set()
            await release.wait()

    task = asyncio.create_task(hold())
    await started.wait()

    reaped = await server.reap_expired(ttl=10, now=time.monotonic())

    assert reaped == []
    assert server.has_room("alice")

    release.set()
    await task


async def test_get_room_touches_activity() -> None:
    server = RoomRegistry()
    room = await server.create_room("alice")
    room._last_active_at = 0.0

    server.get_room("alice")

    assert room._last_active_at > 0.0


async def test_close_exits_game_and_clears_state() -> None:
    """关房与空闲回收必须走同一条拆房路径：都要退出游戏。"""
    room = Room("alice")
    game = _FakeGame()
    room._srpg_game = cast(SRPGGame, game)

    await room.close()

    assert game.pipeline.shutdown_called
    assert room.is_closed
    assert room.game is None
    assert room.session is None


async def test_close_is_idempotent() -> None:
    room = Room("alice")
    room._srpg_game = cast(SRPGGame, _FakeGame())

    await room.close()
    await room.close()

    assert room.is_closed
