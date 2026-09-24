"""Vector store abstraction layer with ChromaDB and Supabase pgvector implementations."""

import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

import chromadb
from chromadb.config import Settings
from supabase import create_client, Client

from src.config import (
    ROOT_DIR,
    CHROMA_PERSIST_DIR,
    DEFAULT_COLLECTION_NAME,
    VECTOR_STORE_BACKEND,
    SUPABASE_VECTOR_TABLE,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    is_supabase_configured,
)
from src.rag.schema import FactChunk, ChunkMetadata

logger = logging.getLogger("upsc-vector-store")


class BaseVectorStore(ABC):
    """Abstract interface for vector databases.
    
    Allows zero-effort migration to cloud databases like Qdrant Cloud or Pinecone
    by simply subclassing this interface.
    """

    @abstractmethod
    def upsert(self, chunks: List[FactChunk]) -> int:
        """Upsert fact chunks with their embeddings into the store.
        
        Returns:
            Number of chunks successfully upserted.
        """
        pass

    @abstractmethod
    def query(
        self,
        vector: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[FactChunk]:
        """Retrieve the top-k most similar chunks for a given query vector.
        
        Args:
            vector: Query embedding.
            top_k: Maximum number of results to return.
            where: Optional metadata filter dictionary.
            
        Returns:
            List of retrieved FactChunk instances with relevance metadata.
        """
        pass

    @abstractmethod
    def get_by_ids(self, ids: List[str]) -> List[FactChunk]:
        """Fetch chunks by their unique IDs."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return the total number of chunks stored."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all chunks from the collection."""
        pass


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation of BaseVectorStore.
    
    Supports persistent disk storage or in-memory ephemeral mode for test isolation.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        persist_dir: Optional[Path] = CHROMA_PERSIST_DIR,
        in_memory: bool = False,
    ):
        self.collection_name = collection_name
        self.in_memory = in_memory

        if in_memory:
            # Ephemeral in-memory client for testing (never writes to disk)
            self._client = chromadb.EphemeralClient()
        else:
            persist_dir_str = str(persist_dir or CHROMA_PERSIST_DIR)
            Path(persist_dir_str).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=persist_dir_str,
                settings=Settings(anonymized_telemetry=False)
            )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Graceful fallback for backwards compatibility with legacy collection names
        if not in_memory and self._collection.count() == 0 and collection_name == "upsc_knowledge_base":
            try:
                existing = [c.name for c in self._client.list_collections()]
                if "gs1_modern_history" in existing:
                    candidate = self._client.get_collection("gs1_modern_history")
                    if candidate.count() > 0:
                        self.collection_name = "gs1_modern_history"
                        self._collection = candidate
            except Exception:
                pass

    def upsert(self, chunks: List[FactChunk]) -> int:
        if not chunks:
            return 0

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk '{chunk.id}' has no embedding vector.")
            ids.append(chunk.id)
            embeddings.append(chunk.embedding)
            # Store prefixed content as document text for text search reference
            documents.append(chunk.prefixed_content)
            # Flatten metadata for Chroma
            meta_dict = chunk.metadata.to_dict()
            meta_dict["raw_content"] = chunk.content
            metadatas.append(meta_dict)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(chunks)

    def query(
        self,
        vector: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[FactChunk]:
        if self.count() == 0:
            return []

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [vector],
            "n_results": min(top_k, self.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        results = self._collection.query(**query_kwargs)

        chunks: List[FactChunk] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return chunks

        ids = results["ids"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        documents = results["documents"][0] if results.get("documents") else []

        for cid, meta, doc in zip(ids, metadatas, documents):
            meta_copy = dict(meta) if meta else {}
            raw_content = meta_copy.pop("raw_content", doc)
            metadata_obj = ChunkMetadata.from_dict(meta_copy)
            chunk = FactChunk(
                id=cid,
                content=raw_content,
                prefixed_content=doc,
                metadata=metadata_obj,
            )
            chunks.append(chunk)

        return chunks

    def get_by_ids(self, ids: List[str]) -> List[FactChunk]:
        if not ids or self.count() == 0:
            return []

        results = self._collection.get(
            ids=ids,
            include=["documents", "metadatas"]
        )

        chunks: List[FactChunk] = []
        for cid, meta, doc in zip(results["ids"], results["metadatas"], results["documents"]):
            meta_copy = dict(meta) if meta else {}
            raw_content = meta_copy.pop("raw_content", doc)
            metadata_obj = ChunkMetadata.from_dict(meta_copy)
            chunk = FactChunk(
                id=cid,
                content=raw_content,
                prefixed_content=doc,
                metadata=metadata_obj,
            )
            chunks.append(chunk)

        return chunks

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )


class SupabaseVectorStore(BaseVectorStore):
    """Supabase pgvector implementation of BaseVectorStore."""

    def __init__(
        self,
        table_name: Optional[str] = None,
        url: Optional[str] = None,
        key: Optional[str] = None,
    ):
        load_dotenv(ROOT_DIR / ".env", override=True)
        self.table_name = (
            table_name
            or os.getenv("SUPABASE_VECTOR_TABLE")
            or SUPABASE_VECTOR_TABLE
            or "knowledge_chunks"
        ).strip()
        self.url = (url or os.getenv("SUPABASE_URL") or SUPABASE_URL).strip()
        self.key = (key or os.getenv("SUPABASE_ANON_KEY") or SUPABASE_ANON_KEY).strip()
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Lazy-initialize Supabase client."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = (self.url or os.getenv("SUPABASE_URL") or "").strip()
        key = (self.key or os.getenv("SUPABASE_ANON_KEY") or "").strip()

        if not url or not key:
            raise RuntimeError(
                "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your environment or .env file."
            )

        if self._client is None:
            self._client = create_client(url, key)
        return self._client

    def is_configured(self) -> bool:
        """Check if Supabase credentials are configured."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = self.url or os.getenv("SUPABASE_URL", "")
        key = self.key or os.getenv("SUPABASE_ANON_KEY", "")
        return bool(url and key)

    def upsert(self, chunks: List[FactChunk], batch_size: int = 100) -> int:
        """Upsert chunks with their embeddings into Supabase pgvector table in batches."""
        if not chunks:
            return 0

        total_upserted = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            records = []
            for chunk in batch:
                if chunk.embedding is None:
                    raise ValueError(f"Chunk '{chunk.id}' has no embedding vector.")
                records.append({
                    "id": chunk.id,
                    "content": chunk.content,
                    "prefixed_content": chunk.prefixed_content,
                    "paper": chunk.metadata.paper,
                    "subject": chunk.metadata.subject,
                    "source_file": chunk.metadata.source_file,
                    "page_number": chunk.metadata.page_number,
                    "token_count": chunk.metadata.token_count,
                    "metadata": chunk.metadata.to_dict(),
                    "embedding": chunk.embedding,
                })
            self.client.table(self.table_name).upsert(records).execute()
            total_upserted += len(batch)

        return total_upserted

    def query(
        self,
        vector: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[FactChunk]:
        """Perform vector cosine similarity search via match_knowledge_chunks RPC."""
        if not self.is_configured():
            return []

        try:
            rpc_params: Dict[str, Any] = {
                "query_embedding": vector,
                "match_count": top_k,
                "filter": where or {},
            }
            response = self.client.rpc("match_knowledge_chunks", rpc_params).execute()
            rows = response.data or []

            chunks: List[FactChunk] = []
            for row in rows:
                meta_dict = row.get("metadata") or {}
                metadata_obj = ChunkMetadata.from_dict(meta_dict)
                chunks.append(
                    FactChunk(
                        id=row["id"],
                        content=row["content"],
                        prefixed_content=row["prefixed_content"],
                        metadata=metadata_obj,
                    )
                )
            return chunks
        except Exception as e:
            logger.error(f"Error querying Supabase vector store: {e}", exc_info=True)
            return []

    def get_by_ids(self, ids: List[str]) -> List[FactChunk]:
        """Fetch chunks by their IDs from Supabase."""
        if not ids or not self.is_configured():
            return []

        try:
            response = (
                self.client.table(self.table_name)
                .select("id, content, prefixed_content, metadata")
                .in_("id", ids)
                .execute()
            )
            rows = response.data or []
            chunks: List[FactChunk] = []
            for row in rows:
                meta_dict = row.get("metadata") or {}
                metadata_obj = ChunkMetadata.from_dict(meta_dict)
                chunks.append(
                    FactChunk(
                        id=row["id"],
                        content=row["content"],
                        prefixed_content=row["prefixed_content"],
                        metadata=metadata_obj,
                    )
                )
            return chunks
        except Exception as e:
            logger.error(f"Error fetching chunks by ID from Supabase: {e}", exc_info=True)
            return []

    def count(self) -> int:
        """Return total number of chunks stored in Supabase."""
        if not self.is_configured():
            return 0
        try:
            response = (
                self.client.table(self.table_name)
                .select("id", count="exact")
                .limit(0)
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"Error counting chunks in Supabase: {e}", exc_info=True)
            return 0

    def clear(self) -> None:
        """Clear all chunks from the Supabase vector table."""
        if not self.is_configured():
            return
        try:
            self.client.table(self.table_name).delete().neq("id", "___nonexistent_dummy___").execute()
        except Exception as e:
            logger.error(f"Error clearing Supabase vector table: {e}", exc_info=True)


# Cached singletons
_chroma_store: Optional[ChromaVectorStore] = None
_supabase_store: Optional[SupabaseVectorStore] = None


def get_vector_store(
    backend: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    persist_dir: Optional[Path] = None,
    in_memory: bool = False,
) -> BaseVectorStore:
    """Resolve and return active vector store based on configuration.

    Args:
        backend: Optional override ('supabase', 'sqlite', 'chroma').
                 Defaults to VECTOR_STORE_BACKEND env var.
        collection_name: Collection or table identifier name.
        persist_dir: Disk directory for ChromaDB (ignored for Supabase).
        in_memory: If True, forces ephemeral in-memory Chroma for isolated tests.

    Returns:
        BaseVectorStore instance.
    """
    global _chroma_store, _supabase_store

    # Test isolation always routes to ephemeral ChromaDB
    if in_memory:
        return ChromaVectorStore(collection_name=collection_name, in_memory=True)

    # Determine backend preference
    target_backend = (
        backend
        or os.getenv("VECTOR_STORE_BACKEND")
        or VECTOR_STORE_BACKEND
        or "supabase"
    ).strip().lower()

    if target_backend in ("supabase", "pgvector"):
        if is_supabase_configured():
            if _supabase_store is None:
                _supabase_store = SupabaseVectorStore()
            return _supabase_store
        else:
            logger.warning(
                "VECTOR_STORE_BACKEND is set to 'supabase', but SUPABASE_URL / SUPABASE_ANON_KEY are missing. "
                "Falling back to local SQLite ChromaDB store."
            )

    # Default to ChromaDB (SQLite backed)
    target_persist = persist_dir or CHROMA_PERSIST_DIR
    if _chroma_store is None or _chroma_store.collection_name != collection_name:
        _chroma_store = ChromaVectorStore(
            collection_name=collection_name,
            persist_dir=target_persist,
            in_memory=False,
        )
    return _chroma_store
