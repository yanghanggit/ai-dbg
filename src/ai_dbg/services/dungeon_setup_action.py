"""
副本实体创建模块

负责根据静态副本定义创建游戏实体（副本、房间、敌人、场景）。
"""

import uuid
from typing import Tuple

from loguru import logger

from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_room,
    get_dungeon_entity,
    is_dungeon_setup_entities,
    is_player_in_dungeon_stage,
)
from ..game.entities import (
    create_actor_entities,
    create_entity,
    create_stage_entities,
    get_actor_entity,
    get_stage_entity,
)
from ..models import (
    ActorType,
    Dungeon,
    DungeonComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    DungeonRunComponent,
    IdentityComponent,
    StageType,
)
from ..paths import DUNGEONS_DIR


###################################################################################################################################################################
def setup_dungeon(dbg_game: DBGGame, dungeon_name: str) -> Tuple[bool, str]:
    """从文件加载副本定义，并创建副本/房间/场景/敌人实体。（幂等）"""
    # 1. 校验名称并加载文件
    if not dungeon_name:
        error_msg = "setup_dungeon 失败: dungeon_name 为空"
        logger.error(error_msg)
        return False, error_msg

    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if not dungeon_path.exists():
        error_msg = f"setup_dungeon 失败: 副本文件不存在 {dungeon_path}"
        logger.error(error_msg)
        return False, error_msg

    dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))

    if len(dungeon.rooms) == 0:
        error_msg = f"setup_dungeon 失败: {dungeon.name} 没有关卡数据"
        logger.error(error_msg)
        return False, error_msg

    if not dungeon.name:
        error_msg = "setup_dungeon 失败: 副本名为空"
        logger.error(error_msg)
        return False, error_msg

    # 守护：已有副本实体时只允许同名的幂等返回
    existing_dungeon = get_dungeon_entity(dbg_game)
    if existing_dungeon is not None:
        if current_dungeon_room(dbg_game) is not None:
            error_msg = f"setup_dungeon 失败: 当前副本 {existing_dungeon.name!r} 正在进行中，请先退出"
            logger.error(error_msg)
            return False, error_msg
        if existing_dungeon.name != dungeon.name:
            error_msg = f"setup_dungeon 失败: 已存在副本实体 {existing_dungeon.name!r}，不能再创建 {dungeon.name!r}"
            logger.error(error_msg)
            return False, error_msg
        if is_dungeon_setup_entities(dbg_game):
            logger.debug(f"setup_dungeon: {dungeon.name} 实体已创建，跳过")
            return True, f"副本实体已存在，跳过创建: {dungeon.name}"
        error_msg = f"setup_dungeon 失败: 副本 {dungeon.name!r} 实体不完整"
        logger.error(error_msg)
        return False, error_msg

    assert not is_player_in_dungeon_stage(
        dbg_game
    ), "setup_dungeon 失败: 玩家已在副本场景中！"

    # 2. 验证：所有 actor 必须是 MONSTER 类型，所有关卡场景必须是 DUNGEON 类型
    for room in dungeon.rooms:
        for actor in room.stage.actors:
            actor_entity = get_actor_entity(dbg_game, actor.name)
            assert actor_entity is None, "actor_entity is not None"
            assert actor.type == ActorType.MONSTER, "actor_entity is not enemy type"

    for room in dungeon.rooms:
        stage_entity = get_stage_entity(dbg_game, room.stage.name)
        assert stage_entity is None, "stage_entity is not None"
        assert room.stage.type == StageType.DUNGEON, "stage_entity is not dungeon type"

    # 3. 创建副本实体
    dungeon_entity = create_entity(dbg_game, dungeon.name)
    dbg_game.world.entity_counter += 1
    dungeon_entity.replace(
        IdentityComponent,
        dungeon.name,
        dbg_game.world.entity_counter,
        str(uuid.uuid4()),
    )
    dungeon_entity.replace(
        DungeonRunComponent,
        dungeon.name,
        dungeon.profile,
        dungeon.created_at,
        dungeon.assets,
    )
    logger.debug(f"setup_dungeon: 已创建副本实体 {dungeon.name}")

    # 4. 创建场景与角色实体
    logger.debug(f"正在根据副本定义创建实体: {dungeon.name}")
    create_actor_entities(
        dbg_game, [actor for room in dungeon.rooms for actor in room.stage.actors]
    )
    create_stage_entities(dbg_game, [room.stage for room in dungeon.rooms])

    # 5. 给每个房间对应的 Stage 实体挂房间组件
    for index, room in enumerate(dungeon.rooms):
        stage_entity = get_stage_entity(dbg_game, room.stage.name)
        assert stage_entity is not None, f"{room.stage.name} 没有对应的 stage 实体！"
        assert stage_entity.has(
            DungeonComponent
        ), f"{room.stage.name} 没有 DungeonComponent 组件！"
        stage_entity.replace(
            DungeonRoomComponent,
            stage_entity.name,
            dungeon.name,
            index,
            DungeonRoomType(room.type),
        )

    logger.info(f"setup_dungeon 完成: {dungeon.name}")
    return True, f"副本实体创建完成: {dungeon.name}"
