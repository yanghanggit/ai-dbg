"""SRPG AI 操作工具 —— 快照驱动的离线副本推进 CLI（骨架）。

只保留命令面、参数与日志骨架：每条子命令把参数交给 `srpg_game_agent`
的动作骨架，后者只记录调用，不读写存档、不推进世界。
待数据层与 SRPG 规则落地后，在动作层填充实现。

命令一览：
  new              创建新游戏并直接进入副本首间
  stages           列出场景-角色映射
  compact-context  手动压缩指定实体的 LLM 记忆
  enter-dungeon    从大厅进入指定副本
  combat-init      战斗房间初始化
  opening-init     开场房间初始化
  draw-cards       全员抽牌
  play-cards-specified  指定角色出牌
  pass-turn        交出行动权
  use-consumable   使用消耗品
  equip-gear       装备装备物
  retreat          主动撤退
  next-dungeon     推进到下一个房间
  exit-dungeon     退出副本回到大厅
"""

import asyncio
import datetime
import sys
from pathlib import Path
from typing import Final

import click
from loguru import logger

from ai_srpg.paths import LOGS_DIR
from ai_srpg.srpg_game_agent.combat import (
    draw_cards_game,
    equip_gear_game,
    init_combat_game,
    pass_turn_game,
    play_cards_specified_game,
    retreat_game,
    use_consumable_game,
)
from ai_srpg.srpg_game_agent.compact import compact_context_game
from ai_srpg.srpg_game_agent.core import create_and_initialize_game, stages_game
from ai_srpg.srpg_game_agent.dungeon import (
    enter_dungeon_game,
    exit_dungeon_game,
    next_dungeon_game,
)
from ai_srpg.srpg_game_agent.opening import init_opening_game

LOG_LEVEL: Final[str] = "DEBUG"


###############################################################################
def _setup_logger() -> Path:
    """初始化控制台与文件日志，返回本次运行日志文件路径。"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"run_agent_game_{timestamp}.log"
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(log_file, level=LOG_LEVEL)
    logger.info(f"日志配置: 级别={LOG_LEVEL}, 文件路径={log_file}")
    return log_file


###############################################################################
@click.group()
def main() -> None:
    """AI 操作工具：快照驱动的离线副本推进（当前为骨架，仅记录调用）。"""


###############################################################################
@main.command("new")
@click.option("--user", default=None, help="玩家用户名。默认为带时间戳的随机名称。")
@click.option(
    "--game", required=True, help="游戏名称（对应 BLUEPRINTS_DIR 下的文件名）。"
)
@click.option(
    "--dungeon", required=True, help="副本名称（骨架仅记录参数，不读取数据）。"
)
def new_game(user: str | None, game: str, dungeon: str) -> None:
    """创建新游戏并进入副本首间（骨架）。"""
    _setup_logger()
    asyncio.run(create_and_initialize_game(user or "skeleton", game, dungeon))


###############################################################################
@main.command("stages")
@click.option("--snapshot", required=True, help="存档目录路径")
def stages(snapshot: str) -> None:
    """列出场景-角色映射（骨架）。"""
    _setup_logger()
    mapping = asyncio.run(stages_game(Path(snapshot)))
    for stage_name, actor_names in mapping.items():
        click.echo(f"{stage_name}: {', '.join(actor_names)}")


###############################################################################
@main.command("compact-context")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--target", required=True, help="要压缩的目标实体名")
def compact_context(snapshot: str, target: str) -> None:
    """手动压缩指定实体的 LLM 记忆（骨架）。"""
    _setup_logger()
    asyncio.run(compact_context_game(Path(snapshot), target))


###############################################################################
@main.command("enter-dungeon")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--dungeon", required=True, help="副本名称")
def enter_dungeon(snapshot: str, dungeon: str) -> None:
    """从大厅进入指定副本（骨架）。"""
    _setup_logger()
    asyncio.run(enter_dungeon_game(Path(snapshot), dungeon))


###############################################################################
@main.command("combat-init")
@click.option("--snapshot", required=True, help="存档目录路径")
def combat_init(snapshot: str) -> None:
    """战斗房间初始化（骨架）。"""
    _setup_logger()
    asyncio.run(init_combat_game(Path(snapshot)))


###############################################################################
@main.command("opening-init")
@click.option("--snapshot", required=True, help="存档目录路径")
def opening_init(snapshot: str) -> None:
    """开场房间初始化（骨架）。"""
    _setup_logger()
    asyncio.run(init_opening_game(Path(snapshot)))


###############################################################################
@main.command("draw-cards")
@click.option("--snapshot", required=True, help="存档目录路径")
def draw_cards(snapshot: str) -> None:
    """全员抽牌（骨架）。"""
    _setup_logger()
    asyncio.run(draw_cards_game(Path(snapshot)))


###############################################################################
@main.command("play-cards-specified")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--actor", required=True, help="出牌角色全名")
@click.option("--card", required=False, default=None, help="要打出的卡牌名称")
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用",
)
def play_cards_specified(
    snapshot: str,
    actor: str,
    card: str | None,
    targets: tuple[str, ...],
) -> None:
    """指定角色出牌（骨架）。"""
    _setup_logger()
    asyncio.run(play_cards_specified_game(Path(snapshot), actor, card, targets))


###############################################################################
@main.command("pass-turn")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--actor", required=True, help="交出行动权的角色全名")
def pass_turn(snapshot: str, actor: str) -> None:
    """交出行动权（骨架）。"""
    _setup_logger()
    asyncio.run(pass_turn_game(Path(snapshot), actor))


###############################################################################
@main.command("use-consumable")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--item", required=True, help="消耗品名称")
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用",
)
def use_consumable(snapshot: str, item: str, targets: tuple[str, ...]) -> None:
    """使用消耗品（骨架）。"""
    _setup_logger()
    asyncio.run(use_consumable_game(Path(snapshot), item, targets))


###############################################################################
@main.command("equip-gear")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--item", required=True, help="装备物名称")
def equip_gear(snapshot: str, item: str) -> None:
    """装备装备物（骨架）。"""
    _setup_logger()
    asyncio.run(equip_gear_game(Path(snapshot), item))


###############################################################################
@main.command("retreat")
@click.option("--snapshot", required=True, help="存档目录路径")
def retreat(snapshot: str) -> None:
    """主动撤退（骨架）。"""
    _setup_logger()
    asyncio.run(retreat_game(Path(snapshot)))


###############################################################################
@main.command("next-dungeon")
@click.option("--snapshot", required=True, help="存档目录路径")
def next_dungeon(snapshot: str) -> None:
    """推进到下一个房间（骨架）。"""
    _setup_logger()
    asyncio.run(next_dungeon_game(Path(snapshot)))


###############################################################################
@main.command("exit-dungeon")
@click.option("--snapshot", required=True, help="存档目录路径")
def exit_dungeon(snapshot: str) -> None:
    """退出副本回到大厅（骨架）。"""
    _setup_logger()
    asyncio.run(exit_dungeon_game(Path(snapshot)))
