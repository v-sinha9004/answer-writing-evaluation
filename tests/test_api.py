"""Unit tests for FastAPI endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.api.server import app
from src.evaluator.schemas import (
    ComprehensiveEvaluationReport,
    ConsolidatedScorecard,
    DemandEvaluation,
    IntroEvaluation,
    StructureEvaluation,
    ConclusionEvaluation,
    KnowledgeEvaluation,
    TransformationRoadmap,
    TokenUsage,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "upsc-evaluator"


@pytest.mark.anyio
async def test_evaluate_sample_endpoint(client):
    """Test evaluate sample endpoint with mocked orchestrator."""
    mock_report = ComprehensiveEvaluationReport(
        scorecard=ConsolidatedScorecard(
            total_score=8.5,
            max_marks=15,
            percentage=56.7,
            benchmark_verdict="Solid Answer (50-60%)",
            dimensions={},
            penalties_applied=[],
        ),
        executive_summary="Good answer covering the main aspects.",
        demand_evaluation=DemandEvaluation(directive_adherence_score=8.0, demand_coverage_pct=80.0),
        intro_evaluation=IntroEvaluation(intro_score=7.0),
        structure_evaluation=StructureEvaluation(structural_score=7.5),
        conclusion_evaluation=ConclusionEvaluation(conclusion_score=7.0),
        knowledge_evaluation=KnowledgeEvaluation(factual_accuracy_score=8.0),
        transformation_roadmap=TransformationRoadmap(
            current_level_summary="Good base",
            step_1_good_answer=["Fix points"],
            step_2_topper_answer=["Add analysis"],
        ),
        top_value_additions=["Add diagram"],
    )

    with patch("src.api.server.orchestrator.evaluate", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        response = client.post("/api/evaluate-sample", data={"paper": "GS-1", "marks": 15})
        assert response.status_code == 200
        data = response.json()
        assert data["scorecard"]["total_score"] == 8.5
        assert data["scorecard"]["max_marks"] == 15
        assert "Good answer" in data["executive_summary"]


def test_evaluate_pdf_invalid_file_type(client):
    """Test rejecting non-PDF file uploads."""
    response = client.post(
        "/api/evaluate",
        files={"file": ("test.txt", b"plain text content", "text/plain")},
        data={"paper": "GS-1", "marks": 15},
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]


@pytest.mark.anyio
async def test_evaluate_pdf_upload_success(client):
    """Test uploading a valid PDF file and receiving evaluation results."""
    mock_report = ComprehensiveEvaluationReport(
        scorecard=ConsolidatedScorecard(
            total_score=7.0,
            max_marks=10,
            percentage=70.0,
            benchmark_verdict="Topper Tier (70%+)",
            dimensions={},
            penalties_applied=[],
        ),
        executive_summary="Solid analytical presentation.",
        demand_evaluation=DemandEvaluation(),
        intro_evaluation=IntroEvaluation(),
        structure_evaluation=StructureEvaluation(),
        conclusion_evaluation=ConclusionEvaluation(),
        knowledge_evaluation=KnowledgeEvaluation(),
        transformation_roadmap=TransformationRoadmap(
            current_level_summary="Topper quality",
            step_1_good_answer=[],
            step_2_topper_answer=[],
        ),
        top_value_additions=["Maintain structure"],
    )

    with patch("src.api.server.orchestrator.evaluate", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        with open("data/test_upload.pdf", "rb") as f:
            pdf_bytes = f.read()

        response = client.post(
            "/api/evaluate",
            files={"file": ("test_upload.pdf", pdf_bytes, "application/pdf")},
            data={"paper": "GS-1", "marks": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["scorecard"]["total_score"] == 7.0
        assert data["scorecard"]["max_marks"] == 10
