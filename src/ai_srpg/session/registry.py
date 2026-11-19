"""进程内房间注册表：``room_id -> Room``，外加 ``user_name -> room_id`` 索引。

只做注册 / 注销 / 席位变更；房间内部一致性由 ``Room`` 的锁负责，进临界区
统一走 ``acquire``。注册表是内存态，因此不支持多 worker / 多进程部署。
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional, final

from .errors import RoomAlreadyExistsError, RoomNotFoundError
from .job_context import get_current_job
from .room import Room


###############################################################################
def _mint_room_id(owner: str) -> str:
    """分配房间号：单人阶段直接用房主用户名，多人阶段换成独立房间号。"""
    return owner


###############################################################################################################################################
@final
class RoomRegistry:
    """进程内房间注册表：负责房间的注册 / 注销、席位变更与空闲回收。"""

    def __init__(
        self,
    ) -> None:
        self._rooms: Dict[str, Room] = {}
        self._user_rooms: Dict[str, str] = {}  # user_name -> room_id
        self._lock: asyncio.Lock = asyncio.Lock()  # 保护注册表变更

    ###############################################################################################################################################
    def has_room(self, room_id: str) -> bool:
        """检查指定房间是否存在"""
        return room_id in self._rooms

    ###############################################################################################################################################
    def get_room(self, room_id: str) -> Optional[Room]:
        """按房间号取房间（同时刷新其活跃时间）。"""
        room = self._rooms.get(room_id, None)
        if room is not None:
            room.touch()
        return room

    ###############################################################################################################################################
    def get_room_of_user(self, user_name: str) -> Optional[Room]:
        """取某用户所在的房间（同时刷新其活跃时间）；不在任何房间时返回 ``None``。"""
        room_id = self._user_rooms.get(user_name)
        return None if room_id is None else self.get_room(room_id)

    ###############################################################################################################################################
    def snapshot_rooms(self) -> List[Room]:
        """房间列表的时间点快照（不持锁、不刷新活跃时间）；权威判断仍走 ``acquire``。"""
        return list(self._rooms.values())

    ###############################################################################################################################################
    async def create_room(self, owner: str) -> Room:
        """为指定用户创建房间（他自动成为房主与第一个席位）。"""
        room_id = _mint_room_id(owner)
        async with self._lock:
            if room_id in self._rooms:
                raise RoomAlreadyExistsError(room_id)

            room = Room(room_id, owner)
            self._rooms[room_id] = room
            self._user_rooms[owner] = room_id
            return room

    ###############################################################################################################################################
    async def join_room(self, room_id: str, user_name: str) -> Room:
        """把一个用户加进已有房间；房间不存在时抛 ``RoomNotFoundError``。

        用户已在别的房间时先退出那里，避免留下无人使用的席位。
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise RoomNotFoundError(room_id)
            current = self._user_rooms.get(user_name)

        if current is not None and current != room_id:
            await self.leave_room(user_name)

        async with room.transaction():
            room.join(user_name)

        async with self._lock:
            self._user_rooms[user_name] = room_id

        return room

    ###############################################################################################################################################
    async def leave_room(self, user_name: str) -> Optional[Room]:
        """用户离开所在房间；房间空了就关闭并注销。房间不存在时返回 ``None``。"""
        async with self._lock:
            room_id = self._user_rooms.get(user_name)
        if room_id is None:
            return None

        room = self._rooms.get(room_id)
        if room is None:
            async with self._lock:
                self._user_rooms.pop(user_name, None)
            return None

        async with room.transaction():
            room.leave(user_name)

        async with self._lock:
            self._user_rooms.pop(user_name, None)
            if room.is_empty:
                self._rooms.pop(room_id, None)

        if room.is_empty:
            await room.close()

        return room

    ###############################################################################################################################################
    async def remove_room(self, room_id: str) -> Optional[Room]:
        """移除并关闭房间：先摘除索引，再等房间事务结束后关闭。"""
        async with self._lock:
            room = self._rooms.pop(room_id, None)
            if room is not None:
                for seat in room.seats:
                    self._user_rooms.pop(seat.user_name, None)

        if room is not None:
            await room.close()

        return room

    ###############################################################################################################################################
    async def reap_expired(
        self, ttl: float, *, now: Optional[float] = None
    ) -> List[str]:
        """回收空闲超过 ``ttl`` 秒且不在忙的房间，返回被回收的房间号。"""
        current = time.monotonic() if now is None else now
        deadline = current - ttl
        reaped: List[str] = []

        for room in self.snapshot_rooms():

            if not await room.evict_if_idle(deadline):
                continue

            async with self._lock:
                if self._rooms.get(room.room_id) is room:
                    self._rooms.pop(room.room_id, None)
                    for seat in room.seats:
                        self._user_rooms.pop(seat.user_name, None)

            reaped.append(room.room_id)

        return reaped

    ###############################################################################################################################################
    @asynccontextmanager
    async def acquire(self, room_id: str) -> AsyncGenerator[Room, None]:
        """在房间事务锁内执行；房间不存在时抛 ``RoomNotFoundError``。

        进入临界区的统一入口，同时把当前 job 绑定到这个房间。
        """
        room = self.get_room(room_id)
        if room is None:
            raise RoomNotFoundError(room_id)

        async with room.transaction():
            job = get_current_job()
            if job is not None:
                job.bind_room(room)
            yield room

    ###############################################################################################################################################
