"""Extended chunk model for source code files."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from indexa.graph.types import ChunkType
from indexa.indexing.chunk import ChunkKind, NormalizedChunk


@dataclass
class SourceChunk(NormalizedChunk):
    """A documentation chunk for source code files.

    Extends NormalizedChunk with source-code-specific metadata
    including language, symbols, and file relationships.
    """

    language: str = ""
    file_type: str = ""

    class_name: str | None = None
    decorators: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    selector: str | None = None
    template_url: str | None = None
    style_urls: list[str] = field(default_factory=list)

    related_files: list[str] = field(default_factory=list)
    component_name: str = ""

    symbols_extracted: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        base = super().to_dict()
        base.update({
            "language": self.language,
            "file_type": self.file_type,
            "class_name": self.class_name,
            "decorators": self.decorators,
            "exports": self.exports,
            "imports": self.imports,
            "selector": self.selector,
            "template_url": self.template_url,
            "style_urls": self.style_urls,
            "related_files": self.related_files,
            "component_name": self.component_name,
            "symbols_extracted": self.symbols_extracted,
        })
        return base

    @classmethod
    def from_dict(cls, data: dict) -> "SourceChunk":
        """Deserialize from JSON storage."""
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            path=data["path"],
            anchor=data.get("anchor"),
            title=data["title"],
            content=data["content"],
            kind=data["kind"],
            depth=data.get("depth", 1),
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
            language=data.get("language", ""),
            file_type=data.get("file_type", ""),
            class_name=data.get("class_name"),
            decorators=data.get("decorators", []),
            exports=data.get("exports", []),
            imports=data.get("imports", []),
            selector=data.get("selector"),
            template_url=data.get("template_url"),
            style_urls=data.get("style_urls", []),
            related_files=data.get("related_files", []),
            component_name=data.get("component_name", ""),
            symbols_extracted=data.get("symbols_extracted", []),
        )

    def is_source_chunk(self) -> bool:
        """Check if this chunk has source metadata."""
        return bool(self.language)
