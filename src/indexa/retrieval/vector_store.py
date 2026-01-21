"""Vector store using Qdrant for semantic search."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from indexa.indexing.chunk import NormalizedChunk
    from indexa.retrieval.embeddings import EmbeddingProvider


@dataclass
class VectorSearchResult:
    """A single vector search result."""

    chunk_id: str
    score: float  # Cosine similarity (0-1, higher = more similar)


class VectorStore:
    """Vector store using Qdrant for semantic search.

    Qdrant is a high-performance vector database that supports:
    - Efficient similarity search
    - Payload filtering
    - Persistent local storage
    - HNSW indexing for fast approximate search

    We use local file-based storage (no server required).
    """

    COLLECTION_NAME = "indexa_chunks"

    def __init__(
        self,
        storage_path: Path | str,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        """Initialize vector store.

        Args:
            storage_path: Path for Qdrant local storage
            embedding_provider: Provider for generating embeddings
        """
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._embedding_provider = embedding_provider
        self._client = None

    def _get_client(self):
        """Get or create Qdrant client."""
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(path=str(self._storage_path))
        return self._client

    def create_collection(self, recreate: bool = False) -> None:
        """Create the vector collection.

        Args:
            recreate: If True, delete existing collection first
        """
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()

        # Check if collection exists
        collections = client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if exists and recreate:
            client.delete_collection(self.COLLECTION_NAME)
            exists = False

        if not exists:
            client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self._embedding_provider.dimension,
                    distance=Distance.COSINE,
                ),
            )

    def add_chunks(
        self,
        chunks: list[NormalizedChunk],
        batch_size: int = 100,
        show_progress: bool = False,
        use_parallel: bool = True,
    ) -> None:
        """Add chunks to the vector store.

        Args:
            chunks: Chunks to index
            batch_size: Batch size for embedding and upsert
            show_progress: Show progress bar
            use_parallel: Use parallel embedding if provider supports it
        """
        from qdrant_client.models import PointStruct

        if not chunks:
            return

        client = self._get_client()

        has_parallel = hasattr(self._embedding_provider, "embed_texts_parallel")

        if use_parallel and has_parallel:
            self._add_chunks_parallel(chunks, batch_size, show_progress, client)
        else:
            self._add_chunks_sequential(chunks, batch_size, show_progress, client)

    def _add_chunks_parallel(
        self,
        chunks: list[NormalizedChunk],
        batch_size: int,
        show_progress: bool,
        client,
    ) -> None:
        """Add chunks using parallel embedding (faster for OpenAI)."""
        from qdrant_client.models import PointStruct

        if show_progress:
            from rich.console import Console
            console = Console()
            console.print("[dim]Using parallel embedding...[/dim]")

        texts = [f"{c.title}\n\n{c.content}" for c in chunks]
        embeddings = self._embedding_provider.embed_texts_parallel(texts)

        points = [
            PointStruct(
                id=self._chunk_id_to_uuid(chunk.id),
                vector=embedding,
                payload={
                    "chunk_id": chunk.id,
                    "source_id": chunk.source_id,
                    "path": chunk.path,
                    "title": chunk.title,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            client.upsert(collection_name=self.COLLECTION_NAME, points=batch)

    def _add_chunks_sequential(
        self,
        chunks: list[NormalizedChunk],
        batch_size: int,
        show_progress: bool,
        client,
    ) -> None:
        """Add chunks using sequential embedding (fallback)."""
        from qdrant_client.models import PointStruct

        total_batches = (len(chunks) + batch_size - 1) // batch_size

        progress = None
        task = None
        if show_progress:
            from rich.progress import Progress

            progress = Progress()
            task = progress.add_task("Embedding chunks...", total=total_batches)
            progress.start()

        try:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                texts = [f"{c.title}\n\n{c.content}" for c in batch]
                embeddings = self._embedding_provider.embed_texts(texts)

                points = [
                    PointStruct(
                        id=self._chunk_id_to_uuid(chunk.id),
                        vector=embedding,
                        payload={
                            "chunk_id": chunk.id,
                            "source_id": chunk.source_id,
                            "path": chunk.path,
                            "title": chunk.title,
                        },
                    )
                    for chunk, embedding in zip(batch, embeddings)
                ]

                client.upsert(collection_name=self.COLLECTION_NAME, points=points)

                if progress:
                    progress.advance(task)

        finally:
            if progress:
                progress.stop()

    def search(
        self,
        query: str,
        source_id: str | None = None,
        top_k: int = 20,
    ) -> list[VectorSearchResult]:
        """Search for similar chunks.

        Args:
            query: Search query
            source_id: Optional source filter
            top_k: Maximum results

        Returns:
            List of VectorSearchResult sorted by similarity (descending)
        """
        # Embed query
        query_vector = self._embedding_provider.embed_query(query)

        return self.search_by_vector(query_vector, source_id=source_id, top_k=top_k)

    def search_by_vector(
        self,
        vector: list[float],
        source_id: str | None = None,
        top_k: int = 20,
    ) -> list[VectorSearchResult]:
        """Search using a pre-computed vector.

        Args:
            vector: Query embedding vector
            source_id: Optional source filter
            top_k: Maximum results

        Returns:
            List of VectorSearchResult
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = self._get_client()

        query_filter = None
        if source_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=source_id),
                    )
                ]
            )

        # Use query_points for qdrant-client 1.7+
        results = client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
        )

        return [
            VectorSearchResult(
                chunk_id=hit.payload["chunk_id"],
                score=hit.score,
            )
            for hit in results.points
        ]

    def get_stats(self) -> dict:
        """Get collection statistics.

        Returns:
            Dict with collection stats
        """
        client = self._get_client()

        try:
            info = client.get_collection(self.COLLECTION_NAME)
            # qdrant-client 1.7+ uses indexed_vectors_count instead of vectors_count
            vectors_count = getattr(info, "indexed_vectors_count", 0) or 0
            points_count = getattr(info, "points_count", 0) or 0
            return {
                "vectors_count": vectors_count,
                "points_count": points_count,
                "dimension": self._embedding_provider.dimension,
                "model": self._embedding_provider.model_name,
                "storage_path": str(self._storage_path),
            }
        except Exception:
            return {
                "vectors_count": 0,
                "points_count": 0,
                "dimension": self._embedding_provider.dimension,
                "model": self._embedding_provider.model_name,
                "storage_path": str(self._storage_path),
            }

    def clear(self) -> None:
        """Clear all vectors from the collection."""
        client = self._get_client()

        try:
            client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass

        self.create_collection()

    def exists(self) -> bool:
        """Check if collection exists and has data."""
        client = self._get_client()

        try:
            collections = client.get_collections().collections
            for c in collections:
                if c.name == self.COLLECTION_NAME:
                    info = client.get_collection(self.COLLECTION_NAME)
                    return info.points_count > 0
            return False
        except Exception:
            return False

    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None

    @staticmethod
    def _chunk_id_to_uuid(chunk_id: str) -> str:
        """Convert chunk ID to UUID string for Qdrant.

        Qdrant requires UUID or integer IDs. We use UUID5 to deterministically
        convert our string IDs.
        """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
