"""世界快照读盘。"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from loguru import logger
from pydantic import TypeAdapter

from ...entitas import EntityData
from ...models import (
    AgentMemory,
    Blueprint,
    ChatMessage,
    PlayerSession,
    SessionMessage,
    WorldState,
)

# TypeAdapter 用于将 JSON 字符串转换为 ChatMessage 对象
_message_adapter: TypeAdapter[ChatMessage] = TypeAdapter(ChatMessage)


def restore_world(save_dir: Path) -> Tuple[WorldState, PlayerSession]:
    """从存档目录中读取并还原 WorldState 与 PlayerSession。

    Args:
        save_dir: 存档目录路径，即含有 world_state.json 与 player_session.jsonl 的目录
                      （例如 .worlds/{username}/{game}/{timestamp}/）

    Returns:
        (world, player_session) 元组

    Raises:
        FileNotFoundError: 若 world_state.json 或 player_session.jsonl 不存在
    """

    # 检查 save_dir 是否存在
    world_path = save_dir / "world_state.json"
    session_path = save_dir / "player_session.jsonl"

    # 检查文件是否存在
    if not world_path.exists():
        raise FileNotFoundError(f"找不到 world_state.json: {world_path}")

    # 检查 player_session.jsonl 是否存在
    if not session_path.exists():
        raise FileNotFoundError(f"找不到 player_session.jsonl: {session_path}")

    # 收集各子目录下待读取的文件清单
    def _files(sub: str, pattern: str) -> List[Path]:
        directory = save_dir / sub
        return sorted(directory.glob(pattern)) if directory.exists() else []

    memory_files = _files("memories", "*.jsonl")
    entity_files = _files("entities", "*.json")
    blueprint_files = _files("blueprint", "*.json")

    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    # 并行读文件（纯 I/O，文件相互独立）
    with ThreadPoolExecutor(max_workers=8) as executor:

        # 提交各类文件的读取任务到线程池
        world_future = executor.submit(_read, world_path)
        session_future = executor.submit(_read, session_path)

        # 并行读取 memories、entities 和 blueprint 文件
        memory_raws = list(executor.map(_read, memory_files))
        entity_raws = list(executor.map(_read, entity_files))
        blueprint_raws = list(executor.map(_read, blueprint_files))

        # 等待读取 world 和 session 文件的结果
        world_raw = world_future.result()

        # 等待读取 player_session 文件的结果
        session_raw = session_future.result()

    # 主线程反序列化 WorldState
    world = WorldState.model_validate_json(world_raw)

    # 从 memories/ 目录重建 agent_memories
    agent_memories: Dict[str, AgentMemory] = {}
    memories_dir = save_dir / "memories"
    for raw, memory_file in zip(memory_raws, memory_files):
        agent_name = memory_file.stem
        memory_messages: List[ChatMessage] = [
            _message_adapter.validate_json(line)
            for line in raw.strip().split("\n")
            if line.strip()
        ]
        agent_memories[agent_name] = AgentMemory(
            name=agent_name,
            messages=memory_messages,
            **_load_agent_memory_meta(memories_dir, agent_name),
        )

    # 将 agent_memories 赋值给 world 对象
    world.agent_memories = agent_memories

    # 从 entities/ 目录重建 entities（文件名即实体名）
    world.entities = {
        path.stem: _load_entity_data(raw)
        for raw, path in zip(entity_raws, entity_files)
    }

    # 从 blueprint/ 目录重建 blueprint
    if blueprint_raws:
        world.blueprint = Blueprint.model_validate_json(blueprint_raws[0])

    # 反序列化 PlayerSession（JSONL 格式：首行元数据，后续每行一个事件）
    lines = [line for line in session_raw.split("\n") if line.strip()]
    if not lines:
        raise ValueError(f"player_session.jsonl 为空: {session_path}")

    # 解析首行元数据
    meta = json.loads(lines[0])
    messages: List[SessionMessage] = [
        SessionMessage.model_validate_json(line) for line in lines[1:]
    ]

    # 创建 PlayerSession 对象
    player_session = PlayerSession(
        name=meta["name"],
        actor=meta["actor"],
        game=meta["game"],
        session_messages=messages,
        event_sequence=max((m.sequence_id for m in messages), default=0),
    )

    # 返回
    logger.debug(f"世界已还原: {save_dir}")
    return world, player_session


def _load_entity_data(raw: str) -> EntityData:
    """读取单个实体文件的组件 dict（文件名另行作为实体名）。"""
    return cast(EntityData, json.loads(raw))


def _load_agent_memory_meta(memories_dir: Path, agent_name: str) -> Dict[str, Any]:
    """读取单个 agent 的记忆元数据（memories/{agent_name}.meta.json），缺失时返回空 dict。"""
    meta_path = memories_dir / f"{agent_name}.meta.json"
    if not meta_path.exists():
        return {}
    return cast(Dict[str, Any], json.loads(meta_path.read_text(encoding="utf-8")))
