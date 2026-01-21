"""NetworkX-based component relationship graph."""

from __future__ import annotations

from typing import Any

import networkx as nx

from indexa.graph.types import ChunkType, EdgeData, NodeData, NodeType, RelationType


class ComponentGraph:
    """Graph structure for component relationships using NetworkX.

    Provides query methods for traversing component hierarchies,
    finding related components, and filtering by category.
    """

    def __init__(self) -> None:
        """Initialize an empty directed graph."""
        self._graph: nx.DiGraph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        """Access the underlying NetworkX graph."""
        return self._graph

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    def add_component(
        self,
        name: str,
        category: str | None = None,
        description: str = "",
    ) -> str:
        """Add a component node to the graph.

        Args:
            name: Component name (e.g., "Button")
            category: Category name (e.g., "Forms")
            description: Brief component description

        Returns:
            The node ID for the component
        """
        node_id = f"component:{name}"

        # Only add if not exists, or update if new data is provided
        if node_id in self._graph:
            # Update only if new category/description provided
            existing = self._graph.nodes[node_id]
            if category and not existing.get("category"):
                existing["category"] = category
            if description and not existing.get("description"):
                existing["description"] = description
        else:
            self._graph.add_node(
                node_id,
                node_type=NodeType.COMPONENT.value,
                name=name,
                category=category or "",
                description=description,
            )

        # Auto-create category relationship if specified
        if category:
            self.add_category(category)
            self.add_relationship(
                node_id,
                f"category:{category}",
                RelationType.BELONGS_TO,
            )

        return node_id

    def add_category(
        self,
        name: str,
        description: str = "",
        parent: str | None = None,
    ) -> str:
        """Add a category node to the graph.

        Args:
            name: Category name (e.g., "Forms")
            description: Brief category description
            parent: Parent category name for hierarchy

        Returns:
            The node ID for the category
        """
        node_id = f"category:{name}"

        # Only add if not exists (idempotent)
        if node_id not in self._graph:
            self._graph.add_node(
                node_id,
                node_type=NodeType.CATEGORY.value,
                name=name,
                description=description,
                parent_category=parent,
            )

            # Add parent relationship if specified
            if parent:
                parent_id = f"category:{parent}"
                self.add_category(parent)  # Ensure parent exists
                self.add_relationship(node_id, parent_id, RelationType.BELONGS_TO)

        return node_id

    def add_chunk(
        self,
        chunk_id: str,
        component_name: str,
        chunk_type: ChunkType,
    ) -> str:
        """Link a documentation chunk to a component.

        Args:
            chunk_id: Unique chunk identifier
            component_name: Component this chunk documents
            chunk_type: Type of documentation (props, example, etc.)

        Returns:
            The node ID for the chunk
        """
        node_id = f"chunk:{chunk_id}"
        component_id = f"component:{component_name}"

        self._graph.add_node(
            node_id,
            node_type=NodeType.CHUNK.value,
            chunk_id=chunk_id,
            chunk_type=chunk_type.value,
            name=chunk_id,
        )

        # Link chunk to component
        if component_id in self._graph:
            self.add_relationship(node_id, component_id, RelationType.DOCUMENTS)

        return node_id

    # -------------------------------------------------------------------------
    # Relationship Operations
    # -------------------------------------------------------------------------

    def add_relationship(
        self,
        source: str,
        target: str,
        relation_type: RelationType,
        weight: float = 1.0,
        bidirectional: bool = False,
    ) -> None:
        """Add a relationship (edge) between two nodes.

        Args:
            source: Source node ID
            target: Target node ID
            relation_type: Type of relationship
            weight: Relationship strength (0-1)
            bidirectional: Whether to add reverse edge
        """
        edge_data: EdgeData = {
            "relation_type": relation_type.value,
            "weight": weight,
            "bidirectional": bidirectional,
        }
        self._graph.add_edge(source, target, **edge_data)

        if bidirectional:
            self._graph.add_edge(target, source, **edge_data)

    def add_variant(self, base_component: str, variant_component: str) -> None:
        """Add a variant relationship between components.

        Args:
            base_component: Base component name (e.g., "Button")
            variant_component: Variant name (e.g., "IconButton")
        """
        base_id = f"component:{base_component}"
        variant_id = f"component:{variant_component}"

        self.add_relationship(base_id, variant_id, RelationType.HAS_VARIANT)
        self.add_relationship(variant_id, base_id, RelationType.EXTENDS)

    def add_uses(self, component: str, uses_component: str) -> None:
        """Mark that a component uses/composes another component.

        Args:
            component: Component that uses another
            uses_component: Component being used
        """
        self.add_relationship(
            f"component:{component}",
            f"component:{uses_component}",
            RelationType.USES,
        )

    def add_related(self, component1: str, component2: str) -> None:
        """Mark two components as related (bidirectional).

        Args:
            component1: First component name
            component2: Second component name
        """
        self.add_relationship(
            f"component:{component1}",
            f"component:{component2}",
            RelationType.RELATED_TO,
            bidirectional=True,
        )

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_component(self, name: str) -> dict | None:
        """Get component data by name.

        Args:
            name: Component name

        Returns:
            Node data dict or None if not found
        """
        node_id = f"component:{name}"
        if node_id in self._graph:
            return dict(self._graph.nodes[node_id])
        return None

    def get_category(self, name: str) -> dict | None:
        """Get category data by name.

        Args:
            name: Category name

        Returns:
            Node data dict or None if not found
        """
        node_id = f"category:{name}"
        if node_id in self._graph:
            return dict(self._graph.nodes[node_id])
        return None

    def list_components(self) -> list[str]:
        """List all component names in the graph.

        Returns:
            List of component names
        """
        return [
            data["name"]
            for _, data in self._graph.nodes(data=True)
            if data.get("node_type") == NodeType.COMPONENT.value
        ]

    def list_categories(self) -> list[str]:
        """List all category names in the graph.

        Returns:
            List of category names
        """
        return [
            data["name"]
            for _, data in self._graph.nodes(data=True)
            if data.get("node_type") == NodeType.CATEGORY.value
        ]

    def get_components_in_category(self, category: str) -> list[str]:
        """Get all components belonging to a category.

        Args:
            category: Category name

        Returns:
            List of component names in the category
        """
        category_id = f"category:{category}"
        if category_id not in self._graph:
            return []

        components = []
        for pred in self._graph.predecessors(category_id):
            node_data = self._graph.nodes[pred]
            edge_data = self._graph.edges[pred, category_id]
            if (
                node_data.get("node_type") == NodeType.COMPONENT.value
                and edge_data.get("relation_type") == RelationType.BELONGS_TO.value
            ):
                components.append(node_data["name"])

        return components

    def get_variants(self, component: str) -> list[str]:
        """Get all variants of a component.

        Args:
            component: Component name

        Returns:
            List of variant component names
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return []

        variants = []
        for succ in self._graph.successors(component_id):
            node_data = self._graph.nodes[succ]
            edge_data = self._graph.edges[component_id, succ]
            if (
                node_data.get("node_type") == NodeType.COMPONENT.value
                and edge_data.get("relation_type") == RelationType.HAS_VARIANT.value
            ):
                variants.append(node_data["name"])

        return variants

    def get_base_component(self, component: str) -> str | None:
        """Get the base component that a variant extends.

        Args:
            component: Variant component name

        Returns:
            Base component name or None
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return None

        for succ in self._graph.successors(component_id):
            node_data = self._graph.nodes[succ]
            edge_data = self._graph.edges[component_id, succ]
            if (
                node_data.get("node_type") == NodeType.COMPONENT.value
                and edge_data.get("relation_type") == RelationType.EXTENDS.value
            ):
                return node_data["name"]

        return None

    def get_uses(self, component: str) -> list[str]:
        """Get components that a component uses/composes.

        Args:
            component: Component name

        Returns:
            List of used component names
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return []

        uses = []
        for succ in self._graph.successors(component_id):
            node_data = self._graph.nodes[succ]
            edge_data = self._graph.edges[component_id, succ]
            if (
                node_data.get("node_type") == NodeType.COMPONENT.value
                and edge_data.get("relation_type") == RelationType.USES.value
            ):
                uses.append(node_data["name"])

        return uses

    def get_used_by(self, component: str) -> list[str]:
        """Get components that use a given component.

        Args:
            component: Component name

        Returns:
            List of component names that use this component
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return []

        used_by = []
        for pred in self._graph.predecessors(component_id):
            node_data = self._graph.nodes[pred]
            edge_data = self._graph.edges[pred, component_id]
            if (
                node_data.get("node_type") == NodeType.COMPONENT.value
                and edge_data.get("relation_type") == RelationType.USES.value
            ):
                used_by.append(node_data["name"])

        return used_by

    def get_related(self, component: str) -> list[str]:
        """Get components related to a component.

        Args:
            component: Component name

        Returns:
            List of related component names
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return []

        related = set()
        # Check both successors and predecessors for RELATED_TO
        for neighbor in list(self._graph.successors(component_id)) + list(
            self._graph.predecessors(component_id)
        ):
            node_data = self._graph.nodes[neighbor]
            if node_data.get("node_type") != NodeType.COMPONENT.value:
                continue

            # Check edge exists in either direction
            if self._graph.has_edge(component_id, neighbor):
                edge_data = self._graph.edges[component_id, neighbor]
                if edge_data.get("relation_type") == RelationType.RELATED_TO.value:
                    related.add(node_data["name"])
            if self._graph.has_edge(neighbor, component_id):
                edge_data = self._graph.edges[neighbor, component_id]
                if edge_data.get("relation_type") == RelationType.RELATED_TO.value:
                    related.add(node_data["name"])

        return list(related)

    def get_chunks_for_component(
        self,
        component: str,
        chunk_type: ChunkType | None = None,
    ) -> list[str]:
        """Get chunk IDs documenting a component.

        Args:
            component: Component name
            chunk_type: Optional filter by chunk type

        Returns:
            List of chunk IDs
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return []

        chunks = []
        for pred in self._graph.predecessors(component_id):
            node_data = self._graph.nodes[pred]
            edge_data = self._graph.edges[pred, component_id]
            if (
                node_data.get("node_type") == NodeType.CHUNK.value
                and edge_data.get("relation_type") == RelationType.DOCUMENTS.value
            ):
                if chunk_type is None or node_data.get("chunk_type") == chunk_type.value:
                    chunks.append(node_data["chunk_id"])

        return chunks

    def find_related_components(
        self,
        component: str,
        max_depth: int = 2,
    ) -> dict[str, int]:
        """Find all related components within a depth.

        Uses BFS to find components connected via any relationship type.

        Args:
            component: Starting component name
            max_depth: Maximum traversal depth

        Returns:
            Dict mapping component name to distance from source
        """
        component_id = f"component:{component}"
        if component_id not in self._graph:
            return {}

        # BFS traversal
        visited: dict[str, int] = {}
        queue: list[tuple[str, int]] = [(component_id, 0)]

        while queue:
            node_id, depth = queue.pop(0)

            if node_id in visited or depth > max_depth:
                continue

            node_data = self._graph.nodes[node_id]
            if node_data.get("node_type") == NodeType.COMPONENT.value:
                name = node_data["name"]
                if name != component:  # Exclude source
                    visited[name] = depth

            if depth < max_depth:
                # Add neighbors
                for neighbor in list(self._graph.successors(node_id)) + list(
                    self._graph.predecessors(node_id)
                ):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

        return visited

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the graph to a dictionary.

        Returns:
            Dict representation suitable for JSON storage
        """
        return {
            "nodes": [
                {"id": node_id, **data}
                for node_id, data in self._graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self._graph.edges(data=True)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComponentGraph":
        """Deserialize a graph from a dictionary.

        Args:
            data: Dict from to_dict()

        Returns:
            Reconstructed ComponentGraph
        """
        graph = cls()

        for node in data.get("nodes", []):
            node_id = node.pop("id")
            graph._graph.add_node(node_id, **node)

        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            graph._graph.add_edge(source, target, **edge)

        return graph

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self._graph)

    def __contains__(self, node_id: str) -> bool:
        """Check if a node ID exists in the graph."""
        return node_id in self._graph
