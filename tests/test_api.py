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


@pytest.fixture(autouse=True)
def isolate_test_db(tmp_path, monkeypatch):
    """Ensure all API tests run against an isolated temporary database."""
    test_db = tmp_path / "test_api_evaluations.db"
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr("src.config.DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr("src.config.DATABASE_PATH", test_db)
    monkeypatch.setattr("src.db.repository.DATABASE_PATH", test_db)
    from src.db.repository import init_db
    init_db(test_db)
    return test_db


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
        demand_evaluation=DemandEvaluation(directive_adherence_score=8.0, demand_coverage_pct=80.0),
        intro_evaluation=IntroEvaluation(intro_score=7.0),
        structure_evaluation=StructureEvaluation(structural_score=7.5),
        conclusion_evaluation=ConclusionEvaluation(conclusion_score=7.0),
        knowledge_evaluation=KnowledgeEvaluation(factual_accuracy_score=8.0),
        transformation_roadmap=TransformationRoadmap(
            good_answer_steps=["Fix points"],
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
        demand_evaluation=DemandEvaluation(),
        intro_evaluation=IntroEvaluation(),
        structure_evaluation=StructureEvaluation(),
        conclusion_evaluation=ConclusionEvaluation(),
        knowledge_evaluation=KnowledgeEvaluation(),
        transformation_roadmap=TransformationRoadmap(
            good_answer_steps=[],
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
        assert data.get("id") is not None


def test_evaluations_endpoints_flow(client):
    """Test full CRUD lifecycle on /api/evaluations endpoints."""
    # 1. Trigger evaluate-sample to persist an entry
    mock_report = ComprehensiveEvaluationReport(
        scorecard=ConsolidatedScorecard(
            total_score=9.0,
            max_marks=15,
            percentage=60.0,
            benchmark_verdict="Good Answer",
            dimensions={},
            penalties_applied=[],
        ),
        demand_evaluation=DemandEvaluation(),
        intro_evaluation=IntroEvaluation(),
        structure_evaluation=StructureEvaluation(),
        conclusion_evaluation=ConclusionEvaluation(),
        knowledge_evaluation=KnowledgeEvaluation(),
        transformation_roadmap=TransformationRoadmap(
            good_answer_steps=[],
        ),
        top_value_additions=["Maintain structure"],
    )

    with patch("src.api.server.orchestrator.evaluate", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        resp = client.post("/api/evaluate-sample", data={"paper": "GS-1", "marks": 15})
        assert resp.status_code == 200
        eval_id = resp.json().get("id")
        assert eval_id is not None

        # 2. List evaluations
        list_resp = client.get("/api/evaluations")
        assert list_resp.status_code == 200
        evals = list_resp.json()
        assert isinstance(evals, list)
        matching = [e for e in evals if e["id"] == eval_id]
        assert len(matching) == 1
        assert matching[0]["paper"] == "GS-1"

        # 3. Get single evaluation by ID
        get_resp = client.get(f"/api/evaluations/{eval_id}")
        assert get_resp.status_code == 200
        record = get_resp.json()
        assert record["id"] == eval_id
        assert record["ocr_json"] is not None

        # 4. Delete evaluation by ID
        del_resp = client.delete(f"/api/evaluations/{eval_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # 5. Verify 404 after deletion
        get_after = client.get(f"/api/evaluations/{eval_id}")
        assert get_after.status_code == 404

