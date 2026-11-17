"""DBG AI 操作工具 —— 基于快照的无状态副本推进 CLI。

每条命令 = 读快照 → 执行动作 → 写新快照。世界状态在 .worlds/，用户级会话历史在 .sessions/。
存档位置：.worlds/{user}/{game}/{timestamp}/（含 world_state.json）
查存档：find .worlds -mindepth 3 -maxdepth 3 -type d | sort
日志：logs/run_agent_game_{timestamp}.log

==== 顶层命令 ====
  new             --game GAME --dungeon DUNGEON [--user NAME]   创建新游戏并直接进入副本首间
  stages          --snapshot PATH                                列出场景-角色映射（只读）
  compact-context --snapshot PATH --target ENTITY               手动压缩指定实体的 LLM 记忆
  enter-dungeon   --snapshot PATH --dungeon NAME                从大厅进入指定副本

==== 副本模式命令 ====
  combat-init     --snapshot PATH                               战斗房间初始化（INITIALIZATION → ONGOING）
  opening-init    --snapshot PATH                               开场房间初始化（叙事 + 环境）
  draw-cards      --snapshot PATH                               全员抽牌
  play-cards-specified --snapshot PATH --actor A [--card C] [--targets T...]
                       我方角色出一张牌（须给 --card）；怪物由 AI 决策出牌或过牌（可省略 --card）
  pass-turn       --snapshot PATH --actor A                     过牌/交出行动权（我方与怪物均适用）
  use-consumable  --snapshot PATH --item I [--targets T...]     使用消耗品
  equip-gear      --snapshot PATH --item I                      装备 GearItem
  retreat         --snapshot PATH                               主动撤退（结算为失败，成员死亡）
  next-dungeon    --snapshot PATH                               下一关（仅推进，不初始化新房间）
  exit-dungeon    --snapshot PATH                               退出副本 → 大厅（无论胜负）

==== 典型流程 ====
  新局：new --game Game1 --dungeon 副本.断桥渡口
  副本（战斗房间）：combat-init → draw-cards
        → 循环：按当前行动者 play-cards-specified / use-consumable / equip-gear，随后 pass-turn 交出行动权
          —— 出牌、用消耗品、装备均不结束行动窗口；所有存活角色都过牌后本回合结束，需再 draw-cards
          —— 怪物：play-cards-specified 触发 AI 决策。若 AI 出牌，需再 pass-turn(怪物) 交出行动权；
                  若 AI 自行过牌，系统已在同一次调用内完成过牌，不要再对其 pass-turn
        胜利 → next-dungeon → combat-init（或 opening-init，视新房间类型）
        失败 → exit-dungeon
        战斗中途撤退 → retreat → exit-dungeon
  副本（开场房间）：opening-init → next-dungeon
  退出副本：exit-dungeon → 回到大厅；再从大厅 enter-dungeon 开下一局"""

import asyncio
import datetime
import sys
from pathlib import Path
from typing import Final, Tuple

import click
from loguru import logger

from ai_dbg.game import restore_world
from ai_dbg.models import PlayerSession, WorldState
from ai_dbg.paths import LOGS_DIR, WORLDS_DIR
from ai_dbg.session import SessionStore

LOG_LEVEL: Final[str] = "DEBUG"


def _restore_snapshot(snapshot_path: Path) -> Tuple[WorldState, PlayerSession]:
    """读取世界快照，并从用户级 session store 取回独立会话历史。"""
    world = restore_world(snapshot_path)
    user_name = snapshot_path.parent.parent.name
    store = SessionStore()
    session = store.load_or_create(
        user_name,
        actor=world.blueprint.player_actor,
        game=str(world.blueprint.name),
    )
    session.set_context(
        actor=world.blueprint.player_actor,
        game=str(world.blueprint.name),
    )
    store.save_meta(session)
    return world, session


def _setup_logger(log_file_path: Path) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(log_file_path, level=LOG_LEVEL)
    logger.info(f"日志配置: 级别={LOG_LEVEL}, 文件路径={log_file_path}")


from ai_dbg.dbg_game_agent.combat import (
    draw_cards_game,
    equip_gear_game,
    init_combat_game,
    pass_turn_game,
    play_cards_specified_game,
    retreat_game,
    use_consumable_game,
)
from ai_dbg.dbg_game_agent.compact import compact_context_game
from ai_dbg.dbg_game_agent.core import create_and_initialize_game, stages_game
from ai_dbg.dbg_game_agent.dungeon import (
    enter_dungeon_game,
    exit_dungeon_game,
    next_dungeon_game,
)
from ai_dbg.dbg_game_agent.opening import (
    init_opening_game,
)


###############################################################################################################################################
@click.group()
def main() -> None:
    """AI 操作工具：基于快照驱动游戏推进。

    每条子命令读取一个存档快照，执行一次游戏动作，写出新的存档快照。
    查看可用存档：find .worlds -mindepth 3 -maxdepth 3 -type d | sort
    """


###############################################################################################################################################
@main.command("new")
@click.option(
    "--user",
    default=None,
    help="玩家用户名。默认为带时间戳的随机名称。",
)
@click.option(
    "--game",
    required=True,
    help="游戏名称（对应 BLUEPRINTS_DIR 下的文件名，如 Game1）。",
)
@click.option(
    "--dungeon",
    required=True,
    help="副本名称（对应 DUNGEONS_DIR 下的文件名，如 Dungeon1）。",
)
def new_game(user: str, game: str, dungeon: str) -> None:
    """创建新游戏实例并写入初始存档。执行后直接位于副本首间。"""

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    if user is None:
        user = f"cli-player-{_timestamp}"

    _save_dir = WORLDS_DIR / user / game / _timestamp
    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(create_and_initialize_game(user, game, dungeon, _save_dir))


###############################################################################################################################################
@main.command("stages")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def stages(snapshot: str) -> None:
    """打印各场景内角色名单（只读，不写新存档）。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")

    mapping = asyncio.run(stages_game(world, player_session))
    for stage_name, actor_names in mapping.items():
        click.echo(f"{stage_name}: {', '.join(actor_names)}")


###############################################################################################################################################
@main.command("compact-context")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--target",
    required=True,
    help="要压缩的目标实体名（角色/怪物/场景/世界，如 角色.顾知秋）",
)
def compact_context(snapshot: str, target: str) -> None:
    """手动压缩指定实体的 LLM 记忆并归档。与场景状态无关。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(compact_context_game(world, player_session, target, _save_dir))


###############################################################################################################################################
@main.command("enter-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--dungeon",
    required=True,
    help="副本名称（对应 DUNGEONS_DIR 下的 JSON 文件名，如 Dungeon1）",
)
def enter_dungeon(snapshot: str, dungeon: str) -> None:
    """进入指定副本第一关并归档（仅传送，不初始化房间）。下一步用 combat-init（战斗房间）或 opening-init（开场房间）。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(enter_dungeon_game(world, player_session, dungeon, _save_dir))


###############################################################################################################################################
@main.command("combat-init")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def combat_init(snapshot: str) -> None:
    """初始化战斗房间（INITIALIZATION → ONGOING）并归档。需进入战斗房间后、抽牌前使用。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(init_combat_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("draw-cards")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def draw_cards(snapshot: str) -> None:
    """全员抽牌并归档。需战斗进行中，下一步用 play-cards-specified。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(draw_cards_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("play-cards-specified")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="出牌角色全名（如 角色.某某）",
)
@click.option(
    "--card",
    required=False,
    default=None,
    help="要打出的卡牌名称（须存在于该角色手牌中）。仅我方角色必填；怪物由 AI 决策，可省略。",
)
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用（如 --targets 怪物.野猪）。怪物由 AI 决策，此参数仅占位。",
)
def play_cards_specified(
    snapshot: str, actor: str, card: str | None, targets: Tuple[str, ...]
) -> None:
    """指定角色出一张牌并归档。需战斗进行中且 draw-cards 之后。

    出牌不结束行动窗口——我方出牌后需再 pass-turn 才交出行动权。
    我方：必须用 --card 指定手牌。
    怪物：本命令触发其 AI 决策（选一张牌或过牌），省略 --card 即可。若 AI 出牌，行动权仍在该怪物，
    需再对其执行 pass-turn；若 AI 自行过牌，同一次调用内已完成过牌，不要再 pass-turn。
    """

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        play_cards_specified_game(
            world, player_session, actor, card, list(targets), _save_dir
        )
    )


###############################################################################################################################################
@main.command("pass-turn")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="过牌角色全名（如 角色.某某 或 怪物.某某）",
)
def pass_turn(snapshot: str, actor: str) -> None:
    """指定当前行动者过牌（交出行动权）并归档。需战斗进行中。

    适用于任意当前行动者（我方与怪物同等）：把当前行动槽标记为已完成、清空其剩余能量
    并推进 current_actor。所有存活角色都过牌后本回合结束，需再 draw-cards 开启下一回合。
    """

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(pass_turn_game(world, player_session, actor, _save_dir))


###############################################################################################################################################
@main.command("use-consumable")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--item",
    required=True,
    help="要使用的消耗品名称（须存在于队伍背包中）",
)
def use_consumable(snapshot: str, item: str) -> None:
    """由当前行动者使用队伍背包内的消耗品并归档：扣库存并把其内置卡牌物化进手牌，需再出牌才结算。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(use_consumable_game(world, player_session, item, _save_dir))


###############################################################################################################################################
@main.command("equip-gear")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--item",
    required=True,
    help="要装备的道具名称（须存在于玩家背包中，类型为 GearItem）",
)
def equip_gear(snapshot: str, item: str) -> None:
    """将 GearItem 转化为当前行动者（我方）的手牌并归档。需战斗进行中。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(equip_gear_game(world, player_session, item, _save_dir))


###############################################################################################################################################
@main.command("exit-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def exit_dungeon(snapshot: str) -> None:
    """退出副本返回大厅并归档。需战斗已结束（无论胜负）。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(exit_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("next-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def next_dungeon(snapshot: str) -> None:
    """进入副本下一关并归档（仅推进，不初始化新房间）。需前一关已胜利且存在下一关；下一步用 combat-init 或 opening-init。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(next_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("retreat")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def retreat(snapshot: str) -> None:
    """主动撤退（结算为失败、成员死亡）并归档。需战斗进行中；随后用 exit-dungeon 返回大厅。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(retreat_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("opening-init")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def opening_init(snapshot: str) -> None:
    """初始化开场房间（叙事 + 环境）并归档。需进入开场房间后使用（管道幂等，可重复调用）。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = _restore_snapshot(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(init_opening_game(world, player_session, _save_dir))


###############################################################################################################################################
if __name__ == "__main__":
    main()
