"""玩家房间：一个用户在进程内的游戏席位。

一房 = 一用户 = 最多一局游戏，房间之间不共享任何状态，只承担三件事：持有当前
游戏与用户级会话、把写操作串行化、按空闲时间被回收。

并发约定：写经 ``transaction()`` 串行；读不加锁，直接取 ``game`` / ``session``。
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final, Optional

from ..game.context import SRPGGame
from ..game.lifecycle import exit_game
from .errors import RoomClosedError
from .player_session import PlayerSession


###############################################################################################################################################
class Room:
    """一个用户在当前进程内的游戏席位（持有游戏、会话与房间锁）。"""

    def __init__(self, user_name: str) -> None:
        self._user_name: Final[str] = user_name
        self._srpg_game: Optional[SRPGGame] = None  # SRPGGame 游戏实例
        self._session: Optional[PlayerSession] = None
        self._lock: asyncio.Lock = asyncio.Lock()  # 每玩家锁，防止并发状态竞争
        self._closed: bool = False
        self._last_active_at: float = time.monotonic()

    ###############################################################################################################################################
    @property
    def user_name(self) -> str:
        return self._user_name

    @property
    def game(self) -> Optional[SRPGGame]:
        return self._srpg_game

    @property
    def session(self) -> Optional[PlayerSession]:
        return self._session

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
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["Room", None]:
        """进入房间临界区，仅用于写变更。"""
        self.touch()
        async with self._lock:
            if self._closed:
                raise RoomClosedError(self._user_name)
            yield self

    ###############################################################################################################################################
    def set_session(self, session: PlayerSession) -> None:
        """绑定用户级会话；不依赖当前是否已有游戏。"""
        if self._closed:
            raise RoomClosedError(self._user_name)
        self._session = session

    ###############################################################################################################################################
    def start_game(self, *, game: SRPGGame, session: PlayerSession) -> None:
        """绑定游戏与会话实例，应在 ``transaction()`` 内调用。"""
        if self._closed:
            raise RoomClosedError(self._user_name)
        self._srpg_game = game
        self._session = session

    ###############################################################################################################################################
    def _teardown(self) -> None:
        """退出游戏并清空状态；调用方必须已持有房间锁。"""
        if self._srpg_game is not None:
            exit_game(self._srpg_game)
        self._closed = True
        self._srpg_game = None
        self._session = None

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

            # 检查房间是否已关闭或仍然活跃
            if self._closed or self._last_active_at > deadline:
                return False

            # 退出游戏并关闭房间
            self._teardown()
            return True

    ###############################################################################################################################################
