"""最近成功世界快照指针。

只记录成功落盘的世界快照；会话历史不参与。job 失败时用它回到进入 job 前的世界。
"""

import json
import os
from pathlib import Path
from typing import Optional

from ...paths import WORLDS_DIR


###############################################################################
def latest_pointer_path(worlds_dir: Path, user_name: str, game_name: str) -> Path:
    return worlds_dir / user_name / game_name / "latest.json"


###############################################################################
def write_latest_snapshot(
    worlds_dir: Path,
    user_name: str,
    game_name: str,
    save_dir: Path,
) -> None:
    """原子更新“最近成功快照”指针。"""
    pointer = latest_pointer_path(worlds_dir, user_name, game_name)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = pointer.parent / f".latest.tmp-{os.getpid()}"
    tmp_path.write_text(
        json.dumps({"snapshot": save_dir.name}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp_path, pointer)


###############################################################################
def latest_snapshot_dir(
    user_name: str,
    game_name: str,
    *,
    worlds_dir: Path = WORLDS_DIR,
) -> Optional[Path]:
    """返回最近一次成功世界快照目录；指针缺失时回退到目录扫描。"""
    base_dir = worlds_dir / user_name / game_name
    pointer = latest_pointer_path(worlds_dir, user_name, game_name)

    if pointer.exists():
        try:
            data = json.loads(pointer.read_text(encoding="utf-8"))
            candidate = base_dir / str(data["snapshot"])
            if (candidate / "world_state.json").exists():
                return candidate
        except (KeyError, OSError, json.JSONDecodeError):
            pass

    if not base_dir.exists():
        return None

    candidates = sorted(
        (
            path
            for path in base_dir.iterdir()
            if path.is_dir()
            and not path.name.startswith(".")
            and (path / "world_state.json").exists()
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    return candidates[0] if candidates else None
