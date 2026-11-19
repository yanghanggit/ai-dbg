"""唯一的游戏流程装配：按业务顺序线性排列全部 system。

这里是游戏业务的核心执行序列。所有 system 每轮都按固定顺序执行，
由 system 自己判断当前 world 状态是否适用；调用方不再选择房间或动作 pipeline。
"""

from ...entitas import ProcessorPipeline
from ...models import ACTION_COMPONENT_TYPES
from ..context import SRPGGame


def build_game_pipeline(srpg_game: SRPGGame) -> ProcessorPipeline:
    """构建全局唯一的线性 system 流程。"""

    ### 不这样就循环引用：systems 依赖 game 领域模块，而 game 装配又依赖 systems。
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.appearance_refresh_system import AppearanceRefreshSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.environment_refresh_system import EnvironmentRefreshSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.stage_pulse_system import StagePulseSystem
    from ..systems.stale_description_system import StaleDescriptionSystem

    pipeline = ProcessorPipeline()

    # ---------------------------------------------------------------------
    # 通用前置：每轮固定入口
    # ---------------------------------------------------------------------
    pipeline.add(PrologueSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 业务：舞台心跳，以及「当前描述」的刷新（收集动作 → 两个反应式处理器）。
    # 它们可以发布领域事件，事件由游戏的事件出口交给订阅者（如会话历史）。
    # ---------------------------------------------------------------------
    pipeline.add(StagePulseSystem(srpg_game))

    # 守卫在收集端：只有描述仍等于底稿才挂动作；已经改写过的不会每轮重写。
    pipeline.add(StaleDescriptionSystem(srpg_game))
    pipeline.add(AppearanceRefreshSystem(srpg_game))
    pipeline.add(EnvironmentRefreshSystem(srpg_game))

    # ---------------------------------------------------------------------
    # 通用尾部：清理动作组件、销毁待销毁实体并收尾
    # 顺序不可对调：先清理动作，再销毁实体，最后收尾。
    # ---------------------------------------------------------------------
    pipeline.add(ActionCleanupSystem(srpg_game, ACTION_COMPONENT_TYPES.values()))
    pipeline.add(DestroyEntitySystem(srpg_game))
    pipeline.add(EpilogueSystem(srpg_game))

    return pipeline
