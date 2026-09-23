"""PDF Loader module for extracting and cleaning text from Spectrum Modern History."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pypdf
from src.config import SPECTRUM_PDF_PATH


# Known major units/chapters in Spectrum Modern History for accurate attribution
SPECTRUM_UNITS = [
    (1, "Front Matter & Contents"),
    (33, "Unit I: Sources and Approaches"),
    (54, "Unit II: Advent of Europeans and British Consolidation"),
    (177, "Unit III: Rising Resentment against Company Rule & 1857 Revolt"),
    (236, "Unit IV: Socio-Religious Reform Movements"),
    (291, "Unit V: The Struggle Begins & Early Congress"),
    (312, "Unit VI: National Movement (1905-1918) - Swadeshi to Home Rule"),
    (346, "Unit VII: Era of Mass Nationalism (1919-1939) - NCM to CDM"),
    (480, "Unit VIII: Towards Freedom and Partition (1939-1947)"),
    (570, "Unit IX: India Under British Rule - Governance & Economy"),
    (680, "Unit X: Nationalist Movement Appendices & Personalities"),
]


class SpectrumPDFLoader:
    """Extracts, cleans, and structures text from gs1_modern_history_spectrum.pdf."""

    def __init__(self, pdf_path: Optional[Path] = None):
        self.pdf_path = Path(pdf_path or SPECTRUM_PDF_PATH)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF resource not found at: {self.pdf_path}")

    def load_pages(
        self,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract text from the PDF pages.
        
        Args:
            page_range: Optional 1-based (start_page, end_page) inclusive tuple.
                        e.g., (1, 50) for testing.
            
        Returns:
            List of dicts with:
                - 'page_number': int (1-based)
                - 'chapter_title': str
                - 'text': str (cleaned text)
                - 'source_file': str
        """
        reader = pypdf.PdfReader(str(self.pdf_path))
        total_pages = len(reader.pages)

        start_p = 1
        end_p = total_pages

        if page_range:
            start_p = max(1, page_range[0])
            end_p = min(total_pages, page_range[1])

        extracted_pages: List[Dict[str, Any]] = []

        for p_num in range(start_p, end_p + 1):
            raw_page = reader.pages[p_num - 1]
            raw_text = raw_page.extract_text() or ""
            clean_text = self._clean_text(raw_text)

            if not clean_text or len(clean_text.strip()) < 40:
                # Skip blank or trivial pages (e.g. blank separator leaves)
                continue

            chapter_title = self._get_chapter_title(p_num, clean_text)

            extracted_pages.append({
                "page_number": p_num,
                "chapter_title": chapter_title,
                "text": clean_text,
                "source_file": self.pdf_path.name,
            })

        return extracted_pages

    def _get_chapter_title(self, page_num: int, page_text: str) -> str:
        """Resolve the chapter or unit title for a given page."""
        # 1. Check if an explicit Unit or Chapter heading appears at the top of the page
        first_lines = page_text.split("\n")[:4]
        for line in first_lines:
            line_str = line.strip()
            # Match CHAPTER X or UNIT X
            if re.match(r"^(UNIT|Unit)\s+[IVXLCDM\d]+", line_str):
                return line_str
            if re.match(r"^(CHAPTER|Chapter)\s+\d+", line_str):
                return line_str

        # 2. Fallback to known Spectrum syllabus units by page number
        current_unit = "General Modern History"
        for unit_page, unit_name in SPECTRUM_UNITS:
            if page_num >= unit_page:
                current_unit = unit_name
            else:
                break
        return current_unit

    def _clean_text(self, text: str) -> str:
        """Remove watermarks, running headers, footers, and OCR/formatting artifacts."""
        lines = text.split("\n")
        cleaned_lines: List[str] = []

        for line in lines:
            trimmed = line.strip()
            # Strip watermarks and promotional channels
            if "t.me/" in trimmed or "telegram" in trimmed.lower():
                continue
            if "ebooks_encyclopedia" in trimmed.lower() or "magazines4all" in trimmed.lower():
                continue

            # Strip running book headers: e.g., "152 A Brief History of Modern India"
            if re.match(r"^\d+\s+A Brief History of Modern India", trimmed):
                continue
            if re.match(r"^A Brief History of Modern India\s+\d+", trimmed):
                continue

            # Skip standalone page numbers
            if re.match(r"^\d+$", trimmed) or re.match(r"^\([ivxlcdm]+\)$", trimmed, re.IGNORECASE):
                continue

            cleaned_lines.append(trimmed)

        full_text = "\n".join(cleaned_lines)
        # Fix hyphens broken across lines (e.g. "govern-\nment" -> "government")
        full_text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", full_text)
        # Collapse excessive blank lines
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)

        return full_text.strip()
