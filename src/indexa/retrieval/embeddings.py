"""Embedding providers for semantic search."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query.

        Default implementation uses embed_texts. Override if the provider
        has a specialized query embedding method.

        Args:
            query: Query text to embed

        Returns:
            Embedding vector
        """
        return self.embed_texts([query])[0]


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small.

    This is the recommended provider for production use.
    - Model: text-embedding-3-small
    - Dimensions: 1536
    - Cost: ~$0.02 per 1M tokens
    - Quality: Excellent for semantic search

    Supports both sync and async embedding generation.
    Use embed_texts_async() for parallel batch processing.
    """

    DEFAULT_MODEL = "text-embedding-3-small"
    DIMENSION = 1536
    BATCH_SIZE = 100  # OpenAI batch limit
    MAX_CONCURRENT_REQUESTS = 4  # Balance throughput vs rate limits

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize OpenAI embedding provider.

        Args:
            model: Model name (default: text-embedding-3-small)
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)

        Raises:
            ValueError: If API key is not provided or found in environment
        """
        self._model = model or self.DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

        if not self._api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Lazy import to avoid dependency if not used
        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key)

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    @property
    def model_name(self) -> str:
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI API (synchronous).

        Handles batching automatically for large inputs.
        For better performance with large inputs, use embed_texts_async().
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            batch = [t if t.strip() else " " for t in batch]

            response = self._client.embeddings.create(
                model=self._model,
                input=batch,
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI API with parallel batch processing.

        Processes multiple batches concurrently for faster throughput.
        Respects rate limits with MAX_CONCURRENT_REQUESTS semaphore.
        """
        if not texts:
            return []

        import aiohttp

        batches = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            batch = [t if t.strip() else " " for t in batch]
            batches.append(batch)

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async def embed_batch(
            session: aiohttp.ClientSession, batch: list[str], batch_idx: int
        ) -> tuple[int, list[list[float]]]:
            async with semaphore:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
                payload = {"model": self._model, "input": batch}

                async with session.post(
                    "https://api.openai.com/v1/embeddings",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    embeddings = [item["embedding"] for item in data["data"]]
                    return (batch_idx, embeddings)

        async with aiohttp.ClientSession() as session:
            tasks = [embed_batch(session, batch, idx) for idx, batch in enumerate(batches)]
            results = await asyncio.gather(*tasks)

        results.sort(key=lambda x: x[0])
        all_embeddings: list[list[float]] = []
        for _, embeddings in results:
            all_embeddings.extend(embeddings)

        return all_embeddings

    def embed_texts_parallel(self, texts: list[str]) -> list[list[float]]:
        """Synchronous wrapper for async parallel embedding.

        Use this when you want parallel processing but are in a sync context.
        """
        if not texts:
            return []

        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.embed_texts_async(texts))
        except RuntimeError:
            return asyncio.run(self.embed_texts_async(texts))


class LocalEmbeddings(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Uses all-MiniLM-L6-v2 by default - a good balance of speed and quality.
    - Model: all-MiniLM-L6-v2
    - Dimensions: 384
    - Cost: Free (runs locally)
    - Quality: Good for most use cases
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    DIMENSION = 384

    def __init__(self, model: str | None = None) -> None:
        """Initialize local embedding provider.

        Args:
            model: Model name from sentence-transformers
                   (default: all-MiniLM-L6-v2)
        """
        self._model_name = model or self.DEFAULT_MODEL

        # Lazy import
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self._model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using local model."""
        if not texts:
            return []

        # sentence-transformers handles batching internally
        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()


def get_embedding_provider(
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
) -> EmbeddingProvider:
    """Factory function to get an embedding provider.

    Args:
        provider: Provider type - "openai" or "local"
        model: Optional model name override
        api_key: Optional API key (for OpenAI)

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If provider is unknown or configuration is invalid
    """
    if provider == "openai":
        return OpenAIEmbeddings(model=model, api_key=api_key)
    elif provider == "local":
        return LocalEmbeddings(model=model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}. Use 'openai' or 'local'.")
