"""Adapters module for parsing different document formats."""

from indexa.adapters.base import BaseAdapter
from indexa.adapters.compodoc import CompodocAdapter
from indexa.adapters.component import ComponentAdapter
from indexa.adapters.markdown import MarkdownAdapter
from indexa.adapters.python import PythonAdapter
from indexa.adapters.source import SourceAdapter

__all__ = [
    "BaseAdapter",
    "CompodocAdapter",
    "ComponentAdapter",
    "MarkdownAdapter",
    "PythonAdapter",
    "SourceAdapter",
]
