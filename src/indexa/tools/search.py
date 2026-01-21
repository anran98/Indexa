"""Search tool for finding documentation."""

from indexa.server import mcp, search_index


@mcp.tool()
def search(query: str, source: str | None = None, top_k: int = 8) -> list[dict]:
    """
    Search documentation for relevant sections.

    Uses hybrid search combining:
    - BM25 (lexical matching with stemming)
    - Vector search (semantic similarity)
    - Query expansion (abbreviations like 'btn' -> 'button')

    Args:
        query: Natural language search query (e.g., "how to onboard tenant")
        source: Optional source ID to limit search (e.g., "agentic_search")
        top_k: Maximum number of results to return (default: 8)

    Returns:
        List of search results with:
        - source_id: The documentation source
        - path: File path within the source
        - anchor: Section anchor (for linking)
        - title: Section heading
        - snippet: Relevant excerpt
        - score: Relevance score
        - uri: Full docs:// URI
    """
    if search_index is None:
        return [{"error": "Search index not initialized. Run 'indexa index' first."}]

    results = search_index.search(query=query, source_id=source, top_k=top_k)
    return [r.to_dict() for r in results]
