"""唯一的游戏流程装配：按业务顺序线性排列全部 system。

这里是游戏业务的核心执行序列。所有 system 每轮都按固定顺序执行，
由 system 自己判断当前 world 状态是否适用；调用方不再选择房间或动作 pipeline。
"""

from ..context import SRPGGame
from .manager import RPGGameProcessPipeline


def build_game_pipeline(srpg_game: SRPGGame) -> RPGGameProcessPipeline:
    """构建全局唯一的线性 system 流程。"""

    ### 不这样就循环引用：systems 依赖 game 领域模块，而 game 装配又依赖 systems。
    from ...systems.action_cleanup_system import ActionCleanupSystem
    from ...systems.combat_hand_cleanup_system import CombatHandCleanupSystem
    from ...systems.combat_outcome_system import CombatOutcomeSystem
    from ...systems.combat_pass_snapshot_system import CombatPassSnapshotSystem
    from ...systems.combat_pile_teardown_system import CombatPileTeardownSystem
    from ...systems.combat_post_combat_transition_system import (
        CombatPostCombatTransitionSystem,
    )
    from ...systems.combat_result_notice_system import CombatResultNoticeSystem
    from ...systems.combat_round_completion_system import CombatRoundCompletionSystem
    from ...systems.combat_round_start_system import (
        ActionOrderStrategy,
        CombatRoundStartSystem,
    )
    from ...systems.compact_context_action_system import CompactContextActionSystem
    from ...systems.context_compaction_system import ContextCompactionSystem
    from ...systems.death_system import DeathSystem
    from ...systems.destroy_entity_system import DestroyEntitySystem
    from ...systems.discard_cards_action_system import DiscardCardsActionSystem
    from ...systems.draw_cards_action_system import DrawCardsActionSystem
    from ...systems.environment_initialization_system import (
        EnvironmentInitializationSystem,
    )
    from ...systems.epilogue_system import EpilogueSystem
    from ...systems.equip_gear_item_action_system import (
        EquipGearItemActionSystem,
    )
    from ...systems.exhaust_cards_action_system import ExhaustCardsActionSystem
    from ...systems.exhaust_ethereal_cards_system import ExhaustEtherealCardsSystem
    from ...systems.exit_dungeon_action_system import ExitDungeonActionSystem
    from ...systems.fill_draw_pile_system import FillDrawPileSystem
    from ...systems.monster_combat_decision_system import MonsterCombatDecisionSystem
    from ...systems.pass_turn_action_system import PassTurnActionSystem
    from ...systems.play_cards_action_system import PlayCardsActionSystem
    from ...systems.play_cards_arbitration_system import PlayCardsArbitrationSystem
    from ...systems.player_combat_decision_system import PlayerCombatDecisionSystem
    from ...systems.prologue_system import PrologueSystem
    from ...systems.retreat_action_system import RetreatActionSystem
    from ...systems.room_init_system import RoomInitSystem
    from ...systems.teardown_dungeon_action_system import (
        TeardownDungeonActionSystem,
    )
    from ...systems.transfer_cards_action_system import TransferCardsActionSystem
    from ...systems.use_consumable_item_action_system import (
        UseConsumableItemActionSystem,
    )

    pipeline = RPGGameProcessPipeline()

    # ---------------------------------------------------------------------
    # 通用前置：每轮固定入口与场景环境补齐
    # ---------------------------------------------------------------------
    pipeline.add(PrologueSystem(srpg_game))
    pipeline.add(EnvironmentInitializationSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 房间初始化：开场角色感知 / 战斗角色牌堆与场景规则
    # ---------------------------------------------------------------------
    pipeline.add(RoomInitSystem(srpg_game))
    pipeline.add(FillDrawPileSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 战斗回合与决策
    # 注意：CombatRoundStartSystem 与 DrawCardsActionSystem 相邻、顺序不可对调：
    # 前者监听 DrawCardsAction 开启新回合，后者抓牌，顺序即因果链。
    # ---------------------------------------------------------------------
    pipeline.add(CombatRoundStartSystem(srpg_game, strategy=ActionOrderStrategy.SPEED))
    # 动作阶段入口：在回合/行动槽确定后、抽牌与决策前冻结本 pass 的行动者。
    pipeline.add(CombatPassSnapshotSystem(srpg_game))
    pipeline.add(DrawCardsActionSystem(srpg_game))
    pipeline.add(MonsterCombatDecisionSystem(srpg_game))
    pipeline.add(PlayerCombatDecisionSystem(srpg_game))
    pipeline.add(RetreatActionSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 战斗动作入口
    # ---------------------------------------------------------------------
    pipeline.add(PlayCardsActionSystem(srpg_game))
    pipeline.add(TransferCardsActionSystem(srpg_game))
    pipeline.add(UseConsumableItemActionSystem(srpg_game))
    pipeline.add(EquipGearItemActionSystem(srpg_game))
    pipeline.add(PassTurnActionSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 出牌后的牌堆处理与静态结算
    # ---------------------------------------------------------------------
    pipeline.add(DiscardCardsActionSystem(srpg_game))
    pipeline.add(ExhaustCardsActionSystem(srpg_game))
    pipeline.add(ExhaustEtherealCardsSystem(srpg_game))

    # ----
    pipeline.add(PlayCardsArbitrationSystem(srpg_game))
    pipeline.add(DeathSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 回合完成、战斗胜负与战后处理
    # ---------------------------------------------------------------------
    pipeline.add(CombatRoundCompletionSystem(srpg_game))
    pipeline.add(CombatOutcomeSystem(srpg_game))
    # 手牌清理必须在 CombatOutcomeSystem 之后：既覆盖正常回合结束，也覆盖战斗提前结束。
    # 同时保证胜负判定读到的是清理前的手牌状态；清理后再进入战后处理。
    pipeline.add(CombatHandCleanupSystem(srpg_game))
    pipeline.add(CombatResultNoticeSystem(srpg_game))
    pipeline.add(CombatPostCombatTransitionSystem(srpg_game))
    pipeline.add(CombatPileTeardownSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 通用动作与每轮尾部
    # ---------------------------------------------------------------------
    pipeline.add(CompactContextActionSystem(srpg_game))

    # 副本生命周期动作放在尾部：先退出副本，再销毁副本实体；
    # 两者必须在 ActionCleanupSystem 之前，才能由动作组件触发。
    pipeline.add(ExitDungeonActionSystem(srpg_game))
    pipeline.add(TeardownDungeonActionSystem(srpg_game))

    pipeline.add(ActionCleanupSystem(srpg_game))
    pipeline.add(DestroyEntitySystem(srpg_game))
    pipeline.add(ContextCompactionSystem(srpg_game))
    pipeline.add(EpilogueSystem(srpg_game))

    return pipeline
