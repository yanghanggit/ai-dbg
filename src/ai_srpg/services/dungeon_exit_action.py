"""退出副本的外部入口：只负责把退出意图挂到玩家实体上。"""

from typing import Tuple

from loguru import logger

from ..game.context import SRPGGame
from ..game.entities import get_player_entity
from ..models import ExitDungeonAction


###################################################################################################################################################################
def activate_exit_dungeon(srpg_game: SRPGGame) -> Tuple[bool, str]:
    """挂载 ExitDungeonAction；房间、战斗、玩家与大厅校验由 system 负责。"""

    player_entity = get_player_entity(srpg_game)
    if player_entity is None:
        logger.error("退出副本失败：玩家实体不存在")
        return False, "玩家实体不存在"

    player_entity.replace(ExitDungeonAction, player_entity.name)
    return True, "退出副本请求已添加"
