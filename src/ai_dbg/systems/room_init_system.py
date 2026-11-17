"""副本房间初始化：开场角色感知 / 战斗角色牌堆与场景规则。"""

from dataclasses import dataclass
from typing import Final, List, Set, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor
from ..game.combat import (
    compute_character_stats,
    get_alive_actors_in_stage,
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
    is_current_room_dungeon_opening,
    is_player_in_dungeon_stage,
)
from ..game.entities import (
    get_player_entity,
    resolve_stage_entity,
)
from ..game.memory import (
    add_ai_message,
    add_human_message,
    filter_messages,
)
from ..game.stage.environment import get_stage_environment
from ..models import (
    AIMessage,
    AppearanceComponent,
    CharacterStats,
    CombatResult,
    CombatState,
    CombatStateComponent,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    FillDrawPileAction,
    HumanMessage,
    MonsterComponent,
    PartyMemberComponent,
)
from ..utils import prompt_builder


###################################################################################################################################################################
@dataclass
class OtherActorInfo:
    """其他在场角色的信息。"""

    other_name: str
    appearance: str
    camp: str


###################################################################################################################################################################
@prompt_builder
def _build_other_actors_info(other_actors_info: List[OtherActorInfo]) -> str:
    """把其他角色信息格式化为 Markdown 列表。"""
    if not other_actors_info:
        return "无"
    return "\n\n".join(
        f"- **{info.other_name}**（{info.camp}）: {info.appearance}"
        for info in other_actors_info
    )


###################################################################################################################################################################
def _build_actor_environment_prompt(
    title: str,
    stage_name: str,
    environment: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成角色侧场景感知提示词。"""
    attrs_prompt = (
        f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 速度:{actor_stats.speed}"
    )
    return f"""# {title}

## 场景叙事

{stage_name} ｜ {environment}

## 其余角色

{_build_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}"""


###################################################################################################################################################################
@prompt_builder
def _build_opening_init_prompt(
    stage_name: str,
    environment: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成副本开场场景感知通知。"""
    return _build_actor_environment_prompt(
        "副本开场场景感知通知",
        stage_name,
        environment,
        other_actors_info,
        actor_stats,
    )


###################################################################################################################################################################
@prompt_builder
def _build_combat_init_prompt(
    stage_name: str,
    environment: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成战斗初始化通知。"""
    return _build_actor_environment_prompt(
        "战斗触发通知",
        stage_name,
        environment,
        other_actors_info,
        actor_stats,
    )


###################################################################################################################################################################
@prompt_builder
def _build_stage_combat_state_prompt(
    environment: str,
    party_names: List[str],
    monster_names: List[str],
) -> str:
    """生成场景视角的战斗状态提示词（含当前存活角色的阵营信息）。"""
    party = "、".join(party_names) if party_names else "无"
    monsters = "、".join(monster_names) if monster_names else "无"
    return f"""# 战斗场景状态

## 场景环境

{environment}

## 场上阵营

- 队伍方（队伍成员）：{party}
- 怪物方（怪物）：{monsters}

（仲裁时凡提到「队伍方/玩家方」，均指上方队伍方阵营全体存活角色。）"""


###################################################################################################################################################################
@final
class RoomInitSystem(ExecuteProcessor):
    """副本房间初始化系统。

    - 开场房间：为队伍注入开场场景感知（按消息标记幂等）。
    - 战斗房间（INITIALIZATION）：初始化参战角色牌堆、注入战场环境、投递
      `FillDrawPileAction`，最后注入场景侧战斗状态并切到 `ONGOING`。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:
        if is_current_room_dungeon_opening(self._game):
            self._initialize_opening_room()
            return

        if not is_current_room_dungeon_combat(self._game):
            logger.debug("当前副本房间既非开场也非战斗，跳过房间初始化")
            return
        if not current_dungeon_combat(self._game).is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化")
            return

        self._initialize_combat_room()

    ###################################################################################################################################################################
    def _initialize_opening_room(self) -> None:
        """开场房间初始化：注入开场场景环境信息。"""
        logger.info("开场初始化开始：注入开场场景环境信息...")

        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "无法找到玩家实体！"

        current_stage_entity = resolve_stage_entity(self._game, player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"

        environment = get_stage_environment(current_stage_entity)
        actor_entities = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actor_entities) > 0, "开场场景内不可能没有队伍成员！"

        self._inject_opening_scene_environment(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            environment=environment,
        )

    ###################################################################################################################################################################
    def _initialize_combat_room(self) -> None:
        """战斗房间初始化：角色侧牌堆/环境 + 场景侧战斗状态。"""
        logger.info("战斗初始化开始：初始化牌堆、注入战场环境并切换战斗状态...")

        assert is_player_in_dungeon_stage(
            self._game
        ), "战斗初始化阶段玩家必须在场景中！"
        assert (
            len(current_dungeon_combat(self._game).rounds or []) == 0
        ), "战斗触发阶段不允许有回合数！"

        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "无法找到玩家实体！"

        current_stage_entity = resolve_stage_entity(self._game, player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"

        environment = get_stage_environment(current_stage_entity)
        actor_entities = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        self._initialize_piles(actor_entities)
        self._inject_combat_environment(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            environment=environment,
        )

        for actor_entity in actor_entities:
            actor_entity.replace(FillDrawPileAction, actor_entity.name)
            logger.debug(f"[{actor_entity.name}] 已添加 FillDrawPileAction")

        self._assert_monster_decks(actor_entities)
        self._inject_stage_combat_state(current_stage_entity, environment)
        self._transition_to_ongoing(current_combat_entity(self._game))
        assert current_dungeon_combat(
            self._game
        ).is_ongoing, "战斗状态转换失败，当前状态非 ONGOING！"

    ###################################################################################################################################################################
    def _initialize_piles(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色初始化战斗临时牌堆。"""
        for actor_entity in actor_entities:
            assert not actor_entity.has(
                DrawPileComponent
            ), f"角色 {actor_entity.name} 已有 DrawPileComponent，理论上不应该出现这种情况！如果确实出现了，请检查之前的系统是否正确清理了旧牌堆。"
            assert not actor_entity.has(
                DiscardPileComponent
            ), f"角色 {actor_entity.name} 已有 DiscardPileComponent，理论上不应该出现这种情况！如果确实出现了，请检查之前的系统是否正确清理了旧牌堆。"
            assert not actor_entity.has(
                ExhaustPileComponent
            ), f"角色 {actor_entity.name} 已有 ExhaustPileComponent，理论上不应该出现这种情况！如果确实出现了，请检查之前的系统是否正确清理了旧牌堆。"

            actor_entity.replace(DrawPileComponent, actor_entity.name, [], [])
            actor_entity.replace(DiscardPileComponent, actor_entity.name, [])
            actor_entity.replace(ExhaustPileComponent, actor_entity.name, [])
            logger.debug(
                f"[{actor_entity.name}] 战斗临时牌堆初始化完成（DrawPile / DiscardPile / ExhaustPile）"
            )

    ###################################################################################################################################################################
    def _assert_monster_decks(self, actor_entities: Set[Entity]) -> None:
        """校验怪物阵营与预置牌库不变式。"""
        for actor_entity in actor_entities:
            if not actor_entity.has(MonsterComponent):
                continue
            assert not actor_entity.has(
                PartyMemberComponent
            ), f"角色 {actor_entity.name} 同时具有 MonsterComponent 与 PartyMemberComponent，阵营异常！"
            assert actor_entity.has(
                DeckComponent
            ), f"怪物 {actor_entity.name} 缺少 DeckComponent 组件！"
            deck_comp = actor_entity.get(DeckComponent)
            assert (
                deck_comp is not None and len(deck_comp.cards) > 0
            ), f"怪物 {actor_entity.name} 缺少预置牌库（DeckComponent）！"

    ###################################################################################################################################################################
    def _inject_opening_scene_environment(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        environment: str,
    ) -> None:
        """为开场场景角色注入环境信息（human + 模拟 AI 回应），按场景标记幂等。"""
        for actor_entity in actor_entities:
            existing_messages = filter_messages(
                self._game,
                entity=actor_entity,
                predicate=lambda msg, index, messages: (
                    getattr(msg, "opening_initialization", None) == stage_name
                ),
            )
            if existing_messages:
                logger.debug(
                    f"[{actor_entity.name}] 已注入过 {stage_name} 的开场场景环境信息，跳过"
                )
                continue

            actor_stats = compute_character_stats(actor_entity)
            prompt = _build_opening_init_prompt(
                stage_name=stage_name,
                environment=environment,
                other_actors_info=self._other_actors_info(actor_entity, actor_entities),
                actor_stats=actor_stats,
            )
            add_human_message(
                self._game,
                entity=actor_entity,
                human_message=HumanMessage(
                    content=prompt,
                    opening_initialization=stage_name,
                ),
            )
            add_ai_message(
                self._game,
                entity=actor_entity,
                ai_message=AIMessage(content="已感知当前场景环境。"),
            )
            logger.debug(
                f"[{actor_entity.name}] 开场场景环境信息注入完成（无 LLM 推理）"
            )

    ###################################################################################################################################################################
    def _inject_combat_environment(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        environment: str,
    ) -> None:
        """为参战角色注入战场环境信息（human + 模拟 AI 回应）。"""
        for actor_entity in actor_entities:
            actor_stats = compute_character_stats(actor_entity)
            prompt = _build_combat_init_prompt(
                stage_name=stage_name,
                environment=environment,
                other_actors_info=self._other_actors_info(actor_entity, actor_entities),
                actor_stats=actor_stats,
            )
            add_human_message(
                self._game,
                entity=actor_entity,
                human_message=HumanMessage(
                    content=prompt,
                    combat_initialization=stage_name,
                ),
            )
            add_ai_message(
                self._game,
                entity=actor_entity,
                ai_message=AIMessage(content="已感知战场环境，进入战斗准备状态。"),
            )
            logger.debug(f"[{actor_entity.name}] 战场环境信息注入完成（无 LLM 推理）")

    ###################################################################################################################################################################
    def _other_actors_info(
        self, actor_entity: Entity, actor_entities: Set[Entity]
    ) -> List[OtherActorInfo]:
        """构造除当前角色外的在场角色信息。"""
        copy_entities = actor_entities.copy()
        copy_entities.remove(actor_entity)

        actor_is_ally = actor_entity.has(PartyMemberComponent)
        actor_is_enemy = actor_entity.has(MonsterComponent)
        infos: List[OtherActorInfo] = []
        for other_entity in copy_entities:
            appearance_comp = other_entity.get(AppearanceComponent)
            assert appearance_comp is not None, "每个在场角色都必须有外观组件！"

            other_is_ally = other_entity.has(PartyMemberComponent)
            other_is_enemy = other_entity.has(MonsterComponent)
            camp = (
                "友方"
                if (actor_is_ally and other_is_ally)
                or (actor_is_enemy and other_is_enemy)
                else "敌方"
            )
            infos.append(
                OtherActorInfo(
                    other_name=other_entity.name,
                    appearance=appearance_comp.appearance,
                    camp=camp,
                )
            )
        return infos

    ###################################################################################################################################################################
    def _inject_stage_combat_state(
        self, stage_entity: Entity, environment: str
    ) -> None:
        """向场景实体注入战斗状态（存活阵营）。"""
        party_members = get_alive_party_members_in_stage(stage_entity, self._game)
        monsters = get_alive_monsters_in_stage(stage_entity, self._game)
        add_human_message(
            self._game,
            stage_entity,
            HumanMessage(
                content=_build_stage_combat_state_prompt(
                    environment=environment,
                    party_names=[e.name for e in party_members],
                    monster_names=[e.name for e in monsters],
                ),
                combat_initialization=stage_entity.name,
            ),
        )
        add_ai_message(
            self._game,
            stage_entity,
            AIMessage(content="已感知当前战斗场景状态。"),
        )

    ###################################################################################################################################################################
    def _transition_to_ongoing(self, combat_entity: Entity) -> None:
        """将战斗状态从 INITIALIZATION 转换为 ONGOING。"""
        state_comp = combat_entity.get(CombatStateComponent)
        assert state_comp.state == CombatState.INITIALIZATION
        assert state_comp.result == CombatResult.NONE
        combat_entity.replace(
            CombatStateComponent,
            state_comp.name,
            state_comp.room_name,
            CombatState.ONGOING,
            state_comp.result,
            state_comp.retreated,
        )
