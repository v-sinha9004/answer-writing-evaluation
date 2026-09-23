"""Vision OCR Engine module for UPSC Mains answer copies, mirroring the dedicated OCR service."""

import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Literal, Dict, Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import VISION_AGENT_MODEL
from src.evaluator.observability import get_async_openai_client, observe_stage
from src.evaluator.schemas import EvaluationInput

logger = logging.getLogger("upsc-ocr")

# Resolve system binary for PDF rendering (Poppler)
PDFTOPPM_PATH = shutil.which("pdftoppm") or "/opt/homebrew/bin/pdftoppm"


class UPSCAnswerOCRResponse(BaseModel):
    """Structured response contract for UPSC answer copy transcription."""
    question_text: str = Field(
        default="",
        description="The printed or handwritten question statement/prompt found at the top of the answer copy. Empty string if not present on the scanned page(s).",
    )
    question_marks: Optional[str] = Field(
        default=None,
        description="The allotted marks indicated for the question (e.g. '10 Marks', '15', '12.5', '250 words / 15m'), or null if not indicated.",
    )
    full_markdown_text: str = Field(
        default="",
        description="The entire transcribed candidate answer in clean Markdown, preserving headers (###), bullet points (- ), bold underlines (**word**), tables, and flowchart structure.",
    )
    detected_intro: str = Field(
        default="",
        description="The opening 1–2 paragraphs where the candidate sets context or defines the topic. Empty string if not present on the scanned page(s).",
    )
    detected_conclusion: str = Field(
        default="",
        description="The final closing paragraph written by the candidate. Empty string if not present on the scanned page(s).",
    )
    estimated_word_count: int = Field(
        default=0,
        description="Total word count of the candidate's written answer only (excluding the question statement and marks).",
    )
    legibility_status: Literal["CLEAR", "AVERAGE", "POOR"] = Field(
        default="AVERAGE",
        description="Overall readability of the candidate's handwriting across the scanned page(s).",
    )


UPSC_OCR_SYSTEM_PROMPT = """You are an expert handwritten document transcriber specializing in UPSC Civil Services Examination answer copies.
Your job is to transcribe the candidate's handwritten pages into clean, structured Markdown with 100% fidelity.

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION:

1. QUESTION AND MARKS EXTRACTION:
   - Identify and extract the question statement/prompt (printed or handwritten) into `question_text`, but ignore/dont include the hindi translation of question_text.
   - Identify any allotted marks specified alongside the question (e.g. "10", "15 Marks", "12.5", "10M") into `question_marks`. If not found, set to null.
   - Do NOT include the question text or marks in `full_markdown_text` or `estimated_word_count`; `full_markdown_text` must focus strictly on the candidate's handwritten answer.

2. VERBATIM TRANSCRIPTION ONLY (NO AUTO-CORRECTION):
   - Transcribe EXACTLY what the candidate wrote.
   - Do NOT correct grammatical mistakes, spelling errors, or incorrect historical dates/facts. Our evaluation agents must see the student's actual mistakes.

3. PRESERVE STRUCTURAL DISCIPLINE:
   - Convert handwritten section headings, underlined headers, or boxed headers into Markdown headings: `### Heading Name`.
   - Convert bullet points, dashes, arrows, and numbers into standard Markdown lists (`- ` or `1. `).
   - Convert underlined keywords or boxed phrases into bold (`**keyword**`).
   - Preserve paragraph breaks with double newlines (`\\n\\n`).
   - If multiple pages are provided, transcribe them sequentially in order as a single continuous answer.

4. TABLES & FLOWCHARTS (CLEAN MARKDOWN):
   - Transcribe handwritten comparison tables or data tables using standard GitHub Flavored Markdown tables (`| Column 1 | Column 2 |`).
   - Transcribe flowcharts, cycle diagrams, or process structures using clean text arrows (e.g., `Step A -> Step B -> Step C`), indented hierarchical lists, or clean Markdown tables.

5. IGNORE CROSSED-OUT / STRIKETHROUGH TEXT:
   - Completely OMIT any words, sentences, or paragraphs that the candidate has scratched out or crossed out with a pen. Do not transcribe deleted mistakes.

6. DIAGRAMS & DRAWINGS (SKIP THEM):
   - Ignore pencil drawings, sketches, or maps. Do NOT attempt to transcribe diagram labels or arrows as garbled text. Simply transcribe the surrounding written text.

7. ILLEGIBLE WORDS:
   - If a word is impossible to decipher, write `[illegible]`. Never guess or hallucinate.

8. SECTION IDENTIFICATION:
   - `detected_intro`: Extract only the opening 1–2 paragraph(s) where the candidate sets context or defines the topic before the main body headings. If the provided page(s) do not contain an introduction, return an empty string `""`.
   - `detected_conclusion`: Extract only the final closing paragraph or 'Way Forward'. If the provided page(s) do not contain a conclusion, return an empty string `""`.
   - `estimated_word_count`: Total word count of the candidate's written answer only.
   - `legibility_status`: Evaluate the overall handwriting legibility as "CLEAR", "AVERAGE", or "POOR".
"""


def _load_image_base64(image_path: str) -> Tuple[str, str]:
    """Read an image file and return its mime type and Base64 encoded string."""
    suffix = Path(image_path).suffix.lower()
    mime_type = "image/png"
    if suffix in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif suffix == ".webp":
        mime_type = "image/webp"

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return mime_type, b64


class PDFProcessor:
    """Vision OCR Agent that processes UPSC Mains answer copies matching the OCR repo architecture."""

    def __init__(self, client: Optional[AsyncOpenAI] = None, model: Optional[str] = None):
        self.client = client or get_async_openai_client()
        self.model = model or VISION_AGENT_MODEL

    def render_pdf_to_images(self, pdf_bytes: bytes) -> Tuple[List[str], str]:
        """
        Render all PDF pages to 150 DPI PNG images using pdftoppm.
        Returns a tuple of (list of image file paths, temp_cleanup_dir).
        """
        temp_dir = tempfile.mkdtemp(prefix="upsc_pdf_render_")
        pdf_tmp_path = os.path.join(temp_dir, "input.pdf")

        with open(pdf_tmp_path, "wb") as f:
            f.write(pdf_bytes)

        ppm_cmd = [
            PDFTOPPM_PATH,
            "-png",
            "-r",
            "150",
            pdf_tmp_path,
            os.path.join(temp_dir, "page"),
        ]
        proc = subprocess.run(ppm_cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"pdftoppm failed: {proc.stderr or 'Failed to render PDF pages'}")

        rendered = sorted(
            Path(temp_dir).glob("page-*.png"),
            key=lambda p: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", p.name)]
        )
        if not rendered:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError("No rendered page images produced from PDF.")

        image_paths = [str(p) for p in rendered]
        return image_paths, temp_dir

    @observe_stage(name="vision_ocr_agent", as_type="generation")
    async def transcribe_with_vision(
        self,
        image_paths: List[str],
        model: Optional[str] = None,
    ) -> UPSCAnswerOCRResponse:
        """Transcribe handwritten pages into structured UPSCAnswerOCRResponse using Vision LLM."""
        if not image_paths:
            return UPSCAnswerOCRResponse()

        chosen_model = model or self.model
        user_content: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"Perform high-fidelity UPSC answer sheet OCR transcription on the attached {len(image_paths)} "
                    f"page image(s). Follow all critical transcription rules verbatim."
                ),
            }
        ]

        for idx, path in enumerate(image_paths, 1):
            mime_type, b64_str = _load_image_base64(path)
            if len(image_paths) > 1:
                user_content.append({
                    "type": "text",
                    "text": f"--- Candidate Answer Sheet Page {idx} of {len(image_paths)} ---",
                })
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64_str}",
                    "detail": "high",
                },
            })

        logger.info(f"Calling Vision OCR Agent '{chosen_model}' with {len(image_paths)} page images...")
        response = await self.client.beta.chat.completions.parse(
            model=chosen_model,
            messages=[
                {"role": "system", "content": UPSC_OCR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=UPSCAnswerOCRResponse,
            temperature=0.0,
        )

        if not response.choices or len(response.choices) == 0:
            raise RuntimeError("Vision OCR Agent returned an empty response with no choices.")

        choice = response.choices[0]
        refusal = getattr(choice.message, "refusal", None)
        if isinstance(refusal, str) and refusal.strip():
            raise RuntimeError(f"Vision OCR Agent refused transcription request: {refusal}")

        parsed = choice.message.parsed
        if not parsed:
            raise RuntimeError("Failed to parse structured UPSC answer from Vision OCR Agent response.")

        logger.info(
            f"Vision OCR Agent succeeded: word_count={parsed.estimated_word_count}, "
            f"legibility={parsed.legibility_status}, question='{parsed.question_text[:50]}...'"
        )
        return parsed

    @observe_stage(name="vision_ocr", as_type="span")
    async def vision_ocr(
        self,
        pdf_bytes: bytes,
        subject_paper: str = "GS-1",
        question_marks: int = 15,
        question_override: Optional[str] = None,
        model: Optional[str] = None,
    ) -> EvaluationInput:
        """
        Main entrypoint mirroring OCR repo endpoint:
        1. Renders PDF pages to 150 DPI PNG images via pdftoppm.
        2. Dispatches multimodal high-resolution pages to Vision LLM.
        3. Returns normalized EvaluationInput populated directly from UPSCAnswerOCRResponse.
        """
        chosen_model = model or self.model
        image_paths, temp_dir = self.render_pdf_to_images(pdf_bytes)

        try:
            ocr_response = await self.transcribe_with_vision(image_paths, model=chosen_model)
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

        # Question text
        final_question = (question_override or "").strip() or ocr_response.question_text.strip()
        if not final_question:
            final_question = "UPSC Question (Not detected)"

        # Marks
        final_marks = question_marks
        if ocr_response.question_marks:
            digits = re.findall(r"\d+", ocr_response.question_marks)
            if digits:
                try:
                    final_marks = int(digits[0])
                except ValueError:
                    final_marks = question_marks

        return EvaluationInput(
            question_text=final_question,
            question_marks=final_marks,
            full_markdown_text=ocr_response.full_markdown_text.strip(),
            detected_intro=ocr_response.detected_intro.strip(),
            detected_conclusion=ocr_response.detected_conclusion.strip(),
            estimated_word_count=ocr_response.estimated_word_count or len(ocr_response.full_markdown_text.split()),
            legibility_status=ocr_response.legibility_status or "AVERAGE",
            subject_paper=subject_paper,
        )

    # Backward compatibility alias
    process_pdf = vision_ocr


# Class alias for first-class Vision OCR Agent identity
VisionOCRAgent = PDFProcessor


