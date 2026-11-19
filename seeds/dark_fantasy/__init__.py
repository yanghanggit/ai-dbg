"""黑暗幻想故事：一套故事级设定，下挂若干剧本。

故事级（``story``）承载战役设定、全局规则与世界职责，对本故事下所有剧本生效；
每个剧本提供自己的世界、舞台与角色，并暴露一个蓝图构建入口。
"""

from typing import Callable, Dict, Final

from ai_srpg.models import Blueprint

from . import mercenary_camp

#: 剧本名 → 该剧本的蓝图构建入口
SCENARIOS: Final[Dict[str, Callable[[str], Blueprint]]] = {
    "mercenary_camp": mercenary_camp.create_blueprint,
}

###############################################################################
__all__ = ["SCENARIOS"]
