"""Pipeline 收尾：记录角色分布并把实体状态同步回世界模型。"""

import json
from typing import Dict, Final, List, final, override

from loguru import logger

from ...entitas import ExecuteProcessor
from ..context import SRPGGame
from ..entities import (
    get_actors_by_stage,
)


@final
class EpilogueSystem(ExecuteProcessor):
    """Pipeline 末端收尾系统。

    记录角色分布日志并将实体状态同步回 world 模型。未来可在此扩展收尾检查。
    """

    ############################################################################################################
    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        """记录各场景中的角色分布情况到日志。"""
        actor_distribution = get_actors_by_stage(self._game)

        actor_distribution_info: Dict[str, List[str]] = {}
        for stage, actors in actor_distribution.items():
            actor_distribution_info[stage.name] = [actor.name for actor in actors]

        logger.warning(
            f"mapping = {json.dumps(actor_distribution_info, indent=2, ensure_ascii=False)}"
        )
