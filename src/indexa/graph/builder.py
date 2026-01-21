"""Graph builder - constructs component graph from indexed chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from indexa.graph.types import ChunkType, NodeType, RelationType

if TYPE_CHECKING:
    from indexa.graph.component_graph import ComponentGraph
    from indexa.indexing.chunk import NormalizedChunk
    from indexa.indexing.component_chunk import ComponentChunk
    from indexa.indexing.source_chunk import SourceChunk


class GraphBuilder:
    """Build component graph from indexed chunks."""

    def build_from_chunks(
        self,
        chunks: list[NormalizedChunk],
        graph: ComponentGraph,
    ) -> None:
        """Add nodes and relationships from chunks to graph."""
        from indexa.indexing.component_chunk import ComponentChunk
        from indexa.indexing.source_chunk import SourceChunk

        for chunk in chunks:
            if isinstance(chunk, ComponentChunk):
                self._add_component_chunk(chunk, graph)
            elif isinstance(chunk, SourceChunk):
                self._add_source_chunk(chunk, graph)

        for chunk in chunks:
            if isinstance(chunk, ComponentChunk):
                self._add_component_relationships(chunk, graph)
            elif isinstance(chunk, SourceChunk):
                self._add_source_relationships(chunk, graph)

    def _add_component_chunk(
        self,
        chunk: ComponentChunk,
        graph: ComponentGraph,
    ) -> None:
        if chunk.component_name:
            graph.add_component(
                name=chunk.component_name,
                category=chunk.component_category,
                description=chunk.title,
            )
            graph.add_chunk(
                chunk_id=chunk.id,
                component_name=chunk.component_name,
                chunk_type=chunk.chunk_type,
            )

    def _add_source_chunk(
        self,
        chunk: SourceChunk,
        graph: ComponentGraph,
    ) -> None:
        if not chunk.component_name:
            return

        graph.add_component(name=chunk.component_name, category="")

        file_node = f"source:{chunk.path}"
        graph._graph.add_node(
            file_node,
            node_type=NodeType.SOURCE_FILE.value,
            name=chunk.path,
            language=chunk.language,
            file_type=chunk.file_type,
        )

        relation = RelationType.HAS_SOURCE
        if chunk.file_type == "template":
            relation = RelationType.HAS_TEMPLATE
        elif chunk.file_type == "stylesheet":
            relation = RelationType.HAS_STYLESHEET

        graph.add_relationship(
            f"component:{chunk.component_name}",
            file_node,
            relation,
        )

    def _add_component_relationships(
        self,
        chunk: ComponentChunk,
        graph: ComponentGraph,
    ) -> None:
        if not chunk.component_name:
            return

        if chunk.extends:
            graph.add_component(chunk.extends)
            graph.add_relationship(
                f"component:{chunk.component_name}",
                f"component:{chunk.extends}",
                RelationType.EXTENDS,
            )

        for used in chunk.uses:
            graph.add_component(used)
            graph.add_uses(chunk.component_name, used)

        for variant in chunk.variants:
            graph.add_component(variant)
            graph.add_variant(chunk.component_name, variant)

        for related in chunk.related_to:
            graph.add_component(related)
            graph.add_related(chunk.component_name, related)

    def _add_source_relationships(
        self,
        chunk: SourceChunk,
        graph: ComponentGraph,
    ) -> None:
        file_node = f"source:{chunk.path}"

        for symbol in chunk.symbols_extracted:
            if symbol.get("type") == "component_ref":
                ref_name = symbol.get("name", "")
                if ref_name and f"component:{ref_name}" in graph:
                    graph.add_relationship(
                        file_node,
                        f"component:{ref_name}",
                        RelationType.REFERENCES,
                    )
