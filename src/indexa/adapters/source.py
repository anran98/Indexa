"""Source adapter - parses source code files into chunks."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import Enum
from pathlib import Path

from indexa.adapters.base import BaseAdapter
from indexa.graph.types import ChunkType
from indexa.indexing.chunk import ChunkKind, NormalizedChunk
from indexa.indexing.source_chunk import SourceChunk


class ChunkStrategy(str, Enum):
    FILE = "file"
    SYMBOL = "symbol"
    HYBRID = "hybrid"


class SourceAdapter(BaseAdapter):
    """Parse source code files into SourceChunks."""

    LANGUAGE_EXTENSIONS = {
        "typescript": {".ts", ".tsx"},
        "javascript": {".js", ".jsx"},
        "html": {".html", ".htm"},
        "scss": {".scss", ".sass", ".css"},
        "python": {".py"},
    }

    FILE_TYPE_PATTERNS = {
        r"\.component\.ts$": "component",
        r"\.service\.ts$": "service",
        r"\.module\.ts$": "module",
        r"\.directive\.ts$": "directive",
        r"\.pipe\.ts$": "pipe",
        r"\.guard\.ts$": "guard",
        r"\.interceptor\.ts$": "interceptor",
        r"\.component\.html$": "template",
        r"\.component\.scss$": "stylesheet",
        r"\.spec\.ts$": "test",
        r"\.test\.ts$": "test",
    }

    PATTERNS = {
        "typescript": {
            "class": re.compile(
                r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
                re.MULTILINE
            ),
            "function": re.compile(
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
                re.MULTILINE
            ),
            "interface": re.compile(
                r"(?:export\s+)?interface\s+(\w+)",
                re.MULTILINE
            ),
            "decorator": re.compile(
                r"@(\w+)\s*\(",
                re.MULTILINE
            ),
            "import": re.compile(
                r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                re.MULTILINE
            ),
            "component_decorator": re.compile(
                r"@Component\s*\(\s*\{([^}]+)\}\s*\)",
                re.DOTALL
            ),
            "selector": re.compile(
                r"selector\s*:\s*['\"]([^'\"]+)['\"]"
            ),
            "template_url": re.compile(
                r"templateUrl\s*:\s*['\"]([^'\"]+)['\"]"
            ),
            "style_urls": re.compile(
                r"styleUrls\s*:\s*\[(.*?)\]",
                re.DOTALL
            ),
        },
        "html": {
            "component_ref": re.compile(
                r"<([a-z]+-[a-z][a-z0-9-]*)",
                re.IGNORECASE
            ),
            "angular_component": re.compile(
                r"<(app-[a-z][a-z0-9-]*|tds-[a-z][a-z0-9-]*)",
                re.IGNORECASE
            ),
        },
    }

    def __init__(
        self,
        source_id: str,
        source_root: Path,
        languages: list[str] | None = None,
        chunk_strategy: ChunkStrategy | str = ChunkStrategy.FILE,
        link_related_files: bool = True,
        extract_symbols: bool = True,
        entrypoints: list[str] | None = None,
    ):
        self.source_id = source_id
        self.source_root = source_root
        self.languages = languages or list(self.LANGUAGE_EXTENSIONS.keys())
        self.chunk_strategy = (
            ChunkStrategy(chunk_strategy)
            if isinstance(chunk_strategy, str)
            else chunk_strategy
        )
        self.link_related_files = link_related_files
        self.extract_symbols = extract_symbols
        self.entrypoints = set(entrypoints or [])

        self._supported_extensions: set[str] = set()
        for lang in self.languages:
            if lang in self.LANGUAGE_EXTENSIONS:
                self._supported_extensions.update(self.LANGUAGE_EXTENSIONS[lang])

    def supports_extension(self, extension: str) -> bool:
        return extension.lower() in self._supported_extensions

    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        extension = file_path.suffix.lower()
        if extension not in self._supported_extensions:
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return []

        relative_path = file_path.relative_to(self.source_root).as_posix()
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
        language = self._detect_language(extension)
        file_type = self._detect_file_type(relative_path)

        metadata = self._extract_metadata(content, language)
        component_name = self._infer_component_name(file_path, metadata)

        related_files = []
        if self.link_related_files:
            related_files = self._find_related_files(file_path)

        if self.chunk_strategy == ChunkStrategy.FILE:
            return [self._create_file_chunk(
                relative_path=relative_path,
                content=content,
                language=language,
                file_type=file_type,
                file_modified=file_modified,
                metadata=metadata,
                component_name=component_name,
                related_files=related_files,
            )]
        elif self.chunk_strategy == ChunkStrategy.SYMBOL:
            chunks = self._create_symbol_chunks(
                relative_path=relative_path,
                content=content,
                language=language,
                file_type=file_type,
                file_modified=file_modified,
                metadata=metadata,
                component_name=component_name,
            )
            return list(chunks)
        else:
            return [self._create_file_chunk(
                relative_path=relative_path,
                content=content,
                language=language,
                file_type=file_type,
                file_modified=file_modified,
                metadata=metadata,
                component_name=component_name,
                related_files=related_files,
            )]

    def _detect_language(self, extension: str) -> str:
        for lang, exts in self.LANGUAGE_EXTENSIONS.items():
            if extension in exts:
                return lang
        return "unknown"

    def _detect_file_type(self, path: str) -> str:
        for pattern, file_type in self.FILE_TYPE_PATTERNS.items():
            if re.search(pattern, path):
                return file_type
        return "source"

    def _extract_metadata(self, content: str, language: str) -> dict:
        metadata = {
            "classes": [],
            "functions": [],
            "interfaces": [],
            "decorators": [],
            "imports": [],
            "selector": None,
            "template_url": None,
            "style_urls": [],
            "component_refs": [],
        }

        patterns = self.PATTERNS.get(language, {})

        if "class" in patterns:
            metadata["classes"] = patterns["class"].findall(content)

        if "function" in patterns:
            metadata["functions"] = patterns["function"].findall(content)

        if "interface" in patterns:
            metadata["interfaces"] = patterns["interface"].findall(content)

        if "decorator" in patterns:
            metadata["decorators"] = list(set(patterns["decorator"].findall(content)))

        if "import" in patterns:
            metadata["imports"] = patterns["import"].findall(content)

        if "component_decorator" in patterns:
            comp_match = patterns["component_decorator"].search(content)
            if comp_match:
                comp_content = comp_match.group(1)

                sel_match = patterns["selector"].search(comp_content)
                if sel_match:
                    metadata["selector"] = sel_match.group(1)

                tpl_match = patterns["template_url"].search(comp_content)
                if tpl_match:
                    metadata["template_url"] = tpl_match.group(1)

                style_match = patterns["style_urls"].search(comp_content)
                if style_match:
                    style_content = style_match.group(1)
                    metadata["style_urls"] = re.findall(r"['\"]([^'\"]+)['\"]", style_content)

        if "angular_component" in patterns:
            refs = patterns["angular_component"].findall(content)
            metadata["component_refs"] = [self._kebab_to_pascal(r) for r in refs]

        return metadata

    def _infer_component_name(self, file_path: Path, metadata: dict) -> str:
        if metadata["classes"]:
            class_name = metadata["classes"][0]
            for suffix in ["Component", "Service", "Module", "Directive", "Pipe"]:
                if class_name.endswith(suffix):
                    return class_name[:-len(suffix)]
            return class_name

        stem = file_path.stem
        for suffix in [".component", ".service", ".module", ".directive", ".pipe"]:
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
                break

        return self._kebab_to_pascal(stem)

    def _kebab_to_pascal(self, name: str) -> str:
        return "".join(word.capitalize() for word in name.split("-"))

    def _find_related_files(self, file_path: Path) -> list[str]:
        related = []
        stem = file_path.stem
        parent = file_path.parent

        base_pattern = None
        for suffix in [".component", ".directive"]:
            if stem.endswith(suffix):
                base_pattern = stem
                break

        if base_pattern:
            for ext in [".ts", ".html", ".scss", ".css", ".spec.ts"]:
                related_path = parent / f"{base_pattern}{ext}"
                if related_path.exists() and related_path != file_path:
                    related.append(related_path.relative_to(self.source_root).as_posix())

        return related

    def _create_file_chunk(
        self,
        relative_path: str,
        content: str,
        language: str,
        file_type: str,
        file_modified: datetime,
        metadata: dict,
        component_name: str,
        related_files: list[str],
    ) -> SourceChunk:
        kind: ChunkKind = "source"
        if file_type == "template":
            kind = "template"
        elif file_type == "stylesheet":
            kind = "stylesheet"

        chunk_type = ChunkType.SOURCE
        if file_type == "template":
            chunk_type = ChunkType.TEMPLATE
        elif file_type == "stylesheet":
            chunk_type = ChunkType.STYLESHEET

        title = f"{component_name} ({file_type})" if component_name else Path(relative_path).name

        symbols_extracted = []
        for class_name in metadata.get("classes", []):
            symbols_extracted.append({"name": class_name, "type": "class"})
        for func_name in metadata.get("functions", []):
            symbols_extracted.append({"name": func_name, "type": "function"})

        return SourceChunk(
            id=self._generate_id(relative_path),
            source_id=self.source_id,
            path=relative_path,
            anchor=None,
            title=title,
            content=content,
            kind=kind,
            depth=1,
            is_entrypoint=relative_path in self.entrypoints,
            code_blocks=[language],
            file_modified=file_modified,
            language=language,
            file_type=file_type,
            class_name=metadata["classes"][0] if metadata["classes"] else None,
            decorators=metadata.get("decorators", []),
            exports=metadata.get("classes", []) + metadata.get("functions", []),
            imports=metadata.get("imports", []),
            selector=metadata.get("selector"),
            template_url=metadata.get("template_url"),
            style_urls=metadata.get("style_urls", []),
            related_files=related_files,
            component_name=component_name,
            symbols_extracted=symbols_extracted,
        )

    def _create_symbol_chunks(
        self,
        relative_path: str,
        content: str,
        language: str,
        file_type: str,
        file_modified: datetime,
        metadata: dict,
        component_name: str,
    ) -> list[NormalizedChunk]:
        chunks = []

        for class_name in metadata.get("classes", []):
            class_pattern = re.compile(
                rf"((?:@\w+\s*\([^)]*\)\s*)*export\s+)?class\s+{class_name}\s*.*?\{{",
                re.DOTALL
            )
            match = class_pattern.search(content)
            if match:
                start = match.start()
                class_content = content[start:start + 2000]

                chunks.append(SourceChunk(
                    id=self._generate_id(f"{relative_path}:{class_name}"),
                    source_id=self.source_id,
                    path=relative_path,
                    anchor=class_name.lower(),
                    title=class_name,
                    content=class_content,
                    kind="source",
                    depth=2,
                    code_blocks=[language],
                    file_modified=file_modified,
                    language=language,
                    file_type=file_type,
                    class_name=class_name,
                    decorators=metadata.get("decorators", []),
                    component_name=component_name,
                ))

        if not chunks:
            chunks.append(self._create_file_chunk(
                relative_path=relative_path,
                content=content,
                language=language,
                file_type=file_type,
                file_modified=file_modified,
                metadata=metadata,
                component_name=component_name,
                related_files=[],
            ))

        return chunks

    def _generate_id(self, path: str) -> str:
        id_source = f"{self.source_id}:source:{path}"
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]
