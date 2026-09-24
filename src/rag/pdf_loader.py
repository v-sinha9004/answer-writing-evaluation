"""Universal and modular PDF Loader for extracting and cleaning text from any UPSC textbook."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pypdf


class PDFLoader:
    """Extracts, cleans, and structures text from any UPSC textbook PDF."""

    def __init__(
        self,
        pdf_path: Path,
        subject_name: str = "General",
    ):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF resource not found at: {self.pdf_path}")
        self.subject_name = subject_name

    def load_pages(
        self,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract text from PDF pages.
        
        Args:
            page_range: Optional 1-based (start_page, end_page) inclusive tuple.
            
        Returns:
            List of dicts with:
                - 'page_number': int (1-based)
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
                # Skip blank or trivial pages
                continue

            extracted_pages.append({
                "page_number": p_num,
                "text": clean_text,
                "source_file": self.pdf_path.name,
            })

        return extracted_pages

    def _clean_text(self, text: str) -> str:
        """Remove watermarks, running headers, footers, and formatting artifacts."""
        lines = text.split("\n")
        cleaned_lines: List[str] = []

        for line in lines:
            trimmed = line.strip()
            # Strip watermarks and promotional channels
            if "t.me/" in trimmed or "telegram" in trimmed.lower():
                continue
            if "ebooks_encyclopedia" in trimmed.lower() or "magazines4all" in trimmed.lower():
                continue

            # Strip common running book headers (e.g., "152 A Brief History of Modern India")
            if re.match(r"^\d+\s+[A-Z][A-Za-z\s]{5,40}$", trimmed):
                continue
            if re.match(r"^[A-Z][A-Za-z\s]{5,40}\s+\d+$", trimmed):
                continue

            # Skip standalone page numbers
            if re.match(r"^\d+$", trimmed) or re.match(r"^\([ivxlcdm]+\)$", trimmed, re.IGNORECASE):
                continue

            cleaned_lines.append(trimmed)

        full_text = "\n".join(cleaned_lines)
        # Fix hyphens broken across lines
        full_text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", full_text)
        # Collapse excessive blank lines
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)

        return full_text.strip()


# Aliases for convenience
UniversalPDFLoader = PDFLoader
SpectrumPDFLoader = PDFLoader


