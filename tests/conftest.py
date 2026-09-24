"""Pytest configuration and isolated fixtures for RAG testing."""

import pytest
from src.rag.schema import FactChunk, ChunkMetadata
from src.rag.store import ChromaVectorStore
from src.rag.retriever import BM25Store, HybridRetriever
from src.rag.embeddings import EmbeddingClient


@pytest.fixture
def sample_modern_history_chunks():
    """Curated realistic chunks from Modern History for offline testing."""
    chunks = [
        FactChunk(
            id="spectrum_p184_c01",
            content=(
                "The Government of India Act 1919 introduced Dyarchy in the provinces. "
                "Subjects were divided into 'Transferred' and 'Reserved' subjects. "
                "Transferred subjects were administered by ministers responsible to the legislative council, "
                "while Reserved subjects like law, justice, and police remained with the Governor and his executive council."
            ),
            prefixed_content=(
                "[Resource: Spectrum Modern History | Page: 184]\n\n"
                "The Government of India Act 1919 introduced Dyarchy in the provinces. "
                "Subjects were divided into 'Transferred' and 'Reserved' subjects."
            ),
            metadata=ChunkMetadata(
                chunk_id="spectrum_p184_c01",
                source_file="gs1_modern_history_spectrum.pdf",
                paper="GS-1",
                subject="Modern History",
                page_number=184,
                token_count=75,
            ),
            # Realistic synthetic 1536-dim vector with a specific signature
            embedding=[0.05] * 1536,
        ),
        FactChunk(
            id="spectrum_p201_c01",
            content=(
                "The Santhal Rebellion (or Santhal Hul) took place between 1855 and 1856 under the leadership of "
                "two brothers, Sidhu and Kanhu Murmu. It was an armed revolt by the Santhal people against the "
                "oppressive zamindari system, British colonial tax collectors, and money-lenders in the Damin-i-Koh region."
            ),
            prefixed_content=(
                "[Resource: Spectrum Modern History | Page: 201]\n\n"
                "The Santhal Rebellion took place between 1855 and 1856 under Sidhu and Kanhu Murmu."
            ),
            metadata=ChunkMetadata(
                chunk_id="spectrum_p201_c01",
                source_file="gs1_modern_history_spectrum.pdf",
                paper="GS-1",
                subject="Modern History",
                page_number=201,
                token_count=70,
            ),
            embedding=[-0.05] * 1536,
        ),
        FactChunk(
            id="spectrum_p312_c01",
            content=(
                "The Non-Cooperation Movement was launched in 1920 by Mahatma Gandhi following the Jallianwala Bagh massacre "
                "and the Khilafat grievance. The movement aimed at attaining Swaraj through boycott of British goods, "
                "government schools, colleges, and law courts, and surrender of government titles."
            ),
            prefixed_content=(
                "[Resource: Spectrum Modern History | Page: 312]\n\n"
                "The Non-Cooperation Movement was launched in 1920 by Mahatma Gandhi."
            ),
            metadata=ChunkMetadata(
                chunk_id="spectrum_p312_c01",
                source_file="gs1_modern_history_spectrum.pdf",
                paper="GS-1",
                subject="Modern History",
                page_number=312,
                token_count=65,
            ),
            embedding=[0.02] * 1536,
        ),
    ]
    return chunks


@pytest.fixture
def ephemeral_chroma():
    """In-memory Chroma instance. Never reads from or writes to data/chromadb."""
    return ChromaVectorStore(
        collection_name="test_modern_history",
        in_memory=True,
    )


@pytest.fixture
def temp_bm25_store(tmp_path):
    """Temporary BM25 index that writes to a temporary sandbox directory."""
    temp_path = tmp_path / "test_bm25.pkl"
    return BM25Store(persist_path=temp_path)
