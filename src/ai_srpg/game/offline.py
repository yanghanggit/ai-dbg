"""离线加载：从蓝图或快照构造可直接运行的 ``SRPGGame``。

这里只做「数据 → 游戏实例」的转换，不访问数据库；快照的读取与保存由上层
服务负责，避免 ECS 运行辅助依赖存储层。
"""

from typing import Optional

from ..models import GAME_SNAPSHOT_FORMAT_VERSION, Blueprint, GameSnapshot
from ..paths import BLUEPRINTS_DIR
from .assembly import create_srpg_game
from .context import SRPGGame
from .entities.world_builder import build_from_blueprint
from .events.sink import DomainEventSink


###############################################################################
def load_blueprint(game_name: str) -> Blueprint:
    """读取 ``.blueprints/<game_name>.json``。"""
    path = BLUEPRINTS_DIR / f"{game_name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"找不到蓝图: {path}")
    blueprint = Blueprint.model_validate_json(path.read_text(encoding="utf-8"))
    if blueprint.name != game_name:
        raise ValueError(
            f"蓝图名与文件名不一致: blueprint={blueprint.name!r}, file={game_name!r}"
        )
    return blueprint


###############################################################################
def create_game_from_blueprint(
    game_name: str,
    *,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """读取蓝图并装配新游戏世界；pipeline 尚未初始化。

    ``events`` 是领域事件出口（如会话历史 sink）；不传则丢弃事件。
    """
    blueprint = load_blueprint(game_name)
    game = create_srpg_game(name=game_name, events=events)
    build_from_blueprint(game, blueprint)
    return game


###############################################################################
def restore_game_from_snapshot(
    game_name: str,
    snapshot: GameSnapshot,
    *,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """在空游戏实例上恢复 ECS 与 agent 记忆；pipeline 尚未初始化。"""
    if snapshot.format_version != GAME_SNAPSHOT_FORMAT_VERSION:
        raise ValueError(
            f"组合快照格式版本不匹配: {snapshot.format_version} != {GAME_SNAPSHOT_FORMAT_VERSION}"
        )
    if snapshot.game != game_name:
        raise ValueError(f"快照属于游戏 {snapshot.game!r}，不能恢复到 {game_name!r}")

    game = create_srpg_game(name=game_name, events=events)
    game.restore_ecs_snapshot(snapshot.ecs)
    game.restore_memory_snapshot(snapshot.memory)
    return game


__all__ = [
    "create_game_from_blueprint",
    "load_blueprint",
    "restore_game_from_snapshot",
]
