"""Component adapter - parses MDX files with component metadata."""

import hashlib
import re
from datetime import datetime
from pathlib import Path

import yaml

from indexa.adapters.base import BaseAdapter
from indexa.graph.types import ChunkType
from indexa.indexing.chunk import ChunkKind, NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk


class ComponentAdapter(BaseAdapter):
    """Parse MDX component documentation with frontmatter metadata.

    Extracts component relationships, categories, and classifies sections
    into types (props, examples, variants, etc.).

    Expected frontmatter format:
    ---
    component: Button
    category: Forms
    extends: BaseButton
    uses:
      - Icon
      - Spinner
    variants:
      - IconButton
      - LoadingButton
    related:
      - Link
      - Anchor
    ---
    """

    # YAML frontmatter pattern
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    # Heading pattern: # Title, ## Title, ### Title, etc.
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Code block pattern: ```language
    CODE_BLOCK_PATTERN = re.compile(r"```(\w+)?", re.MULTILINE)

    # Table pattern: | header | header |
    TABLE_PATTERN = re.compile(r"^\|.+\|$", re.MULTILINE)

    # Component reference patterns (JSX tags)
    JSX_COMPONENT_PATTERN = re.compile(r"<([A-Z][a-zA-Z0-9]*)")

    # Import patterns
    IMPORT_PATTERN = re.compile(
        r"import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]"
    )

    # TypeScript interface/type patterns (for props)
    INTERFACE_PATTERN = re.compile(r"interface\s+(\w+Props)")
    TYPE_PATTERN = re.compile(r"type\s+(\w+Props)\s*=")
    PROP_PATTERN = re.compile(r"^\s*(\w+)\s*[?:]", re.MULTILINE)

    SUPPORTED_EXTENSIONS = {".mdx", ".md"}

    # Section title patterns for classification
    SECTION_CLASSIFIERS: dict[ChunkType, list[str]] = {
        ChunkType.PROPS: ["props", "api", "properties", "attributes", "parameters"],
        ChunkType.EXAMPLE: ["example", "usage", "demo", "sample"],
        ChunkType.VARIANT: ["variant", "variation", "style", "size", "color", "theme"],
        ChunkType.ACCESSIBILITY: ["accessibility", "a11y", "aria", "keyboard", "screen reader"],
        ChunkType.STYLING: ["styling", "css", "theming", "customization", "design token"],
        ChunkType.MIGRATION: ["migration", "upgrade", "changelog", "breaking change"],
        ChunkType.BEST_PRACTICES: ["best practice", "guideline", "recommendation", "pattern"],
    }

    def __init__(
        self,
        source_id: str,
        source_root: Path,
        entrypoints: list[str] | None = None,
        default_category: str = "",
    ):
        """Initialize the component adapter.

        Args:
            source_id: Source identifier
            source_root: Root path of the documentation
            entrypoints: High-value entry point paths
            default_category: Default category if not specified in frontmatter
        """
        self.source_id = source_id
        self.source_root = source_root
        self.entrypoints = set(entrypoints or [])
        self.default_category = default_category

    def supports_extension(self, extension: str) -> bool:
        """Check if this adapter supports the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        """Parse an MDX file into component chunks.

        Args:
            file_path: Path to the MDX file

        Returns:
            List of ComponentChunk objects
        """
        relative_path = file_path.relative_to(self.source_root).as_posix()
        content = file_path.read_text(encoding="utf-8")
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Extract frontmatter
        frontmatter = self._parse_frontmatter(content)
        content_without_frontmatter = self._strip_frontmatter(content)

        # Determine document kind
        kind = self._determine_kind(relative_path)
        is_entrypoint = relative_path in self.entrypoints

        # Get component metadata
        component_name = frontmatter.get(
            "component", self._infer_component_name(file_path)
        )
        component_category = frontmatter.get("category", self.default_category)

        # Parse relationships from frontmatter
        extends = frontmatter.get("extends")
        uses = frontmatter.get("uses", [])
        variants = frontmatter.get("variants", [])
        related_to = frontmatter.get("related", [])

        # Also extract relationships from content
        content_uses = self._extract_jsx_components(content_without_frontmatter)
        import_uses = self._extract_imports(content_without_frontmatter)
        all_uses = list(set(uses + content_uses + import_uses))

        # Parse into sections
        sections = self._split_into_sections(content_without_frontmatter)

        chunks: list[NormalizedChunk] = []
        for section in sections:
            chunk = self._create_component_chunk(
                relative_path=relative_path,
                section=section,
                kind=kind,
                is_entrypoint=is_entrypoint,
                file_modified=file_modified,
                component_name=component_name,
                component_category=component_category,
                extends=extends,
                uses=all_uses,
                variants=variants,
                related_to=related_to,
            )
            chunks.append(chunk)

        return chunks

    def _parse_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from content.

        Args:
            content: Full file content

        Returns:
            Parsed frontmatter dict (empty if no frontmatter)
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _strip_frontmatter(self, content: str) -> str:
        """Remove frontmatter from content.

        Args:
            content: Full file content

        Returns:
            Content without frontmatter
        """
        return self.FRONTMATTER_PATTERN.sub("", content)

    def _infer_component_name(self, file_path: Path) -> str:
        """Infer component name from file name.

        Args:
            file_path: Path to the file

        Returns:
            Inferred component name (e.g., "Button" from "Button.mdx")
        """
        name = file_path.stem
        # Convert kebab-case to PascalCase
        if "-" in name:
            return "".join(word.capitalize() for word in name.split("-"))
        return name

    def _extract_jsx_components(self, content: str) -> list[str]:
        """Extract component names from JSX usage.

        Args:
            content: MDX content

        Returns:
            List of component names used in JSX
        """
        components = set()
        for match in self.JSX_COMPONENT_PATTERN.finditer(content):
            name = match.group(1)
            # Filter out common HTML-like names and the current component
            if name not in {"Fragment", "React", "Component", "Provider"}:
                components.add(name)
        return list(components)

    def _extract_imports(self, content: str) -> list[str]:
        """Extract component imports.

        Args:
            content: MDX content

        Returns:
            List of imported component names
        """
        components = []
        for match in self.IMPORT_PATTERN.finditer(content):
            # Named imports: { Button, Icon }
            if match.group(1):
                names = [n.strip().split(" as ")[0] for n in match.group(1).split(",")]
                components.extend(
                    n for n in names if n and n[0].isupper()
                )
            # Default imports: import Button from '...'
            elif match.group(2):
                name = match.group(2)
                if name[0].isupper():
                    components.append(name)
        return components

    def _determine_kind(self, path: str) -> ChunkKind:
        """Determine document type from path."""
        path_lower = path.lower()

        if "readme.md" in path_lower:
            return "readme"
        elif "api" in path_lower or "reference" in path_lower:
            return "api"
        elif "example" in path_lower:
            return "example"
        else:
            return "reference"

    def _classify_chunk_type(self, title: str, content: str) -> ChunkType:
        """Classify a section into a chunk type.

        Args:
            title: Section title
            content: Section content

        Returns:
            ChunkType for this section
        """
        title_lower = title.lower()
        content_lower = content.lower()

        for chunk_type, keywords in self.SECTION_CLASSIFIERS.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return chunk_type
                # Also check first 500 chars of content for context
                if keyword in content_lower[:500]:
                    return chunk_type

        return ChunkType.OVERVIEW

    def _extract_props(self, content: str) -> list[str]:
        """Extract prop names from TypeScript interfaces in content.

        Args:
            content: Section content

        Returns:
            List of prop names
        """
        props = []
        for match in self.PROP_PATTERN.finditer(content):
            prop_name = match.group(1)
            if not prop_name.startswith("_"):  # Skip private props
                props.append(prop_name)
        return props

    def _extract_example_variant(self, title: str) -> str | None:
        """Extract variant name from example section title.

        Args:
            title: Section title

        Returns:
            Variant name or None
        """
        # Patterns like "Primary Example", "Large Size Example"
        title_lower = title.lower()
        if "example" not in title_lower:
            return None

        # Remove "example" and clean up
        variant = title_lower.replace("example", "").strip()
        if variant and len(variant) > 2:
            return variant.title()
        return None

    def _split_into_sections(self, content: str) -> list[dict]:
        """Split markdown content into sections by headings."""
        lines = content.split("\n")
        sections = []
        current_section = {
            "title": "Overview",
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
        anchor = title.lower()
        anchor = re.sub(r"[^\w\s-]", "", anchor)
        anchor = re.sub(r"\s+", "-", anchor)
        return anchor

    def _create_component_chunk(
        self,
        relative_path: str,
        section: dict,
        kind: ChunkKind,
        is_entrypoint: bool,
        file_modified: datetime,
        component_name: str,
        component_category: str,
        extends: str | None,
        uses: list[str],
        variants: list[str],
        related_to: list[str],
    ) -> ComponentChunk:
        """Create a ComponentChunk from a parsed section."""
        content = "\n".join(section["content_lines"])

        # Generate stable ID
        id_source = f"{self.source_id}:{relative_path}:{section['anchor'] or 'root'}"
        chunk_id = hashlib.sha256(id_source.encode()).hexdigest()[:16]

        # Classify this section
        chunk_type = self._classify_chunk_type(section["title"], content)

        # Extract props if this is a props section
        props_mentioned = []
        if chunk_type == ChunkType.PROPS:
            props_mentioned = self._extract_props(content)

        # Extract example variant if applicable
        example_variant = None
        if chunk_type == ChunkType.EXAMPLE:
            example_variant = self._extract_example_variant(section["title"])

        return ComponentChunk(
            # Base NormalizedChunk fields
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
            # ComponentChunk fields
            component_name=component_name,
            component_category=component_category,
            chunk_type=chunk_type,
            extends=extends,
            uses=uses,
            variants=variants,
            related_to=related_to,
            props_mentioned=props_mentioned,
            example_variant=example_variant,
        )
