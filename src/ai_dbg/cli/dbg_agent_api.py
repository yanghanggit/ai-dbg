"""DBG AI 代理的服务器 API 走查 CLI。

定位：「后端开发者/代理走查服务器 API」的入口。
- 一次性进程：每次调用 = 一次 HTTP 请求（+ 必要时等待 job），无 TTY、无界面。
- 状态在服务端内存里；本脚本不缓存世界状态，只按参数寻址（--user/--game）。
- 输出统一为 JSON；HTTP 4xx/5xx 的 detail 原样透出，并以非零退出码结束。

典型用法（入口 `ai-dbg-agent-api`，见 pyproject 的 [project.scripts]）：
    export AI_DBG_API_HOST=127.0.0.1 AI_DBG_API_PORT=8000
    uv run ai-dbg-agent-api login --user alice --game Game1
    uv run ai-dbg-agent-api new-game --user alice --game Game1 --dungeon 副本.断桥渡口
    uv run ai-dbg-agent-api status --user alice --game Game1
    uv run ai-dbg-agent-api dungeon start --user alice --game Game1 --dungeon 副本.腐谷鼠穴

HTTPS / JWT（连接层集中在一处）：
    --server-scheme https  （或 AI_DBG_API_SCHEME）
    --server-verify false  （自签证书；或传 CA bundle 路径 / AI_DBG_API_VERIFY）
    --token <jwt>          （或 AI_DBG_API_TOKEN，注入 Authorization: Bearer）

日志：``logs/run_agent_api_<timestamp>.log``（DEBUG；控制台级别由 AI_DBG_API_LOG_LEVEL 决定）。
命令分组：dungeon / opening / combat；`status` 会同时给出 suggested_actions；`job` 用于查看单个执行的状态与事件。
"""

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import click
import httpx
from loguru import logger

from ai_dbg.dbg_api_agent.config import server_config
from ai_dbg.dbg_api_agent.flow import suggest_actions
from ai_dbg.dbg_api_agent.server_client import (
    compact_context,
    dungeon_advance_stage,
    dungeon_combat_draw_cards,
    dungeon_combat_equip_gear,
    dungeon_combat_init,
    dungeon_combat_pass_turn,
    dungeon_combat_play_cards,
    dungeon_combat_retreat,
    dungeon_combat_use_consumable,
    dungeon_exit,
    dungeon_opening_init,
    fetch_blueprint_list,
    fetch_dungeon_list,
    fetch_job_detail,
    fetch_job_events,
    login,
    logout,
    new_game,
    start_dungeon,
    watch_job_until_done,
)
from ai_dbg.dbg_api_agent.status import build_status
from ai_dbg.paths import LOGS_DIR


########################################################################################################################
# 日志
########################################################################################################################
def _setup_logger() -> Path:
    """配置本进程日志：stderr 控制台 + ``logs/run_agent_api_<timestamp>.log`` 归档。

    - 控制台级别由 ``AI_DBG_API_LOG_LEVEL`` 控制（默认 WARNING，避免污染 agent 终端）；
    - 文件始终记录 DEBUG；文件名带秒级时间戳，与 run_game_server / run_agent_game 一致。
    注意：日志只写 stderr/文件，stdout 始终留给 JSON 结果。
    """
    logger.remove()
    console_level = os.environ.get("AI_DBG_API_LOG_LEVEL", "WARNING")
    logger.add(
        sys.stderr,
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"run_agent_api_{timestamp}.log"
    logger.add(log_file, level="DEBUG")
    return log_file


def _parse_verify(value: str) -> Union[bool, str]:
    """把 ``--server-verify`` 解析为 httpx 的 verify 参数。

    ``true/false``（大小写不敏感）→ bool；其余按 CA bundle 路径原样返回。
    """
    normalized = value.strip().lower()
    if normalized in ("false", "0", "no", "off"):
        return False
    if normalized in ("true", "1", "yes", "on", ""):
        return True
    return value


########################################################################################################################
# 输出与运行辅助
########################################################################################################################
def _emit(payload: Dict[str, Any], exit_code: int = 0) -> None:
    """把结果以 JSON 打印到 stdout；非零退出码用于让调用方/代理感知失败。"""
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if exit_code != 0:
        sys.exit(exit_code)


def _error_payload(action: str, error: Exception) -> Dict[str, Any]:
    """把异常转成结构化错误，HTTP 错误透出 status_code 与 detail。"""
    if isinstance(error, httpx.HTTPStatusError):
        detail: Any
        try:
            detail = error.response.json().get("detail")
        except Exception:
            detail = error.response.text
        return {
            "ok": False,
            "action": action,
            "status_code": error.response.status_code,
            "detail": detail,
            "error": str(error),
        }
    return {
        "ok": False,
        "action": action,
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _run(action: str, coro: Any) -> None:
    logger.info(f"执行动作: {action}")
    try:
        result = asyncio.run(coro)
    except Exception as error:  # noqa: BLE001 - 顶层兜底，转为结构化错误
        logger.error(f"动作失败: {action}: {type(error).__name__}: {error}")
        _emit(_error_payload(action, error), exit_code=1)
        return
    logger.info(f"动作成功: {action}")
    _emit({"ok": True, "action": action, "result": result})


async def _await_job(resp: Any) -> Dict[str, Any]:
    """统一处理「返回 job_id 的异步动作」：自动等待 job 终态。"""
    try:
        snapshot = await watch_job_until_done(resp.job_id)
    except Exception as error:
        # 失败也保留 job_id，客户端可继续 GET /api/jobs/v1/{job_id} 查看执行事件
        raise RuntimeError(f"job_id={resp.job_id}: {error}") from error
    return {
        "job_id": resp.job_id,
        "message": getattr(resp, "message", None),
        "status": snapshot.status.value,
    }


def _sync_result(resp: Any) -> Dict[str, Any]:
    """统一处理同步动作：返回其 message（若有）。"""
    return {"message": getattr(resp, "message", None)}


########################################################################################################################
# Click 选项装饰器
########################################################################################################################
def identity_options(func: Any) -> Any:
    """为命令加上 --user/--game（支持环境变量，默认从环境读取，便于一次导出多次调用）。"""
    func = click.option(
        "--game", envvar="AI_DBG_GAME", required=True, help="游戏名（蓝图名）"
    )(func)
    func = click.option("--user", envvar="AI_DBG_USER", required=True, help="用户名")(
        func
    )
    return func


########################################################################################################################
# 主命令组
########################################################################################################################
@click.group()
@click.option(
    "--server-host",
    envvar="AI_DBG_API_HOST",
    required=True,
    help="游戏服务器地址（或设 AI_DBG_API_HOST）",
)
@click.option(
    "--server-port",
    envvar="AI_DBG_API_PORT",
    type=int,
    required=True,
    help="游戏服务器端口（或设 AI_DBG_API_PORT）",
)
@click.option(
    "--server-scheme",
    envvar="AI_DBG_API_SCHEME",
    type=click.Choice(["http", "https"]),
    default="http",
    show_default=True,
    help="协议（或设 AI_DBG_API_SCHEME）",
)
@click.option(
    "--server-verify",
    envvar="AI_DBG_API_VERIFY",
    default="true",
    show_default=True,
    help="TLS 校验：true/false 或 CA bundle 路径（或设 AI_DBG_API_VERIFY）",
)
@click.option(
    "--token",
    envvar="AI_DBG_API_TOKEN",
    default=None,
    help="JWT 鉴权 Bearer token（或设 AI_DBG_API_TOKEN）",
)
@click.pass_context
def main(
    ctx: click.Context,
    server_host: str,
    server_port: int,
    server_scheme: str,
    server_verify: str,
    token: Optional[str],
) -> None:
    """DBG AI 代理的服务器 API 走查 CLI。"""
    server_config.host = server_host
    server_config.port = server_port
    server_config.scheme = server_scheme
    server_config.verify = _parse_verify(server_verify)
    server_config.auth_token = token
    log_file = _setup_logger()
    logger.info(
        f"命令={ctx.invoked_subcommand} 目标={server_config.base_url} TLS校验={server_config.verify} 鉴权={'bearer' if token else 'none'} 日志={log_file}"
    )


########################################################################################################################
# 顶层命令
########################################################################################################################
@main.command("login")
@identity_options
def login_cmd(user: str, game: str) -> None:
    """登录并在服务端创建房间（注意：会清掉该 user 已有房间）。"""

    async def go() -> Dict[str, Any]:
        return {"message": await login(user, game)}

    _run("login", go())


@main.command("logout")
@identity_options
def logout_cmd(user: str, game: str) -> None:
    """登出并销毁服务端房间。"""

    async def go() -> Dict[str, Any]:
        return {"message": await logout(user, game)}

    _run("logout", go())


@main.command("new-game")
@identity_options
@click.option("--dungeon", "dungeon_name", required=True, help="副本名（新局直接进入）")
def new_game_cmd(user: str, game: str, dungeon_name: str) -> None:
    """新建游戏并直接进入副本首间。需先 login。"""

    async def go() -> Dict[str, Any]:
        resp = await new_game(user, game, dungeon_name)
        return {
            "message": "新游戏已创建",
            "player_session": resp.player_session.model_dump(mode="json"),
            "blueprint": resp.blueprint.name,
            "dungeon": {
                "name": resp.dungeon.name,
                "current_room_index": resp.dungeon.current_room_index,
                "room_count": len(resp.dungeon.rooms),
            },
        }

    _run("new-game", go())


@main.command("status")
@identity_options
@click.option(
    "--actor", default=None, help="显式指定玩家角色名（默认按 PlayerComponent 反查）"
)
@click.option(
    "--messages-since",
    type=int,
    default=0,
    show_default=True,
    help="会话消息起始 sequence_id（0=全量）",
)
def status_cmd(user: str, game: str, actor: Optional[str], messages_since: int) -> None:
    """观测当前世界状态，并给出 suggested_actions。"""

    async def go() -> Dict[str, Any]:
        snapshot = await build_status(
            user, game, actor=actor, messages_since=messages_since
        )
        snapshot["suggested_actions"] = suggest_actions(snapshot)
        return snapshot

    _run("status", go())


@main.command("blueprint-list")
def blueprint_list_cmd() -> None:
    """列出可用蓝图。"""

    async def go() -> Any:
        resp = await fetch_blueprint_list()
        return resp.model_dump(mode="json")

    _run("blueprint-list", go())


@main.command("dungeon-list")
def dungeon_list_cmd() -> None:
    """列出可用副本。"""

    async def go() -> Any:
        resp = await fetch_dungeon_list()
        return resp.model_dump(mode="json")

    _run("dungeon-list", go())


@main.command("job")
@click.option("--job-id", type=int, required=True, help="要查询的 job id")
@click.option("--after-id", type=int, default=0, show_default=True, help="事件增量游标")
@click.option("--events-only", is_flag=True, help="只返回事件，不返回 job 状态")
def job_cmd(job_id: int, after_id: int, events_only: bool) -> None:
    """查询单个 job 的状态和执行事件。"""

    async def go() -> Dict[str, Any]:
        if events_only:
            events_resp = await fetch_job_events(job_id, after_id=after_id)
            return events_resp.model_dump(mode="json")
        detail_resp = await fetch_job_detail(job_id)
        return detail_resp.model_dump(mode="json")

    _run("job", go())


@main.command("compact")
@identity_options
@click.option("--target", "target", required=True, help="要压缩记忆的实体名")
def compact_cmd(user: str, game: str, target: str) -> None:
    """手动压缩指定实体的 LLM 记忆。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await compact_context(user, game, target))

    _run("compact", go())


########################################################################################################################
# 副本命令组
########################################################################################################################
@main.group("dungeon")
def dungeon_group() -> None:
    """副本生命周期动作。"""


@dungeon_group.command("start")
@identity_options
@click.option("--dungeon", "dungeon_name", required=True, help="副本名")
def dungeon_start_cmd(user: str, game: str, dungeon_name: str) -> None:
    """从大厅进入指定副本首间。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await start_dungeon(user, game, dungeon_name))

    _run("dungeon start", go())


@dungeon_group.command("exit")
@identity_options
def dungeon_exit_cmd(user: str, game: str) -> None:
    """退出副本，返回大厅。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_exit(user, game))

    _run("dungeon exit", go())


@dungeon_group.command("advance-stage")
@identity_options
def dungeon_advance_stage_cmd(user: str, game: str) -> None:
    """推进到下一关卡（战斗胜利后 / 非战斗房间可直接推进）。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await dungeon_advance_stage(user, game))

    _run("dungeon advance-stage", go())


########################################################################################################################
# 开场房间命令组
########################################################################################################################
@main.group("opening")
def opening_group() -> None:
    """开场房间动作。"""


@opening_group.command("init")
@identity_options
def opening_init_cmd(user: str, game: str) -> None:
    """初始化开场房间（叙事 + 环境）。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_opening_init(user, game))

    _run("opening init", go())


########################################################################################################################
# 战斗命令组
########################################################################################################################
@main.group("combat")
def combat_group() -> None:
    """战斗动作。"""


@combat_group.command("init")
@identity_options
def combat_init_cmd(user: str, game: str) -> None:
    """初始化战斗（进入 ONGOING）。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_combat_init(user, game))

    _run("combat init", go())


@combat_group.command("draw-cards")
@identity_options
def combat_draw_cards_cmd(user: str, game: str) -> None:
    """开启新回合并为全体抓牌。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_combat_draw_cards(user, game))

    _run("combat draw-cards", go())


@combat_group.command("play-cards")
@identity_options
@click.option("--actor", "actor_name", required=True, help="出牌角色名")
@click.option(
    "--card",
    "card_name",
    default="",
    help="卡名；怪物回合可留空，服务端自动决策",
)
@click.option("--target", "targets", multiple=True, help="目标实体名（可多次）")
def combat_play_cards_cmd(
    user: str, game: str, actor_name: str, card_name: str, targets: Tuple[str, ...]
) -> None:
    """让角色打出卡牌。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(
            await dungeon_combat_play_cards(
                user, game, actor_name, card_name, list(targets)
            )
        )

    _run("combat play-cards", go())


@combat_group.command("pass-turn")
@identity_options
@click.option("--actor", "actor_name", required=True, help="过牌角色名")
def combat_pass_turn_cmd(user: str, game: str, actor_name: str) -> None:
    """让角色过牌（结束其回合，推进行动权）。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_combat_pass_turn(user, game, actor_name))

    _run("combat pass-turn", go())


@combat_group.command("use-consumable")
@identity_options
@click.option("--item", "item_name", required=True, help="消耗品名")
def combat_use_consumable_cmd(user: str, game: str, item_name: str) -> None:
    """使用背包内消耗品（玩家级，不推进行动权；物化为手牌后需再出牌）。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(
            await dungeon_combat_use_consumable(user, game, item_name)
        )

    _run("combat use-consumable", go())


@combat_group.command("equip-gear")
@identity_options
@click.option("--item", "item_name", required=True, help="装备名")
def combat_equip_gear_cmd(user: str, game: str, item_name: str) -> None:
    """使用背包内装备（玩家级，不推进行动权）。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_combat_equip_gear(user, game, item_name))

    _run("combat equip-gear", go())


@combat_group.command("retreat")
@identity_options
def combat_retreat_cmd(user: str, game: str) -> None:
    """战斗撤退。"""

    async def go() -> Dict[str, Any]:
        return await _await_job(await dungeon_combat_retreat(user, game))

    _run("combat retreat", go())


if __name__ == "__main__":
    main()
