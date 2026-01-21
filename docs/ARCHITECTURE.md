# Indexa Architecture

This document describes the internal architecture of Indexa, an MCP server for documentation search.

## Overview

Indexa follows a pipeline architecture:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              INDEXING PHASE                                     │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────┐            │
│  │   Sources    │───>│   Indexer    │───>│       Adapters         │            │
│  │  (YAML)      │    │ (Multi-Adapt)│    │  ┌────────┐ ┌────────┐ │            │
│  └──────────────┘    └──────────────┘    │  │Markdown│ │Compodoc│ │            │
│                                          │  └────────┘ └────────┘ │            │
│                                          │  ┌────────┐ ┌────────┐ │            │
│                                          │  │Compont │ │ Source │ │            │
│                                          │  └────────┘ └────────┘ │            │
│                                          └────────────────────────┘            │
│                                                      │                          │
│                           ┌──────────────────────────┼──────────────────┐      │
│                           ▼                          ▼                  ▼      │
│                    ┌───────────┐            ┌───────────────┐    ┌───────────┐│
│                    │   Store   │            │  GraphBuilder │───>│   Graph   ││
│                    │  (JSON)   │            │   (v1.0.0+)   │    │(NetworkX) ││
│                    └───────────┘            └───────────────┘    └───────────┘│
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│                              SERVING PHASE                                      │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐    ┌──────────────────────────────────┐    ┌───────────────┐│
│  │    Store     │───>│        Search Engines            │───>│  MCP Server   ││
│  │   (JSON)     │    │  ┌───────┐ ┌────────┐ ┌───────┐  │    │  (FastMCP)    ││
│  └──────────────┘    │  │ BM25  │ │ Vector │ │ Graph │  │    └───────────────┘│
│                      │  └───────┘ └────────┘ └───────┘  │           │         │
│                      │           │    RRF    │          │           │         │
│                      └──────────────────────────────────┘           │         │
│                                                                     ▼         │
│                                                              ┌───────────┐    │
│                                                              │  Cursor   │    │
│                                                              │ (Client)  │    │
│                                                              └───────────┘    │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Configuration (`config/`)

#### Settings (`settings.py`)
Global application settings with auto-discovery of project root.

```python
class Settings:
    project_root: Path      # Where pyproject.toml lives
    config_dir: Path        # config/
    sources_path: Path      # config/sources.yaml
    data_dir: Path          # data/
    index_path: Path        # data/index.json
```

#### Source Config (`sources.py`)
Loads and validates `sources.yaml`:

```python
@dataclass
class SourceConfig:
    id: str
    name: str
    description: str
    root: Path
    include_globs: list[str]
    exclude_globs: list[str]
    entrypoints: list[str]
    adapters: list[str]
    tags: list[str]
```

### 2. Adapters (`adapters/`)

Adapters transform source files into normalized chunks.

#### Base Adapter Protocol

```python
class BaseAdapter(ABC):
    @abstractmethod
    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        """Parse a file into searchable chunks."""
        pass
    
    @abstractmethod
    def supports_extension(self, extension: str) -> bool:
        """Check if adapter handles this file type."""
        pass
```

#### Markdown Adapter

The markdown adapter:
1. Splits content by headings (H1-H6)
2. Generates stable anchors from heading text
3. Extracts metadata (code blocks, tables)
4. Determines document kind from path patterns

```python
# Heading → Anchor transformation
"## Installation Guide" → "installation-guide"
"### 3. Vector Store" → "3-vector-store"
```

**Section splitting logic:**
- Each heading starts a new chunk
- Content until the next heading belongs to that chunk
- Chunks include the heading line itself

#### Component Adapter (v0.2.0+)

The component adapter extends markdown parsing for UI component libraries:
1. Parses YAML frontmatter for component metadata
2. Extracts relationships (extends, uses, variants, related)
3. Classifies sections (props, examples, accessibility)
4. Creates `ComponentChunk` objects with enhanced metadata

```python
# Frontmatter extraction
component: Button
category: Forms
uses: [Icon, Spinner]
→ ComponentChunk(component_name="Button", category="Forms", uses=["Icon", "Spinner"])
```

#### Compodoc Adapter (v1.0.0+)

Parses Angular Compodoc-generated `documentation.json`:
1. Extracts components, directives, services, pipes, modules
2. Parses @Input/@Output decorators with types
3. Extracts method signatures and JSDoc
4. Creates `SourceChunk` objects with API documentation

```python
# Compodoc JSON extraction
{
  "components": [{
    "name": "ButtonComponent",
    "selector": "tds-button",
    "inputsClass": [{"name": "variant", "type": "string"}],
    "outputsClass": [{"name": "clicked", "type": "EventEmitter<void>"}]
  }]
}
→ SourceChunk(kind="api_doc", chunk_type="INPUTS", component_name="ButtonComponent")
```

#### Source Adapter (v1.0.0+)

Indexes source code files:
1. TypeScript: Classes, methods, decorators, imports
2. HTML: Component usage, structural directives
3. SCSS/CSS: Style definitions, selectors

```python
# Source file indexing
button.component.ts + button.component.html + button.component.scss
→ SourceChunk(kind="source", file_type="typescript", language="typescript")
→ SourceChunk(kind="template", file_type="html", language="html")
→ SourceChunk(kind="stylesheet", file_type="scss", language="scss")
```

Links related files via GraphBuilder:
- `HAS_TEMPLATE`: Component → template
- `HAS_STYLESHEET`: Component → styles
- `IMPORTS`: File → imported file

#### Python Adapter (v1.1.0+)

Parses Python source files using the stdlib `ast` module:
1. Extracts module, class, and function docstrings
2. Parses function signatures with type hints
3. Tracks decorators and class inheritance
4. Indexes import statements

```python
# Python file indexing
class UserService:
    """Service for user management."""
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user.
        
        Args:
            username: The username
            password: The password
            
        Returns:
            True if authenticated
        """
        ...

→ SourceChunk(kind="api", language="python", file_type="class")
→ SourceChunk(kind="api", language="python", file_type="method")
```

**Chunking strategies:**
- `file`: One chunk per Python file
- `symbol`: One chunk per class/function (granular search)
- `module`: Overview + top-level symbols

**Metadata extracted:**
- Docstrings (Google, NumPy, Sphinx formats)
- Function signatures with parameters and return types
- Class bases and decorators
- Import statements

### 3. Indexing (`indexing/`)

#### NormalizedChunk (`chunk.py`)

The core data structure for indexed content:

```python
@dataclass
class NormalizedChunk:
    # Identity
    id: str              # SHA256 hash of source:path:anchor
    source_id: str       # e.g., "agentic_search"
    
    # Location
    path: str            # "docs/GETTING_STARTED.md"
    anchor: str | None   # "installation"
    
    # Content
    title: str           # "Installation"
    content: str         # Full section text
    
    # Metadata
    kind: ChunkKind      # guide | api | reference | example | module | readme
    depth: int           # Heading depth (1-6)
    is_entrypoint: bool  # Boosted in search
    
    # Features
    code_blocks: list[str]  # ["python", "bash"]
    has_table: bool
    
    # Timestamps
    indexed_at: datetime
    file_modified: datetime
```

**Chunk kinds** are inferred from file paths:
- `**/AGENTS.md` → `module`
- `**/README.md` → `readme`
- `**/api/**` or `**/*reference*` → `api`
- `**/example*/**` → `example`
- `**/*getting_started*` or `**/*quickstart*` → `guide`
- Everything else → `reference`

#### Indexer (`indexer.py`)

Orchestrates the indexing process:

```python
class Indexer:
    def index_source(self, source: SourceConfig) -> list[NormalizedChunk]:
        # 1. Find all matching files
        files = self._find_files(source)
        
        # 2. Group by adapter
        markdown_files = [f for f in files if f.suffix in ('.md', '.mdx')]
        
        # 3. Parse each file
        for file_path in markdown_files:
            chunks = adapter.parse_file(file_path)
```

#### Store (`store.py`)

JSON-based persistence:

```json
{
  "version": "1.0",
  "indexed_at": "2026-01-11T00:26:56.202774",
  "chunk_count": 1262,
  "chunks": [
    {
      "id": "abc123...",
      "source_id": "agentic_search",
      "path": "docs/GETTING_STARTED.md",
      "anchor": "installation",
      "title": "Installation",
      "content": "...",
      "kind": "guide",
      "depth": 2,
      "is_entrypoint": true,
      ...
    }
  ]
}
```

#### ComponentChunk (v0.2.0+)

Extended chunk for component documentation:

```python
@dataclass
class ComponentChunk(NormalizedChunk):
    # Component identity
    component_name: str       # "Button"
    component_category: str   # "Forms"
    chunk_type: ChunkType     # OVERVIEW | PROPS | EXAMPLE | VARIANT | ...
    
    # Relationships
    extends: str | None       # Base component
    uses: list[str]           # Used components
    variants: list[str]       # Variant components
    related_to: list[str]     # Related components
    
    # Extracted features
    props_mentioned: list[str]   # Props referenced in content
    example_variant: str | None  # If example, which variant
```

#### SourceChunk (v1.0.0+)

Extended chunk for source code:

```python
@dataclass
class SourceChunk(NormalizedChunk):
    # Source identity
    component_name: str | None    # Associated component (if any)
    file_type: str                # "typescript" | "html" | "scss"
    language: str                 # Programming language
    chunk_type: ChunkType         # SOURCE | TEMPLATE | STYLESHEET | INPUTS | OUTPUTS | METHODS
    
    # Source metadata
    class_name: str | None        # TypeScript class name
    selector: str | None          # Angular selector (e.g., "tds-button")
    
    # Relationships (for GraphBuilder)
    imports: list[str]            # Imported modules/files
    exports: list[str]            # Exported symbols
    references: list[str]         # Referenced components (in templates)
    
    # API documentation (from Compodoc)
    inputs: list[dict] | None     # @Input() properties
    outputs: list[dict] | None    # @Output() event emitters
    methods: list[dict] | None    # Public methods
```

### 4. Graph Module (`graph/`) (v0.2.0+)

The graph module provides relationship-aware search for component libraries.

#### ComponentGraph

NetworkX-based directed graph for component relationships:

```python
class ComponentGraph:
    # Node types: component, category, prop, chunk, source_file (v1.0.0+)
    # Edge types: BELONGS_TO, HAS_VARIANT, EXTENDS, USES, RELATED_TO,
    #             HAS_TEMPLATE, HAS_STYLESHEET, HAS_SOURCE, IMPORTS, REFERENCES (v1.0.0+)
    
    # Query methods
    get_variants(component)          # → ["IconButton", "LoadingButton"]
    get_uses(component)              # → ["Spinner", "Icon"]
    get_used_by(component)           # → ["Modal", "Dialog"]
    get_related(component)           # → ["Link", "Anchor"]
    get_components_in_category(cat)  # → ["Button", "Input", "Select"]
    find_related_components(c, d=2)  # → {name: distance}
    
    # Source file methods (v1.0.0+)
    get_component_files(component)   # → {"source": [...], "template": [...], "stylesheet": [...]}
    get_file_references(file_path)   # → [referenced components]
    get_imports(file_path)           # → [imported files]
```

#### GraphBuilder (v1.0.0+)

Constructs the component graph from SourceChunks:

```python
class GraphBuilder:
    def build_from_chunks(self, chunks: list[SourceChunk]) -> ComponentGraph:
        # 1. Create component nodes from API docs
        # 2. Create source file nodes
        # 3. Link components to their files (HAS_SOURCE, HAS_TEMPLATE, HAS_STYLESHEET)
        # 4. Create import edges between files
        # 5. Create reference edges from templates to components
        # 6. Inherit relationships from Compodoc (extends, uses)
```

**Graph Node Types (v1.0.0+):**

| NodeType | Description |
|----------|-------------|
| `COMPONENT` | Angular component |
| `DIRECTIVE` | Angular directive |
| `SERVICE` | Angular service |
| `CATEGORY` | Component category |
| `CHUNK` | Documentation chunk |
| `SOURCE_FILE` | Source code file |

**Graph Edge Types (v1.0.0+):**

| RelationType | From → To | Description |
|--------------|-----------|-------------|
| `BELONGS_TO` | Component → Category | Category membership |
| `EXTENDS` | Component → Component | Inheritance |
| `USES` | Component → Component | Composition |
| `HAS_VARIANT` | Component → Component | Variant relationship |
| `RELATED_TO` | Component → Component | Related components |
| `HAS_SOURCE` | Component → SourceFile | Component's .ts file |
| `HAS_TEMPLATE` | Component → SourceFile | Component's .html file |
| `HAS_STYLESHEET` | Component → SourceFile | Component's .scss file |
| `IMPORTS` | SourceFile → SourceFile | Import statement |
| `REFERENCES` | SourceFile → Component | Template usage |

#### HybridSearchIndex

Combines TF-IDF text search with graph-based filtering:

```python
class HybridSearchIndex:
    # Search with filters
    search(query, component?, category?, chunk_type?, include_related?)
    
    # Component info
    get_component_info(component)  # → relationships, doc summary
    list_categories()              # → [{name, components, count}]
    explore_category(category)     # → {components with details}
```

**Search flow:**
1. TF-IDF scores all chunks
2. Filter by component/category/chunk_type
3. Optionally expand via graph to include related components
4. Return enhanced results with component metadata

### 5. Retrieval (`retrieval/`)

#### Parallel Processing (v1.2.0+)

Indexa uses parallelization at two critical points to reduce latency:

**1. Parallel Hybrid Search**

BM25 and Vector searches are independent operations. We run them concurrently:

```
┌─────────────────────────────────────────────────────────────┐
│                    HybridSearchEngine.search()               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Query → QueryExpander → [expanded terms]                   │
│                              │                               │
│              ┌───────────────┴───────────────┐              │
│              │     ThreadPoolExecutor(2)     │              │
│              │          (parallel)           │              │
│              ▼                               ▼              │
│       ┌──────────────┐              ┌──────────────┐        │
│       │   BM25Index  │              │ VectorStore  │        │
│       │  (SQLite)    │              │  (Qdrant)    │        │
│       └──────────────┘              └──────────────┘        │
│              │                               │              │
│              └───────────────┬───────────────┘              │
│                              ▼                               │
│                       RRF Fusion                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Implementation in `hybrid_search.py`:
```python
with ThreadPoolExecutor(max_workers=2) as executor:
    bm25_future = executor.submit(self._bm25.search_expanded, terms, source_id, fetch_k)
    vector_future = executor.submit(vector_store.search, query, source_id, fetch_k)
    
    for future in as_completed([bm25_future, vector_future]):
        if future is bm25_future:
            bm25_results = future.result()
        else:
            vector_results = future.result()
```

**Impact:** ~100-200ms latency reduction per search query.

**2. Parallel Embedding Generation (OpenAI)**

When indexing with OpenAI embeddings, we process multiple batches concurrently:

```
┌─────────────────────────────────────────────────────────────┐
│              OpenAIEmbeddings.embed_texts_async()            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  texts[] ──► chunk into batches of 100                      │
│                              │                               │
│              ┌───────────────┼───────────────┐              │
│              │   asyncio + aiohttp (parallel) │              │
│              │   Semaphore(4) rate limit      │              │
│              ▼               ▼               ▼              │
│        ┌─────────┐     ┌─────────┐     ┌─────────┐         │
│        │ Batch 1 │     │ Batch 2 │     │ Batch 3 │  ...    │
│        │ POST /v1│     │ POST /v1│     │ POST /v1│         │
│        └─────────┘     └─────────┘     └─────────┘         │
│              │               │               │              │
│              └───────────────┼───────────────┘              │
│                              ▼                               │
│                    all_embeddings[]                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Implementation in `embeddings.py`:
```python
async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)  # 4
    
    async def embed_batch(session, batch, idx):
        async with semaphore:
            async with session.post(OPENAI_URL, json=payload) as response:
                return (idx, await response.json())
    
    async with aiohttp.ClientSession() as session:
        tasks = [embed_batch(session, batch, idx) for idx, batch in enumerate(batches)]
        results = await asyncio.gather(*tasks)
```

A sync wrapper `embed_texts_parallel()` is provided for non-async contexts.

**Impact:** Up to 3-4x faster embedding for large document sets.

**VectorStore Integration:**

`VectorStore.add_chunks()` auto-detects parallel support:
```python
def add_chunks(self, chunks, use_parallel=True):
    if use_parallel and hasattr(self._embedding_provider, "embed_texts_parallel"):
        self._add_chunks_parallel(chunks, ...)  # Single parallel embedding call
    else:
        self._add_chunks_sequential(chunks, ...)  # Batched sequential
```

#### Why Not Full Map-Reduce?

We evaluated full map-reduce for file parsing but found diminishing returns at current scale:

| Approach | Complexity | Benefit |
|----------|------------|---------|
| Parallel search | Low (ThreadPoolExecutor) | ~150ms/query saved |
| Async embeddings | Medium (aiohttp) | 3-4x faster indexing |
| Parallel file parsing | High (ProcessPoolExecutor + pickling) | Marginal for <1000 files |

Full map-reduce makes sense at 10,000+ documents or CI/CD pipelines requiring sub-second indexing.

#### SearchIndex (`search.py`)

TF-IDF based in-memory search:

```python
class SearchIndex:
    chunks: list[NormalizedChunk]
    doc_freq: dict[str, int]      # term → document count
    tf_cache: dict[str, dict]     # chunk_id → {term: frequency}
```

**Scoring formula:**

```
score = sum(tf[term] * log(N / df[term]) for term in query)
      * entrypoint_boost      # 1.5x if is_entrypoint
      * title_match_boost     # 1 + 0.3 * overlap_count
      * depth_boost           # 1 + 0.1 * (4 - depth)
```

**Tokenization:**
- Lowercase all text
- Split on non-word characters
- Remove stopwords (the, a, is, etc.)
- Keep tokens longer than 1 character

**Snippet generation:**
- Find first occurrence of any query term
- Extract ~200 characters around that position
- Add ellipsis if truncated

### 5. MCP Server (`server.py`)

Built with FastMCP framework:

```python
mcp = FastMCP(
    name="Indexa",
    instructions="..."
)

# Global state loaded on import
store = IndexStore(settings.index_path)
search_index = SearchIndex()
if store.exists():
    chunks = store.load()
    search_index.build(chunks)
```

### 6. Tools (`tools/`)

MCP tools exposed to clients:

#### `search(query, source?, top_k?)`
```python
@mcp.tool()
def search(query: str, source: str | None = None, top_k: int = 8) -> list[dict]:
    results = search_index.search(query, source_id=source, top_k=top_k)
    return [r.to_dict() for r in results]
```

Returns:
```json
[
  {
    "source_id": "agentic_search",
    "path": "docs/GETTING_STARTED.md",
    "anchor": "installation",
    "title": "Installation",
    "snippet": "...To install AgenticSearch...",
    "score": 2.867,
    "uri": "docs://agentic_search/section/docs/GETTING_STARTED.md#installation",
    "kind": "guide",
    "is_entrypoint": true
  }
]
```

#### `get_context(source, path, anchor?)`
```python
@mcp.tool()
def get_context(source: str, path: str, anchor: str | None = None) -> str:
    # Returns full markdown content of the section
```

#### `list_sources()`
```python
@mcp.tool()
def list_sources() -> list[dict]:
    # Returns configured sources with chunk counts
```

#### `reload(source?)`
```python
@mcp.tool()
def reload(source: str | None = None) -> str:
    # Re-indexes sources and rebuilds search index
```

---

## Data Flow

### Indexing Flow

```
sources.yaml
    │
    ▼
┌─────────────────┐
│  load_sources() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Indexer      │
│  index_source() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MarkdownAdapter │
│  parse_file()   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ NormalizedChunk │
│   (in memory)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   IndexStore    │
│     save()      │
└────────┬────────┘
         │
         ▼
    index.json
```

### Query Flow

```
User Query: "how to onboard tenant"
         │
         ▼
┌─────────────────┐
│  search() tool  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SearchIndex    │
│    search()     │
└────────┬────────┘
         │
         ├──► Tokenize query
         │
         ├──► Score each chunk (TF-IDF)
         │
         ├──► Apply boosts (entrypoint, title, depth)
         │
         ├──► Sort by score
         │
         ▼
┌─────────────────┐
│  SearchResult[] │
└────────┬────────┘
         │
         ▼
    JSON Response
```

---

## File Structure

```
Indexa/
├── config/
│   └── sources.yaml          # Source definitions
│
├── data/
│   ├── index.json            # Persistent index
│   └── index.graph.json      # Component graph (v0.2.0+)
│
├── src/indexa/
│   ├── __init__.py
│   ├── __main__.py           # Entry: python -m indexa
│   ├── cli.py                # CLI commands
│   ├── server.py             # FastMCP server
│   │
│   ├── config/
│   │   ├── settings.py       # Global settings
│   │   └── sources.py        # YAML loading + AdapterConfig (v1.0.0+)
│   │
│   ├── adapters/
│   │   ├── base.py           # Adapter protocol
│   │   ├── markdown.py       # Markdown parser
│   │   ├── component.py      # Component adapter (v0.2.0+)
│   │   ├── compodoc.py       # Angular Compodoc adapter (v1.0.0+)
│   │   ├── python.py         # Python source adapter (v1.1.0+)
│   │   └── source.py         # Source code adapter (v1.0.0+)
│   │
│   ├── indexing/
│   │   ├── chunk.py          # NormalizedChunk, ChunkKind
│   │   ├── component_chunk.py # ComponentChunk (v0.2.0+)
│   │   ├── source_chunk.py   # SourceChunk (v1.0.0+)
│   │   ├── indexer.py        # Multi-adapter orchestration (v1.0.0+)
│   │   └── store.py          # JSON persistence
│   │
│   ├── graph/                # Graph module (v0.2.0+)
│   │   ├── types.py          # NodeType, RelationType, ChunkType (extended v1.0.0+)
│   │   ├── component_graph.py # NetworkX wrapper
│   │   ├── builder.py        # GraphBuilder (v1.0.0+)
│   │   └── hybrid_search.py  # Combined graph + TF-IDF
│   │
│   ├── retrieval/
│   │   ├── search.py         # TF-IDF search
│   │   ├── bm25.py           # BM25 index (v0.3.0+)
│   │   ├── vector_store.py   # Vector search (v0.3.0+)
│   │   ├── hybrid_search.py  # RRF fusion (v0.3.0+)
│   │   └── query_expander.py # Query expansion (v0.3.0+)
│   │
│   └── tools/
│       ├── search.py         # search() tool
│       ├── context.py        # get_context() tool
│       ├── admin.py          # list_sources(), reload()
│       ├── graph.py          # Component tools (v0.2.0+)
│       └── source.py         # Source code tools (v1.0.0+)
│
├── tests/                    # Test suite
│   ├── conftest.py           # Fixtures
│   ├── test_component_graph.py
│   ├── test_component_adapter.py
│   ├── test_component_chunk.py
│   ├── test_hybrid_search.py
│   ├── test_compodoc_adapter.py  # (v1.0.0+)
│   ├── test_source_adapter.py    # (v1.0.0+)
│   └── test_python_adapter.py    # (v1.1.0+)
│
└── .cursor/
    └── mcp.json              # Cursor MCP config
```

---

## Design Decisions

### Why JSON Storage?

- **Simplicity:** No database dependencies
- **Portability:** Easy to inspect, backup, version
- **Performance:** Fast enough for <100k chunks
- **Trade-off:** Not suitable for very large indexes (>1M chunks)

### Why TF-IDF?

- **No external dependencies:** Pure Python implementation
- **Fast:** Sub-millisecond search for typical indexes
- **Good enough:** Works well for documentation search
- **Trade-off:** No semantic understanding (future: embeddings)

### Why Section-Level Chunking?

- **Token efficiency:** LLMs get focused context, not entire files
- **Precise retrieval:** Can link to specific sections
- **Stable anchors:** Headings provide natural boundaries

### Why FastMCP?

- **Pythonic:** Decorator-based API
- **Battle-tested:** Used in production MCP servers
- **Simple:** stdio transport works out of the box
- **Extensible:** Easy to add new tools

---

## Future Architecture

### Planned Enhancements

1. ~~**Semantic Search**~~ ✓ (v0.3.0)
   - ~~Add embedding generation (OpenAI, local models)~~
   - ~~Vector similarity search alongside TF-IDF~~
   - ~~Hybrid ranking (lexical + semantic)~~

2. ~~**Parallel Processing**~~ ✓ (v1.2.0)
   - ~~Parallel BM25 + Vector search with ThreadPoolExecutor~~
   - ~~Async OpenAI embeddings with concurrent batches~~
   - ~~Auto-detection of parallel-capable providers~~

3. **PostgreSQL Storage**
   - Use `tsvector` for full-text search
   - Scale to millions of chunks
   - Concurrent access support

4. **Additional Adapters**
   - ~~Python: AST parsing for docstrings~~ ✓ (v1.1.0)
   - OpenAPI: Endpoint documentation
   - ~~Angular: Compodoc integration~~ ✓ (v1.0.0)
   - ~~TypeScript/HTML/SCSS: Source code~~ ✓ (v1.0.0)

5. **File Watching**
   - Auto-reindex on file changes
   - Incremental updates (only changed files)

6. **Query Router**
   - Detect query intent (symbol lookup vs prose search)
   - Route to appropriate search strategy

7. **Graph Persistence (v0.2.1)**
   - Save/load graph separately from chunks
   - Incremental graph updates

8. ~~**Angular Component Support**~~ ✓ (v1.0.0)
   - ~~Compodoc adapter for Angular documentation~~
   - ~~Source adapter for TypeScript/HTML/SCSS~~
   - ~~GraphBuilder for file relationships~~

9. **Vue Component Support**
   - Vue SFC parsing
   - Composition API extraction

10. **Full Map-Reduce Pipeline** (Future, if needed)
    - Parallel file parsing with ProcessPoolExecutor
    - Distributed indexing for 10,000+ document sets
    - CI/CD optimized incremental builds
