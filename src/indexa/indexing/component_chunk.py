"""Extended chunk model for UI component documentation."""

from dataclasses import dataclass, field
from datetime import datetime

from indexa.graph.types import ChunkType
from indexa.indexing.chunk import NormalizedChunk


@dataclass
class ComponentChunk(NormalizedChunk):
    """A documentation chunk with component-specific metadata.

    Extends NormalizedChunk to add fields for component relationships,
    categories, and chunk classification (props, examples, variants, etc.).
    """

    # Component identity
    component_name: str = ""  # e.g., "Button"
    component_category: str = ""  # e.g., "Forms"
    chunk_type: ChunkType = ChunkType.OVERVIEW  # What kind of doc is this?

    # Component relationships (extracted from content)
    extends: str | None = None  # Base component this extends
    uses: list[str] = field(default_factory=list)  # Components used/composed
    variants: list[str] = field(default_factory=list)  # Variant names
    related_to: list[str] = field(default_factory=list)  # Similar components

    # Extracted features (component-specific)
    props_mentioned: list[str] = field(default_factory=list)  # Props referenced
    example_variant: str | None = None  # If example chunk, which variant?
    api_signatures: list[str] = field(default_factory=list)  # TypeScript signatures

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        base = super().to_dict()
        base.update({
            "component_name": self.component_name,
            "component_category": self.component_category,
            "chunk_type": self.chunk_type.value,
            "extends": self.extends,
            "uses": self.uses,
            "variants": self.variants,
            "related_to": self.related_to,
            "props_mentioned": self.props_mentioned,
            "example_variant": self.example_variant,
            "api_signatures": self.api_signatures,
        })
        return base

    @classmethod
    def from_dict(cls, data: dict) -> "ComponentChunk":
        """Deserialize from JSON storage."""
        # Parse chunk_type enum
        chunk_type_str = data.get("chunk_type", "overview")
        try:
            chunk_type = ChunkType(chunk_type_str)
        except ValueError:
            chunk_type = ChunkType.OVERVIEW

        return cls(
            # Base NormalizedChunk fields
            id=data["id"],
            source_id=data["source_id"],
            path=data["path"],
            anchor=data.get("anchor"),
            title=data["title"],
            content=data["content"],
            kind=data["kind"],
            depth=data["depth"],
            is_entrypoint=data.get("is_entrypoint", False),
            headings=data.get("headings", []),
            code_blocks=data.get("code_blocks", []),
            has_table=data.get("has_table", False),
            indexed_at=datetime.fromisoformat(data["indexed_at"]),
            file_modified=(
                datetime.fromisoformat(data["file_modified"])
                if data.get("file_modified")
                else None
            ),
            # ComponentChunk fields
            component_name=data.get("component_name", ""),
            component_category=data.get("component_category", ""),
            chunk_type=chunk_type,
            extends=data.get("extends"),
            uses=data.get("uses", []),
            variants=data.get("variants", []),
            related_to=data.get("related_to", []),
            props_mentioned=data.get("props_mentioned", []),
            example_variant=data.get("example_variant"),
            api_signatures=data.get("api_signatures", []),
        )

    @classmethod
    def from_normalized(
        cls,
        chunk: NormalizedChunk,
        component_name: str,
        component_category: str = "",
        chunk_type: ChunkType = ChunkType.OVERVIEW,
    ) -> "ComponentChunk":
        """Create ComponentChunk from a NormalizedChunk.

        Args:
            chunk: Base normalized chunk
            component_name: Component name
            component_category: Category name
            chunk_type: Type of documentation

        Returns:
            New ComponentChunk with base fields copied
        """
        return cls(
            id=chunk.id,
            source_id=chunk.source_id,
            path=chunk.path,
            anchor=chunk.anchor,
            title=chunk.title,
            content=chunk.content,
            kind=chunk.kind,
            depth=chunk.depth,
            is_entrypoint=chunk.is_entrypoint,
            headings=chunk.headings,
            code_blocks=chunk.code_blocks,
            has_table=chunk.has_table,
            indexed_at=chunk.indexed_at,
            file_modified=chunk.file_modified,
            component_name=component_name,
            component_category=component_category,
            chunk_type=chunk_type,
        )

    def is_component_chunk(self) -> bool:
        """Check if this chunk has component metadata."""
        return bool(self.component_name)
