"""
Database access layer: 连接、会话、表定义与各类读写操作。

本文件只做显式汇总再导出，不使用星号导入；新增或删除公开名时，两处都要改。
"""

from .base import Base, UUIDBase
from .client import (
    pgsql_create_database,
    pgsql_database_exists,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
)
from .config import PostgreSQLConfig, postgresql_config
from .game_snapshot import GameSnapshotDB
from .game_snapshot_operations import (
    append_game_snapshot,
    list_game_snapshot_ids,
    list_game_snapshots,
    list_game_summaries,
    load_game_snapshot,
    load_latest_game_snapshot,
)
from .job_event import JobEventDB
from .job_event_operations import append_job_event, get_job_error, list_job_events
from .procrastinate_app import procrastinate_app
from .session_message import SessionMessageDB
from .session_message_operations import (
    append_session_message,
    list_session_messages,
    max_session_sequence,
)
from .user import UserDB
from .vector_document import VectorDocumentDB
from .vector_document_operations import save_vector_document, search_similar_documents

__all__ = [
    # Declarative bases for table models
    "Base",
    "UUIDBase",
    # PostgreSQL configuration
    "PostgreSQLConfig",
    "postgresql_config",
    # Database management functions
    "pgsql_database_exists",
    "pgsql_create_database",
    "pgsql_drop_database",
    "pgsql_ensure_database_tables",
    # Vector database models
    "VectorDocumentDB",
    # Vector document operations (low-level)
    "save_vector_document",
    "search_similar_documents",
    # Game snapshot history
    "GameSnapshotDB",
    "append_game_snapshot",
    "load_latest_game_snapshot",
    "load_game_snapshot",
    "list_game_snapshot_ids",
    "list_game_snapshots",
    "list_game_summaries",
    # Job event models
    "JobEventDB",
    # Job event operations
    "append_job_event",
    "get_job_error",
    "list_job_events",
    # User accounts
    "UserDB",
    # Session history (user-level append-only)
    "SessionMessageDB",
    "append_session_message",
    "list_session_messages",
    "max_session_sequence",
    # Procrastinate task queue app
    "procrastinate_app",
]
