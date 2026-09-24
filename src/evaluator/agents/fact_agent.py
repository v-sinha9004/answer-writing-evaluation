"""Specialist Agent: Knowledge & Factual Accuracy Evaluator powered directly by LLM."""

from typing import Optional, List
from pydantic import BaseModel, Field
from src.config import FACT_AGENT_MODEL
from src.evaluator.base_agent import BaseAgent
from src.evaluator.observability import observe_stage
from src.evaluator.schemas import EvaluationInput, KnowledgeEvaluation, FactualClaimCheck, ActionableImprovement, TokenUsage
from src.evaluator.prompts import FACT_EXTRACTION_PROMPT, FACT_VERIFICATION_PROMPT


class ExtractedClaims(BaseModel):
    """Temporary schema for extracting testable claims."""
    claims: List[str] = Field(default_factory=list, description="List of testable factual statements")


class FactAgent(BaseAgent):
    """Extracts factual claims and verifies accuracy against authoritative UPSC syllabus standards via LLM."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or FACT_AGENT_MODEL, **kwargs)

    @observe_stage(name="fact_agent", as_type="agent")
    async def evaluate(self, input_data: EvaluationInput) -> KnowledgeEvaluation:
        body_text = (input_data.full_markdown_text or "").strip()
        paper = input_data.subject_paper


        if not body_text or len(body_text) < 10:
            return KnowledgeEvaluation(
                status="SUCCESS",
                claims_checked=[],
                factual_accuracy_score=0.0,
                syllabus_enrichments=["Include standard GS-1 Modern History textbook facts."],
                critique="No substantive text provided to assess factual knowledge.",
                improvements=[
                    ActionableImprovement(
                        section="Knowledge & Facts",
                        issue_detected="Empty answer text; zero facts provided.",
                        mark_impact="Zero marks for subject knowledge.",
                        prescription="Include authentic dates, acts, and personalities.",
                        plug_and_play_snippet="Quote specific legislative acts and historical figures."
                    )
                ]
            )

        # Step 1: Extract testable factual claims
        extraction_user_prompt = f"""EXTRACT FACTUAL CLAIMS FROM THIS CANDIDATE ANSWER:

[QUESTION]:
"{input_data.question_text}"

[CANDIDATE TEXT]:
\"\"\"{body_text}\"\"\"

Extract 3 to 6 key testable assertions (dates, names, acts, events, treaties).
"""
        extraction_usage = TokenUsage()
        try:
            extracted, extraction_usage = await self.run_structured_with_usage(
                system_prompt=FACT_EXTRACTION_PROMPT,
                user_prompt=extraction_user_prompt,
                response_format=ExtractedClaims,
            )
            claims = extracted.claims
        except Exception:
            claims = []

        # Step 2: Verify claims directly against authoritative UPSC syllabus knowledge
        ref_section = f"""[REFERENCE KNOWLEDGE BASE]:
Verify against standard authentic UPSC syllabus benchmarks (NCERTs, standard reference texts for {paper.upper() if paper else 'General Studies'}, Constitution of India, Supreme Court precedents, and official reports)."""

        # Step 3: Verify claims against UPSC knowledge base / reference passages
        verification_user_prompt = f"""VERIFY THE CANDIDATE'S FACTUAL CLAIMS:

[QUESTION]:
"{input_data.question_text}"

[SUBJECT PAPER]:
"{paper.upper() if paper else 'GENERAL STUDIES'}"

[EXTRACTED CLAIMS TO VERIFY]:
{chr(10).join(f"- {c}" for c in claims) if claims else "- General factual assertions in the answer"}

[CANDIDATE ANSWER]:
\"\"\"{body_text}\"\"\"

{ref_section}

For each claim:
1. Mark VERIFIED, INCORRECT, or UNVERIFIED.
2. If INCORRECT, provide the exact correction citing the standard authority or reference text.
3. Assign a factual_accuracy_score (0-10).
4. Suggest 2-3 core syllabus concepts/keywords from the standard syllabus to enrich the answer.
5. Provide ActionableImprovement items with ready-to-insert corrections.
6. Mark INCORRECT only when contradictory/opposite claims are provided otherwise mark it as UNVERIFIED.
7. Don't mark a claim as INCORRECT if the answer is partially correct or not fully mentioned.
"""

        result, verification_usage = await self.run_structured_with_usage(
            system_prompt=FACT_VERIFICATION_PROMPT,
            user_prompt=verification_user_prompt,
            response_format=KnowledgeEvaluation,
        )

        total_prompt = extraction_usage.prompt_tokens + verification_usage.prompt_tokens
        total_completion = extraction_usage.completion_tokens + verification_usage.completion_tokens
        result.token_usage = TokenUsage(
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
        )
        result.status = "SUCCESS"
        return result
