"""实体详情查询接口。

两种读法共用同一条前置校验：房间存在 → 游戏存在 → 游戏名匹配；校验失败以
领域异常抛出，由 ``services.http_errors`` 统一映射为响应。
"""

from typing import List, Set, Type

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from ...entitas import Component, Entity, Matcher
from ...game.context import SRPGGame
from ...models import COMPONENT_TYPES
from ...session.errors import GameNotFoundError, RoomNotFoundError
from ...session.server import GameServer
from ..dependencies import CurrentGameServer
from .schemas import EntitiesDetailsResponse

################################################################################################################
entities_api_router = APIRouter()


################################################################################################################
def _require_game(game_server: GameServer, user_name: str, game_name: str) -> SRPGGame:
    """取当前可读的游戏实例；读路径不取房间锁。"""

    # get_room 同时刷新活跃时间，读路径上 has_room 与 get_room 之间没有 await
    room = game_server.get_room(user_name)
    if room is None:
        raise RoomNotFoundError(user_name)

    game = room.game
    if game is None:
        raise GameNotFoundError(user_name=user_name)

    if game.name != game_name:
        logger.error(f"game_name mismatch: user={user_name}, game={game_name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    return game


################################################################################################################
def _resolve_component_types(component_names: List[str]) -> List[Type[Component]]:
    """将组件名称列表解析为组件类型列表。

    遇到未注册的组件名称时，抛出 400 错误。
    """
    component_types: List[Type[Component]] = []
    invalid_names: List[str] = []

    for name in component_names:
        comp_type = COMPONENT_TYPES.get(name)
        if comp_type is None:
            invalid_names.append(name)
            continue
        component_types.append(comp_type)

    if invalid_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法组件名: {', '.join(invalid_names)}",
        )

    return component_types


################################################################################################################
@entities_api_router.get(
    path="/api/entities/v1/{user_name}/{game_name}/details",
    response_model=EntitiesDetailsResponse,
)
async def get_entities_details(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    entity_names: List[str] = Query(..., alias="entities"),
) -> EntitiesDetailsResponse:
    """按实体名批量查询实体详情（任何实体类型均可）。"""

    logger.info(f"/entities/v1/{user_name}/{game_name}/details: {entity_names}")

    if not entity_names or entity_names[0].strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个实体名称",
        )

    game = _require_game(game_server, user_name, game_name)

    entities: Set[Entity] = set()
    for entity_name in entity_names:
        entity = game.get_entity_by_name(entity_name)
        if entity is None:
            logger.error(f"entity not found: user={user_name}, entity={entity_name}")
            continue
        entities.add(entity)

    return EntitiesDetailsResponse(entities=game.serialize(entities))


################################################################################################################
@entities_api_router.get(
    path="/api/entities/v1/{user_name}/{game_name}/group",
    response_model=EntitiesDetailsResponse,
)
async def get_entities_group(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    all_of: List[str] = Query(default=[], alias="all_of"),
    any_of: List[str] = Query(default=[], alias="any_of"),
    none_of: List[str] = Query(default=[], alias="none_of"),
) -> EntitiesDetailsResponse:
    """按组件条件分组查询实体（all_of / any_of / none_of）。"""

    logger.info(
        f"/entities/v1/{user_name}/{game_name}/group: all_of={all_of}, any_of={any_of}, none_of={none_of}"
    )

    all_of = [name.strip() for name in all_of if name.strip()]
    any_of = [name.strip() for name in any_of if name.strip()]
    none_of = [name.strip() for name in none_of if name.strip()]

    if not all_of and not any_of and not none_of:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少提供一个组件条件",
        )

    game = _require_game(game_server, user_name, game_name)

    matcher = Matcher(
        all_of=_resolve_component_types(all_of) or None,
        any_of=_resolve_component_types(any_of) or None,
        none_of=_resolve_component_types(none_of) or None,
    )
    group = game.get_group(matcher)

    return EntitiesDetailsResponse(entities=game.serialize(group.entities))
