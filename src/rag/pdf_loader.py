"""Universal and modular PDF Loader for extracting and cleaning text from any UPSC textbook."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pypdf


class PDFLoader:
    """Extracts, cleans, and structures text from any UPSC textbook PDF.
    
    Dynamically resolves chapter/unit titles using:
    1. In-page headings (e.g. 'CHAPTER X', 'UNIT Y', 'PART Z')
    2. PDF internal outline / bookmarks (TOC)
    3. Fallback to subject name
    """

    def __init__(
        self,
        pdf_path: Path,
        subject_name: str = "General",
    ):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF resource not found at: {self.pdf_path}")
        self.subject_name = subject_name

    def _extract_outline_units(self, reader: pypdf.PdfReader) -> List[Tuple[int, str]]:
        """Extract table of contents bookmarks from PDF outline if available."""
        units: List[Tuple[int, str]] = []
        try:
            def process_outline(item):
                if isinstance(item, list):
                    for sub in item:
                        process_outline(sub)
                elif hasattr(item, "title"):
                    title = str(item.title).strip()
                    try:
                        page_num = reader.get_destination_page_number(item) + 1
                        units.append((page_num, title))
                    except Exception:
                        pass

            if reader.outline:
                process_outline(reader.outline)
                units.sort(key=lambda x: x[0])
        except Exception:
            pass
        return units

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

        # Auto-extract outline bookmarks from PDF
        outline_units = self._extract_outline_units(reader)

        extracted_pages: List[Dict[str, Any]] = []

        for p_num in range(start_p, end_p + 1):
            raw_page = reader.pages[p_num - 1]
            raw_text = raw_page.extract_text() or ""
            clean_text = self._clean_text(raw_text)

            if not clean_text or len(clean_text.strip()) < 40:
                # Skip blank or trivial pages
                continue

            chapter_title = self._get_chapter_title(p_num, clean_text, outline_units)

            extracted_pages.append({
                "page_number": p_num,
                "chapter_title": chapter_title,
                "text": clean_text,
                "source_file": self.pdf_path.name,
            })

        return extracted_pages

    def _get_chapter_title(
        self,
        page_num: int,
        page_text: str,
        units_map: List[Tuple[int, str]],
    ) -> str:
        """Resolve the chapter or unit title for a given page."""
        # 1. Check if an explicit Unit, Chapter, or Part heading appears in the top lines
        first_lines = page_text.split("\n")[:4]
        for line in first_lines:
            line_str = line.strip()
            if re.match(r"^(?:UNIT|Unit|CHAPTER|Chapter|PART|Part)\s+[IVXLCDM\d]+", line_str):
                return line_str

        # 2. Check outline bookmarks from PDF TOC
        if units_map:
            current_unit = units_map[0][1]
            for unit_page, unit_name in units_map:
                if page_num >= unit_page:
                    current_unit = unit_name
                else:
                    break
            return current_unit

        # 3. Fallback to Subject Name
        return f"{self.subject_name}"

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


