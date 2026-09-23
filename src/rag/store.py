"""Vector store abstraction layer and ChromaDB implementation."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
import chromadb
from chromadb.config import Settings
from src.config import CHROMA_PERSIST_DIR, DEFAULT_COLLECTION_NAME
from src.rag.schema import FactChunk, ChunkMetadata


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
