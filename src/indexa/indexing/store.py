"""JSON-based index storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from indexa.indexing.chunk import NormalizedChunk


class IndexStore:
    """Persist and load the search index from JSON."""

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.graph_path = index_path.with_suffix(".graph.json")

    def exists(self) -> bool:
        """Check if index file exists."""
        return self.index_path.exists()

    def save(self, chunks: list[NormalizedChunk]) -> None:
        """Save chunks to JSON file."""
        # Ensure parent directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "indexed_at": datetime.now().isoformat(),
            "chunk_count": len(chunks),
            "chunks": [chunk.to_dict() for chunk in chunks],
        }

        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> list[NormalizedChunk]:
        """Load chunks from JSON file.

        Automatically deserializes to ComponentChunk if component metadata is present.
        """
        if not self.exists():
            return []

        with open(self.index_path, encoding="utf-8") as f:
            data = json.load(f)

        chunks: list[NormalizedChunk] = []
        for chunk_data in data.get("chunks", []):
            # Check if this is a ComponentChunk (has component_name field)
            if chunk_data.get("component_name"):
                from indexa.indexing.component_chunk import ComponentChunk
                chunks.append(ComponentChunk.from_dict(chunk_data))
            else:
                chunks.append(NormalizedChunk.from_dict(chunk_data))

        return chunks

    def get_metadata(self) -> dict:
        """Get index metadata without loading all chunks."""
        if not self.exists():
            return {"exists": False}

        with open(self.index_path, encoding="utf-8") as f:
            data = json.load(f)

        return {
            "exists": True,
            "version": data.get("version"),
            "indexed_at": data.get("indexed_at"),
            "chunk_count": data.get("chunk_count", 0),
            "has_graph": self.graph_path.exists(),
        }

    def save_graph(self, graph_data: dict) -> None:
        """Save component graph to separate JSON file.

        Args:
            graph_data: Serialized graph from ComponentGraph.to_dict()
        """
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            **graph_data,
        }

        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_graph(self) -> dict | None:
        """Load component graph from JSON file.

        Returns:
            Graph data dict or None if no graph file exists
        """
        if not self.graph_path.exists():
            return None

        with open(self.graph_path, encoding="utf-8") as f:
            return json.load(f)
