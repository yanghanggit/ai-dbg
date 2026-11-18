"""实体查询、蓝图装配与场景分组查询。

实体创建/销毁/快照序列化是 ``SRPGGame``（``ECSContext``）自身的方法，不在此包内。
"""

from .blueprint import (
    build_from_blueprint,
    create_actor_entities,
    create_stage_entities,
)
from .queries import (
    get_actors_by_stage,
    get_actors_by_stage_as_names,
    get_actors_in_stage,
)
from .repository import (
    get_actor_entity,
    get_player_entity,
    get_stage_entity,
    get_world_entity,
    resolve_stage_entity,
)

__all__ = [
    "build_from_blueprint",
    "create_actor_entities",
    "create_stage_entities",
    "get_actor_entity",
    "get_actors_by_stage",
    "get_actors_by_stage_as_names",
    "get_actors_in_stage",
    "get_player_entity",
    "get_stage_entity",
    "get_world_entity",
    "resolve_stage_entity",
]
