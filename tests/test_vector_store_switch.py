"""Unit tests for vector store factory, dual-backend switching, and fallback mechanisms."""

import pytest
from unittest.mock import MagicMock
from src.rag.store import (
    get_vector_store,
    ChromaVectorStore,
    SupabaseVectorStore,
)
from src.rag.retriever import get_retriever
from src.rag.schema import FactChunk, ChunkMetadata


def test_in_memory_always_selects_ephemeral_chroma():
    """In-memory flag must always route to ephemeral ChromaDB for clean test isolation."""
    store = get_vector_store(in_memory=True)
    assert isinstance(store, ChromaVectorStore)
    assert store.in_memory is True


def test_switch_backend_via_param():
    """Verify explicit backend parameter routes to correct store class."""
    sqlite_store = get_vector_store(backend="sqlite")
    assert isinstance(sqlite_store, ChromaVectorStore)

    chroma_store = get_vector_store(backend="chroma")
    assert isinstance(chroma_store, ChromaVectorStore)

    supabase_store = get_vector_store(backend="supabase")
    assert isinstance(supabase_store, SupabaseVectorStore)


def test_switch_backend_via_env(monkeypatch):
    """Verify VECTOR_STORE_BACKEND environment variable controls default store selection."""
    monkeypatch.setenv("VECTOR_STORE_BACKEND", "sqlite")
    store = get_vector_store()
    assert isinstance(store, ChromaVectorStore)

    monkeypatch.setenv("VECTOR_STORE_BACKEND", "supabase")
    store_supa = get_vector_store()
    assert isinstance(store_supa, SupabaseVectorStore)


def test_fallback_to_sqlite_when_supabase_unconfigured(monkeypatch):
    """When Supabase credentials are missing, system must gracefully fall back to Chroma."""
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    import src.rag.store as store_mod
    monkeypatch.setattr(store_mod, "is_supabase_configured", lambda: False)

    fallback_store = get_vector_store(backend="supabase")
    assert isinstance(fallback_store, ChromaVectorStore)


def test_get_retriever_respects_backend():
    """Verify get_retriever forwards the backend parameter to the underlying store."""
    retriever_sqlite = get_retriever(backend="sqlite")
    assert isinstance(retriever_sqlite.vector_store, ChromaVectorStore)

    retriever_supa = get_retriever(backend="supabase")
    assert isinstance(retriever_supa.vector_store, SupabaseVectorStore)


def test_supabase_vector_store_mock_query(monkeypatch):
    """Verify SupabaseVectorStore query accurately unpacks RPC results into FactChunk objects."""
    store = SupabaseVectorStore(table_name="knowledge_chunks")

    mock_client = MagicMock()
    mock_rpc = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "mock_chunk_1",
            "content": "Sample content about Dyarchy.",
            "prefixed_content": "[Resource: Spectrum] Sample content about Dyarchy.",
            "metadata": {
                "chunk_id": "mock_chunk_1",
                "source_file": "spectrum.pdf",
                "paper": "GS-1",
                "subject": "Modern History",
                "page_number": 184,
                "token_count": 45,
                "created_at": "2026-09-24T00:00:00Z",
            },
            "similarity": 0.88,
        }
    ]
    mock_rpc.execute.return_value = mock_response
    mock_client.rpc.return_value = mock_rpc

    monkeypatch.setattr(store, "_client", mock_client)

    results = store.query(vector=[0.1] * 1536, top_k=1, where={"paper": "GS-1"})
    assert len(results) == 1
    assert results[0].id == "mock_chunk_1"
    assert results[0].metadata.paper == "GS-1"
    assert results[0].metadata.page_number == 184
    assert "Dyarchy" in results[0].content
