"""Master Scoring & Synthesis Arbiter Agent."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from src.evaluator.base_agent import BaseAgent
from src.evaluator.observability import observe_stage
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
    TokenUsage,
)
from src.config import MASTER_ARBITER_MODEL
from src.evaluator.prompts import MASTER_ARBITER_PROMPT


class ArbiterSynthesis(BaseModel):
    """Structured output for the Master Arbiter's qualitative synthesis."""
    executive_summary: str = Field(description="2-3 sentence candid UPSC examiner assessment")
    current_level_summary: str = Field(description="Short diagnosis of the answer's current state")
    step_1_good_answer: List[str] = Field(description="Top 2-3 concrete fixes to reach 55% marks")
    step_2_topper_answer: List[str] = Field(description="Advanced additions to reach 70%+ topper level")
    top_value_additions: List[str] = Field(description="Top 3 highest-yield micro-boosters")


class MasterScoringAgent(BaseAgent):
    """Computes calibrated mathematical marks, deduplicates feedback, and crafts the transformation roadmap."""

    DEFAULT_WEIGHTS = {
        "demand": 0.30,
        "knowledge": 0.35,
        "intro": 0.10,
        "structure": 0.10,
        "conclusion": 0.15,
    }

    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or MASTER_ARBITER_MODEL, **kwargs)

    def calculate_scorecard(
        self,
        input_data: EvaluationInput,
        demand_eval: DemandEvaluation,
        intro_eval: IntroEvaluation,
        structure_eval: StructureEvaluation,
        conclusion_eval: ConclusionEvaluation,
        fact_eval: KnowledgeEvaluation,
    ) -> ConsolidatedScorecard:
        """Deterministically calculate calibrated scores with dynamic weight redistribution."""
        max_marks = input_data.question_marks

        # Raw scores out of 10
        raw_scores = {
            "demand": demand_eval.directive_adherence_score,
            "knowledge": fact_eval.factual_accuracy_score,
            "intro": intro_eval.intro_score if intro_eval.intro_present else 0.0,
            "structure": structure_eval.structural_score,
            "conclusion": conclusion_eval.conclusion_score if conclusion_eval.conclusion_present else 0.0,
        }

        # Status check for dynamic re-weighting
        active_weights = {}
        for dim, weight in self.DEFAULT_WEIGHTS.items():
            eval_obj = {
                "demand": demand_eval,
                "knowledge": fact_eval,
                "intro": intro_eval,
                "structure": structure_eval,
                "conclusion": conclusion_eval,
            }[dim]

            if eval_obj.status != "FAILED":
                active_weights[dim] = weight

        # If all failed (extreme rare fallback)
        if not active_weights:
            active_weights = self.DEFAULT_WEIGHTS.copy()

        # Re-normalize weights to sum to 1.0
        total_active_weight = sum(active_weights.values())
        normalized_weights = {
            dim: weight / total_active_weight for dim, weight in active_weights.items()
        }

        # Calculate weighted average out of 10
        weighted_out_of_10 = sum(
            raw_scores[dim] * normalized_weights.get(dim, 0.0)
            for dim in raw_scores
        )

        # Scale to max_marks
        scaled_score = round((weighted_out_of_10 / 10.0) * max_marks, 2)

        # Apply deterministic penalty adjustments
        penalties: List[str] = []
        if not intro_eval.intro_present:
            penalties.append("Missing Introduction: Awarded 0/10 for opening context.")
        if not conclusion_eval.conclusion_present:
            penalties.append("Missing Conclusion: Awarded 0/10 for Way Forward.")

        # Under-length penalty
        expected_words = 150 if max_marks <= 10 else 250
        if input_data.estimated_word_count > 0 and input_data.estimated_word_count < (expected_words * 0.45):
            scaled_score = max(0.0, round(scaled_score - 1.0, 2))
            penalties.append(f"Severely under-length ({input_data.estimated_word_count} words vs ~{expected_words} expected): -1.0 mark deduction.")

        percentage = round((scaled_score / max_marks) * 100.0, 1)

        # Calibrated benchmark tier
        if percentage < 35.0:
            benchmark = "Below Average / Needs Fundamental Revision"
        elif percentage < 50.0:
            benchmark = "Average / Baseline Attempt"
        elif percentage < 65.0:
            benchmark = "Good / Competitive Mains Standard"
        else:
            benchmark = "Topper Quality / Exceptional Answer"

        # Build dimension breakdown dictionary
        dimensions_dict: Dict[str, DimensionScore] = {
            "Demand & Directive": DimensionScore(
                dimension_name="Demand & Directive",
                raw_score_out_of_10=round(raw_scores["demand"], 1),
                weight_pct=round(normalized_weights.get("demand", 0.0) * 100.0, 1),
                effective_marks=round((raw_scores["demand"] / 10.0) * normalized_weights.get("demand", 0.0) * max_marks, 2),
            ),
            "Knowledge & Facts": DimensionScore(
                dimension_name="Knowledge & Facts",
                raw_score_out_of_10=round(raw_scores["knowledge"], 1),
                weight_pct=round(normalized_weights.get("knowledge", 0.0) * 100.0, 1),
                effective_marks=round((raw_scores["knowledge"] / 10.0) * normalized_weights.get("knowledge", 0.0) * max_marks, 2),
            ),
            "Introduction": DimensionScore(
                dimension_name="Introduction",
                raw_score_out_of_10=round(raw_scores["intro"], 1),
                weight_pct=round(normalized_weights.get("intro", 0.0) * 100.0, 1),
                effective_marks=round((raw_scores["intro"] / 10.0) * normalized_weights.get("intro", 0.0) * max_marks, 2),
            ),
            "Structure & Presentation": DimensionScore(
                dimension_name="Structure & Presentation",
                raw_score_out_of_10=round(raw_scores["structure"], 1),
                weight_pct=round(normalized_weights.get("structure", 0.0) * 100.0, 1),
                effective_marks=round((raw_scores["structure"] / 10.0) * normalized_weights.get("structure", 0.0) * max_marks, 2),
            ),
            "Conclusion & Way Forward": DimensionScore(
                dimension_name="Conclusion & Way Forward",
                raw_score_out_of_10=round(raw_scores["conclusion"], 1),
                weight_pct=round(normalized_weights.get("conclusion", 0.0) * 100.0, 1),
                effective_marks=round((raw_scores["conclusion"] / 10.0) * normalized_weights.get("conclusion", 0.0) * max_marks, 2),
            ),
        }

        return ConsolidatedScorecard(
            total_score=scaled_score,
            max_marks=max_marks,
            percentage=percentage,
            benchmark_verdict=benchmark,
            dimensions=dimensions_dict,
            penalties_applied=penalties,
        )

    @observe_stage(name="master_arbiter_synthesis", as_type="evaluator")
    async def synthesize(
        self,
        input_data: EvaluationInput,
        demand_eval: DemandEvaluation,
        intro_eval: IntroEvaluation,
        structure_eval: StructureEvaluation,
        conclusion_eval: ConclusionEvaluation,
        fact_eval: KnowledgeEvaluation,
        total_latency_seconds: float = 0.0,
    ) -> ComprehensiveEvaluationReport:
        """Synthesize specialist evaluations into a coherent report with a transformation roadmap."""

        # Step 1: Calculate deterministic scorecard
        scorecard = self.calculate_scorecard(
            input_data=input_data,
            demand_eval=demand_eval,
            intro_eval=intro_eval,
            structure_eval=structure_eval,
            conclusion_eval=conclusion_eval,
            fact_eval=fact_eval,
        )

        # Step 2: Prepare synthesis prompt
        user_prompt = f"""SYNTHESIZE SPECIALIST EVALUATIONS FOR UPSC ANSWER:

[QUESTION STATEMENT]:
"{input_data.question_text}"
[MAX MARKS]: {scorecard.max_marks} | [AWARDED SCORE]: {scorecard.total_score} ({scorecard.percentage}%) - {scorecard.benchmark_verdict}

--- SPECIALIST FINDINGS ---
1. DEMAND AGENT:
- Coverage: {demand_eval.demand_coverage_pct}% | Directive Score: {demand_eval.directive_adherence_score}/10
- Critique: {demand_eval.critique}
- Unaddressed Sub-demands: {demand_eval.unaddressed_sub_parts}

2. INTRO AGENT:
- Intro Present: {intro_eval.intro_present} | Score: {intro_eval.intro_score}/10
- Critique: {intro_eval.critique}
- Model Intro Rewrite: {intro_eval.model_intro_rewrite}

3. STRUCTURE AGENT:
- Structural Score: {structure_eval.structural_score}/10
- Critique: {structure_eval.critique}

4. CONCLUSION AGENT:
- Conclusion Present: {conclusion_eval.conclusion_present} | Score: {conclusion_eval.conclusion_score}/10
- Critique: {conclusion_eval.critique}
- Model Conclusion Rewrite: {conclusion_eval.model_conclusion_rewrite}

5. KNOWLEDGE & RAG FACT AGENT:
- Factual Score: {fact_eval.factual_accuracy_score}/10
- Factual Claims Checked: {[f"{c.claim}: {c.verdict}" for c in fact_eval.claims_checked]}
- Syllabus Enrichments: {fact_eval.syllabus_enrichments}
- Critique: {fact_eval.critique}

Provide:
1. Candid 2-3 sentence executive_summary.
2. 3-step Answer Transformation Roadmap (current_level_summary, step_1_good_answer, step_2_topper_answer).
3. Exactly top 3 high-impact value additions (+1.5 mark boosters).
"""

        master_usage = TokenUsage()
        try:
            synthesis, master_usage = await self.run_structured_with_usage(
                system_prompt=MASTER_ARBITER_PROMPT,
                user_prompt=user_prompt,
                response_format=ArbiterSynthesis,
            )
            roadmap = TransformationRoadmap(
                current_level_summary=synthesis.current_level_summary,
                step_1_good_answer=synthesis.step_1_good_answer,
                step_2_topper_answer=synthesis.step_2_topper_answer,
            )
            exec_summary = synthesis.executive_summary
            value_additions = synthesis.top_value_additions
        except Exception as e:
            # Safe fallback if synthesis LLM call fails
            exec_summary = f"Score: {scorecard.total_score}/{scorecard.max_marks} ({scorecard.percentage}%). {scorecard.benchmark_verdict}."
            roadmap = TransformationRoadmap(
                current_level_summary=f"Evaluated at {scorecard.total_score}/{scorecard.max_marks}.",
                step_1_good_answer=[
                    "Fix factual inaccuracies identified in the knowledge audit.",
                    "Adopt bold-prefixed bullet points for structural clarity.",
                ],
                step_2_topper_answer=[
                    "Incorporate the provided Model Introduction and Model Conclusion.",
                    "Ensure exhaustive coverage of all question sub-parts.",
                ],
            )
            value_additions = [
                "Adopt the provided Model Introduction.",
                "Incorporate core syllabus enrichments from the knowledge audit.",
                "Conclude with constitutional/policy relevance.",
            ]

        # Consolidate per-agent token telemetry
        token_breakdown = {
            "Demand & Directive Agent": demand_eval.token_usage,
            "Introduction Agent": intro_eval.token_usage,
            "Structure & Presentation Agent": structure_eval.token_usage,
            "Conclusion & Way Forward Agent": conclusion_eval.token_usage,
            "Knowledge & Fact Agent (RAG)": fact_eval.token_usage,
            "Master Scoring Arbiter": master_usage,
        }
        total_prompt = sum(u.prompt_tokens for u in token_breakdown.values())
        total_completion = sum(u.completion_tokens for u in token_breakdown.values())
        total_usage = TokenUsage(
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
        )

        return ComprehensiveEvaluationReport(
            scorecard=scorecard,
            executive_summary=exec_summary,
            demand_evaluation=demand_eval,
            intro_evaluation=intro_eval,
            structure_evaluation=structure_eval,
            conclusion_evaluation=conclusion_eval,
            knowledge_evaluation=fact_eval,
            transformation_roadmap=roadmap,
            top_value_additions=value_additions,
            total_latency_seconds=total_latency_seconds,
            token_usage_breakdown=token_breakdown,
            total_token_usage=total_usage,
            is_empty_submission=False,
        )
