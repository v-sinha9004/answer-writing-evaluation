"""Specialist Agent: Knowledge & Factual Accuracy Evaluator grounded in RAG."""

from typing import Optional, List
from pydantic import BaseModel, Field
from src.config import FACT_AGENT_MODEL
from src.evaluator.base_agent import BaseAgent
from src.evaluator.schemas import EvaluationInput, KnowledgeEvaluation, FactualClaimCheck, ActionableImprovement, TokenUsage
from src.evaluator.prompts import FACT_EXTRACTION_PROMPT, FACT_VERIFICATION_PROMPT
from src.rag.retriever import get_retriever, HybridRetriever


class ExtractedClaims(BaseModel):
    """Temporary schema for extracting testable claims."""
    claims: List[str] = Field(default_factory=list, description="List of testable factual statements")


class FactAgent(BaseAgent):
    """Extracts factual claims, retrieves grounded evidence via Hybrid RAG, and verifies accuracy."""

    def __init__(self, retriever: Optional[HybridRetriever] = None, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or FACT_AGENT_MODEL, **kwargs)
        self.retriever = retriever

    def _get_retriever(self) -> Optional[HybridRetriever]:
        if self.retriever is not None:
            return self.retriever
        try:
            return get_retriever()
        except Exception:
            return None

    async def evaluate(self, input_data: EvaluationInput) -> KnowledgeEvaluation:
        body_text = (input_data.full_markdown_text or "").strip()

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

        # Step 2: Retrieve grounded context from Hybrid RAG for each claim
        retriever = self._get_retriever()
        grounded_contexts: List[str] = []

        if retriever and claims:
            seen_chunk_ids = set()
            for claim in claims[:5]:
                try:
                    search_results = retriever.search(query=claim, top_k=2)
                    for res in search_results:
                        cid = res.chunk.id
                        if cid not in seen_chunk_ids:
                            seen_chunk_ids.add(cid)
                            meta = res.chunk.metadata
                            grounded_contexts.append(
                                f"--- [Source: {meta.source_file} | Chapter: {meta.chapter_title} | Page: {meta.page_number}] ---\n"
                                f"{res.chunk.content.strip()}"
                            )
                except Exception:
                    continue

        context_block = (
            "\n\n".join(grounded_contexts)
            if grounded_contexts
            else "[Note: Local RAG passages unavailable or unindexed. Verify against standard GS-1 Modern History facts.]"
        )

        # Step 3: Verify claims against reference passages
        verification_user_prompt = f"""VERIFY THE CANDIDATE'S FACTUAL CLAIMS AGAINST THE GROUNDED REFERENCE TEXT:

[QUESTION]:
"{input_data.question_text}"

[EXTRACTED CLAIMS TO VERIFY]:
{chr(10).join(f"- {c}" for c in claims) if claims else "- General factual assertions in the answer"}

[CANDIDATE ANSWER]:
\"\"\"{body_text}\"\"\"

[AUTHENTIC REFERENCE PASSAGES (SPECTRUM MODERN HISTORY)]:
\"\"\"
{context_block}
\"\"\"

For each claim:
1. Mark VERIFIED, INCORRECT, or UNVERIFIED.
2. If INCORRECT, provide the exact correction quoting the reference text.
3. Assign a factual_accuracy_score (0-10).
4. Suggest 2-3 core syllabus concepts from the reference text to enrich the answer.
5. Provide ActionableImprovement items with ready-to-insert corrections.
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
        return result
