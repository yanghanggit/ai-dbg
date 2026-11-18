"""
Database access layer for the nirva_service application.
"""

from typing import List

from .base import *
from .client import *
from .config import PostgreSQLConfig, postgresql_config
from .game_snapshot import GameSnapshotDB
from .game_snapshot_operations import (
    append_game_snapshot,
    list_game_snapshot_ids,
    list_game_snapshots,
    load_game_snapshot,
    load_latest_game_snapshot,
)
from .job_event import JobEventDB
from .job_event_operations import append_job_event, get_job_error, list_job_events
from .procrastinate_app import procrastinate_app
from .user import *
from .vector_document import VectorDocumentDB
from .vector_document_operations import save_vector_document, search_similar_documents

__all__: List[str] = [
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
    # Job event models
    "JobEventDB",
    # Job event operations
    "append_job_event",
    "get_job_error",
    "list_job_events",
    # Procrastinate task queue app
    "procrastinate_app",
]
