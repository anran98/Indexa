# INDEXA - PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-21
**Version:** 1.2.0
**Branch:** main

## OVERVIEW

MCP server that indexes private documentation and exposes it via Model Context Protocol for AI assistants. Combines BM25 lexical search with vector embeddings using RRF fusion, plus graph-based search for UI component libraries.

**v1.2.0 additions:** Parallel processing - concurrent BM25+Vector search, async OpenAI embeddings with aiohttp.

**v1.1.0 additions:** PythonAdapter for indexing Python source code with docstring and type hint extraction.

**v1.0.0 additions:** Source code indexing with CompodocAdapter (Angular) and SourceAdapter (TypeScript/HTML/SCSS).

## STRUCTURE

```
Indexa/
├── src/indexa/           # Main package
│   ├── adapters/            # Document parsers (markdown, component, compodoc, source)
│   ├── config/              # Settings + source loading from YAML
│   ├── graph/               # Component relationship graph (NetworkX) + GraphBuilder
│   ├── indexing/            # Chunk storage + indexer (multi-adapter support)
│   ├── retrieval/           # Hybrid search (BM25 + Vector + RRF)
│   ├── tools/               # MCP tool definitions (search, graph, source)
│   ├── cli.py               # Click CLI commands
│   └── server.py            # FastMCP server entry
├── config/sources.yaml      # Documentation source definitions
├── data/                    # Runtime index storage (gitignored)
└── tests/                   # pytest suite (97 tests)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new CLI command | `src/indexa/cli.py` | Use `@main.command()` decorator |
| Add MCP tool | `src/indexa/tools/` | Use `@mcp.tool()`, import in `__init__.py` |
| Change search behavior | `src/indexa/retrieval/hybrid_search.py` | RRF weights, boosting logic |
| Add query synonyms | `src/indexa/retrieval/query_expander.py` | Update `SYNONYMS` dict |
| Parse new doc format | `src/indexa/adapters/` | Extend `BaseAdapter` |
| Add component relationship | `src/indexa/graph/component_graph.py` | Use `add_*` methods |
| Configure doc sources | `config/sources.yaml` | YAML with globs + adapters |

## CODE MAP

### Entry Points
| Symbol | Location | Role |
|--------|----------|------|
| `main()` | `cli.py:21` | Click CLI group |
| `run()` | `server.py:89` | FastMCP server launch |
| `__main__` | `__main__.py` | `python -m indexa` |

### Core Classes
| Class | Location | Role |
|-------|----------|------|
| `HybridSearchEngine` | `retrieval/hybrid_search.py` | Orchestrates BM25 + Vector with RRF (parallel search v1.2.0+) |
| `BM25Index` | `retrieval/bm25.py` | SQLite FTS5 lexical search |
| `VectorStore` | `retrieval/vector_store.py` | Qdrant semantic search (parallel embedding support v1.2.0+) |
| `OpenAIEmbeddings` | `retrieval/embeddings.py` | OpenAI embeddings with async parallel batching (v1.2.0+) |
| `QueryExpander` | `retrieval/query_expander.py` | Abbreviation/synonym expansion |
| `ComponentGraph` | `graph/component_graph.py` | NetworkX relationship graph |
| `GraphBuilder` | `graph/builder.py` | Builds graph from SourceChunks (v1.0.0+) |
| `NormalizedChunk` | `indexing/chunk.py` | Standard doc chunk format |
| `SourceChunk` | `indexing/source_chunk.py` | Source code chunk (v1.0.0+) |
| `CompodocAdapter` | `adapters/compodoc.py` | Angular Compodoc parser (v1.0.0+) |
| `SourceAdapter` | `adapters/source.py` | TypeScript/HTML/SCSS parser (v1.0.0+) |
| `PythonAdapter` | `adapters/python.py` | Python source with docstrings (v1.1.0+) |

### Data Types
| Type | Location | Values |
|------|----------|--------|
| `ChunkKind` | `indexing/chunk.py` | guide, api, reference, example, module, readme, source, template, stylesheet, api_doc |
| `ChunkType` | `graph/types.py` | overview, props, example, variant, accessibility, styling, migration, best_practices, INPUTS, OUTPUTS, METHODS, SOURCE, TEMPLATE, STYLESHEET |
| `NodeType` | `graph/types.py` | COMPONENT, DIRECTIVE, SERVICE, CATEGORY, CHUNK, SOURCE_FILE |
| `RelationType` | `graph/types.py` | belongs_to, has_variant, extends, uses, related_to, documents, has_prop, HAS_TEMPLATE, HAS_STYLESHEET, HAS_SOURCE, IMPORTS, REFERENCES |

## CONVENTIONS

### Code Style
- **Line length**: 100 chars (ruff)
- **Python**: >=3.11, modern union syntax (`str | None`)
- **Imports**: Absolute from package root
- **Type hints**: Full annotations, `from __future__ import annotations`

### Patterns
- **Lazy imports**: Tools import at registration time to avoid circular deps
- **Global instances**: `search_index`, `graph_index` in server.py loaded at startup
- **Dataclasses**: Used for all data models (chunks, results, settings)
- **Context managers**: `TYPE_CHECKING` for forward references

### Testing
- **Class-based**: `class Test{ClassName}` in `tests/test_{module}.py`
- **Fixtures**: Shared in `conftest.py`, composite fixtures common
- **Async mode**: `auto` (configured but not currently used)

## ANTI-PATTERNS (THIS PROJECT)

| Forbidden | Reason |
|-----------|--------|
| `as any` / `@ts-ignore` | N/A (Python project) |
| Empty `except:` blocks | Swallows errors silently |
| Modifying `SYNONYMS` dict at runtime | QueryExpander expects static mappings |
| Calling `mcp.run()` outside `server.py` | Server singleton pattern |
| Direct Qdrant `search()` | Use `query_points()` (v1.7+ API) |

## UNIQUE STYLES

### Search Result Boosting
```python
# Entrypoints boosted 1.3x
if chunk.is_entrypoint:
    final_score *= 1.3

# Title matches boosted 1.2x per term
title_overlap = len(title_terms & query_terms)
final_score *= 1 + 0.2 * title_overlap
```

### RRF Fusion Formula
```python
# k=60, weights: BM25=0.4, Vector=0.6
rrf_score = 0.4 * (1/(60 + bm25_rank)) + 0.6 * (1/(60 + vector_rank))
```

### Embedding Provider Auto-Detection
```python
# CLI --provider auto (default)
if os.environ.get("OPENAI_API_KEY"):
    provider = "openai"  # text-embedding-3-small
else:
    provider = "local"   # all-MiniLM-L6-v2
```

## COMMANDS

```bash
# Development
pip install -e ".[dev]"
pytest                           # Run 97 tests
ruff check src/                  # Lint (100 char lines, E/F/I/UP rules)

# Indexing
indexa index                  # Auto-detect embedding provider
indexa index --provider local # Force local embeddings
indexa index --provider openai --model text-embedding-3-large

# Search
indexa search "query"         # Hybrid search with expansion
indexa search "btn" --no-expand  # Exact terms only
indexa status                 # Show index stats

# MCP Server
python -m indexa.server       # Run server (Cursor starts this)
indexa install-cursor         # Write .cursor/mcp.json
```

## NOTES

### Gotchas
- **Qdrant `indexed_vectors_count`**: Can be 0 during indexing; use `points_count` for stats
- **Circular imports**: Tools import `mcp` from server, server imports tools lazily
- **Global index load**: `search_index` loads at import time, not at `run()`
- **Component chunks**: Use `ComponentChunk` (has relationships), not `NormalizedChunk`

### File Artifacts (gitignored)
- `data/index.json` - Chunk storage
- `data/index.graph.json` - Component graph
- `data/bm25.db` - SQLite FTS5 index
- `data/qdrant/` - Vector store

### Dependencies
- `fastmcp>=2.0.0` - MCP server framework
- `qdrant-client>=1.7.0` - Vector database
- `sentence-transformers>=2.2.0` - Local embeddings
- `networkx>=3.0` - Graph data structure
- `aiohttp>=3.9.0` - Async HTTP for parallel OpenAI embeddings (v1.2.0+)
