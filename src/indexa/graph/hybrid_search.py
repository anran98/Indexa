"""Hybrid search combining text search with graph-based filtering."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass

from indexa.graph.component_graph import ComponentGraph
from indexa.graph.types import ChunkType
from indexa.indexing.chunk import NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk


@dataclass
class SearchResult:
    """A single search result."""

    chunk: NormalizedChunk
    score: float
    snippet: str

    def to_dict(self) -> dict:
        return {
            "source_id": self.chunk.source_id,
            "path": self.chunk.path,
            "anchor": self.chunk.anchor,
            "title": self.chunk.title,
            "kind": self.chunk.kind,
            "snippet": self.snippet,
            "score": round(self.score, 4),
            "uri": self.chunk.to_uri(),
            "is_entrypoint": self.chunk.is_entrypoint,
        }


class SimpleTFIDF:
    """Simple in-memory TF-IDF for graph-based component search.

    This is a lightweight implementation used internally by HybridSearchIndex
    for filtering component documentation. The main search uses the full
    HybridSearchEngine with BM25 + Vector search.
    """

    STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "to",
        "of", "and", "or", "in", "on", "at", "for", "with", "it", "this",
        "that", "from", "by", "as", "can", "will", "have", "has", "had",
        "do", "does", "did",
    })

    def __init__(self) -> None:
        self.chunks: list[NormalizedChunk] = []
        self.doc_freq: dict[str, int] = defaultdict(int)
        self.tf_cache: dict[str, dict[str, float]] = {}

    def build(self, chunks: list[NormalizedChunk]) -> None:
        """Build the index from chunks."""
        self.chunks = chunks
        self.doc_freq = defaultdict(int)
        self.tf_cache = {}

        for chunk in chunks:
            terms = self._tokenize(chunk.title + " " + chunk.content)
            unique_terms = set(terms)

            for term in unique_terms:
                self.doc_freq[term] += 1

            tf: dict[str, float] = defaultdict(float)
            for term in terms:
                tf[term] += 1
            doc_len = len(terms)
            if doc_len > 0:
                for term in tf:
                    tf[term] /= doc_len
            self.tf_cache[chunk.id] = dict(tf)

    def search(
        self,
        query: str,
        source_id: str | None = None,
        top_k: int = 8,
    ) -> list[SearchResult]:
        """Search for matching chunks."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        n_docs = len(self.chunks)
        if n_docs == 0:
            return []

        results = []

        for chunk in self.chunks:
            if source_id and chunk.source_id != source_id:
                continue

            score = 0.0
            tf = self.tf_cache.get(chunk.id, {})

            for term in query_terms:
                if term in tf:
                    df = self.doc_freq.get(term, 1)
                    idf = math.log(n_docs / df) if df > 0 else 0
                    score += tf[term] * idf

            if chunk.is_entrypoint:
                score *= 1.5

            title_terms = set(self._tokenize(chunk.title))
            title_overlap = len(set(query_terms) & title_terms)
            if title_overlap > 0:
                score *= 1 + 0.3 * title_overlap

            if score > 0:
                snippet = self._generate_snippet(chunk.content, query_terms)
                results.append(SearchResult(chunk=chunk, score=score, snippet=snippet))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        tokens = re.findall(r"\w+", text)
        return [t for t in tokens if len(t) > 1 and t not in self.STOPWORDS]

    def _generate_snippet(
        self, content: str, query_terms: list[str], max_len: int = 200
    ) -> str:
        content_lower = content.lower()
        best_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        start = max(0, best_pos - 50)
        end = min(len(content), start + max_len)

        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        snippet = re.sub(r"\s+", " ", snippet)
        return snippet


@dataclass
class ComponentSearchResult(SearchResult):
    """Search result with component metadata."""

    component_name: str | None = None
    component_category: str | None = None
    chunk_type: str | None = None

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "component_name": self.component_name,
            "component_category": self.component_category,
            "chunk_type": self.chunk_type,
        })
        return base


class HybridSearchIndex:
    """Combined graph + text search for component documentation.

    This index provides:
    - Text search via simple TF-IDF (for filtering)
    - Graph-based filtering by component, category, relationships
    - Expansion of search results to include related components

    Note: For main documentation search, use indexa.retrieval.HybridSearchEngine
    which provides BM25 + Vector search with query expansion.
    """

    def __init__(self) -> None:
        """Initialize empty hybrid index."""
        self._tfidf = SimpleTFIDF()
        self._graph = ComponentGraph()
        self._chunks: dict[str, NormalizedChunk] = {}  # id → chunk
        self._component_chunks: dict[str, ComponentChunk] = {}  # id → component chunk

    @property
    def graph(self) -> ComponentGraph:
        """Access the component graph."""
        return self._graph

    @property
    def tfidf(self) -> SimpleTFIDF:
        """Access the TF-IDF index."""
        return self._tfidf

    def build(
        self,
        chunks: list[NormalizedChunk],
        graph: ComponentGraph | None = None,
    ) -> None:
        """Build the hybrid index from chunks and optional graph.

        Args:
            chunks: All documentation chunks
            graph: Pre-built component graph (or builds from ComponentChunks)
        """
        # Store all chunks
        self._chunks = {c.id: c for c in chunks}

        # Separate component chunks
        self._component_chunks = {
            c.id: c for c in chunks if isinstance(c, ComponentChunk)
        }

        # Build TF-IDF index over all chunks
        self._tfidf.build(chunks)

        # Use provided graph or build from component chunks
        if graph:
            self._graph = graph
        else:
            self._build_graph_from_chunks()

    def _build_graph_from_chunks(self) -> None:
        """Build component graph from ComponentChunk metadata."""
        self._graph = ComponentGraph()

        for chunk in self._component_chunks.values():
            if not chunk.component_name:
                continue

            # Add component node
            self._graph.add_component(
                name=chunk.component_name,
                category=chunk.component_category or None,
            )

            # Add chunk to graph
            self._graph.add_chunk(
                chunk_id=chunk.id,
                component_name=chunk.component_name,
                chunk_type=chunk.chunk_type,
            )

            # Add relationships from chunk metadata
            if chunk.extends:
                self._graph.add_component(chunk.extends)
                self._graph.add_variant(chunk.extends, chunk.component_name)

            for used in chunk.uses:
                self._graph.add_component(used)
                self._graph.add_uses(chunk.component_name, used)

            for related in chunk.related_to:
                self._graph.add_component(related)
                self._graph.add_related(chunk.component_name, related)

    def search(
        self,
        query: str,
        source_id: str | None = None,
        component: str | None = None,
        category: str | None = None,
        chunk_type: ChunkType | None = None,
        include_related: bool = False,
        related_depth: int = 1,
        top_k: int = 8,
    ) -> list[ComponentSearchResult]:
        """Search with optional component/category filters.

        Args:
            query: Search query text
            source_id: Filter by source
            component: Filter to specific component
            category: Filter by component category
            chunk_type: Filter by chunk type (props, example, etc.)
            include_related: Expand to include related components
            related_depth: How deep to traverse relationships
            top_k: Maximum results to return

        Returns:
            List of search results with component metadata
        """
        # Get base TF-IDF results (get more than needed for filtering)
        base_results = self._tfidf.search(
            query,
            source_id=source_id,
            top_k=top_k * 5,  # Over-fetch for filtering
        )

        # Determine which components to include
        target_components: set[str] | None = None

        if component:
            target_components = {component}
            if include_related:
                related = self._graph.find_related_components(
                    component, max_depth=related_depth
                )
                target_components.update(related.keys())

        elif category:
            target_components = set(self._graph.get_components_in_category(category))
            if include_related:
                expanded = set()
                for comp in target_components:
                    related = self._graph.find_related_components(
                        comp, max_depth=related_depth
                    )
                    expanded.update(related.keys())
                target_components.update(expanded)

        # Filter and enhance results
        results: list[ComponentSearchResult] = []

        for result in base_results:
            chunk = result.chunk
            comp_chunk = self._component_chunks.get(chunk.id)

            # Apply filters
            if target_components is not None:
                if comp_chunk is None:
                    continue
                if comp_chunk.component_name not in target_components:
                    continue

            if chunk_type is not None:
                if comp_chunk is None:
                    continue
                if comp_chunk.chunk_type != chunk_type:
                    continue

            # Create enhanced result
            comp_result = ComponentSearchResult(
                chunk=chunk,
                score=result.score,
                snippet=result.snippet,
                component_name=comp_chunk.component_name if comp_chunk else None,
                component_category=comp_chunk.component_category if comp_chunk else None,
                chunk_type=comp_chunk.chunk_type.value if comp_chunk else None,
            )
            results.append(comp_result)

            if len(results) >= top_k:
                break

        return results

    def search_components(
        self,
        query: str,
        source_id: str | None = None,
        component: str | None = None,
        category: str | None = None,
        chunk_type: str | None = None,
        include_related: bool = False,
        top_k: int = 8,
    ) -> list[ComponentSearchResult]:
        """Search component documentation with filters (MCP-friendly signature).

        Wrapper around search() with string chunk_type for easier MCP integration.

        Args:
            query: Search query text
            source_id: Filter by source
            component: Filter to specific component
            category: Filter by component category
            chunk_type: Filter by chunk type name (e.g., "props", "example")
            include_related: Expand to include related components
            top_k: Maximum results to return

        Returns:
            List of search results with component metadata
        """
        # Parse chunk_type string to enum
        chunk_type_enum: ChunkType | None = None
        if chunk_type:
            try:
                chunk_type_enum = ChunkType(chunk_type)
            except ValueError:
                pass  # Invalid chunk type, ignore filter

        return self.search(
            query=query,
            source_id=source_id,
            component=component,
            category=category,
            chunk_type=chunk_type_enum,
            include_related=include_related,
            top_k=top_k,
        )

    def get_component_info(self, component: str) -> dict | None:
        """Get comprehensive information about a component.

        Args:
            component: Component name

        Returns:
            Dict with component info, relationships, and chunk summary
        """
        comp_data = self._graph.get_component(component)
        if not comp_data:
            return None

        # Get relationships
        variants = self._graph.get_variants(component)
        base = self._graph.get_base_component(component)
        uses = self._graph.get_uses(component)
        used_by = self._graph.get_used_by(component)
        related = self._graph.get_related(component)

        # Get chunk summary
        chunk_ids = self._graph.get_chunks_for_component(component)
        chunks_by_type: dict[str, list[str]] = {}
        for chunk_id in chunk_ids:
            chunk = self._component_chunks.get(chunk_id)
            if chunk:
                type_name = chunk.chunk_type.value
                if type_name not in chunks_by_type:
                    chunks_by_type[type_name] = []
                chunks_by_type[type_name].append(chunk.title)

        return {
            "name": component,
            "category": comp_data.get("category"),
            "description": comp_data.get("description", ""),
            "relationships": {
                "extends": base,
                "variants": variants,
                "uses": uses,
                "used_by": used_by,
                "related_to": related,
            },
            "documentation": {
                "chunk_count": len(chunk_ids),
                "by_type": chunks_by_type,
            },
        }

    def list_categories(self) -> list[dict]:
        """List all component categories with their components.

        Returns:
            List of category info dicts
        """
        categories = []
        for cat_name in self._graph.list_categories():
            components = self._graph.get_components_in_category(cat_name)
            cat_data = self._graph.get_category(cat_name)
            categories.append({
                "name": cat_name,
                "description": cat_data.get("description", "") if cat_data else "",
                "component_count": len(components),
                "components": components,
            })
        return categories

    def explore_category(
        self,
        category: str,
        include_chunks: bool = False,
    ) -> dict | None:
        """Get detailed information about a category.

        Args:
            category: Category name
            include_chunks: Include chunk titles for each component

        Returns:
            Category info with components
        """
        cat_data = self._graph.get_category(category)
        if not cat_data:
            return None

        components = self._graph.get_components_in_category(category)

        component_info = []
        for comp_name in components:
            info: dict = {"name": comp_name}
            comp_data = self._graph.get_component(comp_name)
            if comp_data:
                info["description"] = comp_data.get("description", "")

            if include_chunks:
                chunk_ids = self._graph.get_chunks_for_component(comp_name)
                info["chunks"] = [
                    self._component_chunks[cid].title
                    for cid in chunk_ids
                    if cid in self._component_chunks
                ]

            component_info.append(info)

        return {
            "name": category,
            "description": cat_data.get("description", ""),
            "components": component_info,
        }

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the index for persistence."""
        return {
            "graph": self._graph.to_dict(),
            "component_chunks": [
                c.to_dict() for c in self._component_chunks.values()
            ],
        }

    def load_graph(self, data: dict) -> None:
        """Load graph from serialized data.

        Note: This only loads the graph. TF-IDF index must be rebuilt
        from chunks separately.

        Args:
            data: Dict from to_dict()
        """
        if "graph" in data:
            self._graph = ComponentGraph.from_dict(data["graph"])

        if "component_chunks" in data:
            self._component_chunks = {
                c["id"]: ComponentChunk.from_dict(c)
                for c in data["component_chunks"]
            }
