"""世界快照写盘。"""

import datetime
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from ...models import (
    MEMORY_TAGS,
    AgentMemory,
    WorldState,
    get_buffer_string,
)


def _assert_memory_tags_registered(agent_name: str, agent_memory: AgentMemory) -> None:
    """校验该 agent 全部记忆消息上的结构化标记都已登记（存档前的兜底闸门）。"""
    for index, message in enumerate(agent_memory.messages):
        unknown = set(message.model_extra or {}) - MEMORY_TAGS
        assert (
            not unknown
        ), f"存档中止：{agent_name} 第 {index} 条 {type(message).__name__} 使用了未登记的记忆标记 {sorted(unknown)}；请在 models/memory_tags.py 登记"


def save_world(
    world: WorldState,
    worlds_dir: Path,
    save_dir: Optional[Path] = None,
    *,
    user_name: Optional[str] = None,
    game_name: Optional[str] = None,
) -> bool:
    """保存游戏世界到存档目录。

    存档目录结构：
        {save_dir}/
            ├── world_state.json
            ├── blueprint/{blueprint_name}.json
            ├── entities/{entity}.json ...
            ├── memories/{agent}.jsonl, {agent}.meta.json, {agent}_buffer.txt ...

    用户会话历史不在这里保存，见 session/store.py。
    """

    # 如果未指定 save_dir，则根据玩家名、游戏名和时间戳生成目录
    if save_dir is None:
        assert user_name is not None, "save_world: 自动生成目录需要 user_name"
        assert game_name is not None, "save_world: 自动生成目录需要 game_name"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = worlds_dir / user_name / game_name / timestamp

    # 主线程集中完成 CPU 序列化，产出「相对路径 → 内容」清单
    files: List[Tuple[str, str]] = []

    # 保存 world_state.json
    files.append(
        (
            "world_state.json",
            world.model_dump_json(exclude={"agent_memories", "entities", "blueprint"}),
        )
    )

    # 保存实体数据（name-keyed：文件名即实体名，内容为该实体的组件 dict）
    for entity_name, entity_data in world.entities.items():
        files.append(
            (
                f"entities/{entity_name}.json",
                json.dumps(entity_data, ensure_ascii=False),
            )
        )

    # 保存代理记忆数据
    sep: str = "-" * 100
    for agent_name, agent_memory in world.agent_memories.items():

        # 落盘前的第二道闸门：标记必须已登记。运行时校验只能覆盖走 add_* 的写入，
        # agent_loop 等直写路径到不了那里，因此在这里一次性校验全部消息。
        _assert_memory_tags_registered(agent_name, agent_memory)

        # 正式存档数据
        message_lines = [msg.model_dump_json() for msg in agent_memory.messages]

        # 保存代理记忆的消息内容
        files.append((f"memories/{agent_name}.jsonl", "\n".join(message_lines) + "\n"))
        meta = agent_memory.model_dump(exclude={"name", "messages"})

        # 保存代理记忆的元数据
        files.append(
            (
                f"memories/{agent_name}.meta.json",
                json.dumps(meta, ensure_ascii=False),
            )
        )

        # 可读 buffer 调试产物
        buffer_str = get_buffer_string(
            agent_memory.messages,
            system_prefix="\n" + sep + "\nSystem",
            human_prefix="\n" + sep + "\nHuman",
            ai_prefix="\n" + sep + f"\nAI({agent_name})",
            tool_prefix="\n" + sep + f"\nTool({agent_name})",
        )

        # 保存代理记忆的可读 buffer
        files.append((f"memories/{agent_name}_buffer.txt", buffer_str))

    # 保存蓝图数据
    files.append(
        (f"blueprint/{world.blueprint.name}.json", world.blueprint.model_dump_json())
    )

    # 先写临时目录，全部成功后原子替换为正式存档目录
    tmp_dir = save_dir.parent / f".{save_dir.name}.tmp-{os.getpid()}"
    shutil.rmtree(tmp_dir, ignore_errors=True)

    try:

        # 并行写文件（纯 I/O，文件相互独立）
        with ThreadPoolExecutor(max_workers=min(32, len(files))) as executor:

            # 提交所有文件写入任务
            futures = [
                executor.submit(_write_text, tmp_dir / rel_path, text)
                for rel_path, text in files
            ]

            # 等待所有文件写入完成
            for future in futures:
                future.result()  # 任一失败即抛异常

        # 原子替换正式存档目录
        if save_dir.exists():
            shutil.rmtree(save_dir)

        # 将临时目录替换为正式存档目录
        os.replace(tmp_dir, save_dir)

        logger.debug(f"存档成功: {save_dir}")
        return True

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(f"存档失败: {e}")
        return False


def _write_text(path: Path, text: str) -> None:
    """写入单个文件，自动创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
