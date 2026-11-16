"""房间后台 job 的统一派发入口。

所有针对某个玩家房间的后台 job 都经 ``defer_room_job`` 派发，并带**房间级**
``queueing_lock``：同一房间同时只允许一个 job 排队。pipeline 读写的是同一份 ECS
context，因此不允许同一房间的多个 pipeline 并发；运行期由房间锁保证串行。
"""

from typing import Any

from procrastinate.exceptions import AlreadyEnqueued


###############################################################################################################################################
class RoomBusyError(Exception):
    """该房间已有 job 在排队。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room busy: {user_name}")
        self.user_name: str = user_name


###############################################################################################################################################
async def defer_room_job(job_func: Any, *, user_name: str, **job_kwargs: Any) -> int:
    """派发房间 job，返回 job id；该房间已有 job 排队时抛 ``RoomBusyError``。"""
    queueing_lock = f"room:{user_name}"
    try:
        job_id: int = await job_func.configure(queueing_lock=queueing_lock).defer_async(
            user_name=user_name, **job_kwargs
        )
    except AlreadyEnqueued as exc:
        raise RoomBusyError(user_name) from exc
    return job_id


###############################################################################################################################################
