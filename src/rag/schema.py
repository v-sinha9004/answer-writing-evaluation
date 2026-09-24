"""Data schemas for RAG knowledge chunks and retrieval results."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata attached to each chunk in the vector store."""
    chunk_id: str = Field(..., description="Unique deterministic chunk identifier")
    source_file: str = Field(..., description="Name of source document, e.g. spectrum.pdf")
    paper: str = Field(..., description="UPSC General Studies paper (GS-1, GS-2, etc.)")
    subject: str = Field(..., description="Subject area (e.g. Modern History, Polity)")
    page_number: int = Field(..., description="Exact page number in the source resource")
    token_count: int = Field(default=0, description="Approximate or exact token count")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to flat dictionary suitable for vector databases like ChromaDB."""
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "paper": self.paper,
            "subject": self.subject,
            "page_number": self.page_number,
            "token_count": self.token_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        return cls(
            chunk_id=str(data.get("chunk_id", "")),
            source_file=str(data.get("source_file", "")),
            paper=str(data.get("paper", "")),
            subject=str(data.get("subject", "")),
            page_number=int(data.get("page_number", 0)),
            token_count=int(data.get("token_count", 0)),
            created_at=str(data.get("created_at", "")),
        )



class FactChunk(BaseModel):
    """A self-contained factual chunk of knowledge."""
    id: str = Field(..., description="Matches metadata.chunk_id")
    content: str = Field(..., description="Original extracted chunk text")
    prefixed_content: str = Field(..., description="Content prepended with contextual citation header")
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = Field(default=None, description="Dense embedding vector")


class RetrievalResult(BaseModel):
    """Result returned by the hybrid retriever."""
    chunk: FactChunk
    combined_score: float = Field(..., description="Fused ranking score (e.g. Reciprocal Rank Fusion)")
    dense_score: Optional[float] = Field(default=None, description="Score from dense vector search")
    sparse_score: Optional[float] = Field(default=None, description="Score from BM25 keyword search")
