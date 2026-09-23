"""Specialist Agent: Conclusion Quality & Way Forward Evaluator."""

from src.evaluator.base_agent import BaseAgent
from src.evaluator.schemas import EvaluationInput, ConclusionEvaluation, ActionableImprovement
from src.evaluator.prompts import CONCLUSION_SYSTEM_PROMPT


class ConclusionAgent(BaseAgent):
    """Evaluates conclusion balance, forward-looking perspective, and constitutional grounding."""

    async def evaluate(self, input_data: EvaluationInput) -> ConclusionEvaluation:
        conclusion_text = (input_data.detected_conclusion or "").strip()

        if not conclusion_text:
            user_prompt = f"""THE CANDIDATE DID NOT WRITE A CONCLUSION (IT IS EMPTY OR SKIPPED):

[QUESTION STATEMENT]:
"{input_data.question_text}"

[MAX MARKS]: {input_data.question_marks}

1. Set conclusion_present = False.
2. Set forward_looking_score = 0.0, balance_score = 0.0, conclusion_score = 0.0.
3. Diagnose the impact of missing conclusion in critique and improvements.
4. Craft an authoritative, forward-looking model_conclusion_rewrite (25-35 words) bridging the topic to modern constitutional principles or national vision.
"""
        else:
            user_prompt = f"""EVALUATE THE FOLLOWING CANDIDATE CONCLUSION:

[QUESTION STATEMENT]:
"{input_data.question_text}"

[MAX MARKS]: {input_data.question_marks}

[CANDIDATE CONCLUSION]:
\"\"\"{conclusion_text}\"\"\"

Check forward-looking outlook, synthesis, constitutional/policy grounding, and craft an improved model_conclusion_rewrite.
"""

        return await self.run_structured(
            system_prompt=CONCLUSION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=ConclusionEvaluation,
        )
