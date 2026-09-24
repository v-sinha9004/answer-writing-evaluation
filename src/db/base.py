"""Abstract base repository defining the interface for evaluations persistence."""

from abc import ABC, abstractmethod
from typing import Optional, Union, Dict, Any, List
from src.evaluator.schemas import ComprehensiveEvaluationReport, EvaluationInput


class BaseEvaluationRepository(ABC):
    """Interface for evaluation repositories supporting SQLite and Supabase."""

    @abstractmethod
    def init_db(self, **kwargs) -> None:
        """Initialize database tables, schemas, or connections."""
        pass

    @abstractmethod
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
        """Save an evaluation report and candidate answer input."""
        pass

    @abstractmethod
    def get_evaluation(
        self,
        evaluation_id: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve full evaluation details and deserialized report by ID."""
        pass

    @abstractmethod
    def list_evaluations(
        self,
        limit: int = 50,
        offset: int = 0,
        paper: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """List evaluations ordered by created_at DESC."""
        pass

    @abstractmethod
    def delete_evaluation(
        self,
        evaluation_id: str,
        **kwargs,
    ) -> bool:
        """Delete an evaluation record by ID."""
        pass
