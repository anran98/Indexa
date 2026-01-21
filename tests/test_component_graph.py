"""Tests for ComponentGraph."""

import pytest
from indexa.graph.component_graph import ComponentGraph
from indexa.graph.types import ChunkType, NodeType, RelationType


class TestComponentGraph:
    """Tests for ComponentGraph class."""

    def test_init_creates_empty_graph(self):
        """Test that a new graph is empty."""
        graph = ComponentGraph()
        assert len(graph) == 0

    def test_add_component(self):
        """Test adding a component to the graph."""
        graph = ComponentGraph()
        node_id = graph.add_component("Button", category="Forms", description="A button")
        
        assert node_id == "component:Button"
        assert len(graph) == 2  # Component + Category
        assert "component:Button" in graph
        assert "category:Forms" in graph

    def test_add_component_without_category(self):
        """Test adding a component without a category."""
        graph = ComponentGraph()
        node_id = graph.add_component("Button")
        
        assert node_id == "component:Button"
        assert len(graph) == 1  # Only component

    def test_add_category(self):
        """Test adding a category."""
        graph = ComponentGraph()
        node_id = graph.add_category("Forms", description="Form components")
        
        assert node_id == "category:Forms"
        assert "category:Forms" in graph

    def test_add_category_idempotent(self):
        """Test that adding the same category twice doesn't duplicate."""
        graph = ComponentGraph()
        graph.add_category("Forms")
        graph.add_category("Forms")
        
        # Should still only have one category node
        assert graph.list_categories() == ["Forms"]

    def test_add_variant(self, sample_graph: ComponentGraph):
        """Test adding a variant relationship."""
        variants = sample_graph.get_variants("Button")
        assert "IconButton" in variants

    def test_get_base_component(self, sample_graph: ComponentGraph):
        """Test getting the base component of a variant."""
        base = sample_graph.get_base_component("IconButton")
        assert base == "Button"

    def test_get_uses(self, sample_graph: ComponentGraph):
        """Test getting components that a component uses."""
        uses = sample_graph.get_uses("Button")
        assert "Spinner" in uses

    def test_get_used_by(self, sample_graph: ComponentGraph):
        """Test getting components that use a component."""
        used_by = sample_graph.get_used_by("Button")
        assert "Modal" in used_by

    def test_get_related(self, sample_graph: ComponentGraph):
        """Test getting related components."""
        related = sample_graph.get_related("Button")
        assert "Link" in related

    def test_list_components(self, sample_graph: ComponentGraph):
        """Test listing all components."""
        components = sample_graph.list_components()
        assert set(components) == {"Button", "IconButton", "Modal", "Spinner", "Link"}

    def test_list_categories(self, sample_graph: ComponentGraph):
        """Test listing all categories."""
        categories = sample_graph.list_categories()
        assert set(categories) == {"Forms", "Feedback", "Navigation"}

    def test_get_components_in_category(self, sample_graph: ComponentGraph):
        """Test getting components in a category."""
        forms = sample_graph.get_components_in_category("Forms")
        assert set(forms) == {"Button", "IconButton"}

    def test_get_component_data(self, sample_graph: ComponentGraph):
        """Test getting component data."""
        data = sample_graph.get_component("Button")
        assert data is not None
        assert data["name"] == "Button"
        assert data["category"] == "Forms"

    def test_get_nonexistent_component(self, sample_graph: ComponentGraph):
        """Test getting a component that doesn't exist."""
        data = sample_graph.get_component("NonExistent")
        assert data is None

    def test_find_related_components(self, sample_graph: ComponentGraph):
        """Test finding related components within depth."""
        related = sample_graph.find_related_components("Button", max_depth=2)
        
        # Should include components connected through relationships
        assert "IconButton" in related  # variant
        assert "Spinner" in related  # uses
        assert "Modal" in related  # used_by

    def test_add_chunk(self, sample_graph: ComponentGraph):
        """Test adding a chunk to the graph."""
        chunk_id = sample_graph.add_chunk(
            chunk_id="button_props",
            component_name="Button",
            chunk_type=ChunkType.PROPS,
        )
        
        assert chunk_id == "chunk:button_props"
        chunks = sample_graph.get_chunks_for_component("Button")
        assert "button_props" in chunks

    def test_get_chunks_filtered_by_type(self, sample_graph: ComponentGraph):
        """Test getting chunks filtered by type."""
        # Add different chunk types
        sample_graph.add_chunk("button_props", "Button", ChunkType.PROPS)
        sample_graph.add_chunk("button_example", "Button", ChunkType.EXAMPLE)
        sample_graph.add_chunk("button_a11y", "Button", ChunkType.ACCESSIBILITY)
        
        # Filter by type
        props_chunks = sample_graph.get_chunks_for_component("Button", ChunkType.PROPS)
        assert props_chunks == ["button_props"]
        
        all_chunks = sample_graph.get_chunks_for_component("Button")
        assert len(all_chunks) == 3

    def test_serialization(self, sample_graph: ComponentGraph):
        """Test graph serialization and deserialization."""
        data = sample_graph.to_dict()
        
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0
        
        # Deserialize
        restored = ComponentGraph.from_dict(data)
        
        assert restored.list_components() == sample_graph.list_components()
        assert restored.list_categories() == sample_graph.list_categories()
        assert restored.get_variants("Button") == sample_graph.get_variants("Button")
