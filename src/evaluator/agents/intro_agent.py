"""Specialist Agent: Introduction Quality Evaluator."""

from typing import Optional
from src.config import INTRO_AGENT_MODEL
from src.evaluator.base_agent import BaseAgent
from src.evaluator.schemas import EvaluationInput, IntroEvaluation, ActionableImprovement
from src.evaluator.prompts import INTRO_SYSTEM_PROMPT


class IntroAgent(BaseAgent):
    """Evaluates introduction conciseness, definition, and context."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or INTRO_AGENT_MODEL, **kwargs)

    async def evaluate(self, input_data: EvaluationInput) -> IntroEvaluation:
        intro_text = (input_data.detected_intro or "").strip()

        if not intro_text:
            user_prompt = f"""THE CANDIDATE DID NOT WRITE AN INTRODUCTION (IT IS EMPTY OR SKIPPED):

[QUESTION STATEMENT]:
"{input_data.question_text}"

[MAX MARKS]: {input_data.question_marks}

1. Set intro_present = False.
2. Set conciseness_score = 0.0, contextual_score = 0.0, intro_score = 0.0.
3. Diagnose the impact of missing introduction in critique and improvements.
4. Craft an authoritative, crisp (30-35 words) model_intro_rewrite that sets up the answer perfectly.
"""
        else:
            user_prompt = f"""EVALUATE THE FOLLOWING CANDIDATE INTRODUCTION:

[QUESTION STATEMENT]:
"{input_data.question_text}"

[MAX MARKS]: {input_data.question_marks}

[CANDIDATE INTRODUCTION]:
\"\"\"{intro_text}\"\"\"

Check conciseness (30-40 words), definition/origin grounding, relevance, and craft an improved model_intro_rewrite.
"""

        result, usage = await self.run_structured_with_usage(
            system_prompt=INTRO_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=IntroEvaluation,
        )
        result.token_usage = usage
        return result
