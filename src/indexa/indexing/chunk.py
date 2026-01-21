"""Normalized chunk representation for indexed documentation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ChunkKind = Literal[
    # Documentation types
    "guide",        # How-to documentation
    "api",          # API reference
    "reference",    # General reference docs
    "example",      # Code examples
    "module",       # Module overview (AGENTS.md)
    "readme",       # Project readme
    # Source code types (Phase 1)
    "source",       # Source code file
    "template",     # HTML/template file
    "stylesheet",   # CSS/SCSS file
    "api_doc",      # API documentation from Compodoc
]


@dataclass
class NormalizedChunk:
    """A single indexed documentation chunk."""

    # Identity
    id: str  # Unique hash: source_id + path + anchor
    source_id: str  # e.g., "agentic_search"

    # Location
    path: str  # Relative path: "docs/GETTING_STARTED.md"
    anchor: str | None  # Section anchor: "installation"

    # Content
    title: str  # Section heading: "Installation"
    content: str  # Full text content

    # Metadata
    kind: ChunkKind  # Document type
    depth: int  # Heading depth (1=H1, 2=H2, etc.)
    is_entrypoint: bool = False  # Marked as high-value doc

    # Extracted features
    headings: list[str] = field(default_factory=list)  # Child headings
    code_blocks: list[str] = field(default_factory=list)  # Language tags
    has_table: bool = False  # Contains markdown table

    # Timestamps
    indexed_at: datetime = field(default_factory=datetime.now)
    file_modified: datetime | None = None

    def to_uri(self) -> str:
        """Generate docs:// URI for this chunk."""
        uri = f"docs://{self.source_id}/section/{self.path}"
        if self.anchor:
            uri += f"#{self.anchor}"
        return uri

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "path": self.path,
            "anchor": self.anchor,
            "title": self.title,
            "content": self.content,
            "kind": self.kind,
            "depth": self.depth,
            "is_entrypoint": self.is_entrypoint,
            "headings": self.headings,
            "code_blocks": self.code_blocks,
            "has_table": self.has_table,
            "indexed_at": self.indexed_at.isoformat(),
            "file_modified": self.file_modified.isoformat() if self.file_modified else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NormalizedChunk":
        """Deserialize from JSON storage."""
        return cls(
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
                datetime.fromisoformat(data["file_modified"]) if data.get("file_modified") else None
            ),
        )
