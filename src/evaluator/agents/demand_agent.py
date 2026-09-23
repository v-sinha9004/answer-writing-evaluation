"""Specialist Agent: Demand & Directive Evaluator."""

from src.evaluator.base_agent import BaseAgent
from src.evaluator.schemas import EvaluationInput, DemandEvaluation, ActionableImprovement
from src.evaluator.prompts import DEMAND_SYSTEM_PROMPT


class DemandAgent(BaseAgent):
    """Evaluates question sub-demand fulfillment and directive compliance."""

    async def evaluate(self, input_data: EvaluationInput) -> DemandEvaluation:
        # Check if candidate text is empty or virtually non-existent
        if not input_data.full_markdown_text or len(input_data.full_markdown_text.strip()) < 10:
            return DemandEvaluation(
                status="SUCCESS",
                sub_parts_identified=["Full Question Demand"],
                sub_parts_addressed=[],
                unaddressed_sub_parts=["Entire Question"],
                directive_adherence_score=0.0,
                demand_coverage_pct=0.0,
                critique="No substantive answer text provided to fulfill question demand.",
                improvements=[
                    ActionableImprovement(
                        section="Question Demand",
                        issue_detected="Answer text is blank or missing.",
                        mark_impact="Awarded 0 marks.",
                        prescription="Write a structured response addressing all parts of the question.",
                        plug_and_play_snippet="Deconstruct question into 2-3 core subheadings matching the prompt keywords."
                    )
                ]
            )

        user_prompt = f"""EVALUATE THE FOLLOWING ANSWER FOR QUESTION DEMAND & DIRECTIVES:

[QUESTION STATEMENT]:
"{input_data.question_text}"

[MAX MARKS]: {input_data.question_marks}
[ESTIMATED WORD COUNT]: {input_data.estimated_word_count} words

[CANDIDATE ANSWER]:
\"\"\"{input_data.full_markdown_text}\"\"\"

Analyze explicit and implicit demands, check directive adherence, score rigorously, and prescribe concrete improvements.
"""
        result, usage = await self.run_structured_with_usage(
            system_prompt=DEMAND_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=DemandEvaluation,
        )
        result.token_usage = usage
        return result
