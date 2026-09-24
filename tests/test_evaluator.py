"""Unit and integration tests for the UPSC Multi-Agent Evaluator Engine."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.evaluator.schemas import (
    EvaluationInput,
    ComprehensiveEvaluationReport,
    ConsolidatedScorecard,
    DemandEvaluation,
    IntroEvaluation,
    StructureEvaluation,
    ConclusionEvaluation,
    KnowledgeEvaluation,
    FactualClaimCheck,
    ActionableImprovement,
    TransformationRoadmap,
    TokenUsage,
)
from src.evaluator.agents.master_arbiter import MasterScoringAgent, ArbiterSynthesis
from src.evaluator.agents.demand_agent import DemandAgent
from src.evaluator.agents.intro_agent import IntroAgent
from src.evaluator.agents.structure_agent import StructureAgent
from src.evaluator.agents.conclusion_agent import ConclusionAgent
from src.evaluator.agents.fact_agent import FactAgent, ExtractedClaims
from src.evaluator.orchestrator import EvaluationOrchestrator


USER_SAMPLE_OCR_JSON = {
    "question_text": "Trace the evolution of the press in India. Also, discuss the instrumental impact it had during various stages of the Indian freedom struggle despite the repressive policies of the British.",
    "question_marks": "15",
    "full_markdown_text": "Press played a major part in taking revolutionary ideas across regions, from August Hickey's paper to nationalist papers, all had a role to play\n\n### Evolution of Press in India\n\n1. The Hindu, Bengalee etc were first English Newspapers.\n\n2. With time 'Kesari' and 'Maratha' of Tilak, Rast Goftar of Dada bhai Naoroji came into being\n\n3. vernacular publications like Amrita Bazar Patrika etc conveyed revolutionary ideas to locals when vernacular act banned local papers.\n\n4. Gandhi ji used 'Young India' to transmit his ideas.\n\n### Instrumental in India's freedom struggle, despite repressive policies\n\n1. used to propagate theories.\nEx- Moderates Economic drain theory got vast publicity\n\n2. source of international news.\nEx- News of Japan defeating Russia caught nation's emotions that an Asian nation could win\n\n3. instigated masses\nEx- Tilak's article in Maratha which faced wrath of people British\n\n4. choice of words to escape sedition\nEx \"Iss Raj Ke Taas Hilane Houge\" was about to get seditious turn, when the revolutionary said he was speaking of Esraj (musical instrument) whose wires had to be sorted\n\n5. Publications like Gulam Giri, Dalit Upeedak caught people's attention.\nNeel Darpan highlighted plight of indigo workers.\n\n### Facing repressive Policies\n\n1. Sedition on Tilak\n\n2. Amrita Bazar Patrika turned to English overnight to escape Vernacular Press Act.\n\n3. Gandhi's Article led to British summoning him for sedition.\n\n4. International support to highlight British atrocities.\n\nThus, Press became the open mouth piece of revolutionaries and ensured ideals of freedom struggle reach all nook and corners of India",
    "detected_intro": "Press played a major part in taking revolutionary ideas across regions, from August Hickey's paper to nationalist papers, all had a role to play",
    "detected_conclusion": "Thus, Press became the open mouth piece of revolutionaries and ensured ideals of freedom struggle reach all nook and corners of India",
    "estimated_word_count": 214,
    "legibility_status": "AVERAGE",
}


def test_evaluation_input_schema_validation():
    """Verify EvaluationInput parses string marks ('15'), handles empty fields, and sanitizes strings."""
    input_data = EvaluationInput.model_validate(USER_SAMPLE_OCR_JSON)
    assert input_data.question_marks == 15
    assert isinstance(input_data.question_marks, int)
    assert "Trace the evolution" in input_data.question_text
    assert input_data.estimated_word_count == 214
    assert input_data.legibility_status == "AVERAGE"

    # Test missing intro and conclusion defaulting gracefully
    minimal_json = {
        "question_text": "Examine the 1857 Revolt.",
        "question_marks": 10,
        "full_markdown_text": "Sample text",
        "detected_intro": None,
        "detected_conclusion": None,
    }
    obj = EvaluationInput.model_validate(minimal_json)
    assert obj.detected_intro == ""
    assert obj.detected_conclusion == ""


def test_empty_main_answer_short_circuit():
    """Verify orchestrator short-circuits on empty answer text without calling LLMs."""
    async def _run():
        orchestrator = EvaluationOrchestrator()
        empty_payload = {
            "question_text": "Explain the Subsidiary Alliance system.",
            "question_marks": "10",
            "full_markdown_text": "   \n\n  ",
            "detected_intro": "",
            "detected_conclusion": "",
            "estimated_word_count": 0,
        }

        report = await orchestrator.evaluate(empty_payload)
        assert report.is_empty_submission is True
        assert report.scorecard.total_score == 0.0
        assert report.scorecard.max_marks == 10
        assert report.scorecard.benchmark_verdict == "Blank / Empty Submission"

    asyncio.run(_run())


def test_scoring_calibration_math_deterministic():
    """Verify calibrated score formula and penalty application."""
    arbiter = MasterScoringAgent()
    input_data = EvaluationInput.model_validate(USER_SAMPLE_OCR_JSON)

    # Simulated specialist scores
    demand_eval = DemandEvaluation(
        directive_adherence_score=6.0,
        demand_coverage_pct=65.0,
        critique="Good coverage of policies, moderate on stages.",
    )
    fact_eval = KnowledgeEvaluation(
        factual_accuracy_score=5.0,
        critique="Two factual inaccuracies regarding Bengal Gazette and Neel Darpan.",
    )
    intro_eval = IntroEvaluation(
        intro_present=True,
        intro_score=6.0,
        critique="Good mention of Hickey, missed 1780 date.",
        model_intro_rewrite="Model intro snippet.",
    )
    structure_eval = StructureEvaluation(
        structural_score=7.0,
        critique="Clear headings, need bold keyword prefixes.",
    )
    conclusion_eval = ConclusionEvaluation(
        conclusion_present=True,
        conclusion_score=5.0,
        critique="Summarized well, lacked Article 19(1)(a) bridge.",
        model_conclusion_rewrite="Model conclusion snippet.",
    )

    scorecard = arbiter.calculate_scorecard(
        input_data=input_data,
        demand_eval=demand_eval,
        intro_eval=intro_eval,
        structure_eval=structure_eval,
        conclusion_eval=conclusion_eval,
        fact_eval=fact_eval,
    )

    # Weights: Demand 30%, Fact 35%, Intro 10%, Struct 10%, Concl 15%
    # Expected: (0.30*6.0 + 0.35*5.0 + 0.10*6.0 + 0.10*7.0 + 0.15*5.0) = 1.8 + 1.75 + 0.6 + 0.7 + 0.75 = 5.60 / 10
    # Scaled to 15 marks: (5.60 / 10) * 15 = 8.40 / 15
    assert scorecard.max_marks == 15
    assert scorecard.total_score == 8.4
    assert scorecard.percentage == 56.0
    assert "Good / Competitive Mains Standard" in scorecard.benchmark_verdict
    assert len(scorecard.dimensions) == 5


def test_dynamic_reweighting_on_agent_failure():
    """Verify that when an agent fails, remaining active agents have weights re-normalized to 100%."""
    arbiter = MasterScoringAgent()
    input_data = EvaluationInput.model_validate(USER_SAMPLE_OCR_JSON)

    demand_eval = DemandEvaluation(directive_adherence_score=6.0)
    fact_eval = KnowledgeEvaluation(factual_accuracy_score=6.0)
    intro_eval = IntroEvaluation.fallback("Timeout")  # FAILED
    structure_eval = StructureEvaluation(structural_score=6.0)
    conclusion_eval = ConclusionEvaluation(conclusion_score=6.0)

    scorecard = arbiter.calculate_scorecard(
        input_data=input_data,
        demand_eval=demand_eval,
        intro_eval=intro_eval,
        structure_eval=structure_eval,
        conclusion_eval=conclusion_eval,
        fact_eval=fact_eval,
    )

    # Since Intro failed, its 10% weight is dropped and remaining 90% is normalized to 1.0
    # Since all active scores are 6.0/10, weighted average remains 6.0/10 -> 9.0/15 marks
    assert scorecard.total_score == 9.0
    # Intro dimension should be recorded
    assert "Introduction" in scorecard.dimensions


def test_intro_and_conclusion_missing_handling():
    """Verify IntroAgent and ConclusionAgent handle missing sections gracefully."""
    async def _run():
        intro_agent = IntroAgent()
        conclusion_agent = ConclusionAgent()

        # Mock run_structured to simulate LLM response for empty intro
        expected_intro_res = IntroEvaluation(
            intro_present=False,
            conciseness_score=0.0,
            contextual_score=0.0,
            intro_score=0.0,
            critique="Candidate jumped directly into body headings without an introduction.",
            improvements=[
                ActionableImprovement(
                    section="Introduction",
                    issue_detected="No introduction written.",
                    mark_impact="Loss of ~1.5 opening context marks.",
                    prescription="Include a 30-word contextual definition before body headings.",
                    plug_and_play_snippet="Model intro snippet.",
                )
            ],
            model_intro_rewrite="Originating in 1780 with Bengal Gazette, Indian press catalyzed anti-colonial thought.",
        )

        with patch.object(intro_agent, "run_structured", new=AsyncMock(return_value=expected_intro_res)):
            input_empty_intro = EvaluationInput(
                question_text="Trace evolution of press",
                question_marks=15,
                full_markdown_text="Body content",
                detected_intro="",
            )
            res = await intro_agent.evaluate(input_empty_intro)
            assert res.intro_present is False
            assert res.intro_score == 0.0
            assert len(res.model_intro_rewrite) > 10

        # Mock run_structured for empty conclusion
        expected_concl_res = ConclusionEvaluation(
            conclusion_present=False,
            forward_looking_score=0.0,
            balance_score=0.0,
            conclusion_score=0.0,
            critique="Answer ended abruptly with no concluding synthesis.",
            improvements=[
                ActionableImprovement(
                    section="Conclusion",
                    issue_detected="No conclusion written.",
                    mark_impact="Loss of ~1.5 marks for Way Forward.",
                    prescription="Conclude by connecting the issue to constitutional values.",
                    plug_and_play_snippet="Model conclusion snippet.",
                )
            ],
            model_conclusion_rewrite="Ultimately, the struggle for a free press shaped Article 19(1)(a).",
        )

        with patch.object(conclusion_agent, "run_structured", new=AsyncMock(return_value=expected_concl_res)):
            input_empty_concl = EvaluationInput(
                question_text="Trace evolution of press",
                question_marks=15,
                full_markdown_text="Body content",
                detected_conclusion="",
            )
            c_res = await conclusion_agent.evaluate(input_empty_concl)
            assert c_res.conclusion_present is False
            assert c_res.conclusion_score == 0.0
            assert "Article 19" in c_res.model_conclusion_rewrite

    asyncio.run(_run())


def test_orchestrator_parallel_mock_execution():
    """Verify end-to-end orchestrator runs all 5 specialists concurrently on the user's sample answer."""
    async def _run():
        # Set up mocked specialists
        mock_demand = AsyncMock(spec=DemandAgent)
        mock_demand.evaluate.return_value = DemandEvaluation(
            directive_adherence_score=6.5,
            demand_coverage_pct=70.0,
            critique="Addressed evolution and policies well; group impact by chronological stages.",
            improvements=[
                ActionableImprovement(
                    section="Demand - Stages of Struggle",
                    issue_detected="Impact points not organized by chronological freedom struggle phases.",
                    mark_impact="Loses ~1.5 marks on directive 'various stages'.",
                    prescription="Group points under Moderate, Swadeshi, and Gandhian phases.",
                    plug_and_play_snippet="• **Moderate Phase**: Propagated Drain of Wealth theory...",
                )
            ],
            token_usage=TokenUsage(prompt_tokens=500, completion_tokens=150, total_tokens=650),
        )

        mock_intro = AsyncMock(spec=IntroAgent)
        mock_intro.evaluate.return_value = IntroEvaluation(
            intro_present=True,
            intro_score=6.0,
            critique="Good mention of Hickey; add exact 1780 Bengal Gazette context.",
            model_intro_rewrite="Originating with James Augustus Hicky’s Bengal Gazette (1780), the Indian press evolved into the vanguard of nationalist consciousness.",
            token_usage=TokenUsage(prompt_tokens=300, completion_tokens=100, total_tokens=400),
        )

        mock_structure = AsyncMock(spec=StructureAgent)
        mock_structure.evaluate.return_value = StructureEvaluation(
            structural_score=7.0,
            critique="Subheadings match prompt keywords; upgrade plain numbered points to bold keyword prefixes.",
            token_usage=TokenUsage(prompt_tokens=400, completion_tokens=120, total_tokens=520),
        )

        mock_concl = AsyncMock(spec=ConclusionAgent)
        mock_concl.evaluate.return_value = ConclusionEvaluation(
            conclusion_present=True,
            conclusion_score=5.5,
            critique="Good summary; bridge historical struggle to modern Article 19(1)(a).",
            model_conclusion_rewrite="Ultimately, the nationalist press served as a crucible for civil liberties, directly shaping the democratic bedrock of Article 19(1)(a).",
            token_usage=TokenUsage(prompt_tokens=320, completion_tokens=110, total_tokens=430),
        )

        mock_fact = AsyncMock(spec=FactAgent)
        mock_fact.evaluate.return_value = KnowledgeEvaluation(
            factual_accuracy_score=5.5,
            claims_checked=[
                FactualClaimCheck(
                    claim="The Hindu was first English Newspaper",
                    verdict="INCORRECT",
                    correction="Bengal Gazette (1780) was the first; The Hindu was founded in 1878.",
                ),
                FactualClaimCheck(
                    claim="Amrita Bazar Patrika turned to English overnight",
                    verdict="VERIFIED",
                    grounded_evidence="Sisir Kumar Ghosh converted it into English to evade Vernacular Press Act 1878.",
                ),
            ],
            syllabus_enrichments=["Charles Metcalfe (1835 Liberator of Press)", "Section 124A IPC Tilak Trial 1897"],
            token_usage=TokenUsage(prompt_tokens=900, completion_tokens=250, total_tokens=1150),
        )

        arbiter = MasterScoringAgent()
        with patch.object(
            arbiter,
            "run_structured_with_usage",
            new=AsyncMock(
                return_value=(
                    ArbiterSynthesis(
                        good_answer_steps=[
                            "Fix English newspaper chronology (Bengal Gazette 1780 vs The Hindu 1878).",
                            "Adopt bold-prefixed bullet points under existing headings.",
                            "Adopt the provided Model Introduction rewrite.",
                        ],
                        top_value_additions=[
                            "Replace opening with the 30-word Model Introduction.",
                            "Organize freedom struggle impact chronologically across 3 phases.",
                            "Adopt the Model Conclusion linking to Article 19(1)(a).",
                        ],
                    ),
                    TokenUsage(prompt_tokens=800, completion_tokens=300, total_tokens=1100),
                )
            ),
        ):
            orchestrator = EvaluationOrchestrator(
                demand_agent=mock_demand,
                intro_agent=mock_intro,
                structure_agent=mock_structure,
                conclusion_agent=mock_concl,
                fact_agent=mock_fact,
                master_arbiter=arbiter,
            )

            report = await orchestrator.evaluate(USER_SAMPLE_OCR_JSON)

            # Assertions
            assert isinstance(report, ComprehensiveEvaluationReport)
            assert report.scorecard.max_marks == 15
            assert report.scorecard.total_score > 0
            assert len(report.transformation_roadmap.good_answer_steps) == 3
            assert len(report.transformation_roadmap.step_1_good_answer) == 3
            assert report.transformation_roadmap.step_2_topper_answer is None
            assert report.transformation_roadmap.current_level_summary is None
            assert len(report.top_value_additions) == 3
            assert len(report.knowledge_evaluation.claims_checked) == 2
            assert report.intro_evaluation.model_intro_rewrite != ""
            assert report.conclusion_evaluation.model_conclusion_rewrite != ""

            # Token Telemetry Assertions
            assert len(report.token_usage_breakdown) == 6
            assert report.token_usage_breakdown["Demand & Directive Agent"].prompt_tokens == 500
            assert report.token_usage_breakdown["Knowledge & Fact Agent (RAG)"].completion_tokens == 250
            assert report.token_usage_breakdown["Master Scoring Arbiter"].total_tokens == 1100
            assert report.total_token_usage.prompt_tokens == 500 + 300 + 400 + 320 + 900 + 800
            assert report.total_token_usage.completion_tokens == 150 + 100 + 120 + 110 + 250 + 300
            assert report.total_token_usage.total_tokens == report.total_token_usage.prompt_tokens + report.total_token_usage.completion_tokens

            # Verify all 5 agents were awaited
            mock_demand.evaluate.assert_awaited_once()
            mock_intro.evaluate.assert_awaited_once()
            mock_structure.evaluate.assert_awaited_once()
            mock_concl.evaluate.assert_awaited_once()
            mock_fact.evaluate.assert_awaited_once()

    asyncio.run(_run())


def test_fact_agent_llm_evaluation():
    """Verify FactAgent operates in pure LLM mode without requiring a vector DB or retriever."""
    async def _run():
        fact_agent = FactAgent()

        extracted_mock = ExtractedClaims(
            claims=["Article 21 guarantees the right to life and personal liberty."]
        )
        verified_mock = KnowledgeEvaluation(
            factual_accuracy_score=9.0,
            claims_checked=[
                FactualClaimCheck(
                    claim="Article 21 guarantees the right to life and personal liberty.",
                    verdict="VERIFIED",
                    grounded_evidence=None,
                    source_citation="Constitution of India, Article 21",
                )
            ],
            syllabus_enrichments=["Maneka Gandhi case (1978)", "Due process of law"],
            critique="Accurate constitutional assertion.",
        )

        mock_usage_1 = TokenUsage(prompt_tokens=80, completion_tokens=40, total_tokens=120)
        mock_usage_2 = TokenUsage(prompt_tokens=150, completion_tokens=70, total_tokens=220)

        with patch.object(
            fact_agent,
            "run_structured_with_usage",
            side_effect=[(extracted_mock, mock_usage_1), (verified_mock, mock_usage_2)],
        ) as mock_call:
            input_data = EvaluationInput(
                question_text="Discuss the expansion of Article 21 of the Indian Constitution.",
                question_marks=10,
                subject_paper="gs2",
                full_markdown_text="Article 21 guarantees the right to life and personal liberty.",
            )
            result = await fact_agent.evaluate(input_data)

            assert result.factual_accuracy_score == 9.0
            assert len(result.claims_checked) == 1
            assert result.claims_checked[0].verdict == "VERIFIED"
            assert result.claims_checked[0].source_citation == "Constitution of India, Article 21"
            assert "Maneka Gandhi" in result.syllabus_enrichments[0]
            assert result.token_usage.total_tokens == 340
            assert mock_call.call_count == 2
            # Verify that the verification prompt contained the pure LLM reference knowledge base text
            verification_call_args = mock_call.call_args_list[1]
            user_prompt_passed = verification_call_args.kwargs.get("user_prompt") or verification_call_args.args[1]
            assert "[REFERENCE KNOWLEDGE BASE]:" in user_prompt_passed
            assert "GS2" in user_prompt_passed

    asyncio.run(_run())


def test_agent_model_config_default_and_override(monkeypatch):
    """Verify that each agent has its own configurable model in src.config and can run on any model."""
    import importlib
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for key in [
        "OPENAI_MODEL", "AGENT_MODEL", "EVALUATION_MODEL",
        "DEMAND_AGENT_MODEL", "INTRO_AGENT_MODEL", "STRUCTURE_AGENT_MODEL",
        "CONCLUSION_AGENT_MODEL", "FACT_AGENT_MODEL", "MASTER_ARBITER_MODEL", "VISION_AGENT_MODEL"
    ]:
        monkeypatch.delenv(key, raising=False)
    import src.config
    importlib.reload(src.config)

    import src.evaluator.base_agent
    importlib.reload(src.evaluator.base_agent)
    import src.evaluator.agents.demand_agent
    importlib.reload(src.evaluator.agents.demand_agent)
    import src.evaluator.agents.intro_agent
    importlib.reload(src.evaluator.agents.intro_agent)
    import src.evaluator.agents.structure_agent
    importlib.reload(src.evaluator.agents.structure_agent)
    import src.evaluator.agents.conclusion_agent
    importlib.reload(src.evaluator.agents.conclusion_agent)
    import src.evaluator.agents.fact_agent
    importlib.reload(src.evaluator.agents.fact_agent)
    import src.evaluator.agents.master_arbiter
    importlib.reload(src.evaluator.agents.master_arbiter)
    import src.evaluator.pdf_processor
    importlib.reload(src.evaluator.pdf_processor)
    import src.evaluator.orchestrator
    importlib.reload(src.evaluator.orchestrator)

    from src.evaluator.agents.demand_agent import DemandAgent
    from src.evaluator.agents.intro_agent import IntroAgent
    from src.evaluator.agents.structure_agent import StructureAgent
    from src.evaluator.agents.conclusion_agent import ConclusionAgent
    from src.evaluator.agents.fact_agent import FactAgent
    from src.evaluator.agents.master_arbiter import MasterScoringAgent
    from src.evaluator.orchestrator import EvaluationOrchestrator

    from src.config import (
        AGENT_MODEL,
        OPENAI_MODEL,
        EVALUATION_MODEL,
        DEMAND_AGENT_MODEL,
        INTRO_AGENT_MODEL,
        STRUCTURE_AGENT_MODEL,
        CONCLUSION_AGENT_MODEL,
        FACT_AGENT_MODEL,
        MASTER_ARBITER_MODEL,
        VISION_AGENT_MODEL,
        get_agent_models,
    )
    from src.evaluator.base_agent import BaseAgent
    from src.evaluator.pdf_processor import PDFProcessor

    assert AGENT_MODEL == "gpt-4o"
    assert OPENAI_MODEL == "gpt-4o"
    assert EVALUATION_MODEL == "gpt-4o"

    # Verify per-agent default models
    assert DEMAND_AGENT_MODEL == "gpt-4o"
    assert INTRO_AGENT_MODEL == "gpt-4o"
    assert STRUCTURE_AGENT_MODEL == "gpt-4o"
    assert CONCLUSION_AGENT_MODEL == "gpt-4o"
    assert FACT_AGENT_MODEL == "gpt-4o"
    assert MASTER_ARBITER_MODEL == "gpt-4o"
    assert VISION_AGENT_MODEL == "gpt-4o"

    models_dict = get_agent_models()
    assert models_dict["demand"] == "gpt-4o"
    assert models_dict["intro"] == "gpt-4o"
    assert models_dict["structure"] == "gpt-4o"
    assert models_dict["conclusion"] == "gpt-4o"
    assert models_dict["fact"] == "gpt-4o"
    assert models_dict["master_arbiter"] == "gpt-4o"
    assert models_dict["vision"] == "gpt-4o"

    # Default BaseAgent uses AGENT_MODEL
    agent = BaseAgent()
    assert agent.model == AGENT_MODEL

    # Each individual agent uses its own model by default
    demand = DemandAgent()
    assert demand.model == DEMAND_AGENT_MODEL
    intro = IntroAgent()
    assert intro.model == INTRO_AGENT_MODEL
    struct = StructureAgent()
    assert struct.model == STRUCTURE_AGENT_MODEL
    conclusion = ConclusionAgent()
    assert conclusion.model == CONCLUSION_AGENT_MODEL
    fact = FactAgent()
    assert fact.model == FACT_AGENT_MODEL
    arbiter = MasterScoringAgent()
    assert arbiter.model == MASTER_ARBITER_MODEL
    processor = PDFProcessor()
    assert processor.model == VISION_AGENT_MODEL

    # Each individual agent can be initialized with any custom model
    assert DemandAgent(model="claude-3-opus").model == "claude-3-opus"
    assert IntroAgent(model="gpt-4o-mini").model == "gpt-4o-mini"
    assert StructureAgent(model="mistral-large").model == "mistral-large"
    assert ConclusionAgent(model="gemini-1.5-pro").model == "gemini-1.5-pro"
    assert FactAgent(model="o3-mini").model == "o3-mini"
    assert MasterScoringAgent(model="o1-preview").model == "o1-preview"
    assert PDFProcessor(model="gpt-4o-vision-preview").model == "gpt-4o-vision-preview"

    # Orchestrator with per-agent custom models mapping
    orchestrator_multi = EvaluationOrchestrator(
        agent_models={
            "demand": "gpt-4o-mini",
            "fact": "o3-mini",
            "master_arbiter": "o1",
        }
    )
    assert orchestrator_multi.demand_agent.model == "gpt-4o-mini"
    assert orchestrator_multi.intro_agent.model == INTRO_AGENT_MODEL
    assert orchestrator_multi.structure_agent.model == STRUCTURE_AGENT_MODEL
    assert orchestrator_multi.conclusion_agent.model == CONCLUSION_AGENT_MODEL
    assert orchestrator_multi.fact_agent.model == "o3-mini"
    assert orchestrator_multi.master_arbiter.model == "o1"

    # Orchestrator with global override propagates custom model to all agents
    orchestrator = EvaluationOrchestrator(model="gpt-4o-mini")
    assert orchestrator.model == "gpt-4o-mini"
    assert orchestrator.demand_agent.model == "gpt-4o-mini"
    assert orchestrator.intro_agent.model == "gpt-4o-mini"
    assert orchestrator.structure_agent.model == "gpt-4o-mini"
    assert orchestrator.conclusion_agent.model == "gpt-4o-mini"
    assert orchestrator.fact_agent.model == "gpt-4o-mini"
    assert orchestrator.master_arbiter.model == "gpt-4o-mini"


@pytest.mark.anyio
async def test_vision_ocr_agent_structured_parsing(tmp_path):
    """Verify VisionOCRAgent and structured UPSCAnswerOCRResponse mapping to EvaluationInput."""
    from src.evaluator.pdf_processor import (
        PDFProcessor,
        VisionOCRAgent,
        UPSCAnswerOCRResponse,
    )
    from src.evaluator.schemas import EvaluationInput

    assert VisionOCRAgent is PDFProcessor
    mock_openai = MagicMock()
    processor = VisionOCRAgent(client=mock_openai)
    assert processor.process_pdf == processor.vision_ocr

    # Verify structured response validation
    ocr_resp = UPSCAnswerOCRResponse(
        question_text="Critically examine the impact of the Vernacular Press Act of 1878.",
        question_marks="15 Marks",
        full_markdown_text="### Introduction\nThe Vernacular Press Act was enacted by Lord Lytton...",
        detected_intro="The Vernacular Press Act was enacted by Lord Lytton...",
        detected_conclusion="Thus, the act became a catalyst for national consciousness.",
        estimated_word_count=185,
        legibility_status="CLEAR",
    )
    assert ocr_resp.question_text.startswith("Critically examine")
    assert ocr_resp.estimated_word_count == 185
    assert ocr_resp.legibility_status == "CLEAR"

    # Create an actual test image file in tmp_path
    test_img = tmp_path / "page_1.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    # Mock Vision LLM call returning structured UPSCAnswerOCRResponse
    with patch.object(processor.client.beta.chat.completions, "parse", new_callable=AsyncMock) as mock_parse:
        mock_choice = MagicMock()
        mock_choice.message.parsed = ocr_resp
        mock_choice.message.refusal = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_parse.return_value = mock_response

        # Call transcribe_with_vision directly to verify prompt and parse invocation
        parsed_direct = await processor.transcribe_with_vision([str(test_img)])
        assert parsed_direct.question_text == "Critically examine the impact of the Vernacular Press Act of 1878."

        # Call vision_ocr with fake pdf bytes
        fake_pdf = b"%PDF-1.4 fake content for testing OCR engine"
        with patch.object(processor, "render_pdf_to_images", return_value=([str(test_img)], str(tmp_path))):
            result = await processor.vision_ocr(
                pdf_bytes=fake_pdf,
                subject_paper="GS-1",
                question_marks=15,
            )

        assert isinstance(result, EvaluationInput)
        assert result.question_text == "Critically examine the impact of the Vernacular Press Act of 1878."
        assert result.question_marks == 15
        assert result.detected_intro.startswith("The Vernacular Press Act")
        assert result.detected_conclusion.startswith("Thus, the act")
        assert result.estimated_word_count == 185
        assert result.legibility_status == "CLEAR"
        assert result.subject_paper == "GS-1"
        assert result.ocr_json is not None
        assert "Vernacular Press Act" in result.ocr_json


@pytest.mark.anyio
async def test_vision_ocr_agent_omitted_intro_conclusion(tmp_path):
    """Verify that when a candidate omits intro or conclusion, they are preserved as empty strings."""
    from src.evaluator.pdf_processor import VisionOCRAgent, UPSCAnswerOCRResponse
    from src.evaluator.schemas import EvaluationInput

    mock_openai = MagicMock()
    processor = VisionOCRAgent(client=mock_openai)

    # OCR detected that candidate skipped intro and conclusion
    ocr_resp = UPSCAnswerOCRResponse(
        question_text="Discuss the administrative reforms under Lord Cornwallis.",
        question_marks="10",
        full_markdown_text="### Permanent Settlement\nIntroduced in Bengal in 1793...",
        detected_intro="",
        detected_conclusion="",
        estimated_word_count=120,
        legibility_status="AVERAGE",
    )

    test_img = tmp_path / "p1.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    with patch.object(processor.client.beta.chat.completions, "parse", new_callable=AsyncMock) as mock_parse:
        mock_choice = MagicMock()
        mock_choice.message.parsed = ocr_resp
        mock_choice.message.refusal = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_parse.return_value = mock_response

        fake_pdf = b"%PDF-1.4 fake content"
        with patch.object(processor, "render_pdf_to_images", return_value=([str(test_img)], str(tmp_path))):
            result = await processor.vision_ocr(
                pdf_bytes=fake_pdf,
                subject_paper="GS-1",
                question_marks=10,
            )

        assert result.detected_intro == ""
        assert result.detected_conclusion == ""
        assert result.estimated_word_count == 120
        assert result.question_marks == 10


def test_pypdfium2_not_imported():
    """Verify pypdfium2 is completely removed and not loaded in memory."""
    import src.evaluator.pdf_processor as proc_module
    assert not hasattr(proc_module, "pdfium")
    assert not hasattr(proc_module, "pypdfium2")



