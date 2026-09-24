"""Database package for UPSC answer evaluation engine."""

from src.db.base import BaseEvaluationRepository
from src.db.sqlite_repo import SqliteEvaluationRepository
from src.db.supabase_repo import SupabaseEvaluationRepository
from src.db.repository import (
    init_db,
    save_evaluation,
    get_evaluation,
    list_evaluations,
    delete_evaluation,
    get_connection,
    get_repository,
)

__all__ = [
    "BaseEvaluationRepository",
    "SqliteEvaluationRepository",
    "SupabaseEvaluationRepository",
    "get_repository",
    "init_db",
    "save_evaluation",
    "get_evaluation",
    "list_evaluations",
    "delete_evaluation",
    "get_connection",
]
