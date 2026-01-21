"""Hybrid search engine combining BM25 and vector search with RRF fusion."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from indexa.retrieval.bm25 import BM25Index, BM25Result
from indexa.retrieval.embeddings import EmbeddingProvider, get_embedding_provider
from indexa.retrieval.query_expander import QueryExpander
from indexa.retrieval.vector_store import VectorSearchResult, VectorStore

if TYPE_CHECKING:
    from indexa.indexing.chunk import NormalizedChunk


@dataclass
class SearchResult:
    """A single search result from hybrid search."""

    chunk: NormalizedChunk
    score: float  # Combined RRF score
    snippet: str
    bm25_rank: int | None = None  # Rank in BM25 results (1-indexed)
    vector_rank: int | None = None  # Rank in vector results (1-indexed)

    def to_dict(self) -> dict:
        return {
            "source_id": self.chunk.source_id,
            "path": self.chunk.path,
            "anchor": self.chunk.anchor,
            "title": self.chunk.title,
            "kind": self.chunk.kind,
            "snippet": self.snippet,
            "score": round(self.score, 4),
            "uri": self.chunk.to_uri(),
            "is_entrypoint": self.chunk.is_entrypoint,
            "bm25_rank": self.bm25_rank,
            "vector_rank": self.vector_rank,
        }


class HybridSearchEngine:
    """Hybrid search combining BM25 (lexical) and vector (semantic) search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from both retrievers.
    RRF is a simple but effective fusion method that:
    - Doesn't require score normalization
    - Works well with different ranking scales
    - Is robust to outliers

    RRF formula: score(d) = Σ 1/(k + rank_i(d)) for each retriever i
    where k is a constant (default: 60)

    Architecture:
    ┌──────────────────────────────────────────────────────────────┐
    │                    HybridSearchEngine                         │
    ├──────────────────────────────────────────────────────────────┤
    │  Query → QueryExpander → [expanded terms]                    │
    │                              │                                │
    │            ┌─────────────────┴─────────────────┐             │
    │            ▼                                   ▼             │
    │     ┌──────────────┐                  ┌──────────────┐       │
    │     │   BM25Index  │                  │ VectorStore  │       │
    │     │  (SQLite)    │                  │  (Qdrant)    │       │
    │     └──────────────┘                  └──────────────┘       │
    │            │                                   │             │
    │            └─────────────────┬─────────────────┘             │
    │                              ▼                                │
    │                    ┌──────────────┐                          │
    │                    │  RRF Fusion  │                          │
    │                    └──────────────┘                          │
    │                              │                                │
    │                              ▼                                │
    │                    [Ranked Results]                          │
    └──────────────────────────────────────────────────────────────┘
    """

    # RRF constant - higher values give more weight to lower ranks
    RRF_K = 60

    # Default weights for combining retrievers
    DEFAULT_BM25_WEIGHT = 0.4
    DEFAULT_VECTOR_WEIGHT = 0.6

    def __init__(
        self,
        data_dir: Path | str,
        embedding_provider: EmbeddingProvider | None = None,
        provider_name: str = "openai",
        model: str | None = None,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    ) -> None:
        """Initialize hybrid search engine.

        Args:
            data_dir: Directory for index storage
            embedding_provider: Pre-configured embedding provider
            provider_name: Provider name if embedding_provider not given
            model: Model name override
            bm25_weight: Weight for BM25 scores (default: 0.4)
            vector_weight: Weight for vector scores (default: 0.6)
        """
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Weights for score combination
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight

        # Initialize components
        self._expander = QueryExpander()

        # BM25 index
        self._bm25 = BM25Index(self._data_dir / "bm25.db")

        # Embedding provider (lazy init if not provided)
        self._embedding_provider = embedding_provider
        self._provider_name = provider_name
        self._model = model

        # Vector store (lazy init)
        self._vector_store: VectorStore | None = None

        # Chunk lookup (populated during indexing)
        self._chunks: dict[str, NormalizedChunk] = {}

    def _get_embedding_provider(self) -> EmbeddingProvider:
        """Get or create embedding provider."""
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider(
                provider=self._provider_name,
                model=self._model,
            )
        return self._embedding_provider

    def _get_vector_store(self) -> VectorStore:
        """Get or create vector store."""
        if self._vector_store is None:
            self._vector_store = VectorStore(
                storage_path=self._data_dir / "qdrant",
                embedding_provider=self._get_embedding_provider(),
            )
        return self._vector_store

    def index(
        self,
        chunks: list[NormalizedChunk],
        show_progress: bool = False,
    ) -> None:
        """Index chunks for hybrid search.

        Args:
            chunks: Chunks to index
            show_progress: Show progress bar for embedding
        """
        if not chunks:
            return

        # Store chunk lookup
        self._chunks = {c.id: c for c in chunks}

        # Create BM25 index
        self._bm25.create_index()
        self._bm25.add_chunks(chunks)

        # Create vector index
        vector_store = self._get_vector_store()
        vector_store.create_collection(recreate=True)
        vector_store.add_chunks(chunks, show_progress=show_progress)

    def search(
        self,
        query: str,
        source_id: str | None = None,
        top_k: int = 8,
        expand_query: bool = True,
    ) -> list[SearchResult]:
        """Search using hybrid retrieval with RRF fusion.

        Args:
            query: Search query
            source_id: Optional source filter
            top_k: Maximum results to return
            expand_query: Whether to expand query with synonyms

        Returns:
            List of SearchResult sorted by combined score
        """
        if not query.strip():
            return []

        # Expand query for better recall
        if expand_query:
            expanded_terms = self._expander.get_all_terms(query)
        else:
            expanded_terms = self._tokenize(query)

        # Get more results than needed for fusion
        fetch_k = top_k * 3

        # Parallel search: BM25 and Vector are independent
        # This reduces latency by running both searches concurrently
        bm25_results: list[BM25Result] = []
        vector_results: list[VectorSearchResult] = []

        vector_store = self._get_vector_store()

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both searches in parallel
            bm25_future = executor.submit(
                self._bm25.search_expanded,
                expanded_terms,
                source_id,
                fetch_k,
            )
            vector_future = executor.submit(
                vector_store.search,
                query,
                source_id,
                fetch_k,
            )

            # Collect results as they complete
            for future in as_completed([bm25_future, vector_future]):
                if future is bm25_future:
                    bm25_results = future.result()
                else:
                    vector_results = future.result()

        # Build rank maps
        bm25_ranks: dict[str, int] = {
            r.chunk_id: i + 1 for i, r in enumerate(bm25_results)
        }
        vector_ranks: dict[str, int] = {
            r.chunk_id: i + 1 for i, r in enumerate(vector_results)
        }

        # Get all unique chunk IDs
        all_chunk_ids = set(bm25_ranks.keys()) | set(vector_ranks.keys())

        # Calculate RRF scores
        scored_chunks: list[tuple[str, float, int | None, int | None]] = []

        for chunk_id in all_chunk_ids:
            rrf_score = 0.0

            bm25_rank = bm25_ranks.get(chunk_id)
            vector_rank = vector_ranks.get(chunk_id)

            if bm25_rank is not None:
                rrf_score += self._bm25_weight * (1.0 / (self.RRF_K + bm25_rank))

            if vector_rank is not None:
                rrf_score += self._vector_weight * (1.0 / (self.RRF_K + vector_rank))

            scored_chunks.append((chunk_id, rrf_score, bm25_rank, vector_rank))

        # Sort by RRF score descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results: list[SearchResult] = []

        for chunk_id, score, bm25_rank, vector_rank in scored_chunks[:top_k]:
            chunk = self._chunks.get(chunk_id)
            if chunk is None:
                continue

            # Generate snippet
            snippet = self._generate_snippet(chunk.content, expanded_terms)

            # Boost entrypoints
            final_score = score
            if chunk.is_entrypoint:
                final_score *= 1.3

            # Boost title matches
            title_terms = set(self._tokenize(chunk.title))
            query_terms = set(expanded_terms)
            title_overlap = len(title_terms & query_terms)
            if title_overlap > 0:
                final_score *= 1 + 0.2 * title_overlap

            results.append(SearchResult(
                chunk=chunk,
                score=final_score,
                snippet=snippet,
                bm25_rank=bm25_rank,
                vector_rank=vector_rank,
            ))

        # Re-sort after boosting
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:top_k]

    def load_chunks(self, chunks: list[NormalizedChunk]) -> None:
        """Load chunks into memory for lookup.

        Call this when loading an existing index to enable search.

        Args:
            chunks: All indexed chunks
        """
        self._chunks = {c.id: c for c in chunks}

    def exists(self) -> bool:
        """Check if index exists."""
        return self._bm25.exists() and self._get_vector_store().exists()

    def get_stats(self) -> dict:
        """Get index statistics.

        Returns:
            Dict with index stats
        """
        bm25_stats = self._bm25.get_stats()
        vector_stats = self._get_vector_store().get_stats()

        return {
            "bm25": bm25_stats,
            "vector": vector_stats,
            "chunks_in_memory": len(self._chunks),
            "weights": {
                "bm25": self._bm25_weight,
                "vector": self._vector_weight,
            },
        }

    def close(self) -> None:
        """Close all resources."""
        self._bm25.close()
        if self._vector_store:
            self._vector_store.close()

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        return re.findall(r"\w+", text.lower())

    def _generate_snippet(
        self,
        content: str,
        query_terms: list[str],
        max_len: int = 200,
    ) -> str:
        """Generate a relevant snippet containing query terms.

        Args:
            content: Full content text
            query_terms: Terms to highlight
            max_len: Maximum snippet length

        Returns:
            Snippet string
        """
        content_lower = content.lower()

        # Find first occurrence of any query term
        best_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        # Extract snippet around the match
        if best_pos == len(content):
            # No match found, use beginning
            start = 0
        else:
            start = max(0, best_pos - 50)

        end = min(len(content), start + max_len)

        snippet = content[start:end].strip()

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        # Clean up whitespace
        snippet = re.sub(r"\s+", " ", snippet)

        return snippet


# Backwards compatibility - alias for the old SearchIndex name
SearchIndex = HybridSearchEngine
