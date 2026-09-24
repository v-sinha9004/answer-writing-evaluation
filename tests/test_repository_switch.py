"""Tests for database repository factory and backend switching."""

import pytest
from pathlib import Path
from src.db.repository import get_repository
from src.db.sqlite_repo import SqliteEvaluationRepository
from src.db.supabase_repo import SupabaseEvaluationRepository


def test_explicit_db_path_selects_sqlite(tmp_path: Path):
    db_file = tmp_path / "custom.db"
    repo = get_repository(db_path=db_file)
    assert isinstance(repo, SqliteEvaluationRepository)
    assert repo.default_db_path == db_file


def test_switch_backend_via_param():
    sqlite_repo = get_repository(backend="sqlite")
    assert isinstance(sqlite_repo, SqliteEvaluationRepository)

    supabase_repo = get_repository(backend="supabase")
    assert isinstance(supabase_repo, SupabaseEvaluationRepository)


def test_switch_backend_via_env(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    repo = get_repository()
    assert isinstance(repo, SqliteEvaluationRepository)

    monkeypatch.setenv("DATABASE_BACKEND", "supabase")
    repo2 = get_repository()
    assert isinstance(repo2, SupabaseEvaluationRepository)
