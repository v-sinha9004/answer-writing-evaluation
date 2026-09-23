"""Specialist Agent: Body Structure, Heading Taxonomy & Flow Evaluator."""

from typing import Optional
from src.config import STRUCTURE_AGENT_MODEL
from src.evaluator.base_agent import BaseAgent
from src.evaluator.observability import observe_stage
from src.evaluator.schemas import EvaluationInput, StructureEvaluation, ActionableImprovement
from src.evaluator.prompts import STRUCTURE_SYSTEM_PROMPT


class StructureAgent(BaseAgent):
    """Evaluates heading taxonomy, bullet formatting discipline, and argument transitions."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        super().__init__(model=model or STRUCTURE_AGENT_MODEL, **kwargs)

    @observe_stage(name="structure_agent", as_type="agent")
    async def evaluate(self, input_data: EvaluationInput) -> StructureEvaluation:
        body_text = (input_data.full_markdown_text or "").strip()

        if not body_text or len(body_text) < 10:
            return StructureEvaluation(
                status="SUCCESS",
                heading_taxonomy_score=0.0,
                bullet_discipline_score=0.0,
                structural_score=0.0,
                critique="No substantive text provided to assess presentation or structure.",
                improvements=[
                    ActionableImprovement(
                        section="Structure & Presentation",
                        issue_detected="Empty or missing answer body.",
                        mark_impact="Severe loss of presentation and structure marks.",
                        prescription="Structure answers with clear subheadings matching question keywords.",
                        plug_and_play_snippet="Use ### Headings and bold-prefixed bullets."
                    )
                ]
            )

        user_prompt = f"""EVALUATE THE STRUCTURE AND PRESENTATION OF THIS ANSWER:

[QUESTION STATEMENT]:
"{input_data.question_text}"

[CANDIDATE TRANSCRIBED ANSWER (MARKDOWN)]:
\"\"\"{body_text}\"\"\"

Inspect use of subheadings, bullet discipline, bold keyword prefixes, and readability flow.
Prescribe clear formatting upgrades with plug-and-play restructuring examples.
"""

        result, usage = await self.run_structured_with_usage(
            system_prompt=STRUCTURE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=StructureEvaluation,
        )
        result.token_usage = usage
        result.status = "SUCCESS"
        return result
