"""退出副本动作系统：校验退出条件、传送玩家回大厅，并挂载后续 teardown 请求。"""

from typing import Dict, Final, List, Tuple, final

from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import (
    assert_no_residual_combat_state,
    compute_character_stats,
    set_character_hp,
)
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    current_dungeon_name,
    current_dungeon_room,
    get_dungeon_entity,
    is_current_room_dungeon_combat,
)
from ..game.entities import get_player_entity
from ..game.memory import add_human_message
from ..game.stage.transition import stage_transition
from ..models import (
    DeathComponent,
    ExitDungeonAction,
    HumanMessage,
    LobbyComponent,
    PlayerComponent,
    TeardownDungeonAction,
)
from ..utils import prompt_builder


###################################################################################################################################################################
@prompt_builder
def _build_dungeon_exit_message(dungeon_name: str, lobby_stage_name: str) -> str:
    """生成退出副本返回大厅的提示消息。"""
    return f"# 提示！副本：{dungeon_name} 结束，返回大厅：{lobby_stage_name}\n（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"


###################################################################################################################################################################
@final
class ExitDungeonActionSystem(ReactiveProcessor):
    """响应 ExitDungeonAction：退出副本、恢复玩家，并请求 teardown。"""

    def __init__(self, game: SRPGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[SRPGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(ExitDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(ExitDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not entities:
            return

        dungeon_name, players, dest_stage = self._resolve_context()
        self._execute_exit(dungeon_name, players, dest_stage)

        player_entity = get_player_entity(self._game)
        if player_entity is None:
            raise ValueError("退出副本失败：玩家实体不存在")
        player_entity.replace(TeardownDungeonAction, player_entity.name)

    ####################################################################################################################################
    def _resolve_context(self) -> Tuple[str, List[Entity], Entity]:
        """校验退出条件并返回副本名、玩家和大厅场景。"""

        dungeon_entity = get_dungeon_entity(self._game)
        if dungeon_entity is None:
            raise ValueError("退出副本失败：当前没有副本")

        current_room = current_dungeon_room(self._game)
        if current_room is None:
            raise ValueError("退出副本失败：尚未进入副本房间，无法退出")

        if is_current_room_dungeon_combat(self._game):
            if not current_dungeon_combat(self._game).is_post_combat:
                raise ValueError("退出副本失败：战斗未结束，无法退出")

        player_entities = self._game.ecs.get_group(
            Matcher(all_of=[PlayerComponent])
        ).entities.copy()
        if not player_entities:
            raise ValueError("退出副本失败：当前没有玩家实体")

        lobby_stages = self._game.ecs.get_group(
            Matcher(all_of=[LobbyComponent])
        ).entities.copy()
        if not lobby_stages:
            raise ValueError("退出副本失败：当前没有大厅场景")

        return (
            current_dungeon_name(self._game),
            list(player_entities),
            next(iter(lobby_stages)),
        )

    ####################################################################################################################################
    def _execute_exit(
        self,
        dungeon_name: str,
        player_entities: List[Entity],
        dest_stage: Entity,
    ) -> None:
        """传送玩家回大厅并恢复状态。"""

        for player_entity in player_entities:
            add_human_message(
                self._game,
                player_entity,
                HumanMessage(
                    content=_build_dungeon_exit_message(dungeon_name, dest_stage.name),
                    dungeon_lifecycle_completion=dungeon_name,
                ),
            )
            stage_transition(self._game, {player_entity}, dest_stage)

        for player_entity in player_entities:
            if player_entity.has(DeathComponent):
                player_entity.remove(DeathComponent)

            full_stats = compute_character_stats(player_entity)
            set_character_hp(player_entity, full_stats.max_hp)

        if is_current_room_dungeon_combat(self._game):
            assert_no_residual_combat_state(self._game)
