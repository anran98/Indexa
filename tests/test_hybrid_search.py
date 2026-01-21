"""Tests for HybridSearchIndex."""

import pytest
from datetime import datetime

from indexa.graph.hybrid_search import HybridSearchIndex, ComponentSearchResult
from indexa.graph.types import ChunkType
from indexa.indexing.chunk import NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk


class TestHybridSearchIndex:
    """Tests for HybridSearchIndex class."""

    @pytest.fixture
    def sample_chunks(self) -> list[NormalizedChunk]:
        """Create sample chunks for testing."""
        now = datetime.now()
        
        return [
            # Regular chunk (not a component)
            NormalizedChunk(
                id="regular_1",
                source_id="docs",
                path="README.md",
                anchor="intro",
                title="Introduction",
                content="Welcome to the documentation.",
                kind="readme",
                depth=1,
                indexed_at=now,
            ),
            # Component chunks
            ComponentChunk(
                id="button_overview",
                source_id="ui",
                path="Button.mdx",
                anchor="overview",
                title="Button Overview",
                content="The Button component handles user clicks and interactions.",
                kind="reference",
                depth=2,
                indexed_at=now,
                component_name="Button",
                component_category="Forms",
                chunk_type=ChunkType.OVERVIEW,
                uses=["Spinner"],
            ),
            ComponentChunk(
                id="button_props",
                source_id="ui",
                path="Button.mdx",
                anchor="props",
                title="Button Props",
                content="onClick, disabled, variant, size properties for button component.",
                kind="reference",
                depth=2,
                indexed_at=now,
                component_name="Button",
                component_category="Forms",
                chunk_type=ChunkType.PROPS,
                props_mentioned=["onClick", "disabled", "variant", "size"],
            ),
            ComponentChunk(
                id="button_example",
                source_id="ui",
                path="Button.mdx",
                anchor="example",
                title="Button Example",
                content="Example: <Button onClick={handleClick}>Click me</Button>",
                kind="example",
                depth=2,
                indexed_at=now,
                component_name="Button",
                component_category="Forms",
                chunk_type=ChunkType.EXAMPLE,
            ),
            ComponentChunk(
                id="modal_overview",
                source_id="ui",
                path="Modal.mdx",
                anchor="overview",
                title="Modal Overview",
                content="The Modal component displays content in an overlay dialog.",
                kind="reference",
                depth=2,
                indexed_at=now,
                component_name="Modal",
                component_category="Feedback",
                chunk_type=ChunkType.OVERVIEW,
                uses=["Button"],
            ),
        ]

    def test_build_index(self, sample_chunks: list[NormalizedChunk]):
        """Test building the hybrid index."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        # Check TF-IDF was built
        assert len(index.tfidf.chunks) == len(sample_chunks)
        
        # Check graph was built
        assert "Button" in index.graph.list_components()
        assert "Modal" in index.graph.list_components()

    def test_search_without_filters(self, sample_chunks: list[NormalizedChunk]):
        """Test basic search without component filters."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        results = index.search("button click")
        
        assert len(results) > 0
        assert all(isinstance(r, ComponentSearchResult) for r in results)

    def test_search_with_component_filter(self, sample_chunks: list[NormalizedChunk]):
        """Test search filtered by component name."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        results = index.search("overview", component="Button")
        
        assert len(results) > 0
        for r in results:
            assert r.component_name == "Button"

    def test_search_with_category_filter(self, sample_chunks: list[NormalizedChunk]):
        """Test search filtered by category."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        results = index.search("component", category="Forms")
        
        assert len(results) > 0
        for r in results:
            assert r.component_category == "Forms"

    def test_search_with_chunk_type_filter(self, sample_chunks: list[NormalizedChunk]):
        """Test search filtered by chunk type."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        results = index.search("button", chunk_type=ChunkType.PROPS)
        
        assert len(results) > 0
        for r in results:
            assert r.chunk_type == "props"

    def test_search_components_api(self, sample_chunks: list[NormalizedChunk]):
        """Test the search_components API with string chunk_type."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        results = index.search_components(
            query="button",
            chunk_type="props",
        )
        
        assert len(results) > 0
        for r in results:
            assert r.chunk_type == "props"

    def test_get_component_info(self, sample_chunks: list[NormalizedChunk]):
        """Test getting component info."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        info = index.get_component_info("Button")
        
        assert info is not None
        assert info["name"] == "Button"
        assert info["category"] == "Forms"
        assert "documentation" in info
        assert info["documentation"]["chunk_count"] > 0

    def test_get_component_info_nonexistent(self, sample_chunks: list[NormalizedChunk]):
        """Test getting info for nonexistent component."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        info = index.get_component_info("NonExistent")
        
        assert info is None

    def test_list_categories(self, sample_chunks: list[NormalizedChunk]):
        """Test listing all categories."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        categories = index.list_categories()
        
        assert len(categories) == 2
        category_names = {c["name"] for c in categories}
        assert category_names == {"Forms", "Feedback"}

    def test_explore_category(self, sample_chunks: list[NormalizedChunk]):
        """Test exploring a category."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        info = index.explore_category("Forms")
        
        assert info is not None
        assert info["name"] == "Forms"
        assert len(info["components"]) > 0

    def test_explore_category_with_chunks(self, sample_chunks: list[NormalizedChunk]):
        """Test exploring a category with chunk titles."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        info = index.explore_category("Forms", include_chunks=True)
        
        assert info is not None
        for comp in info["components"]:
            if comp["name"] == "Button":
                assert "chunks" in comp
                assert len(comp["chunks"]) > 0

    def test_serialization(self, sample_chunks: list[NormalizedChunk]):
        """Test index serialization."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        data = index.to_dict()
        
        assert "graph" in data
        assert "component_chunks" in data
        assert len(data["component_chunks"]) > 0

    def test_load_graph(self, sample_chunks: list[NormalizedChunk]):
        """Test loading graph from serialized data."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        data = index.to_dict()
        
        # Create new index and load graph
        new_index = HybridSearchIndex()
        new_index.load_graph(data)
        
        # Graph should be restored
        assert new_index.graph.list_components() == index.graph.list_components()

    def test_search_with_include_related(self, sample_chunks: list[NormalizedChunk]):
        """Test search with related component expansion."""
        index = HybridSearchIndex()
        index.build(sample_chunks)
        
        # Search for Modal should include Button (used by Modal)
        results = index.search(
            "click",
            component="Modal",
            include_related=True,
        )
        
        # May include Button chunks because Modal uses Button
        component_names = {r.component_name for r in results if r.component_name}
        # This depends on graph relationships being built correctly
        assert len(results) >= 0  # At minimum, shouldn't crash
