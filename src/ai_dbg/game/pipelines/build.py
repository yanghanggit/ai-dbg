"""唯一的游戏流程装配：按业务顺序线性排列全部 system。

这里是游戏业务的核心执行序列。所有 system 每轮都按固定顺序执行，
由 system 自己判断当前 world 状态是否适用；调用方不再选择房间或动作 pipeline。
"""

from ..context import DBGGame
from .manager import RPGGameProcessPipeline


def build_game_pipeline(dbg_game: DBGGame) -> RPGGameProcessPipeline:
    """构建全局唯一的线性 system 流程。"""

    ### 不这样就循环引用：systems 依赖 game 领域模块，而 game 装配又依赖 systems。
    from ...systems.action_cleanup_system import ActionCleanupSystem
    from ...systems.artifact_post_arbitration_system import (
        ArtifactPostArbitrationSystem,
    )
    from ...systems.autonomous_arbitration_system import (
        AutonomousArbitrationSystem,
    )
    from ...systems.card_operation_system import CardOperationSystem
    from ...systems.combat_hand_cleanup_system import CombatHandCleanupSystem
    from ...systems.combat_init_actor_system import CombatInitActorSystem
    from ...systems.combat_init_stage_system import CombatInitStageSystem
    from ...systems.combat_loot_system import CombatLootSystem
    from ...systems.combat_outcome_system import CombatOutcomeSystem
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
    from ...systems.generate_spoils_action_system import (
        GenerateSpoilsActionSystem,
    )
    from ...systems.monster_combat_decision_system import MonsterCombatDecisionSystem
    from ...systems.opening_init_actor_system import OpeningInitActorSystem
    from ...systems.party_combat_decision_system import PartyCombatDecisionSystem
    from ...systems.pass_turn_action_system import PassTurnActionSystem
    from ...systems.pick_spoils_action_system import PickSpoilsActionSystem
    from ...systems.play_cards_action_system import PlayCardsActionSystem
    from ...systems.play_cards_arbitration_system import PlayCardsArbitrationSystem
    from ...systems.pre_combat_outcome_system import PreCombatOutcomeSystem
    from ...systems.prologue_system import PrologueSystem
    from ...systems.retreat_action_system import RetreatActionSystem
    from ...systems.teardown_dungeon_action_system import (
        TeardownDungeonActionSystem,
    )
    from ...systems.transfer_cards_action_system import TransferCardsActionSystem
    from ...systems.turn_end_arbitration_system import TurnEndArbitrationSystem
    from ...systems.use_consumable_item_action_system import (
        UseConsumableItemActionSystem,
    )

    pipeline = RPGGameProcessPipeline()

    # ---------------------------------------------------------------------
    # 通用前置：每轮固定入口与场景环境补齐
    # ---------------------------------------------------------------------
    pipeline.add(PrologueSystem(dbg_game))
    pipeline.add(EnvironmentInitializationSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 开场房间：开场初始化与奖励生成/领取（非战斗房间生效）
    # ---------------------------------------------------------------------
    pipeline.add(OpeningInitActorSystem(dbg_game))
    pipeline.add(GenerateSpoilsActionSystem(dbg_game))
    pipeline.add(PickSpoilsActionSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 战斗初始化
    # ---------------------------------------------------------------------
    pipeline.add(CombatInitActorSystem(dbg_game))
    pipeline.add(CombatInitStageSystem(dbg_game))
    pipeline.add(FillDrawPileSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 战斗回合与决策
    # 注意：CombatRoundStartSystem 与 DrawCardsActionSystem 相邻、顺序不可对调：
    # 前者监听 DrawCardsAction 开启新回合，后者抓牌，顺序即因果链。
    # ---------------------------------------------------------------------
    pipeline.add(CombatRoundStartSystem(dbg_game, strategy=ActionOrderStrategy.SPEED))
    pipeline.add(DrawCardsActionSystem(dbg_game))
    pipeline.add(MonsterCombatDecisionSystem(dbg_game))
    pipeline.add(PartyCombatDecisionSystem(dbg_game))
    pipeline.add(RetreatActionSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 战斗动作入口
    # ---------------------------------------------------------------------
    pipeline.add(PlayCardsActionSystem(dbg_game))
    pipeline.add(TransferCardsActionSystem(dbg_game))
    pipeline.add(UseConsumableItemActionSystem(dbg_game))
    pipeline.add(EquipGearItemActionSystem(dbg_game))
    pipeline.add(PassTurnActionSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 出牌后的牌堆与词缀结算
    # ---------------------------------------------------------------------
    pipeline.add(DiscardCardsActionSystem(dbg_game))
    pipeline.add(ExhaustCardsActionSystem(dbg_game))
    pipeline.add(ExhaustEtherealCardsSystem(dbg_game))
    pipeline.add(PlayCardsArbitrationSystem(dbg_game))
    pipeline.add(CardOperationSystem(dbg_game))
    pipeline.add(ArtifactPostArbitrationSystem(dbg_game))
    pipeline.add(TurnEndArbitrationSystem(dbg_game))
    pipeline.add(AutonomousArbitrationSystem(dbg_game))
    pipeline.add(DeathSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 回合完成、战斗胜负与战后处理
    # PreCombatOutcomeSystem 必须在 CombatOutcomeSystem 之前：
    # 超时强制判负的死亡标记先于胜负判定。
    # ---------------------------------------------------------------------
    pipeline.add(CombatRoundCompletionSystem(dbg_game))
    pipeline.add(PreCombatOutcomeSystem(dbg_game))
    pipeline.add(CombatOutcomeSystem(dbg_game))
    # 手牌清理必须在 CombatOutcomeSystem 之后：既覆盖正常回合结束，也覆盖战斗提前结束。
    # 同时保证胜负判定读到的是清理前的手牌状态；清理后再进入掉落与战后处理。
    pipeline.add(CombatHandCleanupSystem(dbg_game))
    pipeline.add(CombatResultNoticeSystem(dbg_game))
    pipeline.add(CombatLootSystem(dbg_game))
    pipeline.add(CombatPostCombatTransitionSystem(dbg_game))
    pipeline.add(CombatPileTeardownSystem(dbg_game))

    # ---------------------------------------------------------------------
    # 通用动作与每轮尾部
    # ---------------------------------------------------------------------
    pipeline.add(CompactContextActionSystem(dbg_game))

    # 副本生命周期动作放在尾部：先退出副本，再销毁副本实体；
    # 两者必须在 ActionCleanupSystem 之前，才能由动作组件触发。
    pipeline.add(ExitDungeonActionSystem(dbg_game))
    pipeline.add(TeardownDungeonActionSystem(dbg_game))

    pipeline.add(ActionCleanupSystem(dbg_game))
    pipeline.add(DestroyEntitySystem(dbg_game))
    pipeline.add(ContextCompactionSystem(dbg_game))
    pipeline.add(EpilogueSystem(dbg_game))

    return pipeline
