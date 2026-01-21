"""Graph-aware search tools for UI component documentation."""

from indexa.server import graph_index, mcp

# Alias for backwards compatibility in this module
hybrid_index = graph_index


@mcp.tool()
def search_components(
    query: str,
    component: str | None = None,
    category: str | None = None,
    chunk_type: str | None = None,
    include_related: bool = False,
    top_k: int = 8,
) -> list[dict]:
    """
    Search component documentation with optional filters.

    This is an enhanced search specifically for UI component libraries.
    Use it when you need to find component usage, props, examples, or variants.

    Args:
        query: Natural language search query (e.g., "button click handler")
        component: Filter to specific component (e.g., "Button", "Modal")
        category: Filter by component category (e.g., "Forms", "Layout")
        chunk_type: Filter by documentation type:
            - "overview": Component introduction
            - "props": Props/API documentation
            - "example": Usage examples
            - "variant": Specific variant docs
            - "accessibility": A11y guidelines
            - "styling": Theming/CSS docs
        include_related: Also search related components (via graph)
        top_k: Maximum results to return (default: 8)

    Returns:
        List of results with:
        - source_id, path, anchor, title, snippet, score
        - component_name: Which component this documents
        - component_category: Category of the component
        - chunk_type: Type of documentation
    """
    if hybrid_index is None:
        return [{"error": "Hybrid index not initialized. Run 'indexa index' first."}]

    results = hybrid_index.search_components(
        query=query,
        component=component,
        category=category,
        chunk_type=chunk_type,
        include_related=include_related,
        top_k=top_k,
    )
    return [r.to_dict() for r in results]


@mcp.tool()
def get_component_info(component: str) -> dict:
    """
    Get comprehensive information about a UI component.

    Returns the component's category, relationships (variants, uses, used_by),
    and a summary of available documentation.

    Args:
        component: Component name (e.g., "Button", "Modal")

    Returns:
        Component info with:
        - name: Component name
        - category: Component category
        - relationships:
            - extends: Base component (if this is a variant)
            - variants: List of variant components
            - uses: Components this one composes
            - used_by: Components that use this one
            - related_to: Similar/related components
        - documentation:
            - chunk_count: Number of doc chunks
            - by_type: Chunks grouped by type (props, examples, etc.)
    """
    if hybrid_index is None:
        return {"error": "Hybrid index not initialized. Run 'indexa index' first."}

    info = hybrid_index.get_component_info(component)
    if info is None:
        return {"error": f"Component '{component}' not found in the index."}

    return info


@mcp.tool()
def list_component_categories() -> list[dict]:
    """
    List all component categories with their components.

    Use this to explore available component categories and see
    which components belong to each category.

    Returns:
        List of categories with:
        - name: Category name
        - description: Category description
        - component_count: Number of components
        - components: List of component names
    """
    if hybrid_index is None:
        return [{"error": "Hybrid index not initialized. Run 'indexa index' first."}]

    return hybrid_index.list_categories()


@mcp.tool()
def explore_category(category: str, include_chunks: bool = False) -> dict:
    """
    Get detailed information about a component category.

    Args:
        category: Category name (e.g., "Forms", "Layout", "Feedback")
        include_chunks: Include documentation chunk titles for each component

    Returns:
        Category info with:
        - name: Category name
        - description: Category description
        - components: List of components with names and descriptions
    """
    if hybrid_index is None:
        return {"error": "Hybrid index not initialized. Run 'indexa index' first."}

    info = hybrid_index.explore_category(category, include_chunks=include_chunks)
    if info is None:
        return {"error": f"Category '{category}' not found in the index."}

    return info


@mcp.tool()
def find_related_components(component: str, depth: int = 2) -> dict:
    """
    Find all components related to a given component.

    Uses graph traversal to discover components connected through
    variants, composition, or explicit relationships.

    Args:
        component: Starting component name
        depth: How many relationship hops to traverse (default: 2)

    Returns:
        Dict mapping component names to their distance from the source.
        Distance 1 = directly related, 2 = related through one component, etc.
    """
    if hybrid_index is None:
        return {"error": "Hybrid index not initialized. Run 'indexa index' first."}

    if hybrid_index.graph is None:
        return {"error": "Component graph not available."}

    related = hybrid_index.graph.find_related_components(component, max_depth=depth)
    if not related:
        return {
            "component": component,
            "related": {},
            "message": f"No related components found for '{component}'.",
        }

    return {
        "component": component,
        "related": related,
        "count": len(related),
    }
