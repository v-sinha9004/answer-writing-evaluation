"""SQLite repository for persistent storage of UPSC evaluations."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

from src.config import DATABASE_PATH
from src.evaluator.schemas import ComprehensiveEvaluationReport, EvaluationInput


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get an SQLite connection with Row factory and WAL mode enabled."""
    target_path = Path(db_path) if db_path else DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables and indexes."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                paper TEXT NOT NULL,
                marks INTEGER NOT NULL,
                question_text TEXT,
                filename TEXT,
                word_count INTEGER DEFAULT 0,
                legibility_status TEXT DEFAULT 'AVERAGE',
                total_score REAL NOT NULL,
                max_marks INTEGER NOT NULL,
                percentage REAL NOT NULL,
                benchmark_verdict TEXT NOT NULL,
                full_answer_text TEXT,
                report_json TEXT NOT NULL,
                total_latency_seconds REAL DEFAULT 0.0
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evaluations_created_at ON evaluations(created_at DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evaluations_paper ON evaluations(paper);"
        )
        conn.commit()


def save_evaluation(
    input_data: Union[EvaluationInput, Dict[str, Any]],
    report: ComprehensiveEvaluationReport,
    filename: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Save an evaluation report and candidate answer input into SQLite."""
    init_db(db_path)

    if isinstance(input_data, dict):
        input_data = EvaluationInput.model_validate(input_data)

    eval_id = f"eval_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Enrich report with metadata
    report.id = eval_id
    report.created_at = now_iso
    report.paper = input_data.subject_paper
    report.question_text = input_data.question_text
    report.filename = filename

    scorecard = report.scorecard
    report_json_str = report.model_dump_json()

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO evaluations (
                id, created_at, paper, marks, question_text, filename,
                word_count, legibility_status, total_score, max_marks,
                percentage, benchmark_verdict,
                full_answer_text, report_json, total_latency_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                now_iso,
                input_data.subject_paper,
                input_data.question_marks,
                input_data.question_text,
                filename or "submission.pdf",
                input_data.estimated_word_count,
                input_data.legibility_status or "AVERAGE",
                scorecard.total_score,
                scorecard.max_marks,
                scorecard.percentage,
                scorecard.benchmark_verdict,
                input_data.full_markdown_text,
                report_json_str,
                report.total_latency_seconds,
            ),
        )
        conn.commit()

    return eval_id


def get_evaluation(
    evaluation_id: str, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve full evaluation details and deserialized report by ID."""
    init_db(db_path)

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,)
        ).fetchone()

        if not row:
            return None

        report_dict = json.loads(row["report_json"])

        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "paper": row["paper"],
            "marks": row["marks"],
            "question_text": row["question_text"],
            "filename": row["filename"],
            "word_count": row["word_count"],
            "legibility_status": row["legibility_status"],
            "total_score": row["total_score"],
            "max_marks": row["max_marks"],
            "percentage": row["percentage"],
            "benchmark_verdict": row["benchmark_verdict"],
            "full_answer_text": row["full_answer_text"],
            "total_latency_seconds": row["total_latency_seconds"],
            "report": report_dict,
        }


def list_evaluations(
    limit: int = 50,
    offset: int = 0,
    paper: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """List evaluations ordered by created_at DESC with summary cards."""
    init_db(db_path)

    query = (
        "SELECT id, created_at, paper, marks, question_text, filename, "
        "word_count, legibility_status, total_score, max_marks, percentage, "
        "benchmark_verdict, total_latency_seconds FROM evaluations "
    )
    params: List[Any] = []

    if paper:
        query += "WHERE paper = ? "
        params.append(paper)

    query += "ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "paper": r["paper"],
                "marks": r["marks"],
                "question_text": r["question_text"],
                "filename": r["filename"],
                "word_count": r["word_count"],
                "legibility_status": r["legibility_status"],
                "total_score": r["total_score"],
                "max_marks": r["max_marks"],
                "percentage": r["percentage"],
                "benchmark_verdict": r["benchmark_verdict"],
                "total_latency_seconds": r["total_latency_seconds"],
            }
            for r in rows
        ]


def delete_evaluation(evaluation_id: str, db_path: Optional[Path] = None) -> bool:
    """Delete an evaluation record by ID."""
    init_db(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM evaluations WHERE id = ?", (evaluation_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
