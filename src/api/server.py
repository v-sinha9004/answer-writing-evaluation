"""FastAPI backend server exposing REST endpoints for UPSC answer evaluation."""

import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.evaluator.orchestrator import EvaluationOrchestrator
from src.evaluator.pdf_processor import PDFProcessor
from src.evaluator.schemas import ComprehensiveEvaluationReport, EvaluationInput
from src.config import DATA_DIR, ROOT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upsc-api")

app = FastAPI(
    title="UPSC Mains Answer Writing Evaluation API",
    description="Multi-agent panel evaluating handwritten or typed UPSC answers.",
    version="1.0.0",
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = EvaluationOrchestrator()
pdf_processor = PDFProcessor()


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "upsc-evaluator", "version": "1.0.0"}


@app.post("/api/evaluate", response_model=ComprehensiveEvaluationReport)
async def evaluate_pdf(
    file: UploadFile = File(...),
    paper: str = Form("GS-1"),
    marks: int = Form(15),
    question: Optional[str] = Form(None),
):
    """Upload a candidate answer PDF, extract/transcribe content, and evaluate with multi-agent panel."""
    filename = file.filename or "upload.pdf"
    logger.info(f"Received PDF upload: {filename}, paper: {paper}, marks: {marks}")

    if not filename.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are supported.")

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes or len(pdf_bytes) < 10:
            raise HTTPException(status_code=400, detail="Uploaded PDF file is empty.")

        # Process PDF to extract text / vision OCR
        input_data = await pdf_processor.process_pdf(
            pdf_bytes=pdf_bytes,
            subject_paper=paper,
            question_marks=marks,
            question_override=question if question and question.strip() else None,
        )

        logger.info(
            f"Processed PDF: word_count={input_data.estimated_word_count}, "
            f"question='{input_data.question_text[:60]}...'"
        )

        # Run multi-agent orchestrator
        report = await orchestrator.evaluate(input_data)
        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.post("/api/evaluate-sample", response_model=ComprehensiveEvaluationReport)
async def evaluate_sample(
    paper: str = Form("GS-1"),
    marks: int = Form(15),
):
    """Run an evaluation using the built-in sample answer for quick testing."""
    sample_path = DATA_DIR / "sample_ocr_press_in_india.json"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample answer file not found.")

    with open(sample_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    payload["subject_paper"] = paper
    payload["question_marks"] = marks

    report = await orchestrator.evaluate(payload)
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
