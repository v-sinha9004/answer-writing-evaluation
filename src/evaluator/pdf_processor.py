"""PDF extraction and OCR processing module for UPSC Mains answer copies."""

import base64
import io
import re
from typing import Optional, Tuple, List
import pypdf
from openai import AsyncOpenAI
from src.config import OPENAI_API_KEY, AGENT_MODEL
from src.evaluator.schemas import EvaluationInput


class PDFProcessor:
    """Extracts candidate answer text from digital or scanned handwritten PDFs."""

    def __init__(self, client: Optional[AsyncOpenAI] = None, model: Optional[str] = None):
        self.client = client or AsyncOpenAI(api_key=OPENAI_API_KEY or "sk-dummy-key-for-testing")
        self.model = model or AGENT_MODEL

    def extract_text_and_images(self, pdf_bytes: bytes) -> Tuple[str, List[bytes]]:
        """Extract embedded text and any embedded page images from PDF bytes."""
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted_pages = []
        images = []

        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                extracted_pages.append(text.strip())

            # Extract images if present
            try:
                if hasattr(page, "images") and page.images:
                    for img in page.images:
                        if hasattr(img, "data") and img.data:
                            images.append(img.data)
            except Exception as img_err:
                print(f"[PDFProcessor] Warning: Could not extract image from page: {img_err}")

        full_text = "\n\n".join(extracted_pages).strip()
        return full_text, images

    async def transcribe_images_with_vision(self, images: List[bytes]) -> str:
        """Transcribe handwritten pages into structured markdown using vision model."""
        if not images:
            return ""

        # Limit to first 6 images/pages to stay within token limits
        selected_images = images[:6]
        content_items = [
            {
                "type": "text",
                "text": (
                    "You are an expert UPSC Mains answer evaluator and OCR transcription specialist. "
                    "Transcribe the handwritten answer from these uploaded page images accurately into clean Markdown format. "
                    "Include the question text if visible at the top, preserve headings, numbered points, bullet points, "
                    "and any diagrams described in text. Do not hallucinate content not present in the pages."
                ),
            }
        ]

        for img_bytes in selected_images:
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            content_items.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content_items}],
            temperature=0.0,
            max_tokens=2500,
        )

        return response.choices[0].message.content or ""

    async def process_pdf(
        self,
        pdf_bytes: bytes,
        subject_paper: str = "GS-1",
        question_marks: int = 15,
        question_override: Optional[str] = None,
    ) -> EvaluationInput:
        """Process an uploaded PDF and return a normalized EvaluationInput."""
        text, images = self.extract_text_and_images(pdf_bytes)

        # If extracted text is very short (< 40 words) and images are present, run vision transcription
        word_count = len(text.split())
        if word_count < 40 and images:
            try:
                vision_text = await self.transcribe_images_with_vision(images)
                if vision_text.strip():
                    text = vision_text.strip()
            except Exception as e:
                # If vision transcription fails or no valid API key, proceed with whatever text was found
                print(f"[PDFProcessor] Vision transcription fallback: {e}")

        # If still empty, return a blank evaluation input
        if not text:
            return EvaluationInput(
                question_text=question_override or "UPSC Question (Not detected)",
                question_marks=question_marks,
                full_markdown_text="",
                detected_intro="",
                detected_conclusion="",
                estimated_word_count=0,
                legibility_status="POOR",
                subject_paper=subject_paper,
            )

        # Parse question if not explicitly provided
        question_text = (question_override or "").strip()
        answer_body = text

        if not question_text:
            question_text, answer_body = self._detect_question_and_body(text)

        # Parse intro and conclusion
        intro, conclusion = self._extract_intro_and_conclusion(answer_body)
        total_words = len(answer_body.split())

        return EvaluationInput(
            question_text=question_text,
            question_marks=question_marks,
            full_markdown_text=answer_body,
            detected_intro=intro,
            detected_conclusion=conclusion,
            estimated_word_count=total_words,
            legibility_status="CLEAR" if total_words > 80 else "AVERAGE",
            subject_paper=subject_paper,
        )

    def _detect_question_and_body(self, text: str) -> Tuple[str, str]:
        """Separate question prompt from answer body if question is at top."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return "UPSC Mains Practice Question", text

        # Check if first line or block matches a question pattern
        first_line = lines[0]
        question_pattern = re.compile(
            r"^(?:Q(?:uestion)?[\s\.\d\:\)]|(?:\d+[\.\)]\s*)).+",
            re.IGNORECASE,
        )

        if question_pattern.match(first_line) or "?" in first_line or len(first_line) < 250:
            question = first_line
            # Check if second line is continuation of question
            idx = 1
            while idx < len(lines) and ("?" in lines[idx - 1] is False) and len(lines[idx]) < 120 and not lines[idx].startswith("#"):
                question += " " + lines[idx]
                idx += 1
                if "?" in lines[idx - 1]:
                    break
            body = "\n\n".join(lines[idx:])
            return question.strip(), body.strip()

        return "Examine the following question and evaluate the candidate's answer.", text

    def _extract_intro_and_conclusion(self, answer_text: str) -> Tuple[str, str]:
        """Heuristically extract introduction and conclusion paragraphs."""
        paragraphs = [p.strip() for p in answer_text.split("\n\n") if p.strip()]
        if not paragraphs:
            return "", ""

        # Filter out standalone headings for intro candidates
        content_paras = [p for p in paragraphs if not p.startswith("#") and len(p.split()) > 8]

        intro = content_paras[0] if content_paras else paragraphs[0]
        conclusion = content_paras[-1] if len(content_paras) > 1 else ""

        # Check if conclusion has explicit conclusion markers
        for p in reversed(paragraphs):
            lower = p.lower()
            if any(k in lower for k in ["conclusion", "way forward", "thus,", "hence,", "in summary", "overall"]):
                conclusion = p
                break

        return intro, conclusion
