"""Indexer - orchestrates adapters to build the index."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from indexa.config.sources import AdapterConfig, SourceConfig
from indexa.indexing.chunk import NormalizedChunk

if TYPE_CHECKING:
    from indexa.adapters.base import BaseAdapter


class Indexer:
    """Orchestrates document indexing across sources and adapters."""

    def index_source(self, source: SourceConfig) -> list[NormalizedChunk]:
        """Index all documents in a source using configured adapters."""
        all_chunks: list[NormalizedChunk] = []
        files = self._find_files(source)

        files_by_ext: dict[str, list[Path]] = {}
        for f in files:
            ext = f.suffix.lower()
            files_by_ext.setdefault(ext, []).append(f)

        for adapter_config in source.adapter_configs:
            adapter = self._create_adapter(source, adapter_config)
            if adapter is None:
                continue

            adapter_files = self._get_files_for_adapter(
                adapter, adapter_config, files_by_ext, source.root
            )

            for file_path in adapter_files:
                try:
                    chunks = adapter.parse_file(file_path)
                    all_chunks.extend(chunks)
                except Exception as e:
                    print(f"Warning: {adapter_config.type} failed on {file_path}: {e}")

        return all_chunks

    def _create_adapter(
        self,
        source: SourceConfig,
        adapter_config: AdapterConfig,
    ) -> BaseAdapter | None:
        """Create an adapter instance from configuration."""
        adapter_type = adapter_config.type
        config = adapter_config.config

        if adapter_type == "markdown":
            from indexa.adapters.markdown import MarkdownAdapter
            return MarkdownAdapter(
                source_id=source.id,
                source_root=source.root,
                entrypoints=source.entrypoints,
            )

        elif adapter_type == "component":
            from indexa.adapters.component import ComponentAdapter
            return ComponentAdapter(
                source_id=source.id,
                source_root=source.root,
                entrypoints=source.entrypoints,
                default_category=config.get("default_category", ""),
            )

        elif adapter_type == "compodoc":
            from indexa.adapters.compodoc import CompodocAdapter
            return CompodocAdapter(
                source_id=source.id,
                source_root=source.root,
                json_path=config.get("json_path", "documentation.json"),
                include_directives=config.get("include_directives", True),
                include_services=config.get("include_services", True),
                include_pipes=config.get("include_pipes", False),
                category_from_path=config.get("category_from_path", True),
                default_category=config.get("default_category", "Components"),
            )

        elif adapter_type == "source":
            from indexa.adapters.source import SourceAdapter
            return SourceAdapter(
                source_id=source.id,
                source_root=source.root,
                languages=config.get("languages"),
                chunk_strategy=config.get("chunk_strategy", "file"),
                link_related_files=config.get("link_related_files", True),
                extract_symbols=config.get("extract_symbols", True),
                entrypoints=source.entrypoints,
            )

        elif adapter_type == "python":
            from indexa.adapters.python import PythonAdapter
            return PythonAdapter(
                source_id=source.id,
                source_root=source.root,
                chunk_strategy=config.get("chunk_strategy", "symbol"),
                include_private=config.get("include_private", False),
                include_tests=config.get("include_tests", False),
                include_dunder=config.get("include_dunder", False),
                entrypoints=source.entrypoints,
            )

        print(f"Warning: Unknown adapter type '{adapter_type}'")
        return None

    def _get_files_for_adapter(
        self,
        adapter: BaseAdapter,
        adapter_config: AdapterConfig,
        files_by_ext: dict[str, list[Path]],
        source_root: Path,
    ) -> list[Path]:
        """Get files that this adapter can handle."""
        if adapter_config.type == "compodoc":
            json_path = source_root / adapter_config.config.get(
                "json_path", "documentation.json"
            )
            return [json_path] if json_path.exists() else []

        adapter_files = []
        for ext, ext_files in files_by_ext.items():
            if adapter.supports_extension(ext):
                adapter_files.extend(ext_files)
        return adapter_files

    def _find_files(self, source: SourceConfig) -> list[Path]:
        """Find all files matching include patterns, excluding exclude patterns."""
        all_files: set[Path] = set()

        # Collect files matching include patterns
        for pattern in source.include_globs:
            # Handle ** patterns
            if "**" in pattern:
                matched = list(source.root.glob(pattern))
            else:
                matched = list(source.root.glob(pattern))
            all_files.update(matched)

        # Filter out excluded files
        filtered_files: list[Path] = []
        for file_path in all_files:
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(source.root).as_posix()

            # Check if matches any exclude pattern
            excluded = False
            for exclude_pattern in source.exclude_globs:
                if fnmatch.fnmatch(relative_path, exclude_pattern):
                    excluded = True
                    break
                # Also check against full path for patterns like **/.git/**
                if fnmatch.fnmatch(str(file_path), f"*{exclude_pattern}"):
                    excluded = True
                    break

            if not excluded:
                filtered_files.append(file_path)

        return sorted(filtered_files)
