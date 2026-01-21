# GRAPH MODULE

Component relationship graph for UI library documentation. Enables relationship-aware search beyond text matching.

## STRUCTURE

```
graph/
├── component_graph.py  # NetworkX DiGraph wrapper
├── hybrid_search.py    # TF-IDF + graph filtering (NOT same as retrieval/)
├── types.py            # NodeType, RelationType, ChunkType enums
└── __init__.py
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add relationship type | `types.py` | Add to `RelationType` enum |
| Add graph traversal | `component_graph.py` | BFS in `find_related_components()` |
| Change TF-IDF scoring | `hybrid_search.py` | `SimpleTFIDF` class |
| Add chunk type | `types.py` | Add to `ChunkType` enum |

## NODE ID PATTERNS

```python
f"component:{name}"   # component:Button
f"category:{name}"    # category:Forms
f"chunk:{chunk_id}"   # chunk:abc123
```

## RELATIONSHIP TYPES

| Type | Direction | Example |
|------|-----------|---------|
| `BELONGS_TO` | Component → Category | Button → Forms |
| `HAS_VARIANT` | Base → Variant | Button → IconButton |
| `EXTENDS` | Variant → Base | IconButton → Button |
| `USES` | Consumer → Dependency | Modal → Button |
| `RELATED_TO` | Bidirectional | Tooltip ↔ Popover |
| `DOCUMENTS` | Chunk → Component | chunk:abc → Button |

## GRAPH vs RETRIEVAL SEARCH

| Aspect | `graph/hybrid_search.py` | `retrieval/hybrid_search.py` |
|--------|--------------------------|------------------------------|
| Engine | SimpleTFIDF (in-memory) | BM25 + Vector (SQLite + Qdrant) |
| Purpose | UI component docs | General documentation |
| Filters | component, category, chunk_type | source_id only |
| Relationships | BFS traversal | None |

## ANTI-PATTERNS

- **Don't use `retrieval/` for component search**: Use `graph/hybrid_search.py`
- **Don't add nodes without prefixed IDs**: Always use `component:`, `category:`, `chunk:`
