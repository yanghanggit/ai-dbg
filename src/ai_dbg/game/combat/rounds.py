"""战斗残留校验。"""

from ...entitas import Matcher
from ...models import (
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
)
from ..context import DBGGame


def assert_no_residual_combat_state(dbg_game: DBGGame) -> None:
    """断言战斗临时组件已被 pipeline（CombatHandCleanupSystem/CombatPileTeardownSystem）清理干净，此函数不做任何清理动作。"""

    residual_entities = dbg_game.ecs.get_group(
        Matcher(
            any_of=[
                HandComponent,
                DrawPileComponent,
                DiscardPileComponent,
                ExhaustPileComponent,
            ]
        )
    ).entities

    assert (
        not residual_entities
    ), f"检测到残留战斗临时组件，pipeline 理应已清理完毕: {[entity.name for entity in residual_entities]}"
