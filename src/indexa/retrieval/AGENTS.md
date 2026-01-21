# RETRIEVAL MODULE

Hybrid search engine combining BM25 lexical + vector semantic search with RRF fusion.

## STRUCTURE

```
retrieval/
├── hybrid_search.py   # Main orchestrator (HybridSearchEngine)
├── bm25.py            # SQLite FTS5 lexical search
├── vector_store.py    # Qdrant semantic search
├── query_expander.py  # Abbreviation/synonym expansion
├── embeddings.py      # OpenAI + local embedding providers
└── __init__.py        # Public exports
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Change RRF weights | `hybrid_search.py:84-86` | `DEFAULT_BM25_WEIGHT`, `DEFAULT_VECTOR_WEIGHT` |
| Add abbreviations | `query_expander.py` | Update `SYNONYMS` dict |
| Change embedding model | `embeddings.py` | `DEFAULT_MODEL` constants |
| Modify BM25 stopwords | `bm25.py:38-51` | `STOPWORDS` frozenset |
| Add vector filters | `vector_store.py:201-210` | Qdrant `Filter` construction |

## DATA FLOW

```
Query → QueryExpander.get_all_terms()
              │
    ┌─────────┴─────────┐
    ▼                   ▼
BM25Index           VectorStore
(SQLite FTS5)       (Qdrant)
    │                   │
    └─────────┬─────────┘
              ▼
         RRF Fusion (k=60)
              │
              ▼
         Score Boosting
         (entrypoint 1.3x, title match 1.2x)
              │
              ▼
         SearchResult[]
```

## KEY FORMULAS

```python
# RRF score combination
rrf_score = bm25_weight * (1/(k + bm25_rank)) + vector_weight * (1/(k + vector_rank))

# Boosting
if is_entrypoint: score *= 1.3
score *= 1 + 0.2 * title_term_overlap
```

## ANTI-PATTERNS

| Forbidden | Use Instead |
|-----------|-------------|
| `VectorStore.search()` deprecated params | `query_points()` for qdrant-client 1.7+ |
| Modify `SYNONYMS` at runtime | Static dict only |
| Call `embed_texts()` for single query | Use `embed_query()` |

## GOTCHAS

- **BM25 returns negative scores**: Converted to positive in `search()` (line 205)
- **Qdrant `indexed_vectors_count`**: Can be 0 during indexing; check `points_count`
- **Porter stemming**: "buttons" → "button", "configuration" → "configur"
