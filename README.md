# Indexa

**MCP server for private documentation search** - Like Context7, but for your own docs.

Indexa indexes your internal documentation (markdown, code docs, READMEs) and exposes them through the Model Context Protocol (MCP), making your docs searchable from AI assistants like Cursor.

**v1.2.0 New:** Parallel processing for faster search and indexing. BM25 and Vector searches now run concurrently. OpenAI embeddings use async batching with aiohttp for up to 3-4x faster indexing.

**v1.1.0:** PythonAdapter for indexing Python source code - extracts docstrings, function signatures, type hints, and decorators using AST parsing.

**v1.0.0:** Source code indexing with CompodocAdapter for Angular libraries and SourceAdapter for TypeScript/HTML/SCSS files. Search source code, get component implementation details, and find usage patterns across your codebase.

**v0.3.0:** Hybrid search with BM25 + Vector embeddings + RRF fusion. Handles abbreviations like "btn" → "button" and provides semantic search capabilities.

**v0.2.0:** Graph-based search for UI component libraries with relationship traversal, category filtering, and chunk type classification.

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** - Installation and setup guide
- **[Configuration Reference](docs/CONFIGURATION.md)** - Full sources.yaml options
- **[Architecture](docs/ARCHITECTURE.md)** - How Indexa works internally
- **[Examples](examples/)** - Sample configurations for different project types

## Quick Start

```bash
# 1. Install
cd /path/to/indexa
pip install -e .

# 2. Build the index (auto-detects embedding provider)
indexa index   # Uses OpenAI if OPENAI_API_KEY is set, else local embeddings

# 3. Install to Cursor (optional - already configured)
indexa install-cursor

# 4. Restart Cursor
# Indexa is now available as an MCP server!
```

## CLI Commands

```bash
# Build/rebuild the search index (auto-detects provider)
indexa index                          # Auto: OpenAI if key available, else local
indexa index --provider local         # Force local embeddings (offline)
indexa index --provider openai        # Force OpenAI (requires OPENAI_API_KEY)
indexa index --provider openai --model text-embedding-3-large

# List configured sources
indexa sources

# Check index status
indexa status

# Test search from command line
indexa search "how to onboard tenant"
indexa search "how to create a btn"   # Query expansion: btn → button
indexa search "vector store" --top-k 10
indexa search "exact match" --no-expand  # Disable query expansion

# Install to Cursor
indexa install-cursor --workspace .
```

## Configuration

Documentation sources are configured in `config/sources.yaml`:

```yaml
sources:
  # Simple markdown documentation
  - id: agentic_search
    name: "AgenticSearch"
    description: "Multi-dialect query generation framework"
    root: "/path/to/your-project"
    
    include_globs:
      - "docs/**/*.md"
      - "**/README.md"
      - "**/AGENTS.md"
    
    exclude_globs:
      - "**/node_modules/**"
      - "**/.git/**"
    
    entrypoints:
      - "README.md"
      - "docs/GETTING_STARTED.md"
    
    tags:
      - python
      - framework

  # Angular library with source code (v1.0.0+)
  - id: tds_enterprise
    name: "TDS Enterprise"
    description: "Angular component library with Compodoc"
    root: "/path/to/ng-tds-enterprise"
    
    # Multi-adapter configuration
    adapters:
      - type: compodoc
        config:
          json_path: "documentation.json"
          include_directives: true
          include_services: true
      - type: source
        config:
          languages: [typescript, html, scss]
          chunk_strategy: file
          link_related_files: true
      - type: markdown
    
    include_globs:
      - "documentation.json"
      - "projects/tds-lib/src/**/*.ts"
      - "projects/tds-lib/src/**/*.html"
      - "projects/tds-lib/src/**/*.scss"
      - "docs/**/*.md"
    
    exclude_globs:
      - "**/*.spec.ts"
      - "**/node_modules/**"
    
    tags:
      - angular
      - components
```

## MCP Tools

Once running, Indexa exposes these tools to AI assistants:

### Basic Search

| Tool | Description |
|------|-------------|
| `search(query, source?, top_k?)` | Find relevant documentation sections |
| `get_context(source, path, anchor?)` | Retrieve full content of a section |
| `list_sources()` | Show all configured sources |
| `reload(source?)` | Re-index documentation |

### Component Search (v0.2.0+)

For UI component libraries, additional tools are available:

| Tool | Description |
|------|-------------|
| `search_components(query, component?, category?, chunk_type?)` | Search with filters |
| `get_component_info(component)` | Get component relationships and docs |
| `list_component_categories()` | List all categories |
| `explore_category(category)` | Explore a category |
| `find_related_components(component, depth?)` | Find related components via graph |

**Chunk types:** `overview`, `props`, `example`, `variant`, `accessibility`, `styling`, `migration`, `best_practices`

### Source Code Search (v1.0.0+)

For source code indexing (Angular, TypeScript, etc.):

| Tool | Description |
|------|-------------|
| `search_source(query, language?, file_type?, component?)` | Search indexed source code |
| `get_component_source(component, include_template?, include_styles?)` | Get all source files for a component |
| `find_component_usage(component)` | Find where a component is used in templates |

**Languages:** `typescript`, `html`, `scss`, `css`, `javascript`
**File types:** `source`, `template`, `stylesheet`, `spec`

## Usage in Cursor

Once installed, just chat naturally:

> "How do I configure authentication in my app?"

Claude will:
1. Call `search("configure authentication")`
2. Get relevant results from your docs
3. Call `get_context()` to retrieve full sections
4. Provide an accurate answer based on YOUR documentation

## Architecture (v1.0.0)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                             Indexa v1.0.0                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────┐    ┌───────────┐ │
│  │   Sources   │───▶│           Adapters               │───▶│  Chunks   │ │
│  │  (YAML)     │    │  ┌──────────┐ ┌───────────────┐  │    │  (JSON)   │ │
│  └─────────────┘    │  │ Markdown │ │   Compodoc    │  │    └───────────┘ │
│                     │  └──────────┘ │  (Angular)    │  │          │       │
│                     │  ┌──────────┐ └───────────────┘  │          │       │
│                     │  │Component │ ┌───────────────┐  │          │       │
│                     │  └──────────┘ │    Source     │  │          │       │
│                     │               │ (TS/HTML/SCSS)│  │          │       │
│                     │               └───────────────┘  │          │       │
│                     └──────────────────────────────────┘          │       │
│                                                                   │       │
│                           ┌───────────────────────────────────────┘       │
│                           │                                               │
│                           ▼                                               │
│         ┌─────────────────┼─────────────────┐      ┌──────────────┐      │
│         ▼                 ▼                 ▼      │              │      │
│  ┌───────────┐     ┌───────────┐     ┌───────────┐│ GraphBuilder │      │
│  │   BM25    │     │  Vector   │     │   Graph   │◀─────────────┘      │
│  │ (SQLite)  │     │ (Qdrant)  │     │(NetworkX) │                      │
│  └───────────┘     └───────────┘     └───────────┘                      │
│         │                 │                 │                            │
│         └────────┬────────┴────────┬────────┘                            │
│                  ▼                 ▼                                     │
│          ┌───────────────┐  ┌─────────────┐                              │
│          │  RRF Fusion   │  │   Graph     │                              │
│          │ Query Expand  │  │   Search    │                              │
│          └───────────────┘  └─────────────┘                              │
│                  │                 │                                     │
│                  └────────┬────────┘                                     │
│                           ▼                                              │
│                  ┌───────────────┐                                       │
│                  │  MCP Tools    │                                       │
│                  │  (FastMCP)    │                                       │
│                  └───────────────┘                                       │
│                           │                                              │
└───────────────────────────│──────────────────────────────────────────────┘
                            ▼
                     ┌─────────────┐
                     │   Cursor    │
                     │  (Client)   │
                     └─────────────┘
```

### Search Pipeline

1. **Query Expansion**: Abbreviations (btn→button) and synonyms (modal→dialog)
2. **BM25 Search**: SQLite FTS5 with porter stemming for lexical matching
3. **Vector Search**: Qdrant with OpenAI/local embeddings for semantic similarity
4. **RRF Fusion**: Reciprocal Rank Fusion combines results from both retrievers

## Project Structure

```
Indexa/
├── config/
│   └── sources.yaml          # Documentation source definitions
├── data/
│   ├── index.json            # Generated search index
│   └── index.graph.json      # Component graph (v0.2.0+)
├── src/indexa/
│   ├── adapters/             # Document parsers
│   │   ├── markdown.py       # Markdown/MDX files
│   │   ├── component.py      # Component docs with frontmatter
│   │   ├── compodoc.py       # Angular Compodoc JSON (v1.0.0+)
│   │   ├── python.py         # Python source files (v1.1.0+)
│   │   └── source.py         # Source code files (v1.0.0+)
│   ├── config/               # Settings and source loading
│   ├── graph/                # Graph search module (v0.2.0+)
│   │   ├── component_graph.py
│   │   ├── builder.py        # GraphBuilder (v1.0.0+)
│   │   └── types.py          # NodeType, RelationType, ChunkType
│   ├── indexing/             # Chunk storage and indexer
│   │   ├── chunk.py          # NormalizedChunk, ChunkKind
│   │   ├── source_chunk.py   # SourceChunk (v1.0.0+)
│   │   └── indexer.py        # Multi-adapter indexer
│   ├── retrieval/            # Search implementation
│   ├── tools/                # MCP tool definitions
│   │   ├── search.py         # search() tool
│   │   ├── graph.py          # Component tools
│   │   └── source.py         # Source code tools (v1.0.0+)
│   ├── cli.py                # CLI commands
│   └── server.py             # FastMCP server
├── tests/                    # Test suite
└── .cursor/
    └── mcp.json              # Cursor MCP configuration
```

## Adding New Sources

1. Edit `config/sources.yaml` to add your source
2. Run `indexa index` to rebuild
3. Your docs are now searchable!

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## Future Plans

- [x] Component adapter with graph search (v0.2.0)
- [x] Semantic search with embeddings (v0.3.0)
- [x] Hybrid BM25 + Vector search (v0.3.0)
- [x] Query expansion for abbreviations (v0.3.0)
- [x] Angular component support with Compodoc (v1.0.0)
- [x] Source code indexing (TypeScript, HTML, SCSS) (v1.0.0)
- [x] Multi-adapter configuration per source (v1.0.0)
- [x] Python adapter (docstrings + signatures) (v1.1.0)
- [ ] OpenAPI adapter
- [ ] PostgreSQL storage (for scale)
- [ ] File watcher (auto-reindex)
- [ ] Vue component support

## License

MIT
