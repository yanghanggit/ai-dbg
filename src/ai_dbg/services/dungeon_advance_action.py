"""
副本推进模块 —— 推进到副本下一关卡

advance_dungeon 是推进副本的唯一入口。
"""

from typing import Tuple

from loguru import logger

from ..entitas import Matcher
from ..game.combat import (
    assert_no_residual_combat_state,
    set_character_hp,
)
from ..game.combat.state import create_combat
from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_combat,
    current_dungeon_name,
    current_dungeon_room,
    get_dungeon_entity,
    get_dungeon_room_by_index,
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


###################################################################################################################################################################
@prompt_builder
def _build_dungeon_advance_message(dungeon_name: str, next_stage_name: str) -> str:
    """生成副本推进到下一关卡的传送提示消息。"""
    return f"# 副本：{dungeon_name}，进入下一关卡场景：{next_stage_name}\n（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"


###################################################################################################################################################################
async def advance_dungeon(dbg_game: DBGGame) -> Tuple[bool, str]:
    """
    推进到副本的下一个关卡。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        logger.error("副本前进失败，当前没有副本实体")
        return False, "当前没有副本"
    dungeon_name = current_dungeon_name(dbg_game)

    # 当前房间必须有效
    current_room = current_dungeon_room(dbg_game)
    if current_room is None:
        logger.error("副本前进失败，尚未进入任何房间")
        return False, "尚未进入副本房间，无法推进"

    current_room_component = current_room.get(DungeonRoomComponent)
    assert current_room_component is not None, "当前房间缺少 DungeonRoomComponent"
    next_room_index = current_room_component.index + 1

    # 下一房间必须存在
    next_room = get_dungeon_room_by_index(dbg_game, next_room_index)
    if next_room is None:
        logger.error("副本前进失败，没有更多房间")
        return False, "副本已全部通关"

    next_room_component = next_room.get(DungeonRoomComponent)
    assert next_room_component is not None, "下一房间缺少 DungeonRoomComponent"
    assert next_room.has(
        DungeonComponent
    ), f"{next_room.name} 没有 DungeonComponent 组件！"

    # 确保存在队伍成员
    party_member_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert len(party_member_entities) > 0, "没有找到队伍成员"

    # 当前房间若是战斗房间，必须处于战斗后且已胜利
    leaving_combat = current_room_component.room_type == DungeonRoomType.COMBAT
    if leaving_combat:
        combat = current_dungeon_combat(dbg_game)
        if not combat.is_post_combat:
            logger.error("当前不处于战斗后状态，无法推进副本关卡")
            return False, "战斗未结束，无法推进"

        if combat.is_lost:
            logger.info("英雄失败，应该返回营地")
            return False, "战斗失败，无法推进"

        assert combat.is_won, "不可能出现的情况！"

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================

    # 切换当前房间标记
    current_room.remove(CurrentDungeonRoomComponent)
    next_room.replace(CurrentDungeonRoomComponent, next_room.name)

    # 生成并发送传送提示消息
    trans_message = _build_dungeon_advance_message(dungeon_name, next_room.name)
    for party_member in party_member_entities:
        add_human_message(
            dbg_game,
            party_member,
            HumanMessage(
                content=trans_message,
                dungeon_lifecycle_stage_advance=f"{dungeon_name}:{next_room.name}",
            ),
        )

        # 战斗中可能死亡，推进关卡时复活并恢复 1 点生命值
        if party_member.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member.name}")
            party_member.remove(DeathComponent)
            revived_stats = set_character_hp(party_member, 1)
            logger.info(
                f"恢复生命值: {party_member.name} 生命值 = {revived_stats.hp}/{revived_stats.max_hp}"
            )

    # 执行场景传送
    stage_transition(dbg_game, party_member_entities, next_room)

    # 离开战斗房间：保底断言 pipeline 已清理完毕，不应存在残留战斗临时组件
    if leaving_combat:
        assert_no_residual_combat_state(dbg_game)

    # 进入战斗房间时创建战斗实体并初始化
    if next_room_component.room_type == DungeonRoomType.COMBAT:
        create_combat(dbg_game, next_room)
    logger.info(f"advance_dungeon 完成: {dungeon_name}，进入第 {next_room_index} 关")
    return True, f"已前进到第 {next_room_index} 关"
