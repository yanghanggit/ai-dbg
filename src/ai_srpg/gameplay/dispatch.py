"""房间 job 的派发入口：带房间级 ``queueing_lock``，同一房间同时只排队一个 job。"""

from typing import Any

from procrastinate.exceptions import AlreadyEnqueued

from ..session.errors import RoomJobBusyError


###############################################################################################################################################
async def defer_room_job(job_func: Any, *, room_id: str, **job_kwargs: Any) -> int:
    """派发房间 job，返回 job id；该房间已有 job 排队时抛 ``RoomJobBusyError``。"""
    queueing_lock = f"room:{room_id}"
    try:
        job_id: int = await job_func.configure(queueing_lock=queueing_lock).defer_async(
            room_id=room_id, **job_kwargs
        )
    except AlreadyEnqueued as exc:
        raise RoomJobBusyError(room_id) from exc
    return job_id


###############################################################################################################################################
