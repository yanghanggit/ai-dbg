"""Job 失败后的世界恢复。"""

import asyncio
from pathlib import Path
from typing import Optional

from ..game.assembly import create_dbg_game
from ..game.lifecycle import exit_game, initialize_game
from ..game.persistence import latest_snapshot_dir, restore_world
from ..game.persistence.latest import write_latest_snapshot
from ..game.persistence.snapshot import restore_from_snapshot
from ..models import PlayerSession
from ..paths import WORLDS_DIR
from ..session.events import PlayerSessionEventSink
from ..session.room import PlayerRoom
from ..session.store import SessionStore


###############################################################################
def latest_snapshot_for_room(room: PlayerRoom) -> Optional[Path]:
    """返回房间所属玩家/游戏最近一次成功世界快照。"""
    game = room.game
    if game is None:
        return None
    return latest_snapshot_dir(room.username, game.name)


###############################################################################
async def restore_room_from_snapshot(
    room: PlayerRoom,
    snapshot: Path,
    session: PlayerSession,
) -> None:
    """用快照重建 DBGGame，并替换房间中的旧实例。

    session 不参与回滚，仍然是同一个用户级对象。
    """
    world = await asyncio.to_thread(restore_world, snapshot)
    game_name = room.game.name if room.game is not None else str(world.blueprint.name)
    new_game = create_dbg_game(
        name=game_name,
        player_name=session.name,
        player_actor=session.actor or world.blueprint.player_actor,
        world=world,
        events=PlayerSessionEventSink(session, SessionStore()),
    )
    restore_from_snapshot(new_game)
    await initialize_game(new_game)

    old_game = room.game
    if old_game is not None:
        exit_game(old_game)
    room.bind(game=new_game, player_session=session)

    # 回滚后把“最近成功快照”指针也拨回该快照，避免下一次 job 使用已回滚的快照
    write_latest_snapshot(WORLDS_DIR, room.username, game_name, snapshot)
