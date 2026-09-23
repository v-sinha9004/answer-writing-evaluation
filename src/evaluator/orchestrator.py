"""Asynchronous orchestrator coordinating the multi-agent evaluation pipeline."""

import asyncio
import time
from typing import Dict, Any, Union, Optional
from src.evaluator.schemas import (
    EvaluationInput,
    ComprehensiveEvaluationReport,
    ConsolidatedScorecard,
    DimensionScore,
    TransformationRoadmap,
    DemandEvaluation,
    IntroEvaluation,
    StructureEvaluation,
    ConclusionEvaluation,
    KnowledgeEvaluation,
    ActionableImprovement,
)
from src.evaluator.agents.demand_agent import DemandAgent
from src.evaluator.agents.intro_agent import IntroAgent
from src.evaluator.agents.structure_agent import StructureAgent
from src.evaluator.agents.conclusion_agent import ConclusionAgent
from src.evaluator.agents.fact_agent import FactAgent
from src.evaluator.agents.master_arbiter import MasterScoringAgent


class EvaluationOrchestrator:
    """Coordinates parallel execution of specialist evaluator agents in a deterministic Native DAG."""

    def __init__(
        self,
        demand_agent: Optional[DemandAgent] = None,
        intro_agent: Optional[IntroAgent] = None,
        structure_agent: Optional[StructureAgent] = None,
        conclusion_agent: Optional[ConclusionAgent] = None,
        fact_agent: Optional[FactAgent] = None,
        master_arbiter: Optional[MasterScoringAgent] = None,
    ):
        self.demand_agent = demand_agent or DemandAgent()
        self.intro_agent = intro_agent or IntroAgent()
        self.structure_agent = structure_agent or StructureAgent()
        self.conclusion_agent = conclusion_agent or ConclusionAgent()
        self.fact_agent = fact_agent or FactAgent()
        self.master_arbiter = master_arbiter or MasterScoringAgent()

    def _handle_empty_submission(self, input_data: EvaluationInput, start_time: float) -> ComprehensiveEvaluationReport:
        """Short-circuit for empty answer sheets without incurring LLM API costs."""
        max_marks = input_data.question_marks
        elapsed = round(time.perf_counter() - start_time, 3)

        empty_dims = {
            dim: DimensionScore(
                dimension_name=dim,
                raw_score_out_of_10=0.0,
                weight_pct=w * 100.0,
                effective_marks=0.0,
            )
            for dim, w in [
                ("Demand & Directive", 0.30),
                ("Knowledge & Facts", 0.35),
                ("Introduction", 0.10),
                ("Structure & Presentation", 0.10),
                ("Conclusion & Way Forward", 0.15),
            ]
        }

        scorecard = ConsolidatedScorecard(
            total_score=0.0,
            max_marks=max_marks,
            percentage=0.0,
            benchmark_verdict="Blank / Empty Submission",
            dimensions=empty_dims,
            penalties_applied=["Zero submission: Answer text was completely blank or missing."],
        )

        roadmap = TransformationRoadmap(
            current_level_summary="Blank copy detected. No written text was provided for evaluation.",
            step_1_good_answer=[
                "Ensure answer page images are clear, properly lighted, and legible before uploading.",
                "Verify OCR transcription contains the written answer text.",
            ],
            step_2_topper_answer=[
                "Write an answer addressing all sub-demands of the question within the prescribed word limit.",
            ],
        )

        return ComprehensiveEvaluationReport(
            scorecard=scorecard,
            executive_summary=(
                "Evaluation could not be performed because the answer text was empty or illegible. "
                "Awarded 0 marks. Please check your uploaded copy and re-submit."
            ),
            demand_evaluation=DemandEvaluation(
                status="SKIPPED",
                directive_adherence_score=0.0,
                demand_coverage_pct=0.0,
                critique="No text provided.",
            ),
            intro_evaluation=IntroEvaluation(
                status="SKIPPED",
                intro_present=False,
                intro_score=0.0,
                critique="No text provided.",
                model_intro_rewrite="[N/A - Empty Submission]",
            ),
            structure_evaluation=StructureEvaluation(
                status="SKIPPED",
                structural_score=0.0,
                critique="No text provided.",
            ),
            conclusion_evaluation=ConclusionEvaluation(
                status="SKIPPED",
                conclusion_present=False,
                conclusion_score=0.0,
                critique="No text provided.",
                model_conclusion_rewrite="[N/A - Empty Submission]",
            ),
            knowledge_evaluation=KnowledgeEvaluation(
                status="SKIPPED",
                factual_accuracy_score=0.0,
                critique="No text provided.",
            ),
            transformation_roadmap=roadmap,
            top_value_additions=["Submit a legible copy with handwritten or typed answer text."],
            total_latency_seconds=elapsed,
            is_empty_submission=True,
        )

    async def evaluate(self, input_payload: Union[Dict[str, Any], EvaluationInput]) -> ComprehensiveEvaluationReport:
        """Run end-to-end multi-agent evaluation on the input answer."""
        start_time = time.perf_counter()

        # Step 1: Validate & normalize input payload
        if isinstance(input_payload, dict):
            input_data = EvaluationInput.model_validate(input_payload)
        else:
            input_data = input_payload

        # Step 2: Pre-flight check for empty answer
        if not input_data.full_markdown_text or not input_data.full_markdown_text.strip():
            return self._handle_empty_submission(input_data, start_time)

        # Step 3: Fan-Out - Dispatch all 5 specialists concurrently
        results = await asyncio.gather(
            self.demand_agent.evaluate(input_data),
            self.intro_agent.evaluate(input_data),
            self.structure_agent.evaluate(input_data),
            self.conclusion_agent.evaluate(input_data),
            self.fact_agent.evaluate(input_data),
            return_exceptions=True,
        )

        demand_res, intro_res, struct_res, concl_res, fact_res = results

        # Step 4: Handle partial failures gracefully with typed fallback models
        if isinstance(demand_res, Exception):
            demand_res = DemandEvaluation.fallback(str(demand_res))
        if isinstance(intro_res, Exception):
            intro_res = IntroEvaluation.fallback(str(intro_res))
        if isinstance(struct_res, Exception):
            struct_res = StructureEvaluation.fallback(str(struct_res))
        if isinstance(concl_res, Exception):
            concl_res = ConclusionEvaluation.fallback(str(concl_res))
        if isinstance(fact_res, Exception):
            fact_res = KnowledgeEvaluation.fallback(str(fact_res))

        # Step 5: Fan-In - Synthesize with Master Arbiter
        total_latency = round(time.perf_counter() - start_time, 2)
        final_report = await self.master_arbiter.synthesize(
            input_data=input_data,
            demand_eval=demand_res,
            intro_eval=intro_res,
            structure_eval=struct_res,
            conclusion_eval=concl_res,
            fact_eval=fact_res,
            total_latency_seconds=total_latency,
        )

        return final_report
