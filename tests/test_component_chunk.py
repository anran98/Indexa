"""Tests for ComponentChunk."""

import pytest
from datetime import datetime

from indexa.graph.types import ChunkType
from indexa.indexing.chunk import NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk


class TestComponentChunk:
    """Tests for ComponentChunk class."""

    def test_create_component_chunk(self):
        """Test creating a ComponentChunk."""
        chunk = ComponentChunk(
            id="test_1",
            source_id="ui",
            path="Button.mdx",
            anchor="props",
            title="Props",
            content="Button props documentation.",
            kind="reference",
            depth=2,
            indexed_at=datetime.now(),
            component_name="Button",
            component_category="Forms",
            chunk_type=ChunkType.PROPS,
        )
        
        assert chunk.component_name == "Button"
        assert chunk.component_category == "Forms"
        assert chunk.chunk_type == ChunkType.PROPS

    def test_default_values(self):
        """Test default values for ComponentChunk."""
        chunk = ComponentChunk(
            id="test_1",
            source_id="ui",
            path="Button.mdx",
            anchor=None,
            title="Button",
            content="Content",
            kind="reference",
            depth=1,
            indexed_at=datetime.now(),
        )
        
        assert chunk.component_name == ""
        assert chunk.component_category == ""
        assert chunk.chunk_type == ChunkType.OVERVIEW
        assert chunk.extends is None
        assert chunk.uses == []
        assert chunk.variants == []
        assert chunk.related_to == []
        assert chunk.props_mentioned == []
        assert chunk.example_variant is None

    def test_to_dict(self, sample_component_chunk: ComponentChunk):
        """Test serialization to dict."""
        data = sample_component_chunk.to_dict()
        
        # Base fields
        assert data["id"] == "button_overview"
        assert data["source_id"] == "ui_components"
        assert data["title"] == "Overview"
        
        # Component fields
        assert data["component_name"] == "Button"
        assert data["component_category"] == "Forms"
        assert data["chunk_type"] == "overview"
        assert data["uses"] == ["Spinner"]
        assert data["variants"] == ["IconButton", "LoadingButton"]
        assert data["related_to"] == ["Link", "Anchor"]

    def test_from_dict(self, sample_component_chunk: ComponentChunk):
        """Test deserialization from dict."""
        data = sample_component_chunk.to_dict()
        restored = ComponentChunk.from_dict(data)
        
        assert restored.id == sample_component_chunk.id
        assert restored.component_name == sample_component_chunk.component_name
        assert restored.component_category == sample_component_chunk.component_category
        assert restored.chunk_type == sample_component_chunk.chunk_type
        assert restored.uses == sample_component_chunk.uses
        assert restored.variants == sample_component_chunk.variants

    def test_from_dict_invalid_chunk_type(self):
        """Test deserialization with invalid chunk type falls back to OVERVIEW."""
        data = {
            "id": "test",
            "source_id": "ui",
            "path": "test.mdx",
            "anchor": None,
            "title": "Test",
            "content": "Content",
            "kind": "reference",
            "depth": 1,
            "indexed_at": datetime.now().isoformat(),
            "chunk_type": "invalid_type",  # Invalid
        }
        
        restored = ComponentChunk.from_dict(data)
        
        assert restored.chunk_type == ChunkType.OVERVIEW

    def test_from_normalized(self, sample_chunk: NormalizedChunk):
        """Test creating ComponentChunk from NormalizedChunk."""
        component_chunk = ComponentChunk.from_normalized(
            sample_chunk,
            component_name="Button",
            component_category="Forms",
            chunk_type=ChunkType.PROPS,
        )
        
        # Base fields should be preserved
        assert component_chunk.id == sample_chunk.id
        assert component_chunk.source_id == sample_chunk.source_id
        assert component_chunk.title == sample_chunk.title
        assert component_chunk.content == sample_chunk.content
        
        # Component fields should be set
        assert component_chunk.component_name == "Button"
        assert component_chunk.component_category == "Forms"
        assert component_chunk.chunk_type == ChunkType.PROPS

    def test_is_component_chunk(self):
        """Test is_component_chunk method."""
        # With component name
        chunk_with_name = ComponentChunk(
            id="test",
            source_id="ui",
            path="test.mdx",
            anchor=None,
            title="Test",
            content="Content",
            kind="reference",
            depth=1,
            indexed_at=datetime.now(),
            component_name="Button",
        )
        assert chunk_with_name.is_component_chunk()
        
        # Without component name
        chunk_without_name = ComponentChunk(
            id="test",
            source_id="ui",
            path="test.mdx",
            anchor=None,
            title="Test",
            content="Content",
            kind="reference",
            depth=1,
            indexed_at=datetime.now(),
            component_name="",
        )
        assert not chunk_without_name.is_component_chunk()

    def test_inherits_from_normalized_chunk(self):
        """Test that ComponentChunk inherits from NormalizedChunk."""
        chunk = ComponentChunk(
            id="test",
            source_id="ui",
            path="test.mdx",
            anchor="section",
            title="Test",
            content="Content",
            kind="reference",
            depth=2,
            indexed_at=datetime.now(),
            component_name="Button",
        )
        
        assert isinstance(chunk, NormalizedChunk)
        
        # Should have inherited methods
        uri = chunk.to_uri()
        assert uri == "docs://ui/section/test.mdx#section"
