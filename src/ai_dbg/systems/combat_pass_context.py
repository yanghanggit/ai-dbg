"""战斗 pass 上下文查询 mixin：让系统自己通过 ECS Matcher/Group 定位本 pass 快照。"""

from typing import List, Optional

from ..entitas import Entity, Matcher
from ..game.context import DBGGame
from ..models import (
    CombatPassSnapshotComponent,
    CombatRoundComponent,
    CombatTurnComponent,
    CombatTurnStatus,
)


###################################################################################################################################################################
class CombatPassContextMixin:
    """为战斗动作系统提供 pass 快照、行动槽与回合的 ECS 查询。

    这些查询只描述当前 pass 的动作阶段上下文，不属于领域状态；因此放在系统层，
    由使用方通过 ``self`` 调用，避免领域层出现仅供系统消费的实体 GET 封装。
    """

    _game: DBGGame

    ###############################################################################################################################################################
    def _pass_snapshot_entity_or_none(self) -> Optional[Entity]:
        """返回挂载 pass 快照的实体；没有快照时返回 None。"""
        entities = self._game.ecs.get_group(
            Matcher(all_of=[CombatPassSnapshotComponent])
        ).entities
        if len(entities) > 1:
            raise ValueError(
                f"同一时刻最多只能有一个 pass 快照，实际找到 {len(entities)} 个"
            )
        return next(iter(entities), None)

    ###############################################################################################################################################################
    def _pass_snapshot_entity(self) -> Entity:
        """返回挂载 pass 快照的实体；没有快照时抛错。"""
        entity = self._pass_snapshot_entity_or_none()
        if entity is None:
            raise ValueError("当前 pass 没有战斗快照：尚未进入动作阶段")
        return entity

    ###############################################################################################################################################################
    def _pass_snapshot_or_none(self) -> Optional[CombatPassSnapshotComponent]:
        """返回 pass 快照组件；没有快照时返回 None。"""
        entity = self._pass_snapshot_entity_or_none()
        if entity is None:
            return None
        return entity.get(CombatPassSnapshotComponent)

    ###############################################################################################################################################################
    def _pass_snapshot(self) -> CombatPassSnapshotComponent:
        """返回 pass 快照组件；没有快照时抛错。"""
        return self._pass_snapshot_entity().get(CombatPassSnapshotComponent)

    ###############################################################################################################################################################
    def _pass_turn(self) -> Entity:
        """返回 pass 快照冻结的行动槽实体，并校验其归属与状态。"""
        turn_entity = self._pass_snapshot_entity()
        if not turn_entity.has(CombatTurnComponent):
            raise ValueError(f"pass 快照实体不是行动槽: {turn_entity.name}")

        snapshot = turn_entity.get(CombatPassSnapshotComponent)
        turn_comp = turn_entity.get(CombatTurnComponent)
        if (
            turn_comp.combat_name != snapshot.combat_name
            or turn_comp.round_name != snapshot.round_name
            or turn_comp.actor_name != snapshot.actor_name
        ):
            raise ValueError(f"pass 快照行动槽 {turn_entity.name} 与快照归属不一致")
        if turn_comp.status != CombatTurnStatus.PENDING:
            raise ValueError(
                f"pass 快照行动槽 {turn_entity.name} 已结束，不能继续消费该快照"
            )
        return turn_entity

    ###############################################################################################################################################################
    def _pass_round(self) -> Entity:
        """返回 pass 快照指向的回合实体，并校验其归属。"""
        snapshot = self._pass_snapshot()
        round_entities: List[Entity] = [
            entity
            for entity in self._game.ecs.get_group(
                Matcher(all_of=[CombatRoundComponent])
            ).entities
            if entity.name == snapshot.round_name
        ]
        if len(round_entities) > 1:
            raise ValueError(f"pass 快照指向多个回合实体: {snapshot.round_name}")
        if not round_entities:
            raise ValueError(f"pass 快照指向的回合不存在: {snapshot.round_name}")

        round_entity = round_entities[0]
        round_comp = round_entity.get(CombatRoundComponent)
        if round_comp.combat_name != snapshot.combat_name:
            raise ValueError(
                f"pass 快照回合 {round_entity.name} 不属于战斗 {snapshot.combat_name}"
            )
        return round_entity

    ###############################################################################################################################################################
    def _assert_pass_actor(self, actor_name: str) -> None:
        """断言动作发起者就是本 pass 冻结的行动者。"""
        snapshot = self._pass_snapshot()
        if snapshot.actor_name != actor_name:
            raise ValueError(
                f"本 pass 行动者为 {snapshot.actor_name}，但收到来自 {actor_name} 的请求"
            )
