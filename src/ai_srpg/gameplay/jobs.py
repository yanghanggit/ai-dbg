"""后台 gameplay job 定义。

job 体只做一件事：调用 ``run_game_pass``。快照、回滚、房间锁都在编排层，
这里不出现 ECS 或数据库细节。
"""

from procrastinate import JobContext

from ..pgsql import procrastinate_app
from .job_runtime import job_task
from .runtime import run_game_pass


###############################################################################
@procrastinate_app.task(name="advance_game", pass_context=True)
@job_task("advance_game")
async def advance_game_job(context: JobContext, *, user_name: str) -> None:
    """推进一次游戏 pass。"""
    await run_game_pass(user_name)
