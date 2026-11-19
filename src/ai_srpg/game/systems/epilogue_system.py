"""Pipeline 收尾：记录角色分布。"""

from typing import final, override

from loguru import logger

from ...entitas import ExecuteProcessor
from ..entities import get_actors_by_stage_as_names
from .system_mixin import SystemMixin


@final
class EpilogueSystem(SystemMixin, ExecuteProcessor):
    """Pipeline 末端收尾系统；将来需要收尾检查时在这里追加。"""

    ############################################################################################################
    @override
    async def execute(self) -> None:
        """记录各舞台中的角色分布（树先序，空舞台也列出）。"""
        logger.debug("mapping = {}", get_actors_by_stage_as_names(self._game))
