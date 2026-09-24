"""Unit and integration tests for RAG pipeline with strict test isolation."""

import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.config import CHROMA_PERSIST_DIR
from src.rag.pdf_loader import PDFLoader
from src.rag.chunker import TextbookChunker
from src.rag.store import ChromaVectorStore
from src.rag.retriever import HybridRetriever, tokenize_for_bm25
from src.rag.embeddings import EmbeddingClient
from src.rag.ingest import detect_metadata_from_path
from src.rag.schema import FactChunk, ChunkMetadata

SAMPLE_PDF_PATH = Path("data/resources/gs1/modern_history/spectrum.pdf")


def test_pdf_loader_sample_pages():
    """Verify PDFLoader extracts clean text and page numbers."""
    loader = PDFLoader(pdf_path=SAMPLE_PDF_PATH, subject_name="Modern History")
    pages = loader.load_pages(page_range=(180, 182))

    assert len(pages) > 0
    first_page = pages[0]
    assert "page_number" in first_page
    assert first_page["page_number"] == 180
    assert "source_file" in first_page
    # Watermark text should have been stripped
    assert "t.me/" not in first_page["text"]


def test_chunker_structure_and_prefix():
    """Verify chunker creates structured FactChunks with context prefixes."""
    loader = PDFLoader(pdf_path=SAMPLE_PDF_PATH, subject_name="Modern History")
    pages = loader.load_pages(page_range=(180, 181))
    chunker = TextbookChunker(target_tokens=400, overlap_tokens=80)
    chunks = chunker.chunk_pages(
        pages,
        paper="GS-1",
        subject="Modern History",
        resource_name="Spectrum Modern History",
        id_prefix="spectrum",
    )

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


def test_detect_metadata_from_path():
    """Verify auto-detection of GS paper, subject name, and ID prefix from folder paths."""
    # Test GS-1 Modern History (new layout)
    meta1 = detect_metadata_from_path(Path("data/resources/gs1/modern_history/spectrum.pdf"))
    assert meta1["paper"] == "GS-1"
    assert meta1["subject"] == "Modern History"
    assert meta1["id_prefix"] == "modern_history"


    # Test GS-2 Polity
    meta2 = detect_metadata_from_path(Path("resources/gs2/polity/laxmikanth.pdf"))
    assert meta2["paper"] == "GS-2"
    assert meta2["subject"] == "Polity"
    assert meta2["id_prefix"] == "polity"

    # Test GS-3 Economy
    meta3 = detect_metadata_from_path(Path("data/resources/gs3/economy/ramesh_singh.pdf"))
    assert meta3["paper"] == "GS-3"
    assert meta3["subject"] == "Economy"
    assert meta3["id_prefix"] == "economy"

    # Test GS-4 Ethics
    meta4 = detect_metadata_from_path(Path("resources/gs4/ethics/lexicon.pdf"))
    assert meta4["paper"] == "GS-4"
    assert meta4["subject"] == "Ethics"
    assert meta4["id_prefix"] == "ethics"

    # Test GS-1 Geography
    meta5 = detect_metadata_from_path(Path("data/resources/gs1/geography/ncert_physical_geography.pdf"))
    assert meta5["paper"] == "GS-1"
    assert meta5["subject"] == "Geography"
    assert meta5["id_prefix"] == "geography"


def test_textbook_chunker_multi_subject():
    """Verify TextbookChunker parameterizes paper, subject, prefix, and ID correctly."""
    dummy_pages = [
        {
            "page_number": 12,
            "source_file": "laxmikanth.pdf",
            "text": "The American Constitution was the first to begin with a Preamble. Many countries including India followed this practice.",
        }
    ]
    chunker = TextbookChunker(target_tokens=400, overlap_tokens=80)
    chunks = chunker.chunk_pages(
        dummy_pages,
        paper="GS-2",
        subject="Indian Polity",
        resource_name="Laxmikanth Indian Polity",
        id_prefix="polity",
    )

    assert len(chunks) == 1
    c = chunks[0]
    assert c.id == "polity_p012_c01"
    assert c.metadata.paper == "GS-2"
    assert c.metadata.subject == "Indian Polity"
    assert c.metadata.page_number == 12
    assert c.prefixed_content.startswith("[Resource: Laxmikanth Indian Polity | Subject: GS-2 Indian Polity")
    assert "Page: 12" in c.prefixed_content


def test_hybrid_retriever_where_filtering(temp_bm25_store):
    """Verify HybridRetriever respects where_filter for dense and BM25 search."""
    isolated_chroma = ChromaVectorStore(collection_name="test_filter_retriever", in_memory=True)
    # Create one GS-1 chunk and one GS-2 chunk with overlapping keywords
    c_gs1 = FactChunk(
        id="hist_p001_c01",
        content="The Constitution of India evolved historically through acts like the Government of India Act 1935.",
        prefixed_content="[Resource: History] The Constitution of India evolved historically through acts like the Government of India Act 1935.",
        metadata=ChunkMetadata(
            chunk_id="hist_p001_c01",
            source_file="history.pdf",
            paper="GS-1",
            subject="Modern History",
            page_number=1,
            token_count=20,
        ),
        embedding=[0.01] * 1536,
    )
    c_gs2 = FactChunk(
        id="polity_p001_c01",
        content="The Constitution of India provides for a parliamentary system of government at both Centre and States.",
        prefixed_content="[Resource: Polity] The Constitution of India provides for a parliamentary system of government at both Centre and States.",
        metadata=ChunkMetadata(
            chunk_id="polity_p001_c01",
            source_file="polity.pdf",
            paper="GS-2",
            subject="Indian Polity",
            page_number=1,
            token_count=20,
        ),
        embedding=[0.01] * 1536,
    )

    isolated_chroma.upsert([c_gs1, c_gs2])
    temp_bm25_store.build_and_save([c_gs1, c_gs2])

    mock_embedder = MagicMock(spec=EmbeddingClient)
    mock_embedder.embed_query.return_value = [0.01] * 1536

    retriever = HybridRetriever(
        vector_store=isolated_chroma,
        embedding_client=mock_embedder,
        bm25_store=temp_bm25_store,
        rrf_k=60,
    )


    # Search filtering strictly for GS-2
    results_gs2 = retriever.search(
        query="Constitution of India government",
        top_k=5,
        where_filter={"paper": "GS-2"},
    )
    assert len(results_gs2) == 1
    assert results_gs2[0].chunk.metadata.paper == "GS-2"
    assert results_gs2[0].chunk.id == "polity_p001_c01"

    # Search filtering strictly for GS-1
    results_gs1 = retriever.search(
        query="Constitution of India government",
        top_k=5,
        where_filter={"paper": "GS-1"},
    )
    assert len(results_gs1) == 1
    assert results_gs1[0].chunk.metadata.paper == "GS-1"
    assert results_gs1[0].chunk.id == "hist_p001_c01"

