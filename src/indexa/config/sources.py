"""Source configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AdapterConfig:
    """Configuration for a specific adapter."""

    type: str
    config: dict = field(default_factory=dict)


@dataclass
class SourceConfig:
    """Configuration for a documentation source."""

    id: str
    name: str
    description: str
    root: Path
    include_globs: list[str] = field(default_factory=list)
    exclude_globs: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    adapter_configs: list[AdapterConfig] = field(default_factory=list)

    # Legacy fields (backward compatibility)
    adapters: list[str] = field(default_factory=lambda: ["markdown"])
    adapter: str = "markdown"
    default_category: str = ""
    source_type: str = "documentation"

    def __post_init__(self):
        """Convert root to Path if string."""
        if isinstance(self.root, str):
            self.root = Path(self.root)

    def validate(self) -> list[str]:
        """Validate the source configuration. Returns list of errors."""
        errors = []

        if not self.id:
            errors.append("Source 'id' is required")

        if not self.root.exists():
            errors.append(f"Source root does not exist: {self.root}")

        if not self.include_globs:
            errors.append("At least one 'include_globs' pattern is required")

        return errors


def _parse_adapter_configs(source_data: dict) -> list[AdapterConfig]:
    """Parse adapter configurations from source data."""
    adapter_configs = []

    adapters_raw = source_data.get("adapters", [])

    for adapter_data in adapters_raw:
        if isinstance(adapter_data, str):
            adapter_configs.append(AdapterConfig(type=adapter_data))
        elif isinstance(adapter_data, dict):
            adapter_configs.append(AdapterConfig(
                type=adapter_data.get("type", "markdown"),
                config=adapter_data.get("config", {}),
            ))

    if not adapter_configs and source_data.get("adapter"):
        legacy_adapter = source_data["adapter"]
        legacy_config = {}
        if legacy_adapter == "component":
            legacy_config["default_category"] = source_data.get("default_category", "")
        adapter_configs.append(AdapterConfig(type=legacy_adapter, config=legacy_config))

    if not adapter_configs:
        adapter_configs.append(AdapterConfig(type="markdown"))

    return adapter_configs


def load_sources(config_path: Path) -> list[SourceConfig]:
    """Load source configurations from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Sources config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = []
    for source_data in data.get("sources", []):
        adapter_configs = _parse_adapter_configs(source_data)

        source = SourceConfig(
            id=source_data["id"],
            name=source_data.get("name", source_data["id"]),
            description=source_data.get("description", ""),
            root=Path(source_data["root"]),
            include_globs=source_data.get("include_globs", ["**/*.md"]),
            exclude_globs=source_data.get("exclude_globs", []),
            entrypoints=source_data.get("entrypoints", []),
            tags=source_data.get("tags", []),
            adapter_configs=adapter_configs,
            adapters=source_data.get("adapters", ["markdown"]),
            adapter=source_data.get("adapter", "markdown"),
            default_category=source_data.get("default_category", ""),
            source_type=source_data.get("type", "documentation"),
        )

        errors = source.validate()
        if errors:
            raise ValueError(f"Invalid source '{source.id}': {errors}")

        sources.append(source)

    return sources
