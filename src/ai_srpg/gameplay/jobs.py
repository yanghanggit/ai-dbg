"""后台 gameplay job：job 体只调用 ``run_game_pass``。"""

from procrastinate import JobContext

from ..pgsql import procrastinate_app
from .job_runtime import job_task
from .runtime import run_game_pass


###############################################################################
@procrastinate_app.task(name="advance_game", pass_context=True)
@job_task("advance_game")
async def advance_game_job(context: JobContext, *, room_id: str) -> None:
    """推进一次 pass（一局游戏 = 一个房间）。"""
    await run_game_pass(room_id)
