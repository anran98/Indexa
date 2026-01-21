"""Global settings for Indexa."""

from pathlib import Path


class Settings:
    """Application settings with sensible defaults."""

    def __init__(self):
        # Find project root (where pyproject.toml lives)
        self.project_root = self._find_project_root()

        # Config paths
        self.config_dir = self.project_root / "config"
        self.sources_path = self.config_dir / "sources.yaml"

        # Data paths
        self.data_dir = self.project_root / "data"
        self.index_path = self.data_dir / "index.json"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _find_project_root(self) -> Path:
        """Find project root by looking for pyproject.toml."""
        current = Path(__file__).resolve()

        # Walk up looking for pyproject.toml
        for parent in [current] + list(current.parents):
            if (parent / "pyproject.toml").exists():
                return parent

        # Fallback to src parent
        return Path(__file__).resolve().parent.parent.parent.parent
