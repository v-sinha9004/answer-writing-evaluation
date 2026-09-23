"""UPSC Mains Answer Evaluation & Coaching Engine."""

from src.evaluator.schemas import (
    EvaluationInput,
    ComprehensiveEvaluationReport,
    ConsolidatedScorecard,
    ActionableImprovement,
    DemandEvaluation,
    IntroEvaluation,
    StructureEvaluation,
    ConclusionEvaluation,
    KnowledgeEvaluation,
)
from src.evaluator.orchestrator import EvaluationOrchestrator
from src.evaluator.pdf_processor import PDFProcessor, VisionOCRAgent

__all__ = [
    "EvaluationOrchestrator",
    "PDFProcessor",
    "VisionOCRAgent",
    "EvaluationInput",
    "ComprehensiveEvaluationReport",
    "ConsolidatedScorecard",
    "ActionableImprovement",
    "DemandEvaluation",
    "IntroEvaluation",
    "StructureEvaluation",
    "ConclusionEvaluation",
    "KnowledgeEvaluation",
]
