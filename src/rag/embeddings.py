"""OpenAI Embedding Client for vector generation."""

import time
from typing import List, Optional
from openai import OpenAI
from src.config import OPENAI_API_KEY, EMBEDDING_MODEL


class EmbeddingClient:
    """Generates dense vector embeddings using OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: str = EMBEDDING_MODEL):
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not set. Please add OPENAI_API_KEY to your .env file "
                    "or pass it to EmbeddingClient(api_key=...)."
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def embed_texts(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed a list of text strings in batches with retry logic.
        
        Args:
            texts: List of strings to embed.
            batch_size: Number of strings per OpenAI API call (default 100).
            
        Returns:
            List of embedding vectors (list of floats).
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        results = self.embed_texts([query])
        return results[0]

    def _embed_batch_with_retry(self, batch: List[str], max_retries: int = 4) -> List[List[float]]:
        """Call OpenAI embeddings API with exponential backoff on transient errors."""
        cleaned_batch = [t.replace("\n", " ").strip() or " " for t in batch]

        for attempt in range(max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=cleaned_batch
                )
                # Sort by index to preserve order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                return [item.embedding for item in sorted_data]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"OpenAI embedding failed after {max_retries} attempts: {e}") from e
                sleep_sec = 2 ** attempt
                time.sleep(sleep_sec)
        return []
