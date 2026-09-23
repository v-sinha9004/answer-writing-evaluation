"""CLI runner for evaluating UPSC answer copies from OCR JSON files."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from src.evaluator.orchestrator import EvaluationOrchestrator
from src.evaluator.schemas import ComprehensiveEvaluationReport


def print_report(report: ComprehensiveEvaluationReport):
    """Render the evaluation report in clean, readable terminal cards."""
    sc = report.scorecard
    border = "=" * 80

    print("\n" + border)
    print(f" 🏛️  UPSC MAINS ANSWER EVALUATION SCORECARD")
    print(border)
    print(f" TOTAL SCORE     : {sc.total_score} / {sc.max_marks} Marks ({sc.percentage}%)")
    print(f" BENCHMARK TIER  : {sc.benchmark_verdict}")
    print(f" EVALUATION TIME : {report.total_latency_seconds}s")
    print("-" * 80)
    print(" 📊 PARAMETER-WISE BREAKDOWN:")
    for dim_name, ds in sc.dimensions.items():
        print(f"   • {dim_name:<26} : {ds.raw_score_out_of_10:>4.1f}/10  (Weight: {ds.weight_pct:>4.1f}%) -> {ds.effective_marks:>4.2f} marks")

    if sc.penalties_applied:
        print("\n ⚠️ PENALTIES APPLIED:")
        for p in sc.penalties_applied:
            print(f"   - {p}")

    print("\n" + "-" * 80)
    print(" 🎯 EXECUTIVE EXAMINER VERDICT:")
    print(f" {report.executive_summary}")

    print("\n" + "-" * 80)
    print(" ✍️ MODEL INTRO & CONCLUSION REWRITES:")
    print(f" [Model Intro Rewrite]:\n \"{report.intro_evaluation.model_intro_rewrite}\"\n")
    print(f" [Model Conclusion Rewrite]:\n \"{report.conclusion_evaluation.model_conclusion_rewrite}\"")

    if report.knowledge_evaluation.claims_checked:
        print("\n" + "-" * 80)
        print(" 🔍 FACTUAL ACCURACY AUDIT (RAG Grounded):")
        for claim in report.knowledge_evaluation.claims_checked:
            icon = "✅" if claim.verdict == "VERIFIED" else "❌" if claim.verdict == "INCORRECT" else "⚠️"
            print(f"   {icon} [{claim.verdict}] \"{claim.claim}\"")
            if claim.correction:
                print(f"      Correction: {claim.correction}")
            if claim.grounded_evidence:
                print(f"      Evidence  : {claim.grounded_evidence}")

    print("\n" + "-" * 80)
    print(" 🚀 3-STEP ANSWER TRANSFORMATION ROADMAP:")
    print(f" Current State : {report.transformation_roadmap.current_level_summary}")
    print("\n [Step 1: Fixes to reach 55% marks (Solid Answer)]:")
    for item in report.transformation_roadmap.step_1_good_answer:
        print(f"   • {item}")
    print("\n [Step 2: Additions to reach 70%+ marks (Topper Level)]:")
    for item in report.transformation_roadmap.step_2_topper_answer:
        print(f"   • {item}")

    print("\n" + "-" * 80)
    print(" 💡 TOP 3 VALUE ADDITIONS (+1.5 MARK BOOSTERS):")
    for idx, va in enumerate(report.top_value_additions, start=1):
        print(f"   {idx}. {va}")
    print(border + "\n")


async def async_main():
    parser = argparse.ArgumentParser(description="Evaluate a UPSC answer copy from an OCR JSON payload.")
    parser.add_argument("json_file", nargs="?", default=None, help="Path to OCR JSON file.")
    args = parser.parse_args()

    if not args.json_file:
        print("Usage: python -m src.evaluator.cli <path_to_ocr.json>")
        sys.exit(1)

    file_path = Path(args.json_file)
    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    orchestrator = EvaluationOrchestrator()
    print("Running multi-agent evaluation in parallel (Native Async DAG)...")
    report = await orchestrator.evaluate(payload)
    print_report(report)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
