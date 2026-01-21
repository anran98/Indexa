"""Context retrieval tool for getting full section content."""

from indexa.server import mcp, store


@mcp.tool()
def get_context(source: str, path: str, anchor: str | None = None) -> str:
    """
    Retrieve full content of a documentation section.

    Args:
        source: Source ID (e.g., "agentic_search")
        path: File path within source (e.g., "docs/GETTING_STARTED.md")
        anchor: Optional section anchor (e.g., "installation")

    Returns:
        Full markdown content of the section.
        If anchor is not specified, returns the entire file content.
    """
    chunks = store.load()

    # Find matching chunk(s)
    matching_chunks = []
    for chunk in chunks:
        if chunk.source_id != source:
            continue
        if chunk.path != path:
            continue
        matching_chunks.append(chunk)
        if anchor and chunk.anchor == anchor:
            return chunk.content

    # If anchor specified but not found exactly, return all file sections
    if matching_chunks:
        # Sort by position (depth and order in file preserved by indexer)
        return "\n\n".join(c.content for c in matching_chunks)

    return f"No content found for {source}/{path}" + (f"#{anchor}" if anchor else "")
