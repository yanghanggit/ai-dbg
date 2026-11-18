"""SRPG AI 操作工具 —— 快照驱动的离线游戏推进 CLI（骨架）。

只保留命令面、参数与日志骨架：每条子命令把参数交给 `srpg_game_agent`
的动作骨架，后者只记录调用，不读写存档、不推进世界。
待数据层与 SRPG 规则落地后，在动作层填充实现。

命令一览：
  new              创建新游戏
  stages           列出场景-角色映射
  compact-context  手动压缩指定实体的 LLM 记忆
  opening-init     开场房间初始化
  combat-init      战斗房间初始化
  pass-turn        交出行动权
  use-consumable   使用消耗品
  retreat          主动撤退
"""

import asyncio
import datetime
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any, Coroutine, Final

import click
from loguru import logger

from ai_srpg.llm.call_context import llm_call_trace
from ai_srpg.llm.call_records import find_llm_call, iter_llm_call_records
from ai_srpg.paths import LOGS_DIR
from ai_srpg.srpg_game_agent.combat import (
    init_combat_game,
    pass_turn_game,
    retreat_game,
    use_consumable_game,
)
from ai_srpg.srpg_game_agent.compact import compact_context_game
from ai_srpg.srpg_game_agent.core import create_and_initialize_game, stages_game
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
def _run_game(
    coro: Coroutine[Any, Any, Any],
    *,
    command: str,
    user: str = "",
    game: str = "",
) -> Any:
    """在 CLI 作用域的 trace 中执行游戏动作。"""
    with llm_call_trace(
        scope="cli",
        scope_id=str(os.getpid()),
        command=command,
        user=user,
        game=game,
    ):
        return asyncio.run(coro)


###############################################################################
@click.group()
def main() -> None:
    """AI 操作工具：快照驱动的离线游戏推进（当前为骨架，仅记录调用）。"""


###############################################################################
@main.command("llm-calls")
@click.option("--limit", default=20, show_default=True, help="最多显示多少条")
@click.option("--label", default=None, help="按 label 精确过滤")
@click.option("--user", default=None, help="按用户过滤")
@click.option("--game", default=None, help="按游戏过滤")
@click.option("--command", default=None, help="按命令/动作过滤")
@click.option("--loop-id", default=None, help="按 agent loop 过滤")
@click.option("--round", "round_num", type=int, default=None, help="按 loop 轮次过滤")
@click.option("--scope", default=None, help="按 cli / room 过滤")
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]),
    default=None,
    help="起始时间（含）",
)
@click.option(
    "--until",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]),
    default=None,
    help="结束时间（含）",
)
@click.option("--json", "as_json", is_flag=True, help="逐行输出完整 JSON")
def llm_calls(
    limit: int,
    label: str | None,
    user: str | None,
    game: str | None,
    command: str | None,
    loop_id: str | None,
    round_num: int | None,
    scope: str | None,
    since: datetime.datetime | None,
    until: datetime.datetime | None,
    as_json: bool,
) -> None:
    """列出最近的 LLM 调用记录（查问题 / 调提示词）。"""
    records = list(
        itertools.islice(
            iter_llm_call_records(
                label=label,
                user=user,
                game=game,
                command=command,
                scope=scope,
                loop_id=loop_id,
                round_num=round_num,
                since=since,
                until=until,
            ),
            limit,
        )
    )
    if not records:
        click.echo("（没有 llm call 记录）")
        return
    if as_json:
        for record in records:
            click.echo(record.model_dump_json())
        return
    for record in records:
        status = "ERR" if record.response.get("error") else "OK"
        tokens = (record.usage or {}).get("total_tokens", "-")
        fields = [
            f"{record.created_at.astimezone():%Y-%m-%d %H:%M:%S}",
            record.request_id[:8],
            f"{status:<3}",
            f"{record.elapsed_ms:>6}ms",
            f"{str(tokens):>6}tok",
            f"{record.trace.scope or '-':<4}",
            record.label,
        ]
        click.echo("  ".join(fields))


###############################################################################
@main.command("llm-call")
@click.argument("request_id")
@click.option("--json", "as_json", is_flag=True, help="输出完整 JSON")
def llm_call(request_id: str, as_json: bool) -> None:
    """查看一条 LLM 调用记录（支持完整 id 或唯一前缀）。"""
    record = find_llm_call(request_id)
    if record is None:
        raise click.ClickException(f"找不到记录: {request_id}")

    if as_json:
        click.echo(record.model_dump_json(indent=2))
        return

    click.echo(f"request_id: {record.request_id}")
    click.echo(f"time:       {record.created_at.astimezone():%Y-%m-%d %H:%M:%S}")
    if record.started_at is not None:
        click.echo(f"started:    {record.started_at.astimezone():%Y-%m-%d %H:%M:%S}")
    click.echo(f"label:      {record.label}")
    click.echo(f"model:      {record.model or '(provider default)'}")
    click.echo(f"elapsed:    {record.elapsed_ms}ms")
    if record.context_usage_ratio is not None:
        click.echo(f"context:    {record.context_usage_ratio:.2%}")
    trace = record.trace.model_dump(exclude_defaults=True)
    if trace:
        click.echo(f"trace:      {json.dumps(trace, ensure_ascii=False)}")
    if record.usage:
        click.echo(f"usage:      {json.dumps(record.usage, ensure_ascii=False)}")

    error = record.response.get("error")
    if error:
        click.echo(f"error:      {json.dumps(error, ensure_ascii=False)}")

    for message in record.messages:
        click.echo(f"\n===== {message.get('type', '?')} =====")
        click.echo(message.get("content") or "")
        tool_calls = (message.get("additional_kwargs") or {}).get("tool_calls")
        if tool_calls:
            click.echo(json.dumps(tool_calls, ensure_ascii=False, indent=2))

    ai_message = record.response.get("ai_message") or {}
    click.echo("\n===== ai =====")
    click.echo(ai_message.get("content") or "")
    tool_calls = ai_message.get("additional_kwargs", {}).get("tool_calls")
    if tool_calls:
        click.echo(json.dumps(tool_calls, ensure_ascii=False, indent=2))
    reasoning = ai_message.get("additional_kwargs", {}).get("reasoning_content")
    if reasoning:
        click.echo("\n===== reasoning =====")
        click.echo(reasoning)


###############################################################################
@main.command("new")
@click.option("--user", default=None, help="玩家用户名。默认为带时间戳的随机名称。")
@click.option(
    "--game", required=True, help="游戏名称（对应 BLUEPRINTS_DIR 下的文件名）。"
)
def new_game(user: str | None, game: str) -> None:
    """创建新游戏（骨架）。"""
    _setup_logger()
    _run_game(
        create_and_initialize_game(user or "skeleton", game),
        command="new",
        user=user or "skeleton",
        game=game,
    )


###############################################################################
@main.command("stages")
@click.option("--snapshot", required=True, help="存档目录路径")
def stages(snapshot: str) -> None:
    """列出场景-角色映射（骨架）。"""
    _setup_logger()
    mapping = _run_game(stages_game(Path(snapshot)), command="stages")
    for stage_name, actor_names in mapping.items():
        click.echo(f"{stage_name}: {', '.join(actor_names)}")


###############################################################################
@main.command("compact-context")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--target", required=True, help="要压缩的目标实体名")
def compact_context(snapshot: str, target: str) -> None:
    """手动压缩指定实体的 LLM 记忆（骨架）。"""
    _setup_logger()
    _run_game(compact_context_game(Path(snapshot), target), command="compact-context")


###############################################################################
@main.command("combat-init")
@click.option("--snapshot", required=True, help="存档目录路径")
def combat_init(snapshot: str) -> None:
    """战斗房间初始化（骨架）。"""
    _setup_logger()
    _run_game(init_combat_game(Path(snapshot)), command="combat-init")


###############################################################################
@main.command("opening-init")
@click.option("--snapshot", required=True, help="存档目录路径")
def opening_init(snapshot: str) -> None:
    """开场房间初始化（骨架）。"""
    _setup_logger()
    _run_game(init_opening_game(Path(snapshot)), command="opening-init")


###############################################################################
@main.command("pass-turn")
@click.option("--snapshot", required=True, help="存档目录路径")
@click.option("--actor", required=True, help="交出行动权的角色全名")
def pass_turn(snapshot: str, actor: str) -> None:
    """交出行动权（骨架）。"""
    _setup_logger()
    _run_game(pass_turn_game(Path(snapshot), actor), command="pass-turn")


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
    _run_game(
        use_consumable_game(Path(snapshot), item, targets), command="use-consumable"
    )


###############################################################################
@main.command("retreat")
@click.option("--snapshot", required=True, help="存档目录路径")
def retreat(snapshot: str) -> None:
    """主动撤退（骨架）。"""
    _setup_logger()
    _run_game(retreat_game(Path(snapshot)), command="retreat")
