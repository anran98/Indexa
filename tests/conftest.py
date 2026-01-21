"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from datetime import datetime

from indexa.indexing.chunk import NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk
from indexa.graph.types import ChunkType
from indexa.graph.component_graph import ComponentGraph


@pytest.fixture
def sample_chunk() -> NormalizedChunk:
    """Create a sample NormalizedChunk for testing."""
    return NormalizedChunk(
        id="test_chunk_1",
        source_id="test_source",
        path="docs/test.md",
        anchor="introduction",
        title="Introduction",
        content="# Introduction\n\nThis is a test document.",
        kind="guide",
        depth=1,
        is_entrypoint=True,
        headings=["Introduction"],
        code_blocks=["python"],
        has_table=False,
        indexed_at=datetime.now(),
        file_modified=datetime.now(),
    )


@pytest.fixture
def sample_component_chunk() -> ComponentChunk:
    """Create a sample ComponentChunk for testing."""
    return ComponentChunk(
        id="button_overview",
        source_id="ui_components",
        path="Button.mdx",
        anchor="overview",
        title="Overview",
        content="## Overview\n\nThe Button component is for user interactions.",
        kind="reference",
        depth=2,
        is_entrypoint=False,
        headings=[],
        code_blocks=["tsx"],
        has_table=False,
        indexed_at=datetime.now(),
        file_modified=datetime.now(),
        component_name="Button",
        component_category="Forms",
        chunk_type=ChunkType.OVERVIEW,
        extends=None,
        uses=["Spinner"],
        variants=["IconButton", "LoadingButton"],
        related_to=["Link", "Anchor"],
        props_mentioned=["onClick", "disabled"],
        example_variant=None,
        api_signatures=[],
    )


@pytest.fixture
def sample_graph() -> ComponentGraph:
    """Create a sample ComponentGraph for testing."""
    graph = ComponentGraph()
    
    # Add components
    graph.add_component("Button", category="Forms", description="User interaction")
    graph.add_component("IconButton", category="Forms", description="Icon-only button")
    graph.add_component("Modal", category="Feedback", description="Dialog overlay")
    graph.add_component("Spinner", category="Feedback", description="Loading indicator")
    graph.add_component("Link", category="Navigation", description="Hyperlink")  # Added
    
    # Add relationships
    graph.add_variant("Button", "IconButton")
    graph.add_uses("Button", "Spinner")
    graph.add_uses("Modal", "Button")
    graph.add_related("Button", "Link")
    
    return graph


@pytest.fixture
def tmp_mdx_file(tmp_path: Path) -> Path:
    """Create a temporary MDX file for testing the adapter."""
    mdx_content = '''---
component: TestButton
category: Forms
extends: BaseButton
uses:
  - Icon
variants:
  - PrimaryButton
related:
  - Link
---

# TestButton

A test button component.

## Props

| Prop | Type | Description |
|------|------|-------------|
| onClick | function | Click handler |
| disabled | boolean | Disable state |

```typescript
interface TestButtonProps {
  onClick?: () => void;
  disabled?: boolean;
}
```

## Example

Basic usage example.

```tsx
<TestButton onClick={() => alert('clicked')}>
  Click me
</TestButton>
```

## Accessibility

Accessibility guidelines for the button.
'''
    mdx_file = tmp_path / "TestButton.mdx"
    mdx_file.write_text(mdx_content, encoding="utf-8")
    return mdx_file
