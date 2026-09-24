"""Hybrid Retriever combining Dense Vector search with BM25 keyword matching via RRF."""

import pickle
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rank_bm25 import BM25Okapi
from src.config import BM25_PERSIST_DIR
from src.rag.schema import FactChunk, RetrievalResult
from src.rag.store import BaseVectorStore, ChromaVectorStore
from src.rag.embeddings import EmbeddingClient


def tokenize_for_bm25(text: str) -> List[str]:
    """Tokenize and lower-case text for BM25 keyword indexing."""
    # Split on non-alphanumeric characters, retaining numbers (e.g. 1919, 1857)
    tokens = re.findall(r"\b\w+\b", text.lower())
    return [t for t in tokens if len(t) > 1]


class BM25Store:
    """Manages disk persistence and searching for the BM25 keyword index."""

    def __init__(self, persist_path: Optional[Path] = None):
        default_unified = BM25_PERSIST_DIR / "bm25_index.pkl"
        legacy_path = BM25_PERSIST_DIR / "modern_history.pkl"
        if persist_path:
            self.persist_path = Path(persist_path)
        elif default_unified.exists():
            self.persist_path = default_unified
        elif legacy_path.exists():
            self.persist_path = legacy_path
        else:
            self.persist_path = default_unified

        self.corpus_ids: List[str] = []
        self.corpus_chunks: Dict[str, FactChunk] = {}
        self.bm25: Optional[BM25Okapi] = None

    def build_and_save(self, chunks: List[FactChunk]) -> None:
        """Build BM25 index from chunks and save to disk."""
        if not chunks:
            return

        self.corpus_ids = [c.id for c in chunks]
        self.corpus_chunks = {c.id: c for c in chunks}

        # Tokenize content
        tokenized_corpus = [tokenize_for_bm25(c.content) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump({
                "corpus_ids": self.corpus_ids,
                "corpus_chunks": self.corpus_chunks,
                "bm25": self.bm25,
            }, f)

    def load(self) -> bool:
        """Load BM25 index from disk if present."""
        if not self.persist_path.exists():
            return False

        try:
            with open(self.persist_path, "rb") as f:
                data = pickle.load(f)
                self.corpus_ids = data["corpus_ids"]
                self.corpus_chunks = data["corpus_chunks"]
                self.bm25 = data["bm25"]
            return True
        except Exception:
            return False

    def search(
        self,
        query: str,
        top_k: int = 10,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[FactChunk, float]]:
        """Run BM25 search returning list of (FactChunk, raw_score) pairs."""
        if not self.bm25 or not self.corpus_ids:
            return []

        tokenized_query = tokenize_for_bm25(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        # Pair IDs with scores
        scored_pairs = list(zip(self.corpus_ids, scores))
        # Filter zero scores and sort descending
        scored_pairs = [p for p in scored_pairs if p[1] > 0.0]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results: List[Tuple[FactChunk, float]] = []
        for cid, score in scored_pairs:
            chunk = self.corpus_chunks.get(cid)
            if not chunk:
                continue

            # Apply metadata filter if provided
            if where_filter:
                match = True
                for k, v in where_filter.items():
                    val = getattr(chunk.metadata, k, None)
                    if val != v:
                        match = False
                        break
                if not match:
                    continue

            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break

        return results


class HybridRetriever:
    """Combines Dense Vector search and Sparse BM25 search via Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_client: EmbeddingClient,
        bm25_store: Optional[BM25Store] = None,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.bm25_store = bm25_store or BM25Store()
        self.rrf_k = rrf_k

        # Try to load existing BM25 index from disk
        self.bm25_store.load()

    def search(
        self,
        query: str,
        top_k: int = 5,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Perform hybrid retrieval using Reciprocal Rank Fusion.
        
        Args:
            query: The user query, claim to verify, or student answer excerpt.
            top_k: Number of final fused passages to return.
            where_filter: Optional metadata filter for vector and BM25 search (e.g. {"paper": "GS-1"}).
            
        Returns:
            List of RetrievalResult objects sorted by highest RRF score.
        """
        candidate_pool = max(top_k * 3, 20)

        # 1. Dense Vector Search
        dense_results: List[FactChunk] = []
        try:
            query_vector = self.embedding_client.embed_query(query)
            dense_results = self.vector_store.query(
                vector=query_vector,
                top_k=candidate_pool,
                where=where_filter,
            )
        except Exception as e:
            # If embedding fails (e.g. offline test without API key), log and fall back to BM25
            print(f"[Warning] Dense search skipped or failed: {e}")

        # 2. Sparse BM25 Keyword Search
        bm25_scored = self.bm25_store.search(
            query,
            top_k=candidate_pool,
            where_filter=where_filter,
        )


        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_score(d) = sum(1 / (k + rank))
        rrf_scores: Dict[str, float] = {}
        chunk_lookup: Dict[str, FactChunk] = {}
        dense_ranks: Dict[str, int] = {}
        sparse_ranks: Dict[str, int] = {}
        sparse_raw_scores: Dict[str, float] = {}

        # Process Dense Ranks
        for rank_idx, chunk in enumerate(dense_results, start=1):
            cid = chunk.id
            chunk_lookup[cid] = chunk
            dense_ranks[cid] = rank_idx
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank_idx))

        # Process Sparse Ranks
        for rank_idx, (chunk, score) in enumerate(bm25_scored, start=1):
            cid = chunk.id
            chunk_lookup[cid] = chunk
            sparse_ranks[cid] = rank_idx
            sparse_raw_scores[cid] = score
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank_idx))

        # Sort all candidates by descending RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        final_results: List[RetrievalResult] = []
        for cid in sorted_ids[:top_k]:
            chunk = chunk_lookup[cid]
            final_results.append(
                RetrievalResult(
                    chunk=chunk,
                    combined_score=round(rrf_scores[cid], 5),
                    dense_score=float(dense_ranks[cid]) if cid in dense_ranks else None,
                    sparse_score=sparse_raw_scores.get(cid),
                )
            )

        return final_results


def get_retriever() -> HybridRetriever:
    """Factory function to get default configured HybridRetriever."""
    store = ChromaVectorStore()
    embedding_client = EmbeddingClient()
    bm25 = BM25Store()
    bm25.load()
    return HybridRetriever(
        vector_store=store,
        embedding_client=embedding_client,
        bm25_store=bm25,
    )
