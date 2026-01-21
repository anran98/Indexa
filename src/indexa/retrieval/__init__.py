"""Retrieval module for searching documentation.

v0.3.0: Hybrid search with BM25 + Vector + RRF fusion.
"""

from indexa.retrieval.bm25 import BM25Index, BM25Result
from indexa.retrieval.embeddings import (
    EmbeddingProvider,
    LocalEmbeddings,
    OpenAIEmbeddings,
    get_embedding_provider,
)
from indexa.retrieval.hybrid_search import HybridSearchEngine, SearchResult
from indexa.retrieval.query_expander import QueryExpander
from indexa.retrieval.vector_store import VectorSearchResult, VectorStore

# Backwards compatibility alias
SearchIndex = HybridSearchEngine

__all__ = [
    # Main search engine
    "HybridSearchEngine",
    "SearchResult",
    # Backwards compat
    "SearchIndex",
    # BM25
    "BM25Index",
    "BM25Result",
    # Vector
    "VectorStore",
    "VectorSearchResult",
    # Embeddings
    "EmbeddingProvider",
    "OpenAIEmbeddings",
    "LocalEmbeddings",
    "get_embedding_provider",
    # Query expansion
    "QueryExpander",
]
