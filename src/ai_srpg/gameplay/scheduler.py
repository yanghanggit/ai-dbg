"""玩法定时器骨架：周期性遍历房间，在房间锁内执行一次回调，不含业务逻辑。

回调只做「判断 + 派发」，长流程交给后台 job；房间忙则本轮跳过。
"""

import asyncio

from loguru import logger

from ..session.errors import RoomClosedError, RoomNotFoundError
from ..session.registry import RoomRegistry
from ..session.room import Room


###############################################################################################################################################
async def on_room_tick(room: Room) -> None:
    """单个房间的定时回调（占位）；调用时已持有该房间的锁。"""
    return


###############################################################################################################################################
async def _tick_once(room_registry: RoomRegistry) -> None:
    """执行一轮：遍历房间快照，逐个在房间锁内调用 ``on_room_tick``。"""
    rooms = room_registry.snapshot_rooms()
    processed = 0
    for room in rooms:

        # 跳过已关闭或正忙的房间：忙表示已有 pipeline 在跑，本轮直接放弃，避免阻塞整个 tick。
        # 单事件循环下，此处判断与下面取锁之间没有 await，因此不会与其他协程交错。
        if room.is_closed or room.is_busy:
            continue

        try:
            async with room_registry.acquire(room.room_id) as locked:
                await on_room_tick(locked)
                processed += 1
        except (RoomNotFoundError, RoomClosedError):
            # 快照与取锁之间房间被移除/关闭，属正常竞态，跳过即可。
            continue
        except Exception as e:
            logger.error(f"gameplay tick error for {room.room_id}: {e}")

    logger.debug(f"gameplay tick: 扫描 {len(rooms)} 个房间，处理 {processed} 个")


###############################################################################################################################################
async def run_gameplay_scheduler(room_registry: RoomRegistry, interval: float) -> None:
    """周期性玩法调度循环，由 ``lifespan`` 启动；``interval`` 为秒。"""
    logger.info(f"⏱️ 游戏玩法定时器启动，间隔 {interval}s")
    while True:
        await asyncio.sleep(interval)
        try:
            await _tick_once(room_registry)
        except Exception as e:
            logger.error(f"gameplay scheduler error: {e}")
