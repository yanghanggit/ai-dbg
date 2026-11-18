"""用户会话历史存储。

会话历史与游戏运行状态分离：游戏状态可重建，session 只追加。
当前实现使用 append-only JSONL；文件按用户隔离，跨游戏持续累积。
"""

import json
import os
from pathlib import Path
from typing import List, Optional

from loguru import logger

from ..models import PlayerSession, SessionMessage
from ..paths import SESSIONS_DIR


###############################################################################
class SessionStore:
    """按用户名读写 append-only 会话历史。"""

    def __init__(self, base_dir: Path = SESSIONS_DIR) -> None:
        self._base_dir: Path = base_dir

    ###############################################################################
    def _session_dir(self, user_name: str) -> Path:
        return self._base_dir / user_name

    def _messages_path(self, user_name: str) -> Path:
        return self._session_dir(user_name) / "messages.jsonl"

    def _meta_path(self, user_name: str) -> Path:
        return self._session_dir(user_name) / "meta.json"

    ###############################################################################
    def load(self, user_name: str) -> PlayerSession:
        """加载用户会话；文件不存在时返回空会话。"""
        meta = self._load_meta(user_name)
        messages = self._load_messages(user_name)
        session = PlayerSession(
            name=user_name,
            actor=meta.get("actor"),
            game=meta.get("game"),
            session_messages=messages,
            event_sequence=max((m.sequence_id for m in messages), default=0),
        )
        logger.debug(
            f"会话已加载: user={user_name}, messages={len(messages)}, sequence={session.event_sequence}"
        )
        return session

    ###############################################################################
    def load_or_create(
        self,
        user_name: str,
        *,
        actor: Optional[str] = None,
        game: Optional[str] = None,
    ) -> PlayerSession:
        """加载会话；若尚未建立上下文，则用给定值补齐并落 meta。"""
        session = self.load(user_name)
        changed = False
        if session.actor is None and actor is not None:
            session.actor = actor
            changed = True
        if session.game is None and game is not None:
            session.game = game
            changed = True
        if changed:
            self.save_meta(session)
        return session

    ###############################################################################
    def append(self, session: PlayerSession, message: SessionMessage) -> None:
        """追加一条会话消息。"""
        path = self._messages_path(session.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message.model_dump_json() + "\n")
            handle.flush()

    ###############################################################################
    def save_meta(self, session: PlayerSession) -> None:
        """原子更新当前 game / actor 上下文，不重写历史消息。"""
        directory = self._session_dir(session.name)
        directory.mkdir(parents=True, exist_ok=True)
        path = self._meta_path(session.name)
        tmp_path = directory / f".meta.tmp-{os.getpid()}"
        payload = {
            "name": session.name,
            "actor": session.actor,
            "game": session.game,
        }
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)

    ###############################################################################
    def _load_meta(self, user_name: str) -> dict[str, Optional[str]]:
        path = self._meta_path(user_name)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            "actor": raw.get("actor"),
            "game": raw.get("game"),
        }

    def _load_messages(self, user_name: str) -> List[SessionMessage]:
        path = self._messages_path(user_name)
        if not path.exists():
            return []
        messages: List[SessionMessage] = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                messages.append(SessionMessage.model_validate_json(line))
            except Exception as exc:  # noqa: BLE001 - 带行号的损坏历史需要明确报错
                raise ValueError(f"会话历史损坏: {path}:{line_number}: {exc}") from exc
        return messages
