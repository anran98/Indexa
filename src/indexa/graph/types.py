"""Type definitions for the component graph."""

from enum import Enum
from typing import TypedDict


class NodeType(str, Enum):
    """Types of nodes in the component graph."""

    COMPONENT = "component"  # UI component (Button, Modal, etc.)
    CATEGORY = "category"  # Component category (Forms, Layout, etc.)
    PROP = "prop"  # Component prop/API
    CHUNK = "chunk"  # Documentation chunk
    # Phase 1: Source code nodes
    SOURCE_FILE = "source_file"  # Source code file node


class RelationType(str, Enum):
    """Types of relationships between nodes."""

    # Component → Category
    BELONGS_TO = "belongs_to"  # Button BELONGS_TO Forms

    # Component → Component
    HAS_VARIANT = "has_variant"  # Button HAS_VARIANT IconButton
    EXTENDS = "extends"  # IconButton EXTENDS Button
    USES = "uses"  # Modal USES Button (composition)
    RELATED_TO = "related_to"  # Tooltip RELATED_TO Popover (similar purpose)

    # Component → Prop
    HAS_PROP = "has_prop"  # Button HAS_PROP onClick

    # Chunk → Component/Category
    DOCUMENTS = "documents"  # Chunk DOCUMENTS Button

    # Phase 1: Source file relationships
    HAS_TEMPLATE = "has_template"      # Component → Template file
    HAS_STYLESHEET = "has_stylesheet"  # Component → Stylesheet file
    HAS_SOURCE = "has_source"          # Component → Source file
    IMPORTS = "imports"                # File → Imported module
    REFERENCES = "references"          # Template → Used component


class ChunkType(str, Enum):
    """Types of documentation chunks for components."""

    OVERVIEW = "overview"  # Component overview/introduction
    PROPS = "props"  # Props/API documentation
    EXAMPLE = "example"  # Usage example
    VARIANT = "variant"  # Specific variant documentation
    ACCESSIBILITY = "accessibility"  # A11y guidelines
    STYLING = "styling"  # Theming/CSS documentation
    MIGRATION = "migration"  # Migration guide between versions
    BEST_PRACTICES = "best_practices"  # Recommended usage patterns
    # Phase 1: Compodoc types
    INPUTS = "inputs"           # @Input() properties
    OUTPUTS = "outputs"         # @Output() events
    METHODS = "methods"         # Public methods
    # Phase 1: Source types
    SOURCE = "source"           # Component class source
    TEMPLATE = "template"       # Component template
    STYLESHEET = "stylesheet"   # Component styles


class NodeData(TypedDict, total=False):
    """Data stored on graph nodes."""

    node_type: str
    name: str
    description: str
    # For components
    category: str
    # For chunks
    chunk_id: str
    chunk_type: str
    # For categories
    parent_category: str | None


class EdgeData(TypedDict, total=False):
    """Data stored on graph edges."""

    relation_type: str
    weight: float  # Relationship strength (0-1)
    bidirectional: bool
