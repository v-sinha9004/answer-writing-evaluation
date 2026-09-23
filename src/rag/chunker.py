"""Recursive structural chunker with Context Prefix Injection for UPSC Modern History."""

import re
from typing import List, Dict, Any
import tiktoken
from src.config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS
from src.rag.schema import FactChunk, ChunkMetadata


class SpectrumChunker:
    """Chunks Spectrum PDF pages with sliding overlap and context prefix injection."""

    def __init__(
        self,
        target_tokens: int = CHUNK_SIZE_TOKENS,
        overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
        encoding_name: str = "cl100k_base",
    ):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def chunk_pages(self, pages: List[Dict[str, Any]]) -> List[FactChunk]:
        """Split a list of extracted PDF pages into structured FactChunks.
        
        Args:
            pages: List of page dicts from SpectrumPDFLoader.
            
        Returns:
            List of FactChunk instances with rich metadata and prefixed content.
        """
        all_chunks: List[FactChunk] = []

        for page in pages:
            page_num = page["page_number"]
            chapter_title = page["chapter_title"]
            source_file = page["source_file"]
            raw_text = page["text"]

            page_chunks = self._chunk_page_text(
                raw_text=raw_text,
                page_num=page_num,
                chapter_title=chapter_title,
                source_file=source_file,
            )
            all_chunks.extend(page_chunks)

        return all_chunks

    def _chunk_page_text(
        self,
        raw_text: str,
        page_num: int,
        chapter_title: str,
        source_file: str,
    ) -> List[FactChunk]:
        """Split a single page's text into one or more chunks."""
        # Split text into paragraphs
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [raw_text.strip()]

        chunks_text: List[str] = []
        current_chunk_parts: List[str] = []
        current_token_count = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            # If a single paragraph is larger than target_tokens, split by sentences
            if para_tokens > self.target_tokens:
                sentences = re.split(r"(?<=[.?!])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    s_tokens = self.count_tokens(sentence)

                    if current_token_count + s_tokens > self.target_tokens and current_chunk_parts:
                        # Flush current chunk
                        full_chunk = "\n\n".join(current_chunk_parts)
                        chunks_text.append(full_chunk)

                        # Overlap: keep the last sentence(s) up to overlap_tokens
                        overlap_parts: List[str] = []
                        overlap_count = 0
                        for part in reversed(current_chunk_parts):
                            p_tok = self.count_tokens(part)
                            if overlap_count + p_tok <= self.overlap_tokens:
                                overlap_parts.insert(0, part)
                                overlap_count += p_tok
                            else:
                                break
                        current_chunk_parts = overlap_parts + [sentence]
                        current_token_count = overlap_count + s_tokens
                    else:
                        current_chunk_parts.append(sentence)
                        current_token_count += s_tokens

            # Standard paragraph appending
            elif current_token_count + para_tokens > self.target_tokens and current_chunk_parts:
                full_chunk = "\n\n".join(current_chunk_parts)
                chunks_text.append(full_chunk)

                # Overlap: keep last paragraph if it fits overlap limit
                last_part = current_chunk_parts[-1]
                last_tokens = self.count_tokens(last_part)
                if last_tokens <= self.overlap_tokens:
                    current_chunk_parts = [last_part, para]
                    current_token_count = last_tokens + para_tokens
                else:
                    current_chunk_parts = [para]
                    current_token_count = para_tokens
            else:
                current_chunk_parts.append(para)
                current_token_count += para_tokens

        # Flush remainder
        if current_chunk_parts:
            full_chunk = "\n\n".join(current_chunk_parts)
            chunks_text.append(full_chunk)

        # Convert chunk texts to FactChunk models with Context Prefix
        fact_chunks: List[FactChunk] = []
        for idx, text in enumerate(chunks_text, start=1):
            chunk_id = f"spectrum_p{page_num:03d}_c{idx:02d}"
            token_count = self.count_tokens(text)

            # Injected context prefix
            prefix = (
                f"[Resource: Spectrum Modern History | Subject: GS-1 Modern History | "
                f"Chapter: {chapter_title} | Page: {page_num}]\n\n"
            )
            prefixed_content = prefix + text

            meta = ChunkMetadata(
                chunk_id=chunk_id,
                source_file=source_file,
                paper="GS-1",
                subject="Modern History",
                page_number=page_num,
                chapter_title=chapter_title,
                token_count=token_count,
            )

            fact_chunks.append(FactChunk(
                id=chunk_id,
                content=text,
                prefixed_content=prefixed_content,
                metadata=meta,
            ))

        return fact_chunks
