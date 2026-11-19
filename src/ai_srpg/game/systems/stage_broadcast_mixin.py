"""舞台广播：局部舞台只影响自己，全局舞台按战场格距波及一片。

只有局部舞台能收到「在场者」这类局部广播。全局舞台（``GlobalStageComponent``）
代表整张地图，没有「在场者」这回事，向它广播等于把一条局部事件当成全局事实。
需要影响多个舞台时走 ``broadcast_to_global_stage``：以锚点的战场坐标为中心，按格距
选中若干据点（连同其整棵子树），事件仍然只发布一次。
"""

from typing import Dict, List, Optional, Set, Tuple

from ...entitas import Entity
from ...models import (
    ActorComponent,
    AnyAgentEvent,
    GlobalStageComponent,
    PositionComponent,
    StageComponent,
)
from ..entities import (
    get_actors_in_stage,
    get_child_stages,
    get_stage_entity,
    resolve_stage_entity,
)
from ..events.publish import notify_entities, notify_entities_by_stage
from .system_mixin import SystemMixin

#: 战场上的一个位置：全局舞台 + 格子坐标
Anchor = Tuple[Entity, Tuple[int, int]]


class StageBroadcastMixin(SystemMixin):
    """向舞台广播事件的 mixin：局部一份，全局一片。"""

    ############################################################################################################
    def broadcast_to_local_stage(
        self,
        entity: Entity,
        agent_event: AnyAgentEvent,
        *,
        exclude_entities: Optional[Set[Entity]] = None,
    ) -> None:
        """向 ``entity`` 所在舞台的全部角色与该舞台投递一条事件。

        ``exclude_entities`` 用于「说话者自己不必收到自己的话」这类场景。
        """
        stage_entity = self._local_stage_of(entity)
        targets = (get_actors_in_stage(self._game, stage_entity) | {stage_entity}) - (
            exclude_entities or set()
        )
        notify_entities(
            self._game, targets, agent_event, broadcast_stage=stage_entity.name
        )

    ############################################################################################################
    def broadcast_at_location(
        self,
        location: Entity,
        agent_event: AnyAgentEvent,
        *,
        exclude_entities: Optional[Set[Entity]] = None,
    ) -> None:
        """向一个「位置」投递：据点发给在场者与据点本身，地图只发给地图自己。

        地图不是场所：站在同一张图上不等于站在同一处，所以格上的其他角色不在此列。
        """
        if location.has(GlobalStageComponent):
            targets = {location} - (exclude_entities or set())
            notify_entities(
                self._game, targets, agent_event, broadcast_stage=location.name
            )
            return
        self.broadcast_to_local_stage(
            location, agent_event, exclude_entities=exclude_entities
        )

    ############################################################################################################
    def broadcast_to_global_stage(
        self,
        entity: Entity,
        agent_event: AnyAgentEvent,
        *,
        radius: Optional[int] = 1,
        exclude_entities: Optional[Set[Entity]] = None,
    ) -> None:
        """以 ``entity`` 的战场坐标为原点，波及 ``radius`` 格以内的据点及其子树。

        距离取切比雪夫距离（八方向 ``max(|dx|, |dy|)``）：盘面上「几格以内」的直觉即
        此，斜向相邻也算一格；``radius=0`` 只覆盖原点所在的那一处。

        ``radius=None`` 表示全图，此时原点可以是全局舞台本身（它没有坐标）。无论范围
        多大，事件只发布一次，每条消息带自己所在舞台的标记。
        """
        assert radius is None or radius >= 0, f"广播半径不能为负数: {radius}"
        excluded = exclude_entities or set()
        global_stage, cell = self._anchor_of(entity, radius)
        targets = self._targets_by_stage(global_stage, cell, radius, excluded)
        notify_entities_by_stage(self._game, targets, agent_event)

    ############################################################################################################
    def _local_stage_of(self, entity: Entity) -> Entity:
        """把实体解析成可以局部广播的舞台；全局舞台与悬空状态都不允许。"""
        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台，无法广播"
        assert not stage_entity.has(
            GlobalStageComponent
        ), f"{stage_entity.name} 是全局舞台，不能用局部舞台广播"
        return stage_entity

    ############################################################################################################
    def _anchor_of(
        self, entity: Entity, radius: Optional[int]
    ) -> Tuple[Entity, Tuple[int, int]]:
        """把实体映射到「哪个全局舞台的哪一格」。

        建筑这类自身没有坐标的节点沿父链上溯，用最近的带坐标祖先；一直上溯到全局舞台
        说明它没有盘面坐标，此时只有全图广播（``radius=None``）才有意义。
        """
        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台，无法广播"
        global_stage = self._global_stage_of(stage_entity)

        # 从实体自己开始上溯：站在战场上的角色自带坐标，据点的坐标在舞台身上
        node: Optional[Entity] = entity
        while node is not None and node is not global_stage:
            if node.has(PositionComponent):
                position = node.get(PositionComponent)
                return global_stage, (position.x, position.y)
            node = self._up(node)

        assert (
            radius is None
        ), f"{stage_entity.name} 在战场上没有坐标，只能做全图广播（radius=None）"
        return global_stage, (0, 0)

    ############################################################################################################
    def _global_stage_of(self, stage_entity: Entity) -> Entity:
        """沿父链找到这个舞台所属的全局舞台。"""
        node = stage_entity
        while not node.has(GlobalStageComponent):
            parent = self._parent_of(node)
            assert parent is not None, f"{stage_entity.name} 不在任何全局舞台之下"
            node = parent
        return node

    ############################################################################################################
    def _targets_by_stage(
        self,
        global_stage: Entity,
        cell: Tuple[int, int],
        radius: Optional[int],
        excluded: Set[Entity],
    ) -> Dict[str, Set[Entity]]:
        """按舞台分组的投递目标：命中的据点及其子树，各自带上直接在场角色。"""
        targets: Dict[str, Set[Entity]] = {}
        for stage_entity in self._stages_in_range(global_stage, cell, radius):
            group = targets.setdefault(stage_entity.name, set())
            group.add(stage_entity)
            group.update(get_actors_in_stage(self._game, stage_entity))

        for entities in targets.values():
            entities.difference_update(excluded)
        return {name: entities for name, entities in targets.items() if entities}

    ############################################################################################################
    def _stages_in_range(
        self,
        global_stage: Entity,
        cell: Tuple[int, int],
        radius: Optional[int],
    ) -> List[Entity]:
        """全局舞台的直接子舞台里落在范围内的，连同各自的整棵子树。"""
        hit: List[Entity] = []
        for child in get_child_stages(self._game, global_stage.name):
            if radius is not None and _distance(child, cell) > radius:
                continue
            hit.append(child)
            hit.extend(self._descendants_of(child))
        return hit

    ############################################################################################################
    def _descendants_of(self, stage_entity: Entity) -> List[Entity]:
        """某舞台的整棵子树（先序），不含自己。"""
        found: List[Entity] = []
        for child in get_child_stages(self._game, stage_entity.name):
            found.append(child)
            found.extend(self._descendants_of(child))
        return found

    ############################################################################################################
    def _up(self, entity: Entity) -> Optional[Entity]:
        """上一层：角色上到所在舞台，舞台上到父舞台。"""
        if entity.has(ActorComponent):
            return get_stage_entity(
                self._game, entity.get(ActorComponent).current_stage
            )
        return self._parent_of(entity)

    ############################################################################################################
    def _parent_of(self, stage_entity: Entity) -> Optional[Entity]:
        """父舞台实体；根舞台返回 ``None``。"""
        parent_name = stage_entity.get(StageComponent).parent_stage
        if parent_name is None:
            return None
        parent = get_stage_entity(self._game, parent_name)
        assert parent is not None, f"{stage_entity.name} 的父舞台不存在: {parent_name}"
        return parent


###############################################################################
def _distance(entity: Entity, cell: Tuple[int, int]) -> int:
    """切比雪夫距离：斜向相邻也算一格。"""
    position = entity.get(PositionComponent)
    return max(abs(position.x - cell[0]), abs(position.y - cell[1]))


###############################################################################
__all__ = ["StageBroadcastMixin"]
