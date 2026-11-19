"""客户端 CLI：通过 HTTP 驱动游戏服务器。

每条子命令只发一次请求、进程内不保持状态；路径里的 ``user_name`` 就是身份。
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import click
from procrastinate.jobs import Status as JobStatus

from ai_srpg.services.api.schemas import (
    JobDetail,
    RoomStateResponse,
    ServerInfoResponse,
)
from ai_srpg.srpg_game_client.core import GameClient, GameClientError, JobWaitTimeout

DEFAULT_SERVER = "http://127.0.0.1:8000"


###############################################################################
@dataclass(frozen=True)
class Options:
    """全局选项上下文。"""

    server: str
    timeout: float
    as_json: bool


def _client(options: Options) -> GameClient:
    """构造客户端；测试可替换这一层。"""
    return GameClient(options.server, timeout=options.timeout)


@contextmanager
def _connected(options: Options) -> Iterator[GameClient]:
    """使用一次客户端，退出即关闭连接。"""
    client = _client(options)
    try:
        yield client
    finally:
        client.close()


###############################################################################
class _ClientGroup(click.Group):
    """把客户端异常统一转成 ClickException（非 0 退出码 + 一行提示）。"""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (GameClientError, JobWaitTimeout) as exc:
            raise click.ClickException(str(exc)) from exc


###############################################################################
@click.group(cls=_ClientGroup)
@click.option(
    "--server",
    default=DEFAULT_SERVER,
    show_default=True,
    envvar="AI_SRPG_SERVER_URL",
    show_envvar=True,
    help="服务端基地址",
)
@click.option("--timeout", default=30.0, show_default=True, help="单次请求超时（秒）")
@click.option("--json", "as_json", is_flag=True, help="输出原始 JSON（供脚本消费）")
@click.pass_context
def main(ctx: click.Context, server: str, timeout: float, as_json: bool) -> None:
    """通过 HTTP 驱动游戏服务器（与离线 agent-game CLI 平级）。"""
    ctx.obj = Options(server=server, timeout=timeout, as_json=as_json)


###############################################################################
def _options(ctx: click.Context) -> Options:
    options = ctx.obj
    assert isinstance(options, Options), "上下文缺少客户端选项"
    return options


def _dump(options: Options, model: Any) -> None:
    click.echo(model.model_dump_json(indent=2))


def _print_state(options: Options, state: RoomStateResponse) -> None:
    if options.as_json:
        _dump(options, state)
        return
    click.echo(f"user:     {state.user_name}")
    click.echo(f"room:     {state.room_id} (owner: {state.owner})")
    click.echo(f"game:     {state.game or '-'}")
    click.echo(f"messages: {state.session_event_sequence}")
    for seat in state.seats:
        click.echo(f"seat:     {seat.user_name} -> {seat.actor or '-'}")


def _print_job(options: Options, detail: JobDetail) -> None:
    if options.as_json:
        _dump(options, detail)
        return
    click.echo(f"status: {detail.status.value}")
    if detail.error:
        click.echo(f"error:  {detail.error}")
    for event in detail.events:
        system = f" {event.system}" if event.system else ""
        message = f" {event.message}" if event.message else ""
        click.echo(f"  {event.kind}{system}{message}")


###############################################################################
@main.command("info")
@click.pass_context
def info(ctx: click.Context) -> None:
    """查看服务端自描述（版本与已注册路由）。"""
    options = _options(ctx)
    with _connected(options) as client:
        server: ServerInfoResponse = client.server_info()

    if options.as_json:
        _dump(options, server)
        return

    click.echo(f"{server.service} v{server.version} @ {server.base_url}")
    for route in server.routes:
        click.echo(f"  {','.join(sorted(route.methods)):<12} {route.path}")


###############################################################################
@main.command("enter")
@click.argument("user_name")
@click.pass_context
def enter(ctx: click.Context, user_name: str) -> None:
    """进入房间（=登录）；不存在则创建，已存在则复用。"""
    options = _options(ctx)
    with _connected(options) as client:
        _print_state(options, client.enter_room(user_name))


@main.command("state")
@click.argument("user_name")
@click.pass_context
def state(ctx: click.Context, user_name: str) -> None:
    """查询房间状态。"""
    options = _options(ctx)
    with _connected(options) as client:
        _print_state(options, client.room_state(user_name))


@main.command("leave")
@click.argument("user_name")
@click.pass_context
def leave(ctx: click.Context, user_name: str) -> None:
    """离开房间（已落库的快照保留）。"""
    options = _options(ctx)
    with _connected(options) as client:
        client.leave_room(user_name)
    click.echo(f"left: {user_name}")


###############################################################################
@main.command("open")
@click.argument("user_name")
@click.argument("game_name")
@click.pass_context
def open_game(ctx: click.Context, user_name: str, game_name: str) -> None:
    """开局：加载最新快照，没有快照则从蓝图新建；幂等。"""
    options = _options(ctx)
    with _connected(options) as client:
        _print_state(options, client.open_game(user_name, game_name))


@main.command("advance")
@click.argument("user_name")
@click.argument("game_name")
@click.option(
    "--wait/--no-wait", default=True, show_default=True, help="是否等待 job 终态"
)
@click.option("--wait-timeout", default=120.0, show_default=True, help="等待超时（秒）")
@click.option("--interval", default=0.3, show_default=True, help="轮询间隔（秒）")
@click.pass_context
def advance(
    ctx: click.Context,
    user_name: str,
    game_name: str,
    wait: bool,
    wait_timeout: float,
    interval: float,
) -> None:
    """派发一次 pass；默认等待 job 到达终态并打印事件。"""
    options = _options(ctx)
    with _connected(options) as client:
        job_id = client.advance(user_name, game_name)
        if not wait:
            click.echo(f"job: {job_id}")
            return
        detail = client.wait_job(job_id, timeout=wait_timeout, interval=interval)

    click.echo(f"job: {job_id}")
    _print_job(options, detail)


@main.command("play")
@click.argument("user_name")
@click.argument("game_name")
@click.option("--rounds", default=1, show_default=True, help="推进轮数")
@click.option(
    "--wait-timeout", default=120.0, show_default=True, help="单轮等待超时（秒）"
)
@click.option("--interval", default=0.3, show_default=True, help="轮询间隔（秒）")
@click.pass_context
def play(
    ctx: click.Context,
    user_name: str,
    game_name: str,
    rounds: int,
    wait_timeout: float,
    interval: float,
) -> None:
    """无人值守推进：自动进入房间、开局，然后连续跑 N 轮 pass。"""
    options = _options(ctx)
    with _connected(options) as client:
        _print_state(options, client.enter_room(user_name))
        _print_state(options, client.open_game(user_name, game_name))

        for round_index in range(1, rounds + 1):
            job_id = client.advance(user_name, game_name)
            detail = client.wait_job(job_id, timeout=wait_timeout, interval=interval)
            latest = client.snapshots(user_name, game_name, limit=1)
            snapshot = latest[0].id if latest else "-"
            status = detail.status.value
            click.echo(
                f"round {round_index}: job={job_id} status={status} snapshot={snapshot}"
            )
            if detail.status != JobStatus.SUCCEEDED:
                reason = detail.error or detail.status.value
                raise click.ClickException(f"第 {round_index} 轮未成功: {reason}")


###############################################################################
@main.command("snapshots")
@click.argument("user_name")
@click.argument("game_name")
@click.option("--limit", default=20, show_default=True, help="最多返回多少条")
@click.pass_context
def snapshots(ctx: click.Context, user_name: str, game_name: str, limit: int) -> None:
    """列出该局的快照元数据（时间倒序）。"""
    options = _options(ctx)
    with _connected(options) as client:
        items = client.snapshots(user_name, game_name, limit=limit)

    if options.as_json:
        for item in items:
            click.echo(item.model_dump_json())
        return

    for item in items:
        created = item.created_at.isoformat()
        click.echo(
            f"{item.id:<8} {created} entities={item.entity_count} memories={item.memory_count}"
        )


@main.command("messages")
@click.argument("user_name")
@click.option(
    "--since", "since", default=0, show_default=True, help="上次读到的最大序号"
)
@click.pass_context
def messages(ctx: click.Context, user_name: str, since: int) -> None:
    """增量读取用户级会话历史。"""
    options = _options(ctx)
    with _connected(options) as client:
        items = client.session_messages(user_name, since=since)

    if options.as_json:
        for item in items:
            click.echo(item.model_dump_json())
        return

    if not items:
        click.echo("(no messages)")
        return
    for item in items:
        click.echo(f"{item.sequence_id:<6} {item.game_name or '-'} {item.actor or '-'}")


###############################################################################
@main.command("job")
@click.argument("job_id", type=int)
@click.pass_context
def job(ctx: click.Context, job_id: int) -> None:
    """查询单个 job 的状态与执行事件。"""
    options = _options(ctx)
    with _connected(options) as client:
        detail = client.job(job_id)
    _print_job(options, detail)


###############################################################################
if __name__ == "__main__":
    main()
