"""
副本进入模块 —— 组建队伍并传送至副本第一关

enter_dungeon 是进入副本的唯一入口。
"""

from typing import Set, Tuple

from loguru import logger

from ..entitas import Entity, Matcher
from ..game.combat import assert_no_residual_combat_state
from ..game.combat.state import create_combat
from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_name,
    current_dungeon_room,
    dungeon_rooms,
    get_dungeon_entity,
    is_dungeon_setup_entities,
)
from ..game.entities import (
    get_player_entity,
)
from ..game.memory import (
    add_human_message,
)
from ..game.stage.transition import stage_transition
from ..models import (
    CurrentDungeonRoomComponent,
    DeathComponent,
    DungeonComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    HumanMessage,
    PartyMemberComponent,
)
from ..utils import prompt_builder
from .dungeon_spoils_actions import clear_party_spoils


###################################################################################################################################################################
@prompt_builder
def _build_dungeon_enter_message(dungeon_name: str, stage_name: str) -> str:
    """生成进入副本第一关的传送提示消息。"""
    return f"# 进入副本：{dungeon_name}，开始关卡场景：{stage_name}\n（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"


###################################################################################################################################################################
def enter_dungeon(dbg_game: DBGGame) -> Tuple[bool, str]:
    """组建队伍并传送至副本第一关，启动首个战斗序列。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    # 副本实体必须存在
    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        error_msg = "enter_dungeon 失败: 当前没有副本实体，请先调用 setup_dungeon"
        logger.error(error_msg)
        return False, error_msg
    dungeon_name = current_dungeon_name(dbg_game)

    # 副本尚未通过 setup_dungeon 创建实体
    assert is_dungeon_setup_entities(
        dbg_game
    ), f"{dungeon_name} 副本尚未 setup_entities，请先调用 setup_dungeon"
    if not is_dungeon_setup_entities(dbg_game):
        error_msg = (
            f"enter_dungeon 失败: {dungeon_name} 实体尚未创建，请先调用 setup_dungeon"
        )
        logger.error(error_msg)
        return False, error_msg

    # 尚未进入副本（当前房间标记必须为空）
    if current_dungeon_room(dbg_game) is not None:
        error_msg = f"enter_dungeon 失败: {dungeon_name} 已经进入副本"
        logger.error(error_msg)
        return False, error_msg

    # 副本无房间数据
    rooms = dungeon_rooms(dbg_game)
    if len(rooms) == 0:
        error_msg = f"enter_dungeon 失败: {dungeon_name} 没有房间数据"
        logger.error(error_msg)
        return False, error_msg

    # 首间
    enter_room = rooms[0]
    room_component = enter_room.get(DungeonRoomComponent)
    assert room_component is not None, f"{enter_room.name} 缺少 DungeonRoomComponent"
    assert enter_room.has(
        DungeonComponent
    ), f"{enter_room.name} 没有 DungeonComponent 组件！"

    # 确保此时不存在任何队伍标记（PartyMemberComponent）
    party_members = dbg_game.ecs.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities
    assert (
        len(party_members) == 0
    ), f"enter_dungeon 失败: 进入前已存在 {len(party_members)} 个队伍成员，请先退出当前副本"

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================

    # 选择队伍成员并挂载 PartyMemberComponent
    player_entity = get_player_entity(dbg_game)
    assert player_entity is not None, "玩家实体不存在！"
    party_member_entities: Set[Entity] = {player_entity}
    logger.info(f"玩家 {player_entity.name} 将参与本次副本")
    logger.info(
        f"最终队伍成员 ({len(party_member_entities)}): {[e.name for e in party_member_entities]}"
    )
    for party_member in party_member_entities:
        party_member.replace(PartyMemberComponent, party_member.name)
        logger.debug(
            f"将 {party_member.name} 添加 PartyMemberComponent 组件，标记为队伍成员"
        )

    assert len(party_member_entities) > 0, "没有选择任何队伍成员，无法进入副本"
    for party_member in party_member_entities:
        assert not party_member.has(
            DeathComponent
        ), f"队伍成员 {party_member.name} 已死亡，无法进入副本"
        logger.info(f"队伍成员: {party_member.name}，目标副本：{dungeon_name}")

    # 标记当前房间（-1 → 0）
    enter_room.replace(CurrentDungeonRoomComponent, enter_room.name)

    # 生成并发送传送提示消息
    trans_message = _build_dungeon_enter_message(dungeon_name, enter_room.name)
    for party_member in party_member_entities:
        add_human_message(
            dbg_game,
            party_member,
            HumanMessage(content=trans_message, dungeon_lifecycle_entry=dungeon_name),
        )

    # 执行场景传送
    stage_transition(dbg_game, party_member_entities, enter_room)

    # 保底断言：pipeline 理应已清理完毕，此时不应存在残留战斗临时组件
    assert_no_residual_combat_state(dbg_game)

    # 若是战斗房间则创建战斗实体并初始化；开场房间仅做场景传送，不创建战斗
    if room_component.room_type == DungeonRoomType.COMBAT:
        create_combat(dbg_game, enter_room)
    else:
        # 进入非战斗房间时，清理上一局残留的奖励状态（奖励与房间生命周期绑定）
        cleared = clear_party_spoils(dbg_game)
        if cleared:
            logger.info(f"enter_dungeon: 已清理残留奖励状态: {cleared}")
        logger.info(
            f"enter_dungeon: 首间为 {room_component.room_type.value!r} 房间，跳过战斗初始化，等待玩家手动推进"
        )

    logger.info(f"enter_dungeon 完成: {dungeon_name}")
    return True, f"成功进入副本: {dungeon_name}"
