"""Tests for ComponentAdapter."""

import pytest
from pathlib import Path

from indexa.adapters.component import ComponentAdapter
from indexa.graph.types import ChunkType
from indexa.indexing.component_chunk import ComponentChunk


class TestComponentAdapter:
    """Tests for ComponentAdapter class."""

    def test_supports_mdx(self):
        """Test that adapter supports .mdx files."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        assert adapter.supports_extension(".mdx")
        assert adapter.supports_extension(".MDX")
        assert adapter.supports_extension(".md")

    def test_parse_frontmatter(self):
        """Test frontmatter parsing."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        
        content = '''---
component: Button
category: Forms
uses:
  - Icon
---

# Button content
'''
        frontmatter = adapter._parse_frontmatter(content)
        
        assert frontmatter["component"] == "Button"
        assert frontmatter["category"] == "Forms"
        assert frontmatter["uses"] == ["Icon"]

    def test_strip_frontmatter(self):
        """Test frontmatter stripping."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        
        content = '''---
component: Button
---

# Button content
'''
        stripped = adapter._strip_frontmatter(content)
        
        assert "---" not in stripped
        assert "# Button content" in stripped

    def test_infer_component_name_from_filename(self):
        """Test component name inference from filename."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        
        # PascalCase filename
        assert adapter._infer_component_name(Path("/tmp/Button.mdx")) == "Button"
        
        # kebab-case filename
        assert adapter._infer_component_name(Path("/tmp/icon-button.mdx")) == "IconButton"

    def test_extract_jsx_components(self):
        """Test JSX component extraction."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        
        content = '''
```tsx
<Button onClick={handleClick}>
  <Icon name="star" />
  Click me
</Button>
<Modal isOpen={true}>
  <Content />
</Modal>
```
'''
        components = adapter._extract_jsx_components(content)
        
        assert "Button" in components
        assert "Icon" in components
        assert "Modal" in components
        assert "Content" in components

    def test_classify_chunk_type_from_title(self):
        """Test chunk type classification from section title."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        
        assert adapter._classify_chunk_type("Props", "") == ChunkType.PROPS
        assert adapter._classify_chunk_type("API Reference", "") == ChunkType.PROPS
        assert adapter._classify_chunk_type("Example Usage", "") == ChunkType.EXAMPLE
        assert adapter._classify_chunk_type("Accessibility", "") == ChunkType.ACCESSIBILITY
        assert adapter._classify_chunk_type("Styling", "") == ChunkType.STYLING
        assert adapter._classify_chunk_type("Overview", "") == ChunkType.OVERVIEW

    def test_parse_file_creates_component_chunks(self, tmp_mdx_file: Path):
        """Test that parse_file creates ComponentChunk objects."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_mdx_file.parent,
        )
        
        chunks = adapter.parse_file(tmp_mdx_file)
        
        assert len(chunks) > 0
        assert all(isinstance(c, ComponentChunk) for c in chunks)

    def test_parse_file_extracts_component_name(self, tmp_mdx_file: Path):
        """Test that component name is extracted from frontmatter."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_mdx_file.parent,
        )
        
        chunks = adapter.parse_file(tmp_mdx_file)
        
        for chunk in chunks:
            assert chunk.component_name == "TestButton"

    def test_parse_file_extracts_category(self, tmp_mdx_file: Path):
        """Test that category is extracted from frontmatter."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_mdx_file.parent,
        )
        
        chunks = adapter.parse_file(tmp_mdx_file)
        
        for chunk in chunks:
            assert chunk.component_category == "Forms"

    def test_parse_file_extracts_relationships(self, tmp_mdx_file: Path):
        """Test that relationships are extracted."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_mdx_file.parent,
        )
        
        chunks = adapter.parse_file(tmp_mdx_file)
        
        # All chunks should have the same relationships (from frontmatter)
        first_chunk = chunks[0]
        assert first_chunk.extends == "BaseButton"
        assert "Icon" in first_chunk.uses
        assert "PrimaryButton" in first_chunk.variants
        assert "Link" in first_chunk.related_to

    def test_parse_file_classifies_sections(self, tmp_mdx_file: Path):
        """Test that sections are classified into chunk types."""
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_mdx_file.parent,
        )
        
        chunks = adapter.parse_file(tmp_mdx_file)
        chunk_types = {c.title: c.chunk_type for c in chunks}
        
        # Check that specific sections got correct types
        assert chunk_types.get("Props") == ChunkType.PROPS
        assert chunk_types.get("Example") == ChunkType.EXAMPLE
        assert chunk_types.get("Accessibility") == ChunkType.ACCESSIBILITY

    def test_default_category_used_when_not_specified(self, tmp_path: Path):
        """Test that default_category is used when frontmatter doesn't specify."""
        mdx_content = '''---
component: SimpleButton
---

# SimpleButton

A simple button.
'''
        mdx_file = tmp_path / "SimpleButton.mdx"
        mdx_file.write_text(mdx_content, encoding="utf-8")
        
        adapter = ComponentAdapter(
            source_id="test",
            source_root=tmp_path,
            default_category="General",
        )
        
        chunks = adapter.parse_file(mdx_file)
        
        for chunk in chunks:
            assert chunk.component_category == "General"
