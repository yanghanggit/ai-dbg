"""游戏生命周期与唯一 pipeline 的运行时管理。"""

from typing import Optional

from loguru import logger

from ..entitas.processor_interfaces import ProcessorObserver
from ..models import GAME_SNAPSHOT_FORMAT_VERSION, GameSnapshot
from .context import SRPGGame
from .pipelines import close_pipeline
from .pipelines.build import build_game_pipeline


###############################################################################################################################################
async def initialize_pipeline(
    srpg_game: SRPGGame, observer: Optional[ProcessorObserver] = None
) -> None:
    """初始化唯一 pipeline，并激活其中的反应式处理器。

    ``observer`` 会收到每个 initialize processor 的边界事件；任何失败都会
    中断后续初始化并上抛。
    """
    srpg_game.pipeline.activate_reactive_processors()
    await srpg_game.pipeline.initialize(observer)


###############################################################################################################################################
async def rebuild_pipeline(
    srpg_game: SRPGGame, observer: Optional[ProcessorObserver] = None
) -> None:
    """重建唯一 pipeline 并重新初始化。

    回滚会清空 context 的分组，reactive collector 仍持有旧 group 引用，
    因此必须换一套全新的 processor 实例。
    """
    srpg_game.pipeline = build_game_pipeline(srpg_game)
    await initialize_pipeline(srpg_game, observer)


###############################################################################################################################################
def shutdown_pipeline(
    srpg_game: SRPGGame, observer: Optional[ProcessorObserver] = None
) -> None:
    """关闭唯一 pipeline 并清理资源。"""
    close_pipeline(srpg_game.pipeline, observer)


###############################################################################################################################################
async def initialize_game(
    srpg_game: SRPGGame, observer: Optional[ProcessorObserver] = None
) -> None:
    logger.debug("Initializing game, setting up pipeline and world state...")
    await initialize_pipeline(srpg_game, observer)


###############################################################################################################################################
def exit_game(
    srpg_game: SRPGGame, observer: Optional[ProcessorObserver] = None
) -> None:
    logger.debug("Exiting game, performing cleanup...")
    shutdown_pipeline(srpg_game, observer)


###############################################################################################################################################
def snapshot_game(srpg_game: SRPGGame) -> GameSnapshot:
    """同时抓取 ECS 与 agent 记忆，形成一次游戏运行的组合快照。"""
    return GameSnapshot(
        ecs=srpg_game.ecs_snapshot(),
        memory=srpg_game.memory_snapshot(),
    )


###############################################################################################################################################
async def rollback_game(
    srpg_game: SRPGGame,
    snapshot: GameSnapshot,
    observer: Optional[ProcessorObserver] = None,
) -> None:
    """把 ECS 与 agent 记忆一起回滚到快照，然后重建 pipeline。

    ECS 与记忆是平级系统，必须由本函数（上层编排）同时恢复；只回滚其中
    一边会出现「实体回到过去、记忆停在未来」。``observer`` 同时用于关闭
    与重建阶段。
    """
    if snapshot.format_version != GAME_SNAPSHOT_FORMAT_VERSION:
        raise ValueError(
            f"组合快照格式版本不匹配: {snapshot.format_version} != {GAME_SNAPSHOT_FORMAT_VERSION}"
        )

    shutdown_pipeline(srpg_game, observer)
    srpg_game.rollback_ecs(snapshot.ecs)
    srpg_game.restore_memory_snapshot(snapshot.memory)
    await rebuild_pipeline(srpg_game, observer)
