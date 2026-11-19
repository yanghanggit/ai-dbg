"""一局游戏在进程内的席位容器：持有游戏、各席位会话游标与房间锁。

写经 ``transaction()`` 串行；读不加锁。
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Final, List, Optional, final

from ..game.context import SRPGGame
from ..game.lifecycle import exit_game
from .errors import RoomClosedError
from .player_session import PlayerSession


###############################################################################################################################################
@final
class Seat:
    """房间里的一个席位：谁在玩、控制哪个角色（未分配时 ``actor`` 为 None）。"""

    def __init__(self, user_name: str) -> None:
        self.user_name: Final[str] = user_name
        self.actor: Optional[str] = None


###############################################################################################################################################
class Room:
    """一局游戏的运行时容器；写操作经 ``transaction()`` 串行。"""

    def __init__(self, room_id: str, owner: str) -> None:
        self._room_id: Final[str] = room_id
        self._owner: Final[str] = owner
        # 房主排第一，其后按进入顺序
        self._seats: Dict[str, Seat] = {owner: Seat(owner)}
        self._sessions: Dict[str, PlayerSession] = {}
        self._srpg_game: Optional[SRPGGame] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._closed: bool = False
        self._last_active_at: float = time.monotonic()
        self._event_sequence: int = 0  # 局级流头，跨席位共享

    ###############################################################################################################################################
    @property
    def room_id(self) -> str:
        return self._room_id

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def seats(self) -> List[Seat]:
        return list(self._seats.values())

    @property
    def is_empty(self) -> bool:
        return not self._seats

    @property
    def game(self) -> Optional[SRPGGame]:
        return self._srpg_game

    @property
    def sessions(self) -> Dict[str, PlayerSession]:
        return dict(self._sessions)

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def is_busy(self) -> bool:
        """是否有进行中的事务（供定时器/回收器等需非阻塞判断的场景使用）。"""
        return self._lock.locked()

    def touch(self) -> None:
        """刷新房间活跃时间。"""
        self._last_active_at = time.monotonic()

    ###############################################################################################################################################
    def seat(self, user_name: str) -> Optional[Seat]:
        """某用户的席位；不在房里时返回 ``None``。"""
        return self._seats.get(user_name)

    def join(self, user_name: str) -> Seat:
        """加入房间（幂等）；房间已关闭时抛 ``RoomClosedError``。"""
        if self._closed:
            raise RoomClosedError(self._room_id)
        seat = self._seats.get(user_name)
        if seat is None:
            seat = Seat(user_name)
            self._seats[user_name] = seat
        return seat

    def leave(self, user_name: str) -> bool:
        """离开房间：移除席位与该席位的会话游标；返回是否确实移除了。"""
        self._sessions.pop(user_name, None)
        return self._seats.pop(user_name, None) is not None

    ###############################################################################################################################################
    def session_of(self, user_name: str) -> Optional[PlayerSession]:
        """该席位在当前局会话流上的游标。"""
        return self._sessions.get(user_name)

    def attach_session(self, session: PlayerSession) -> None:
        """绑定某席位的会话（席位必须已在房里）。"""
        if self._closed:
            raise RoomClosedError(self._room_id)
        assert session.user_name in self._seats, "会话必须属于房间内的席位"
        self._sessions[session.user_name] = session

    ###############################################################################################################################################
    def start_game(self, *, game: SRPGGame) -> None:
        """绑定游戏实例，应在 ``transaction()`` 内调用。"""
        if self._closed:
            raise RoomClosedError(self._room_id)
        self._srpg_game = game

    ###############################################################################################################################################
    def bind_seat_actor(self, user_name: str, actor: str) -> None:
        """记录某席位控制的角色全名。"""
        seat = self._seats.get(user_name)
        assert seat is not None, f"席位不存在: {user_name}"
        seat.actor = actor

    ###############################################################################################################################################
    def seed_event_sequence(self, head: int) -> None:
        """用存储里的流头初始化序号（开局或恢复时调用）。"""
        self._event_sequence = max(self._event_sequence, head)

    def next_event_sequence(self) -> int:
        """分配局级会话流的下一个序号；仅在 ``transaction()`` 内调用。"""
        self._event_sequence += 1
        return self._event_sequence

    ###############################################################################################################################################
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["Room", None]:
        """进入房间临界区（写变更）。"""
        self.touch()
        async with self._lock:
            if self._closed:
                raise RoomClosedError(self._room_id)
            yield self

    ###############################################################################################################################################
    def _teardown(self) -> None:
        """退出游戏并清空状态；调用方必须已持有房间锁。"""
        if self._srpg_game is not None:
            exit_game(self._srpg_game)
        self._closed = True
        self._srpg_game = None
        self._sessions.clear()

    ###############################################################################################################################################
    async def close(self) -> None:
        """等待进行中的事务结束后退出游戏并关闭房间。"""
        async with self._lock:
            self._teardown()

    ###############################################################################################################################################
    async def evict_if_idle(self, deadline: float) -> bool:
        """若房间不忙且活跃时间早于 deadline，则退出游戏并关闭；返回是否已关闭。"""
        if self._lock.locked():
            return False

        async with self._lock:
            if self._closed or self._last_active_at > deadline:
                return False

            self._teardown()
            return True

    ###############################################################################################################################################
