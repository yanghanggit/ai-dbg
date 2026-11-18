"""实体创建、查询、序列化与蓝图构建。"""

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
    create_entity,
    destroy_entity,
    get_actor_entity,
    get_entity_by_name,
    get_player_entity,
    get_stage_entity,
    get_world_entity,
    resolve_stage_entity,
)
from .serialization import (
    restore_context,
    serialize_context,
    serialize_entities,
)

__all__ = [
    "build_from_blueprint",
    "create_actor_entities",
    "create_entity",
    "create_stage_entities",
    "destroy_entity",
    "get_actor_entity",
    "get_actors_by_stage",
    "get_actors_by_stage_as_names",
    "get_actors_in_stage",
    "get_entity_by_name",
    "get_player_entity",
    "get_stage_entity",
    "get_world_entity",
    "resolve_stage_entity",
    "restore_context",
    "serialize_context",
    "serialize_entities",
]
