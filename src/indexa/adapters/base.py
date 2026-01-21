"""Base adapter protocol for document parsing."""

from abc import ABC, abstractmethod
from pathlib import Path

from indexa.indexing.chunk import NormalizedChunk


class BaseAdapter(ABC):
    """Abstract base class for document adapters."""

    @abstractmethod
    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        """Parse a file and return normalized chunks.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of NormalizedChunk objects extracted from the file
        """
        pass

    @abstractmethod
    def supports_extension(self, extension: str) -> bool:
        """Check if this adapter supports the given file extension.

        Args:
            extension: File extension (e.g., ".md", ".py")

        Returns:
            True if this adapter can handle files with this extension
        """
        pass
