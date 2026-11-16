"""针对 game/persistence 的单元测试。

覆盖 save_world / restore_world 的往返一致性、存档目录结构、
错误处理，以及临时目录 + 原子替换带来的失败安全性。
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from ai_dbg.entitas import dump_components
from ai_dbg.game.persistence import restore_world
from ai_dbg.game.persistence import save as persistence_save
from ai_dbg.models import (
    AgentMemory,
    AIMessage,
    Blueprint,
    CombatComponent,
    CombatRoundComponent,
    CombatRoundEntryComponent,
    CombatState,
    CombatStateComponent,
    CombatTurnComponent,
    CombatTurnStatus,
    CurrentCombatTurnComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    DungeonRunComponent,
    HumanMessage,
    RoundEntryKind,
    WorldState,
)

# ---------------------------------------------------------------------------
# 构造辅助
# ---------------------------------------------------------------------------


def _make_blueprint(name: str = "demo") -> Blueprint:
    return Blueprint(
        name=name,
        player_actor="hero",
        campaign_setting="setting",
        system_rules="",
        stages=[],
        world_entities=[],
    )


def _make_world(entity_counter: int = 1) -> WorldState:
    return WorldState(
        entity_counter=entity_counter,
        entities={},
        blueprint=_make_blueprint(),
        agent_memories={},
    )


# ---------------------------------------------------------------------------
# 往返一致性
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_basic_round_trip(self, tmp_path: Path) -> None:
        world = _make_world(entity_counter=7)
        save_dir = tmp_path / "snap"

        assert persistence_save.save_world(world, tmp_path, save_dir)

        restored_world = restore_world(save_dir)

        assert restored_world.entity_counter == 7
        assert restored_world.blueprint.name == "demo"
        assert not (save_dir / "player_session.jsonl").exists()

    def test_agent_memories_round_trip(self, tmp_path: Path) -> None:
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(
            name="alice",
            messages=[HumanMessage(content="hi"), AIMessage(content="hello")],
            context_usage_ratio=0.42,
        )
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(world, tmp_path, save_dir)

        # 磁盘文件齐全
        assert (save_dir / "memories" / "alice.jsonl").exists()
        assert (save_dir / "memories" / "alice.meta.json").exists()
        assert (save_dir / "memories" / "alice_buffer.txt").exists()

        # buffer 为可读调试产物，含按 agent 名生成的 AI 前缀
        buffer = (save_dir / "memories" / "alice_buffer.txt").read_text(
            encoding="utf-8"
        )
        assert "AI(alice)" in buffer

        restored_world = restore_world(save_dir)
        mem = restored_world.agent_memories["alice"]
        assert mem.context_usage_ratio == 0.42
        assert [m.content for m in mem.messages] == ["hi", "hello"]

    def test_entities_round_trip(self, tmp_path: Path) -> None:
        world = _make_world()
        world.entities = {
            "goblin": {"stats": {"hp": 10}},
            "slime": {"stats": {"hp": 3}},
        }
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(world, tmp_path, save_dir)

        restored_world = restore_world(save_dir)
        assert list(restored_world.entities) == ["goblin", "slime"]
        assert restored_world.entities["goblin"] == {"stats": {"hp": 10}}

    def test_dungeon_ecs_components_round_trip(self, tmp_path: Path) -> None:
        """副本/房间/战斗组件应按 JSON 模式落盘，并能还原出原始字段类型。"""
        world = _make_world()
        created_at = datetime(2026, 1, 2, 3, 4, 5)
        world.entities = {
            "副本.测试": dump_components(
                DungeonRunComponent(
                    name="副本.测试",
                    profile="profile",
                    created_at=created_at,
                    assets={},
                )
            ),
            "场景.测试": dump_components(
                DungeonRoomComponent(
                    name="场景.测试",
                    dungeon_name="副本.测试",
                    index=0,
                    room_type=DungeonRoomType.COMBAT,
                ),
                CombatComponent(
                    name="场景.测试",
                    combat_name="场景.测试#combat",
                ),
            ),
            "场景.测试#combat": dump_components(
                CombatStateComponent(
                    name="场景.测试#combat",
                    room_name="场景.测试",
                    state=CombatState.ONGOING,
                )
            ),
            "场景.测试#combat#round-1": dump_components(
                CombatRoundComponent(
                    name="场景.测试#combat#round-1",
                    combat_name="场景.测试#combat",
                    index=1,
                )
            ),
            "场景.测试#combat#round-1#turn-1": dump_components(
                CombatTurnComponent(
                    name="场景.测试#combat#round-1#turn-1",
                    combat_name="场景.测试#combat",
                    round_name="场景.测试#combat#round-1",
                    actor_name="角色.无名",
                    order_index=1,
                    status=CombatTurnStatus.PENDING,
                    energy=1,
                ),
                CurrentCombatTurnComponent(
                    name="场景.测试#combat#round-1#turn-1",
                ),
            ),
            "场景.测试#combat#round-1#entry-1": dump_components(
                CombatRoundEntryComponent(
                    name="场景.测试#combat#round-1#entry-1",
                    combat_name="场景.测试#combat",
                    round_name="场景.测试#combat#round-1",
                    turn_name="场景.测试#combat#round-1#turn-1",
                    index=1,
                    kind=RoundEntryKind.CARDS,
                    log="log",
                    narrative="narrative",
                )
            ),
        }
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(world, tmp_path, save_dir)

        restored_world = restore_world(save_dir)
        raw_dungeon = restored_world.entities["副本.测试"]["DungeonRunComponent"]
        raw_room = restored_world.entities["场景.测试"]["DungeonRoomComponent"]
        raw_combat = restored_world.entities["场景.测试"]["CombatComponent"]
        raw_state = restored_world.entities["场景.测试#combat"]["CombatStateComponent"]
        raw_round = restored_world.entities["场景.测试#combat#round-1"][
            "CombatRoundComponent"
        ]
        raw_turn = restored_world.entities["场景.测试#combat#round-1#turn-1"][
            "CombatTurnComponent"
        ]
        raw_entry = restored_world.entities["场景.测试#combat#round-1#entry-1"][
            "CombatRoundEntryComponent"
        ]
        assert DungeonRunComponent(**raw_dungeon).created_at == created_at
        assert DungeonRoomComponent(**raw_room).room_type == DungeonRoomType.COMBAT
        assert CombatComponent(**raw_combat).combat_name == "场景.测试#combat"
        assert CombatStateComponent(**raw_state).state == CombatState.ONGOING
        assert CombatRoundComponent(**raw_round).index == 1
        restored_turn = CombatTurnComponent(**raw_turn)
        assert restored_turn.actor_name == "角色.无名"
        assert restored_turn.status == CombatTurnStatus.PENDING
        assert restored_turn.energy == 1
        restored_entry = CombatRoundEntryComponent(**raw_entry)
        assert restored_entry.kind == RoundEntryKind.CARDS
        assert restored_entry.turn_name == "场景.测试#combat#round-1#turn-1"

    def test_world_state_json_excludes_split_fields(self, tmp_path: Path) -> None:
        """world_state.json 应排除独立存储的字段。"""
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(name="alice", messages=[])
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(world, tmp_path, save_dir)

        data = json.loads((save_dir / "world_state.json").read_text(encoding="utf-8"))
        for key in ("agent_memories", "entities", "blueprint"):
            assert key not in data


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------


class TestRestoreErrors:
    def test_missing_world_state_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="world_state.json"):
            restore_world(tmp_path)


# ---------------------------------------------------------------------------
# 临时目录 + 原子替换
# ---------------------------------------------------------------------------


class TestAtomicSave:
    def test_failure_returns_false_and_leaves_no_partial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_dir = tmp_path / "snap"
        real_write = persistence_save._write_text

        def failing_write(path: Path, text: str) -> None:
            if path.name == "world_state.json":
                raise OSError("simulated write failure")
            real_write(path, text)

        monkeypatch.setattr(persistence_save, "_write_text", failing_write)

        assert persistence_save.save_world(_make_world(), tmp_path, save_dir) is False
        assert not save_dir.exists()
        assert not [p for p in tmp_path.iterdir() if ".tmp-" in p.name]

    def test_failure_preserves_existing_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(
            _make_world(entity_counter=1), tmp_path, save_dir
        )

        real_write = persistence_save._write_text

        def failing_write(path: Path, text: str) -> None:
            if path.name == "world_state.json":
                raise OSError("simulated write failure")
            real_write(path, text)

        monkeypatch.setattr(persistence_save, "_write_text", failing_write)

        assert (
            persistence_save.save_world(
                _make_world(entity_counter=2),
                tmp_path,
                save_dir,
            )
            is False
        )

        # 旧存档应保持不变
        restored_world = restore_world(save_dir)
        assert restored_world.entity_counter == 1

    def test_overwrite_replaces_cleanly(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "snap"

        world1 = _make_world()
        world1.agent_memories["alice"] = AgentMemory(name="alice", messages=[])
        assert persistence_save.save_world(world1, tmp_path, save_dir)

        world2 = _make_world()
        world2.agent_memories["bob"] = AgentMemory(name="bob", messages=[])
        assert persistence_save.save_world(world2, tmp_path, save_dir)

        restored_world = restore_world(save_dir)
        assert set(restored_world.agent_memories.keys()) == {"bob"}
        assert not (save_dir / "memories" / "alice.jsonl").exists()

    def test_auto_generated_save_dir(self, tmp_path: Path) -> None:
        world = _make_world()  # blueprint.name == "demo"

        assert persistence_save.save_world(
            world,
            worlds_dir=tmp_path,
            user_name="user",
            game_name="demo",
        )

        game_dir = tmp_path / "user" / "demo"
        assert game_dir.exists()
        snapshots = [p for p in game_dir.iterdir() if p.is_dir()]
        assert len(snapshots) == 1
        assert (snapshots[0] / "world_state.json").exists()

        restored_world = restore_world(snapshots[0])
        assert restored_world.entity_counter == 1


# ---------------------------------------------------------------------------
# 存档前的标记闸门（覆盖 agent_loop 等绕过 add_* 的直写路径）
# ---------------------------------------------------------------------------


class TestMemoryTagGate:
    def test_unregistered_tag_aborts_save(self, tmp_path: Path) -> None:
        """记忆里有未登记标记时存档中止：直写路径不经过 add_* 校验，这里兜底。"""
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(
            name="alice",
            messages=[HumanMessage(content="hi", typo_tag="x")],
        )

        with pytest.raises(AssertionError, match="未登记的记忆标记"):
            persistence_save.save_world(world, tmp_path, tmp_path / "snap")

    def test_registered_tag_saves_and_round_trips(self, tmp_path: Path) -> None:
        """已登记标记照常保存，且往返后标记不丢。"""
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(
            name="alice",
            messages=[
                HumanMessage(content="hi", broadcast_stage="场景.酒馆"),
                AIMessage(content="", context_usage_ratio=0.5),
            ],
        )
        save_dir = tmp_path / "snap"
        assert persistence_save.save_world(world, tmp_path, save_dir)

        restored_world = restore_world(save_dir)
        messages = restored_world.agent_memories["alice"].messages
        assert isinstance(messages[0], HumanMessage)
        assert getattr(messages[0], "broadcast_stage") == "场景.酒馆"
