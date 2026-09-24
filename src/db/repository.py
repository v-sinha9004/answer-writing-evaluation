"""Unified repository dispatcher for evaluation persistence (SQLite / Supabase)."""

import os
import logging
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
import sqlite3

from src.config import (
    DATA_DIR,
    DATABASE_PATH,
    DATABASE_BACKEND,
    is_supabase_configured,
)
from src.evaluator.schemas import ComprehensiveEvaluationReport, EvaluationInput
from src.db.base import BaseEvaluationRepository
from src.db.sqlite_repo import SqliteEvaluationRepository
from src.db.supabase_repo import SupabaseEvaluationRepository

logger = logging.getLogger("upsc-db-repository")

# Cached singletons
_sqlite_repo: Optional[SqliteEvaluationRepository] = None
_supabase_repo: Optional[SupabaseEvaluationRepository] = None


def get_repository(
    backend: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> BaseEvaluationRepository:
    """Resolve and return active evaluation repository based on configuration."""
    global _sqlite_repo, _supabase_repo

    # Explicit SQLite path always routes to SQLite (e.g., test suites)
    if db_path is not None:
        return SqliteEvaluationRepository(db_path=db_path)

    # Determine backend preference
    target_backend = (backend or os.getenv("DATABASE_BACKEND") or DATABASE_BACKEND or "supabase").strip().lower()

    if target_backend == "supabase":
        if is_supabase_configured():
            if _supabase_repo is None:
                _supabase_repo = SupabaseEvaluationRepository()
            return _supabase_repo
        else:
            logger.warning(
                "DATABASE_BACKEND is set to 'supabase', but SUPABASE_URL / SUPABASE_ANON_KEY are missing. "
                "Falling back to local SQLite repository."
            )

    # Default to SQLite
    target_path = Path(DATABASE_PATH)
    if _sqlite_repo is None or _sqlite_repo.default_db_path != target_path:
        _sqlite_repo = SqliteEvaluationRepository(db_path=target_path)
    return _sqlite_repo


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get an SQLite connection with Row factory and WAL mode enabled (SQLite only)."""
    repo = SqliteEvaluationRepository(db_path=db_path or DATABASE_PATH)
    return repo.get_connection(db_path=db_path)


def init_db(db_path: Optional[Path] = None, backend: Optional[str] = None, **kwargs) -> None:
    """Initialize database tables and schemas for the active backend."""
    repo = get_repository(backend=backend, db_path=db_path)
    if isinstance(repo, SqliteEvaluationRepository):
        repo.init_db(db_path=db_path, **kwargs)
    else:
        repo.init_db(**kwargs)


def save_evaluation(
    input_data: Union[EvaluationInput, Dict[str, Any]],
    report: ComprehensiveEvaluationReport,
    filename: Optional[str] = None,
    ocr_json: Optional[Union[str, Dict[str, Any]]] = None,
    pdf_url: Optional[str] = None,
    eval_id: Optional[str] = None,
    db_path: Optional[Path] = None,
    backend: Optional[str] = None,
    **kwargs,
) -> str:
    """Save an evaluation report and candidate answer input into the active backend."""
    repo = get_repository(backend=backend, db_path=db_path)
    if isinstance(repo, SqliteEvaluationRepository):
        return repo.save_evaluation(
            input_data=input_data,
            report=report,
            filename=filename,
            ocr_json=ocr_json,
            pdf_url=pdf_url,
            eval_id=eval_id,
            db_path=db_path,
            **kwargs,
        )
    return repo.save_evaluation(
        input_data=input_data,
        report=report,
        filename=filename,
        ocr_json=ocr_json,
        pdf_url=pdf_url,
        eval_id=eval_id,
        **kwargs,
    )


def get_evaluation(
    evaluation_id: str,
    db_path: Optional[Path] = None,
    backend: Optional[str] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Retrieve full evaluation details and deserialized report by ID from the active backend."""
    repo = get_repository(backend=backend, db_path=db_path)
    if isinstance(repo, SqliteEvaluationRepository):
        return repo.get_evaluation(evaluation_id=evaluation_id, db_path=db_path, **kwargs)
    return repo.get_evaluation(evaluation_id=evaluation_id, **kwargs)


def list_evaluations(
    limit: int = 50,
    offset: int = 0,
    paper: Optional[str] = None,
    db_path: Optional[Path] = None,
    backend: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """List evaluations ordered by created_at DESC with summary cards from the active backend."""
    repo = get_repository(backend=backend, db_path=db_path)
    if isinstance(repo, SqliteEvaluationRepository):
        return repo.list_evaluations(
            limit=limit,
            offset=offset,
            paper=paper,
            db_path=db_path,
            **kwargs,
        )
    return repo.list_evaluations(
        limit=limit,
        offset=offset,
        paper=paper,
        **kwargs,
    )


def delete_evaluation(
    evaluation_id: str,
    db_path: Optional[Path] = None,
    backend: Optional[str] = None,
    **kwargs,
) -> bool:
    """Delete an evaluation record by ID from the active backend."""
    repo = get_repository(backend=backend, db_path=db_path)
    if isinstance(repo, SqliteEvaluationRepository):
        return repo.delete_evaluation(evaluation_id=evaluation_id, db_path=db_path, **kwargs)
    return repo.delete_evaluation(evaluation_id=evaluation_id, **kwargs)
