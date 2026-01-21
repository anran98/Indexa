"""Markdown adapter - parses markdown files into normalized chunks."""

import hashlib
import re
from datetime import datetime
from pathlib import Path

from indexa.adapters.base import BaseAdapter
from indexa.indexing.chunk import ChunkKind, NormalizedChunk


class MarkdownAdapter(BaseAdapter):
    """Parse markdown files into searchable chunks."""

    # Heading pattern: # Title, ## Title, ### Title, etc.
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Code block pattern: ```language
    CODE_BLOCK_PATTERN = re.compile(r"```(\w+)?", re.MULTILINE)

    # Table pattern: | header | header |
    TABLE_PATTERN = re.compile(r"^\|.+\|$", re.MULTILINE)

    SUPPORTED_EXTENSIONS = {".md", ".mdx", ".markdown"}

    def __init__(
        self, source_id: str, source_root: Path, entrypoints: list[str] | None = None
    ):
        self.source_id = source_id
        self.source_root = source_root
        self.entrypoints = set(entrypoints or [])

    def supports_extension(self, extension: str) -> bool:
        """Check if this adapter supports the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        """Parse a markdown file into chunks (one per section)."""
        relative_path = file_path.relative_to(self.source_root).as_posix()
        content = file_path.read_text(encoding="utf-8")
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Determine document kind
        kind = self._determine_kind(relative_path)
        is_entrypoint = relative_path in self.entrypoints

        # Parse into sections
        sections = self._split_into_sections(content)

        chunks = []
        for section in sections:
            chunk = self._create_chunk(
                relative_path=relative_path,
                section=section,
                kind=kind,
                is_entrypoint=is_entrypoint,
                file_modified=file_modified,
            )
            chunks.append(chunk)

        return chunks

    def _determine_kind(self, path: str) -> ChunkKind:
        """Determine document type from path."""
        path_lower = path.lower()

        if "agents.md" in path_lower:
            return "module"
        elif "readme.md" in path_lower:
            return "readme"
        elif "api" in path_lower or "reference" in path_lower:
            return "api"
        elif "example" in path_lower:
            return "example"
        elif "getting_started" in path_lower or "quickstart" in path_lower:
            return "guide"
        else:
            return "reference"

    def _split_into_sections(self, content: str) -> list[dict]:
        """Split markdown content into sections by headings."""
        lines = content.split("\n")
        sections = []
        current_section = {
            "title": "Introduction",
            "anchor": None,
            "depth": 1,
            "content_lines": [],
            "headings": [],
            "code_blocks": [],
            "has_table": False,
        }

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(line)

            if heading_match:
                # Save previous section if it has content
                if current_section["content_lines"]:
                    sections.append(current_section)

                # Start new section
                depth = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                anchor = self._generate_anchor(title)

                current_section = {
                    "title": title,
                    "anchor": anchor,
                    "depth": depth,
                    "content_lines": [line],
                    "headings": [],
                    "code_blocks": [],
                    "has_table": False,
                }
            else:
                current_section["content_lines"].append(line)

                # Track code blocks
                code_match = self.CODE_BLOCK_PATTERN.match(line)
                if code_match and code_match.group(1):
                    current_section["code_blocks"].append(code_match.group(1))

                # Track tables
                if self.TABLE_PATTERN.match(line):
                    current_section["has_table"] = True

        # Don't forget the last section
        if current_section["content_lines"]:
            sections.append(current_section)

        return sections

    def _generate_anchor(self, title: str) -> str:
        """Generate URL-friendly anchor from heading."""
        # Lowercase, replace spaces with hyphens, remove special chars
        anchor = title.lower()
        anchor = re.sub(r"[^\w\s-]", "", anchor)
        anchor = re.sub(r"\s+", "-", anchor)
        return anchor

    def _create_chunk(
        self,
        relative_path: str,
        section: dict,
        kind: ChunkKind,
        is_entrypoint: bool,
        file_modified: datetime,
    ) -> NormalizedChunk:
        """Create a NormalizedChunk from a parsed section."""
        content = "\n".join(section["content_lines"])

        # Generate stable ID
        id_source = f"{self.source_id}:{relative_path}:{section['anchor'] or 'root'}"
        chunk_id = hashlib.sha256(id_source.encode()).hexdigest()[:16]

        return NormalizedChunk(
            id=chunk_id,
            source_id=self.source_id,
            path=relative_path,
            anchor=section["anchor"],
            title=section["title"],
            content=content,
            kind=kind,
            depth=section["depth"],
            is_entrypoint=is_entrypoint,
            headings=section["headings"],
            code_blocks=list(set(section["code_blocks"])),
            has_table=section["has_table"],
            file_modified=file_modified,
        )
