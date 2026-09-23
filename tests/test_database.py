"""Unit tests for SQLite evaluations repository."""

import pytest
from pathlib import Path
from src.db.repository import (
    init_db,
    save_evaluation,
    get_evaluation,
    list_evaluations,
    delete_evaluation,
)
from src.evaluator.schemas import (
    EvaluationInput,
    ComprehensiveEvaluationReport,
    ConsolidatedScorecard,
    DemandEvaluation,
    IntroEvaluation,
    StructureEvaluation,
    ConclusionEvaluation,
    KnowledgeEvaluation,
    TransformationRoadmap,
)


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_evaluations.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_report():
    return ComprehensiveEvaluationReport(
        scorecard=ConsolidatedScorecard(
            total_score=8.5,
            max_marks=15,
            percentage=56.7,
            benchmark_verdict="Solid Answer (50-60%)",
            dimensions={},
            penalties_applied=[],
        ),
        demand_evaluation=DemandEvaluation(directive_adherence_score=8.0, demand_coverage_pct=85.0),
        intro_evaluation=IntroEvaluation(intro_score=7.0),
        structure_evaluation=StructureEvaluation(structural_score=7.5),
        conclusion_evaluation=ConclusionEvaluation(conclusion_score=7.0),
        knowledge_evaluation=KnowledgeEvaluation(factual_accuracy_score=8.0),
        transformation_roadmap=TransformationRoadmap(
            current_level_summary="Good standard",
            step_1_good_answer=["Fix formatting"],
            step_2_topper_answer=["Add maps"],
        ),
        top_value_additions=["Quote landmark commissions"],
        total_latency_seconds=3.42,
    )


@pytest.fixture
def sample_input():
    return EvaluationInput(
        question_text="Examine the role of the press during the Indian freedom struggle.",
        question_marks=15,
        full_markdown_text="The press played a revolutionary role in awakening national consciousness...",
        detected_intro="The press played a revolutionary role...",
        detected_conclusion="Thus, the press was an instrument of liberation.",
        estimated_word_count=215,
        legibility_status="CLEAR",
        subject_paper="GS-1",
    )


def test_init_and_save_evaluation(temp_db, sample_input, sample_report):
    eval_id = save_evaluation(sample_input, sample_report, filename="press_role.pdf", db_path=temp_db)
    assert eval_id.startswith("eval_")
    assert sample_report.id == eval_id
    assert sample_report.paper == "GS-1"


def test_get_evaluation(temp_db, sample_input, sample_report):
    eval_id = save_evaluation(sample_input, sample_report, filename="press_role.pdf", db_path=temp_db)
    record = get_evaluation(eval_id, db_path=temp_db)

    assert record is not None
    assert record["id"] == eval_id
    assert record["paper"] == "GS-1"
    assert record["marks"] == 15
    assert record["total_score"] == 8.5
    assert record["benchmark_verdict"] == "Solid Answer (50-60%)"
    assert "revolutionary role" in record["full_answer_text"]


def test_list_evaluations(temp_db, sample_input, sample_report):
    # Save two evaluations
    id1 = save_evaluation(sample_input, sample_report, filename="copy1.pdf", db_path=temp_db)

    input2 = sample_input.model_copy(update={"subject_paper": "GS-2", "question_marks": 10})
    report2 = sample_report.model_copy(deep=True)
    report2.scorecard.total_score = 6.0
    report2.scorecard.max_marks = 10
    id2 = save_evaluation(input2, report2, filename="copy2.pdf", db_path=temp_db)

    # List all
    all_evals = list_evaluations(db_path=temp_db)
    assert len(all_evals) == 2
    assert all_evals[0]["id"] == id2  # Most recent first
    assert all_evals[1]["id"] == id1

    # Filter by paper
    gs1_evals = list_evaluations(paper="GS-1", db_path=temp_db)
    assert len(gs1_evals) == 1
    assert gs1_evals[0]["id"] == id1


def test_delete_evaluation(temp_db, sample_input, sample_report):
    eval_id = save_evaluation(sample_input, sample_report, filename="delete_me.pdf", db_path=temp_db)
    assert get_evaluation(eval_id, db_path=temp_db) is not None

    deleted = delete_evaluation(eval_id, db_path=temp_db)
    assert deleted is True
    assert get_evaluation(eval_id, db_path=temp_db) is None

    # Deleting nonexistent returns False
    assert delete_evaluation("nonexistent_id", db_path=temp_db) is False
