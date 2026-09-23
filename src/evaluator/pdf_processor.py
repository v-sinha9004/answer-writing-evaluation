"""PDF extraction and OCR processing module for UPSC Mains answer copies."""

import base64
import io
import logging
import re
from typing import Optional, Tuple, List
import pypdf
from PIL import Image
from openai import AsyncOpenAI
from src.config import OPENAI_API_KEY, VISION_AGENT_MODEL
from src.evaluator.observability import get_async_openai_client, observe_stage
from src.evaluator.schemas import EvaluationInput

logger = logging.getLogger("upsc-ocr")


class PDFProcessor:
    """Extracts candidate answer text from digital or scanned handwritten PDFs."""

    def __init__(self, client: Optional[AsyncOpenAI] = None, model: Optional[str] = None):
        self.client = client or get_async_openai_client()
        self.model = model or VISION_AGENT_MODEL

    def render_pdf_pages_to_images(self, pdf_bytes: bytes, max_pages: int = 6) -> List[bytes]:
        """Render PDF pages directly to high-resolution JPEG images using pypdfium2."""
        images = []
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(pdf_bytes)
            n_pages = min(len(doc), max_pages)
            for i in range(n_pages):
                page = doc[i]
                # Render at 2x resolution (~150-200 DPI, perfect for OCR on handwriting)
                pil_img = page.render(scale=2.0).to_pil()
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                # Downscale if excessively large to keep payload size optimal
                if max(pil_img.size) > 2048:
                    pil_img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                images.append(buf.getvalue())
        except Exception as e:
            logger.warning(f"pypdfium2 rendering fallback: {e}")
        return images

    def extract_text_and_images(self, pdf_bytes: bytes) -> Tuple[str, List[bytes]]:
        """Extract embedded text and any embedded page images from PDF bytes."""
        # 1. Extract digital text via pypdf
        extracted_pages = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    extracted_pages.append(text.strip())
        except Exception as read_err:
            logger.warning(f"pypdf text extraction warning: {read_err}")

        full_text = "\n\n".join(extracted_pages).strip()

        # 2. Extract images: Prefer rendering visual pages directly (essential for scanned copies)
        images = self.render_pdf_pages_to_images(pdf_bytes)

        # 3. Fallback to extracting embedded /XObject images via pypdf if pypdfium2 returned nothing
        if not images:
            try:
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    if hasattr(page, "images") and page.images:
                        for img in page.images:
                            if hasattr(img, "data") and img.data:
                                try:
                                    im = Image.open(io.BytesIO(img.data))
                                    if im.mode != "RGB":
                                        im = im.convert("RGB")
                                    buf = io.BytesIO()
                                    im.save(buf, format="JPEG", quality=85)
                                    images.append(buf.getvalue())
                                except Exception:
                                    images.append(img.data)
            except Exception as img_err:
                logger.warning(f"pypdf image extraction warning: {img_err}")

        return full_text, images

    @observe_stage(name="vision_transcription", as_type="generation")
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

        logger.info(f"Calling vision model '{self.model}' with {len(selected_images)} page images...")
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content_items}],
            temperature=0.0,
            max_completion_tokens=2500,
        )

        transcription = response.choices[0].message.content or ""
        logger.info(f"Vision transcription succeeded with {len(transcription.split())} words.")
        return transcription

    @observe_stage(name="pdf_processing", as_type="span")
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
                    cleaned = vision_text.strip()
                    if cleaned.startswith("```markdown"):
                        cleaned = cleaned[len("```markdown"):].strip()
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:].strip()
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3].strip()
                    text = cleaned
            except Exception as e:
                logger.error(f"Vision transcription error: {e}", exc_info=True)

        # If still empty, return a blank evaluation input
        if not text:
            logger.warning("No readable text found after digital extraction and OCR.")
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

        # Check if first line matches a question pattern
        first_line = lines[0]
        cleaned_first_line = re.sub(r"^[#\*\_\s]+", "", first_line).strip()
        question_pattern = re.compile(
            r"^(?:Q(?:uestion)?[\s\.\d\:\)]|(?:\d+[\.\)]\s*)).+",
            re.IGNORECASE,
        )

        is_question = bool(question_pattern.match(cleaned_first_line) or "?" in first_line)

        if is_question:
            question = re.sub(r"\*\*+", "", first_line).strip("*#_ ")
            idx = 1
            # Continue reading question until '?' or explicit answer marker
            while idx < len(lines):
                line = lines[idx]
                cleaned_line = re.sub(r"^[#\*\_\s]+", "", line).lower()
                # Stop if answer marker is encountered
                if cleaned_line.startswith(("ans", "answer", "intro", "heading", "#")):
                    break
                if "?" in lines[idx - 1]:
                    break
                if len(line) < 160:
                    question += " " + re.sub(r"\*\*+", "", line).strip("*#_ ")
                    idx += 1
                else:
                    break

            body = "\n\n".join(lines[idx:])
            # If body became empty, fallback so answer text is not lost
            if not body.strip():
                return question.strip(), text
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
