"""游戏玩法定时系统（骨架）。

只提供“周期性地遍历所有房间、并在房间锁内执行一次回调”的框架，**不含任何业务逻辑**。
未来要加玩法（例如定时查看 ECS 状态、满足条件就推进玩法）时，只需实现 ``on_room_tick``。

并发约定（重要）
----------------
* **发现房间**：用 ``game_server.snapshot_rooms()`` 做无锁只读快照。
* **改状态**：必须经 ``game_server.acquire(user)`` 进入房间锁——同一个房间同一时刻只允许
  一个 pipeline 访问它的 ECS context。
* **不阻塞 tick**：用非阻塞方式判断房间是否忙（``room.is_busy``），忙则本轮跳过；否则一个
  长 pipeline 会拖住整个遍历。
* **不跑长流程**：本回调只做“判断 + 派发”，真正的 LLM pipeline 交给后台 job
  （``gameplay.dispatch.defer_room_job`` + Procrastinate worker）执行。

注：房间是进程内内存态，因此定时器应与 GameServer 跑在同一进程（当前由 ``lifespan`` 启动）。
"""

import asyncio

from loguru import logger

from ..session.errors import RoomClosedError, RoomNotFoundError
from ..session.room import PlayerRoom
from ..session.server import GameServer


###############################################################################################################################################
async def on_room_tick(room: PlayerRoom) -> None:
    """单个房间的一次定时回调（占位，待填充业务逻辑）。

    调用时**已持有该房间的锁**（由 ``_tick_once`` 通过 ``game_server.acquire`` 获取），
    因此可以安全读写 ``room.game``（ECS context）。

    未来在此实现玩法，例如：

        # 满足条件时派发 job；长流程交给 worker，不要在本回调里直接跑 pipeline。
        # from .dispatch import defer_room_job
        # from .jobs import advance_game_job
        # if room.game is not None:
        #     await defer_room_job(advance_game_job, user_name=room.username)
    """
    return


###############################################################################################################################################
async def _tick_once(game_server: GameServer) -> None:
    """执行一轮：遍历房间快照，逐个在房间锁内调用 ``on_room_tick``。"""
    rooms = game_server.snapshot_rooms()
    processed = 0
    for room in rooms:

        # 跳过已关闭或正忙的房间：忙表示已有 pipeline 在跑，本轮直接放弃，避免阻塞整个 tick。
        # 单事件循环下，此处判断与下面取锁之间没有 await，因此不会与其他协程交错。
        if room.is_closed or room.is_busy:
            continue

        try:
            async with game_server.acquire(room.username) as locked:
                await on_room_tick(locked)
                processed += 1
        except (RoomNotFoundError, RoomClosedError):
            # 快照与取锁之间房间被移除/关闭，属正常竞态，跳过即可。
            continue
        except Exception as e:
            logger.error(f"gameplay tick error for {room.username}: {e}")

    logger.debug(f"gameplay tick: 扫描 {len(rooms)} 个房间，处理 {processed} 个")


###############################################################################################################################################
async def run_gameplay_scheduler(game_server: GameServer, interval: float) -> None:
    """周期性玩法调度循环，由 ``lifespan`` 启动；``interval`` 为秒。"""
    logger.info(f"⏱️ 游戏玩法定时器启动，间隔 {interval}s")
    while True:
        await asyncio.sleep(interval)
        try:
            await _tick_once(game_server)
        except Exception as e:
            logger.error(f"gameplay scheduler error: {e}")
