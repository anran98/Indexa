"""FastMCP server definition for Indexa."""

from fastmcp import FastMCP

from indexa.config.settings import Settings
from indexa.graph.hybrid_search import HybridSearchIndex as GraphHybridSearchIndex
from indexa.indexing.store import IndexStore
from indexa.retrieval import HybridSearchEngine

# Global instances
settings = Settings()
store = IndexStore(settings.index_path)
data_dir = settings.index_path.parent

# Initialize hybrid search engine (BM25 + Vector)
# Use local embeddings by default to avoid API key requirement at startup
search_index: HybridSearchEngine | None = None
graph_index: GraphHybridSearchIndex | None = None

# Load index on startup
if store.exists():
    chunks = store.load()

    # Initialize hybrid search engine
    search_index = HybridSearchEngine(
        data_dir=data_dir,
        provider_name="local",  # Local embeddings for query-time search
    )
    search_index.load_chunks(chunks)

    # Initialize graph index for component search
    graph_index = GraphHybridSearchIndex()
    graph_index.build(chunks)

    # Load graph data if available
    graph_data = store.load_graph()
    if graph_data:
        graph_index.load_graph(graph_data)

# Create MCP server
mcp = FastMCP(
    name="Indexa",
    instructions="""
Indexa provides documentation search for internal frameworks and libraries.

## Available Tools

### Basic Search
- **search(query)**: Find relevant documentation sections. Returns ranked results with snippets.
- **get_context(source, path, anchor?)**: Retrieve full content of a specific section.
- **list_sources()**: Show all configured documentation sources.
- **reload()**: Re-index all documentation sources.

### Component Search (for UI libraries)
- **search_components(query, component?, category?, chunk_type?)**: Search component docs with filters.
- **get_component_info(component)**: Get component details, relationships, and available docs.
- **list_component_categories()**: List all component categories.
- **explore_category(category)**: Get details about a category and its components.
- **find_related_components(component, depth?)**: Find related components via graph traversal.

## Usage Pattern

1. Use `search()` to find relevant docs for a topic
2. Use `get_context()` to retrieve full content of promising results
3. Combine information from multiple sections as needed

## Example

User: "How do I configure authentication?"
1. Call search("configure authentication") → Returns results from GETTING_STARTED.md, auth/README.md
2. Call get_context("my_project", "docs/GETTING_STARTED.md", "authentication-setup")
3. Returns full section with code examples

## Tips

- Use specific keywords from the domain (e.g., "authentication", "vector store", "API")
- If search returns too many results, add the source parameter to filter
- Entry point documents (README, GETTING_STARTED) are boosted in results
""",
)


def _register_tools():
    """Import tools to register them with the MCP server."""
    # Import triggers @mcp.tool() decorators
    from indexa.tools import admin, context, graph, search  # noqa: F401


def run():
    """Run the MCP server."""
    _register_tools()
    mcp.run()


if __name__ == "__main__":
    run()
