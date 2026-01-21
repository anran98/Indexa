"""Admin tools for managing the index."""

from indexa.config.settings import Settings
from indexa.config.sources import load_sources
from indexa.indexing.indexer import Indexer
from indexa.server import mcp, search_index, store


@mcp.tool()
def list_sources() -> list[dict]:
    """
    List all configured documentation sources.

    Returns:
        List of sources with:
        - id: Source identifier
        - name: Display name
        - description: What this source contains
        - root: Filesystem path
        - chunk_count: Number of indexed chunks
        - tags: Associated tags
    """
    settings = Settings()
    sources = load_sources(settings.sources_path)
    chunks = store.load() if store.exists() else []

    result = []
    for source in sources:
        chunk_count = sum(1 for c in chunks if c.source_id == source.id)
        result.append(
            {
                "id": source.id,
                "name": source.name,
                "description": source.description,
                "root": str(source.root),
                "chunk_count": chunk_count,
                "tags": source.tags,
            }
        )

    return result


@mcp.tool()
def reload(source: str | None = None) -> str:
    """
    Re-index documentation sources.

    Note: This only reloads chunks into the JSON store and refreshes the in-memory
    search index. For full hybrid search (BM25 + Vector), run `indexa index`
    from the command line.

    Args:
        source: Optional source ID to reload. If not specified, reloads all sources.

    Returns:
        Status message with indexing results.
    """
    settings = Settings()
    sources = load_sources(settings.sources_path)

    if source:
        sources = [s for s in sources if s.id == source]
        if not sources:
            return f"Source '{source}' not found"

    indexer = Indexer()
    all_chunks = []

    for src in sources:
        chunks = indexer.index_source(src)
        all_chunks.extend(chunks)

    # Save chunks to store
    store.save(all_chunks)

    # Update in-memory chunk lookup if search_index is initialized
    if search_index is not None:
        search_index.load_chunks(all_chunks)

    return (
        f"Indexed {len(all_chunks)} chunks from {len(sources)} source(s). "
        "Note: For full hybrid search, run 'indexa index' from CLI."
    )
