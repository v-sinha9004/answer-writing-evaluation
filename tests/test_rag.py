"""Unit and integration tests for RAG pipeline with strict test isolation."""

import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.config import CHROMA_PERSIST_DIR
from src.rag.pdf_loader import SpectrumPDFLoader
from src.rag.chunker import SpectrumChunker
from src.rag.store import ChromaVectorStore
from src.rag.retriever import HybridRetriever, tokenize_for_bm25
from src.rag.embeddings import EmbeddingClient


def test_pdf_loader_sample_pages():
    """Verify SpectrumPDFLoader extracts clean text and assigns chapter titles."""
    loader = SpectrumPDFLoader()
    pages = loader.load_pages(page_range=(180, 182))

    assert len(pages) > 0
    first_page = pages[0]
    assert "page_number" in first_page
    assert first_page["page_number"] == 180
    assert "chapter_title" in first_page
    assert "Rising Resentment" in first_page["chapter_title"] or "Unit III" in first_page["chapter_title"]
    assert "source_file" in first_page
    # Watermark text should have been stripped
    assert "t.me/" not in first_page["text"]


def test_chunker_structure_and_prefix():
    """Verify chunker creates structured FactChunks with context prefixes."""
    loader = SpectrumPDFLoader()
    pages = loader.load_pages(page_range=(180, 181))
    chunker = SpectrumChunker(target_tokens=400, overlap_tokens=80)
    chunks = chunker.chunk_pages(pages)

    assert len(chunks) >= len(pages)
    for c in chunks:
        assert c.id.startswith("spectrum_p")
        assert c.metadata.paper == "GS-1"
        assert c.metadata.subject == "Modern History"
        assert c.metadata.token_count > 0
        # Check context prefix injection
        assert c.prefixed_content.startswith("[Resource: Spectrum Modern History")
        assert f"Page: {c.metadata.page_number}" in c.prefixed_content


def test_chroma_ephemeral_store(ephemeral_chroma, sample_modern_history_chunks):
    """Verify ChromaVectorStore runs in-memory without error and performs vector queries."""
    store = ephemeral_chroma
    assert store.count() == 0

    # Upsert sample chunks
    upserted = store.upsert(sample_modern_history_chunks)
    assert upserted == 3
    assert store.count() == 3

    # Query using vector matching chunk 0
    query_vec = [0.05] * 1536
    results = store.query(vector=query_vec, top_k=2)
    assert len(results) == 2
    assert results[0].id == "spectrum_p184_c01"
    assert "Dyarchy" in results[0].content

    # Query with where filter
    filtered = store.query(vector=query_vec, top_k=5, where={"page_number": 201})
    assert len(filtered) == 1
    assert filtered[0].id == "spectrum_p201_c01"

    # Get by IDs
    fetched = store.get_by_ids(["spectrum_p312_c01"])
    assert len(fetched) == 1
    assert "Non-Cooperation" in fetched[0].content


def test_bm25_store_keyword_matching(temp_bm25_store, sample_modern_history_chunks):
    """Verify BM25 index correctly scores exact historical keywords and dates."""
    bm25 = temp_bm25_store
    bm25.build_and_save(sample_modern_history_chunks)

    # Search for exact Santhal rebellion
    santhal_results = bm25.search("Santhal rebellion 1855 Sidhu Kanhu", top_k=2)
    assert len(santhal_results) > 0
    top_chunk, score = santhal_results[0]
    assert top_chunk.id == "spectrum_p201_c01"
    assert score > 0.0

    # Search for Dyarchy 1919
    dyarchy_results = bm25.search("Dyarchy 1919 Transferred Reserved", top_k=2)
    assert len(dyarchy_results) > 0
    assert dyarchy_results[0][0].id == "spectrum_p184_c01"


def test_hybrid_retriever_rrf(ephemeral_chroma, temp_bm25_store, sample_modern_history_chunks):
    """Verify HybridRetriever fuses dense and sparse rankings via Reciprocal Rank Fusion."""
    # Populate stores
    ephemeral_chroma.upsert(sample_modern_history_chunks)
    temp_bm25_store.build_and_save(sample_modern_history_chunks)

    # Mock embedding client to return deterministic vector
    mock_embedder = MagicMock(spec=EmbeddingClient)
    # Give vector close to Non-Cooperation Movement (chunk 2)
    mock_embedder.embed_query.return_value = [0.02] * 1536

    retriever = HybridRetriever(
        vector_store=ephemeral_chroma,
        embedding_client=mock_embedder,
        bm25_store=temp_bm25_store,
        rrf_k=60,
    )

    # Query for Non-Cooperation movement
    results = retriever.search("Non-Cooperation Movement 1920 Swaraj Gandhi", top_k=2)
    assert len(results) == 2
    # The Non-Cooperation chunk should win the top rank
    assert results[0].chunk.id == "spectrum_p312_c01"
    assert results[0].combined_score > 0.0
    assert results[0].sparse_score is not None


def test_zero_disk_pollution(ephemeral_chroma, sample_modern_history_chunks):
    """Verify that running ephemeral operations does not write any data to CHROMA_PERSIST_DIR."""
    # Ensure ephemeral client was used
    assert ephemeral_chroma.in_memory is True
    ephemeral_chroma.upsert(sample_modern_history_chunks)

    # Verify that data/chromadb directory was not modified or populated by the test
    if CHROMA_PERSIST_DIR.exists():
        # Any file in CHROMA_PERSIST_DIR should not belong to the ephemeral test collection
        files = list(CHROMA_PERSIST_DIR.glob("**/*"))
        for f in files:
            assert "test_modern_history" not in f.name
