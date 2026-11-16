"""
副本退出模块 —— 退出副本并传送角色回大厅

exit_dungeon 是退出副本的唯一入口。
"""

from typing import Tuple

from loguru import logger

from ..entitas import Matcher
from ..game.combat import (
    assert_no_residual_combat_state,
    compute_character_stats,
    set_character_hp,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_combat,
    current_dungeon_name,
    current_dungeon_room,
    get_dungeon_entity,
    is_current_room_dungeon_combat,
)
from ..game.memory import (
    add_human_message,
)
from ..game.stage.transition import stage_transition
from ..models import (
    DeathComponent,
    HumanMessage,
    LobbyComponent,
    PartyMemberComponent,
    SpoilsComponent,
)
from ..utils import prompt_builder


###################################################################################################################################################################
@prompt_builder
def _build_dungeon_exit_message(dungeon_name: str, lobby_stage_name: str) -> str:
    """生成退出副本返回大厅的提示消息。"""
    return f"# 提示！副本：{dungeon_name} 结束，返回大厅：{lobby_stage_name}\n（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"


###################################################################################################################################################################
def exit_dungeon(dbg_game: DBGGame) -> Tuple[bool, str]:
    """
    退出副本并将角色传送回大厅。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        logger.error("退出副本失败，当前没有副本实体")
        return False, "当前没有副本"

    # 当前房间必须有效
    current_room = current_dungeon_room(dbg_game)
    if current_room is None:
        logger.error("退出副本失败，尚未进入任何房间")
        return False, "尚未进入副本房间，无法退出"

    # 战斗房间必须处于战斗后状态才能退出（无论胜负）
    if is_current_room_dungeon_combat(dbg_game):
        combat = current_dungeon_combat(dbg_game)
        if not combat.is_post_combat:
            logger.error("当前不处于战斗后状态，无法退出副本！必须先完成战斗。")
            return False, "战斗未结束，无法退出"

    # 确保存在队伍成员
    party_member_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert len(party_member_entities) > 0, "没有找到队伍成员"

    # 确保存在大厅场景
    lobby_stages = dbg_game.ecs.get_group(
        Matcher(all_of=[LobbyComponent])
    ).entities.copy()
    assert len(lobby_stages) >= 1, "必须存在至少一个大厅场景！"
    dest_stage = next(iter(lobby_stages))

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================
    dungeon_name = current_dungeon_name(dbg_game)

    # 传送队伍成员回大厅
    for party_member_entity in party_member_entities:
        add_human_message(
            dbg_game,
            party_member_entity,
            HumanMessage(
                content=_build_dungeon_exit_message(dungeon_name, dest_stage.name),
                dungeon_lifecycle_completion=dungeon_name,
            ),
        )
        stage_transition(dbg_game, {party_member_entity}, dest_stage)

    # 恢复所有队伍成员状态
    for party_member_entity in party_member_entities:
        if party_member_entity.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member_entity.name}")
            party_member_entity.remove(DeathComponent)

        full_stats = compute_character_stats(party_member_entity)
        set_character_hp(party_member_entity, full_stats.max_hp)
        logger.info(
            f"恢复满血: {party_member_entity.name} 生命值 = {full_stats.max_hp}/{full_stats.max_hp}"
        )

        assert party_member_entity.has(PartyMemberComponent)
        party_member_entity.remove(PartyMemberComponent)
        logger.info(f"从队伍移除: {party_member_entity.name}")

        # 清理仅在本局副本队伍内才有意义的奖励状态（SpoilsComponent）
        if party_member_entity.has(SpoilsComponent):
            party_member_entity.remove(SpoilsComponent)
            logger.info(f"清理副本奖励状态（Spoils）: {party_member_entity.name}")

    # 离开战斗房间：保底断言 pipeline 已清理完毕，不应存在残留战斗临时组件
    if is_current_room_dungeon_combat(dbg_game):
        assert_no_residual_combat_state(dbg_game)

    logger.info(f"exit_dungeon 完成: {dungeon_name}")
    return True, "成功退出副本"
