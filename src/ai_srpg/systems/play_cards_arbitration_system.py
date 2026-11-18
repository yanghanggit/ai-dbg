"""出牌结算系统：由所在场景静态计算 damage 与目标格挡，结果写入场景记忆并全场景广播。"""

from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import compute_character_hand_block, compute_character_stats
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actor_entity,
    resolve_stage_entity,
)
from ..models import (
    PlayCardsAction,
    TargetType,
)
from .combat_resolution import (
    apply_combat_resolution,
    build_empty_combat_log,
    compute_damage,
)


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction，对单张出牌进行确定性伤害结算。"""

    def __init__(self, game: SRPGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[SRPGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过结算")
            return

        for entity in entities:
            self._resolve(entity)

    #######################################################################################################################################
    def _resolve(self, actor_entity: Entity) -> None:
        """解析一次出牌并落库。"""
        stage_entity = resolve_stage_entity(self._game, actor_entity)
        assert stage_entity is not None, f"无法获取 {actor_entity.name} 所在场景实体！"

        action = actor_entity.get(PlayCardsAction)
        card = action.card
        hp_changes, segments = self._compute_hp_changes(
            actor_entity.name,
            action.targets,
            card.name,
            card.damage,
            card.hit_count,
            card.target_type,
        )
        combat_log = "；".join(segments) if segments else build_empty_combat_log()
        narrative = card.description or f"{actor_entity.name} 打出「{card.name}」"

        apply_combat_resolution(
            self._game,
            stage_entity,
            title_label=f"{actor_entity.name} 出牌结算",
            narrative=narrative,
            combat_log=combat_log,
            hp_changes=hp_changes,
        )

    #######################################################################################################################################
    def _compute_hp_changes(
        self,
        actor_name: str,
        targets: List[str],
        card_name: str,
        damage: int,
        hit_count: int,
        target_type: TargetType,
    ) -> tuple[Dict[str, int], List[str]]:
        """按目标逐个计算 HP 变化与日志段；SPREAD 的 targets 即命中分配。"""
        hp_changes: Dict[str, int] = {}
        segments: List[str] = []

        for target_name in dict.fromkeys(targets):
            target_entity = get_actor_entity(self._game, target_name)
            if target_entity is None:
                raise ValueError(f"出牌结算找不到目标角色: {target_name}")

            hits = (
                targets.count(target_name)
                if target_type == TargetType.SPREAD
                else hit_count
            )
            stats = compute_character_stats(target_entity)
            result = compute_damage(
                base_damage=damage,
                hits=hits,
                block=compute_character_hand_block(target_entity),
                old_hp=stats.hp,
                max_hp=stats.max_hp,
            )
            segments.append(
                f"[{actor_name}|{card_name}→{target_name}: {result.expr}] HP:{target_name} {stats.hp}→{result.new_hp}"
            )
            if result.new_hp != stats.hp:
                hp_changes[target_name] = result.new_hp

        return hp_changes, segments
