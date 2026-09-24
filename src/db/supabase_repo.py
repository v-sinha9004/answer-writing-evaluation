"""Supabase repository for persistent storage of UPSC evaluations."""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Union, Dict, Any, List
from dotenv import load_dotenv
from supabase import create_client, Client

from src.config import (
    ROOT_DIR,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    is_supabase_configured,
)
from src.evaluator.schemas import ComprehensiveEvaluationReport, EvaluationInput
from src.db.base import BaseEvaluationRepository

logger = logging.getLogger("upsc-supabase-db")


class SupabaseEvaluationRepository(BaseEvaluationRepository):
    """Supabase implementation of evaluation storage using PostgREST."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
    ):
        load_dotenv(ROOT_DIR / ".env", override=True)
        self.url = (url or os.getenv("SUPABASE_URL") or SUPABASE_URL).strip()
        self.key = (key or os.getenv("SUPABASE_ANON_KEY") or SUPABASE_ANON_KEY).strip()
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Lazy-initialize Supabase client."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = (self.url or os.getenv("SUPABASE_URL") or "").strip()
        key = (self.key or os.getenv("SUPABASE_ANON_KEY") or "").strip()

        if not url or not key:
            raise RuntimeError(
                "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your environment or .env file."
            )

        if self._client is None:
            self._client = create_client(url, key)
        return self._client

    def is_configured(self) -> bool:
        """Check if Supabase credentials are configured."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = self.url or os.getenv("SUPABASE_URL", "")
        key = self.key or os.getenv("SUPABASE_ANON_KEY", "")
        return bool(url and key)

    def init_db(self, **kwargs) -> None:
        """Check connectivity to Supabase evaluations table."""
        if not self.is_configured():
            logger.warning("Supabase is not configured. Skipping table check.")
            return

        try:
            # Quick connectivity check
            self.client.table("evaluations").select("id").limit(1).execute()
            logger.info("Supabase connection to 'evaluations' table verified.")
        except Exception as e:
            logger.error(f"Error checking Supabase 'evaluations' table: {e}", exc_info=True)
            raise

    def save_evaluation(
        self,
        input_data: Union[EvaluationInput, Dict[str, Any]],
        report: ComprehensiveEvaluationReport,
        filename: Optional[str] = None,
        ocr_json: Optional[Union[str, Dict[str, Any]]] = None,
        pdf_url: Optional[str] = None,
        eval_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Save an evaluation report and candidate answer input into Supabase."""
        if isinstance(input_data, dict):
            input_data = EvaluationInput.model_validate(input_data)

        final_id = eval_id or f"eval_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        final_pdf_url = (
            pdf_url
            or getattr(input_data, "pdf_url", None)
            or getattr(report, "pdf_url", None)
        )

        report.id = final_id
        report.created_at = now_iso
        report.paper = input_data.subject_paper
        report.question_text = input_data.question_text
        report.filename = filename
        report.pdf_url = final_pdf_url

        scorecard = report.scorecard
        report_dict = json.loads(report.model_dump_json())

        # Determine OCR JSON
        raw_ocr = ocr_json or getattr(input_data, "ocr_json", None)
        ocr_dict = None
        if isinstance(raw_ocr, dict):
            ocr_dict = raw_ocr
        elif isinstance(raw_ocr, str) and raw_ocr.strip():
            try:
                ocr_dict = json.loads(raw_ocr)
            except Exception:
                ocr_dict = raw_ocr

        record = {
            "id": final_id,
            "created_at": now_iso,
            "paper": input_data.subject_paper,
            "marks": input_data.question_marks,
            "question_text": input_data.question_text,
            "filename": filename or "submission.pdf",
            "word_count": input_data.estimated_word_count,
            "legibility_status": input_data.legibility_status or "AVERAGE",
            "total_score": scorecard.total_score,
            "max_marks": scorecard.max_marks,
            "percentage": scorecard.percentage,
            "benchmark_verdict": scorecard.benchmark_verdict,
            "full_answer_text": input_data.full_markdown_text,
            "report_json": report_dict,
            "ocr_json": ocr_dict,
            "pdf_url": final_pdf_url,
            "total_latency_seconds": report.total_latency_seconds,
        }

        try:
            self.client.table("evaluations").insert(record).execute()
            logger.info(f"Saved evaluation '{final_id}' to Supabase evaluations table.")
            return final_id
        except Exception as e:
            logger.error(f"Failed to insert evaluation into Supabase: {e}", exc_info=True)
            raise

    def get_evaluation(
        self,
        evaluation_id: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve full evaluation details and deserialized report by ID from Supabase."""
        try:
            response = (
                self.client.table("evaluations")
                .select("*")
                .eq("id", evaluation_id)
                .execute()
            )

            if not response.data:
                return None

            row = response.data[0]

            report_data = row.get("report_json")
            if isinstance(report_data, str):
                report_dict = json.loads(report_data)
            elif isinstance(report_data, dict):
                report_dict = report_data
            else:
                report_dict = {}

            if row.get("pdf_url"):
                report_dict["pdf_url"] = row["pdf_url"]
            report_dict["id"] = row["id"]

            ocr_data = row.get("ocr_json")
            if isinstance(ocr_data, str):
                try:
                    ocr_data = json.loads(ocr_data)
                except Exception:
                    pass

            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "paper": row["paper"],
                "marks": row["marks"],
                "question_text": row.get("question_text"),
                "filename": row.get("filename"),
                "pdf_url": row.get("pdf_url"),
                "word_count": row.get("word_count", 0),
                "legibility_status": row.get("legibility_status", "AVERAGE"),
                "total_score": row.get("total_score", 0.0),
                "max_marks": row.get("max_marks", 15),
                "percentage": row.get("percentage", 0.0),
                "benchmark_verdict": row.get("benchmark_verdict", ""),
                "full_answer_text": row.get("full_answer_text"),
                "ocr_json": ocr_data,
                "total_latency_seconds": row.get("total_latency_seconds", 0.0),
                "report": report_dict,
            }
        except Exception as e:
            logger.error(f"Error fetching evaluation '{evaluation_id}' from Supabase: {e}", exc_info=True)
            raise

    def list_evaluations(
        self,
        limit: int = 50,
        offset: int = 0,
        paper: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """List evaluations ordered by created_at DESC from Supabase."""
        try:
            fields = (
                "id, created_at, paper, marks, question_text, filename, "
                "word_count, legibility_status, total_score, max_marks, "
                "percentage, benchmark_verdict, pdf_url, total_latency_seconds"
            )
            query = self.client.table("evaluations").select(fields)

            if paper:
                query = query.eq("paper", paper)

            query = query.order("created_at", desc=True)

            if limit > 0:
                query = query.range(offset, offset + limit - 1)

            response = query.execute()

            results = []
            for r in response.data or []:
                results.append({
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "paper": r["paper"],
                    "marks": r["marks"],
                    "question_text": r.get("question_text"),
                    "filename": r.get("filename"),
                    "pdf_url": r.get("pdf_url"),
                    "word_count": r.get("word_count", 0),
                    "legibility_status": r.get("legibility_status", "AVERAGE"),
                    "total_score": r.get("total_score", 0.0),
                    "max_marks": r.get("max_marks", 15),
                    "percentage": r.get("percentage", 0.0),
                    "benchmark_verdict": r.get("benchmark_verdict", ""),
                    "total_latency_seconds": r.get("total_latency_seconds", 0.0),
                })
            return results
        except Exception as e:
            logger.error(f"Error listing evaluations from Supabase: {e}", exc_info=True)
            raise

    def delete_evaluation(
        self,
        evaluation_id: str,
        **kwargs,
    ) -> bool:
        """Delete an evaluation record by ID from Supabase."""
        try:
            response = (
                self.client.table("evaluations")
                .delete()
                .eq("id", evaluation_id)
                .execute()
            )
            return bool(response.data and len(response.data) > 0)
        except Exception as e:
            logger.error(f"Error deleting evaluation '{evaluation_id}' from Supabase: {e}", exc_info=True)
            raise
