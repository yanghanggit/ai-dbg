"""
Database access layer for the nirva_service application.
"""

from typing import List

from .base import *
from .card_prototype import CardPrototypeDB
from .card_prototype_operations import (
    CardPrototypeIndexEntry,
    delete_card_prototypes,
    get_card_prototype,
    get_card_prototype_by_name,
    list_card_prototype_index,
    save_card_prototype,
)
from .client import *
from .config import PostgreSQLConfig, postgresql_config
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
    # Card prototype models
    "CardPrototypeDB",
    "CardPrototypeIndexEntry",
    # Card prototype operations
    "save_card_prototype",
    "delete_card_prototypes",
    "list_card_prototype_index",
    "get_card_prototype",
    "get_card_prototype_by_name",
    # Job event models
    "JobEventDB",
    # Job event operations
    "append_job_event",
    "get_job_error",
    "list_job_events",
    # Procrastinate task queue app
    "procrastinate_app",
]
