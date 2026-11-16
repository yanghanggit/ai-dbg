"""
DBG 游戏业务上下文。

`DBGGame` 只保存一次游戏运行所需的数据：世界状态、ECS context、玩家会话、
实体名称索引与 pipeline 列表。所有游戏领域操作都以模块函数的形式接收
`DBGGame`，不再把行为挂在这个对象上。
"""

from typing import Dict, List

from ..entitas import Context, Entity
from ..models import PlayerSession, WorldState
from .game_process_pipeline import RPGGameProcessPipeline


#################################################################################################################################################
class DBGGame:
    """DBG，Deck Building Game 的业务上下文（纯数据对象）。"""

    # 类级注解让类型检查与测试替身（MagicMock(spec=DBGGame)）都能看到这些字段。
    name: str
    player_session: PlayerSession
    world: WorldState
    ecs: Context
    entity_index: Dict[str, Entity]
    pipelines: List[RPGGameProcessPipeline]
    opening_pipeline: RPGGameProcessPipeline
    combat_pipeline: RPGGameProcessPipeline
    compact_pipeline: RPGGameProcessPipeline
    should_terminate: bool

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: WorldState,
    ) -> None:
        self.name: str = name
        self.player_session: PlayerSession = player_session
        self.world: WorldState = world

        # ECS 运行时状态与业务数据分离：Entity 的 _context 指向这里。
        self.ecs: Context = Context()

        # 名称索引，避免每次查询都遍历 ECS。
        self.entity_index: Dict[str, Entity] = {}

        # Pipeline 是本轮游戏运行的编排设施，不属于 ECS。
        self.pipelines: List[RPGGameProcessPipeline] = []
        self.opening_pipeline: RPGGameProcessPipeline
        self.combat_pipeline: RPGGameProcessPipeline
        self.compact_pipeline: RPGGameProcessPipeline

        self.should_terminate: bool = False

        # 延迟导入 pipeline 工厂，避免 systems -> game -> systems 的循环导入。
        from .dbg_compact_pipeline import create_compact_pipeline
        from .dbg_dungeon_combat_room_pipeline import (
            create_dungeon_combat_room_pipeline,
        )
        from .dbg_dungeon_opening_room_pipeline import (
            create_dungeon_opening_room_pipeline,
        )

        self.opening_pipeline = create_dungeon_opening_room_pipeline(self)
        self.combat_pipeline = create_dungeon_combat_room_pipeline(self)
        self.compact_pipeline = create_compact_pipeline(self)
        self.pipelines = [
            self.opening_pipeline,
            self.combat_pipeline,
            self.compact_pipeline,
        ]

    def __repr__(self) -> str:
        return f"<DBGGame name={self.name!r} entities={self.ecs.entity_count}>"
