"""Source code search tools."""

from indexa.server import mcp, search_index, graph_index


@mcp.tool()
def search_source(
    query: str,
    language: str | None = None,
    file_type: str | None = None,
    component: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """
    Search source code files.

    Args:
        query: Search query (e.g., "ReviewPanel", "handleSubmit", "authentication")
        language: Filter by language (typescript, html, scss, python)
        file_type: Filter by file type (component, service, template, module)
        component: Filter by component name
        top_k: Number of results to return

    Returns:
        Matching source code chunks with file path, content snippet, and metadata
    """
    if search_index is None:
        return [{"error": "Search index not initialized. Run 'indexa index' first."}]

    results = search_index.search(query=query, top_k=top_k * 2)

    filtered = []
    for r in results:
        chunk = r.chunk
        if chunk.kind not in ("source", "template", "stylesheet"):
            continue

        chunk_dict = chunk.to_dict()

        if language and chunk_dict.get("language") != language:
            continue
        if file_type and chunk_dict.get("file_type") != file_type:
            continue
        if component and chunk_dict.get("component_name") != component:
            continue

        filtered.append({
            "source_id": chunk.source_id,
            "path": chunk.path,
            "title": chunk.title,
            "language": chunk_dict.get("language", ""),
            "file_type": chunk_dict.get("file_type", ""),
            "component_name": chunk_dict.get("component_name", ""),
            "snippet": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
            "score": r.score,
        })

        if len(filtered) >= top_k:
            break

    return filtered


@mcp.tool()
def get_component_source(
    component: str,
    include_template: bool = True,
    include_styles: bool = False,
) -> dict:
    """
    Get all source files for a component.

    Args:
        component: Component name (e.g., "ReviewPanel", "TdsButton")
        include_template: Include HTML template content
        include_styles: Include SCSS/CSS styles

    Returns:
        Component source files with content
    """
    if search_index is None:
        return {"error": "Search index not initialized. Run 'indexa index' first."}

    results = search_index.search(query=component, top_k=20)

    component_files = {
        "component": component,
        "source": None,
        "template": None,
        "styles": None,
        "related_files": [],
    }

    for r in results:
        chunk = r.chunk
        chunk_dict = chunk.to_dict()

        comp_name = chunk_dict.get("component_name", "")
        if comp_name.lower() != component.lower():
            continue

        file_type = chunk_dict.get("file_type", "")

        if file_type == "component" and component_files["source"] is None:
            component_files["source"] = {
                "path": chunk.path,
                "content": chunk.content,
                "class_name": chunk_dict.get("class_name"),
                "selector": chunk_dict.get("selector"),
            }
            component_files["related_files"] = chunk_dict.get("related_files", [])

        elif file_type == "template" and include_template and component_files["template"] is None:
            component_files["template"] = {
                "path": chunk.path,
                "content": chunk.content,
            }

        elif file_type == "stylesheet" and include_styles and component_files["styles"] is None:
            component_files["styles"] = {
                "path": chunk.path,
                "content": chunk.content,
            }

    if not component_files["source"] and not component_files["template"]:
        return {"error": f"Component '{component}' not found"}

    return component_files


@mcp.tool()
def find_component_usage(
    component: str,
    top_k: int = 20,
) -> list[dict]:
    """
    Find where a component is used in templates.

    Args:
        component: Component name to search for (e.g., "TdsButton")
        top_k: Maximum results

    Returns:
        Templates that reference this component
    """
    if search_index is None:
        return [{"error": "Search index not initialized. Run 'indexa index' first."}]

    selector_patterns = [
        component.lower(),
        _pascal_to_kebab(component),
        f"<{_pascal_to_kebab(component)}",
        f"<app-{_pascal_to_kebab(component)}",
        f"<tds-{_pascal_to_kebab(component)}",
    ]

    all_results = []
    seen_paths = set()

    for pattern in selector_patterns:
        results = search_index.search(query=pattern, top_k=top_k)
        for r in results:
            chunk = r.chunk
            if chunk.path in seen_paths:
                continue

            chunk_dict = chunk.to_dict()
            if chunk_dict.get("file_type") != "template":
                continue

            component_refs = chunk_dict.get("symbols_extracted", [])
            ref_names = [ref.get("name", "").lower() for ref in component_refs]

            if component.lower() in ref_names or any(
                pattern.lower() in chunk.content.lower() for pattern in selector_patterns[:2]
            ):
                seen_paths.add(chunk.path)
                all_results.append({
                    "path": chunk.path,
                    "component_name": chunk_dict.get("component_name", ""),
                    "snippet": _extract_usage_snippet(chunk.content, component),
                })

    return all_results[:top_k]


def _pascal_to_kebab(name: str) -> str:
    """Convert PascalCase to kebab-case."""
    import re
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def _extract_usage_snippet(content: str, component: str) -> str:
    """Extract a snippet showing component usage."""
    kebab = _pascal_to_kebab(component)
    patterns = [f"<{kebab}", f"<app-{kebab}", f"<tds-{kebab}"]

    for pattern in patterns:
        idx = content.lower().find(pattern.lower())
        if idx != -1:
            start = max(0, idx - 50)
            end = min(len(content), idx + 200)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
            return snippet

    return content[:300] + "..." if len(content) > 300 else content
