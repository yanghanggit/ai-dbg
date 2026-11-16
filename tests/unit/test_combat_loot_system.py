"""CombatLootSystem 单元测试：掉落推理必须写回怪物记忆（与出牌决策一致）。"""

from typing import Any, List, cast
from unittest.mock import MagicMock, patch

import pytest

from ai_dbg.entitas import Entity
from ai_dbg.entitas.context import Context
from ai_dbg.game.game_dungeon import (
    current_dungeon_combat_room,
)
from ai_dbg.llm import ChatCompletionRequest, ChatCompletionResult
from ai_dbg.models import (
    ActorComponent,
    AIMessage,
    AppearanceComponent,
    LootComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
    StageComponent,
)
from ai_dbg.systems.combat_loot_system import CombatLootSystem

_MODULE = "ai_dbg.systems.combat_loot_system"

_LOOT_JSON = """{
  "base_materials": [{"name": "材料.兽骨", "description": "断裂的兽骨。", "count": 2}],
  "part_breaks": [
    {"part_name": "前爪", "broken": true,
     "materials": [{"name": "材料.利爪", "description": "尖锐的爪。", "count": 1}]}
  ]
}"""


def _make_player(context: Context) -> Entity:
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity._name, "场景.河湾芦苇丛")
    entity.add(PartyMemberComponent, entity._name)
    entity.add(PlayerComponent, entity._name)
    entity.add(LootComponent, entity._name, [])
    return entity


def _make_monster(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.河湾芦苇丛")
    entity.add(MonsterComponent, name)
    entity.add(AppearanceComponent, name, "体型基础", "一头灰褐色的野狗")
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


def _make_game(context: Context, monsters: List[Entity], player: Entity) -> Any:
    stage = context.create_entity()
    stage._name = "场景.河湾芦苇丛"
    stage.add(StageComponent, stage.name)
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.world.agent_memories = {}
    game.player_session = MagicMock()
    game.world.dungeon = MagicMock()
    game.world.dungeon.current_room = MagicMock(
        combat=MagicMock(
            is_combat_completed=True,
            is_won=True,
            rounds=[MagicMock()],
        )
    )
    return game


class TestLootMemory:
    async def test_writes_prompt_and_ai_response_to_monster_memory(
        self, context: Context
    ) -> None:
        """掉落推理必须留痕：human = 请求原文（带 combat_loot 标记），ai = 回包原文。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        system = CombatLootSystem(game)

        async def fake_batch_complete(
            requests: List[ChatCompletionRequest],
        ) -> List[ChatCompletionResult]:
            return [
                ChatCompletionResult(
                    request=request, ai_message=AIMessage(content=_LOOT_JSON)
                )
                for request in requests
            ]

        with patch(f"{_MODULE}.batch_complete", side_effect=fake_batch_complete):
            await system.execute()

        # human：怪物侧记请求原文 + 结构化标记
        messages = game.world.agent_memories[monster.name].messages
        human_messages = [m for m in messages if m.type == "human"]
        assert len(human_messages) == 1
        assert human_messages[0].combat_loot_reasoning == monster.name
        assert "掉落" in human_messages[0].content
        ai_messages = [m for m in messages if m.type == "ai"]
        assert len(ai_messages) == 1
        assert ai_messages[0].content == _LOOT_JSON

        # 掉落照常写入玩家
        assert [item.name for item in player.get(LootComponent).items] == [
            "材料.兽骨",
            "材料.利爪",
        ]

        # 玩家侧也留一条自我状态说明（只写给本人）
        player_messages = game.world.agent_memories[player.name].messages
        loot_messages = [m for m in player_messages if m.type == "human"]
        assert len(loot_messages) == 1
        loot_message = loot_messages[0]
        assert loot_message.content.startswith("# 你的战利品")
        assert "材料.兽骨 ×2" in loot_message.content
        assert "材料.利爪 ×1" in loot_message.content
        assert loot_message.combat_loot_items == "场景.河湾芦苇丛"

    async def test_records_prompt_only_when_no_response(self, context: Context) -> None:
        """LLM 无回包时只记请求侧，不伪造 AI 回复（add_ai_message 会断言非空）。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        system = CombatLootSystem(game)

        async def fake_batch_complete(
            requests: List[ChatCompletionRequest],
        ) -> List[ChatCompletionResult]:
            return [
                ChatCompletionResult(request=request, ai_message=None)
                for request in requests
            ]

        with patch(f"{_MODULE}.batch_complete", side_effect=fake_batch_complete):
            await system.execute()

        messages = game.world.agent_memories[monster.name].messages
        assert len([m for m in messages if m.type == "human"]) == 1
        assert not [m for m in messages if m.type == "ai"]
        assert player.get(LootComponent).items == []

    async def test_skips_entirely_when_combat_not_won(self, context: Context) -> None:
        """未胜利（或未结束）时不推理、不留痕。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        cast(Any, current_dungeon_combat_room(game)).combat.is_won = False
        system = CombatLootSystem(game)

        await system.execute()

        assert not game.world.agent_memories

    async def test_asserts_when_player_has_no_stage(self, context: Context) -> None:
        """actor 与 stage 不允许脱离：缺失场景是断言失败，而不是降级空串。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        player.replace(ActorComponent, player.name, "不存在的场景")
        system = CombatLootSystem(game)

        with pytest.raises(AssertionError):
            await system.execute()
