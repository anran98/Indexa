"""Python adapter - parses Python source files using AST."""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from indexa.adapters.base import BaseAdapter
from indexa.indexing.chunk import ChunkKind, NormalizedChunk
from indexa.indexing.source_chunk import SourceChunk


class ChunkStrategy(str, Enum):
    """Chunking strategy for Python files."""
    FILE = "file"      # One chunk per file
    SYMBOL = "symbol"  # One chunk per class/function
    MODULE = "module"  # Module overview + symbols


class DocstringStyle(str, Enum):
    """Docstring format styles."""
    GOOGLE = "google"
    NUMPY = "numpy"
    SPHINX = "sphinx"
    AUTO = "auto"


@dataclass
class ExtractedSymbol:
    """Extracted Python symbol (class/function)."""
    name: str
    kind: Literal["class", "function", "method", "async_function", "async_method"]
    lineno: int
    docstring: str | None
    signature: str | None
    decorators: list[str]
    bases: list[str]  # For classes: base class names
    is_async: bool = False
    is_private: bool = False
    return_type: str | None = None
    parameters: list[dict] | None = None


class PythonAdapter(BaseAdapter):
    """Parse Python source files using stdlib ast module.
    
    Extracts:
    - Module-level docstrings
    - Class definitions with docstrings and bases
    - Function/method definitions with signatures and docstrings
    - Decorators
    - Type hints (as strings)
    - Import statements
    
    Example configuration:
    ```yaml
    adapters:
      - type: python
        config:
          chunk_strategy: symbol  # file, symbol, or module
          include_private: false  # Skip _private and __dunder__
          include_tests: false    # Skip test_*.py files
    ```
    """

    SUPPORTED_EXTENSIONS = {".py", ".pyw"}

    # Patterns for docstring style detection
    GOOGLE_PATTERN = re.compile(r"^\s*(Args|Returns|Raises|Yields|Examples?|Attributes|Note|Warning):", re.MULTILINE)
    NUMPY_PATTERN = re.compile(r"^\s*(Parameters|Returns|Raises|Yields|Examples?|Attributes|Notes?|Warnings?)\s*\n\s*-+", re.MULTILINE)
    SPHINX_PATTERN = re.compile(r"^\s*:(param|type|returns?|rtype|raises?|var|ivar|cvar):", re.MULTILINE)

    def __init__(
        self,
        source_id: str,
        source_root: Path,
        chunk_strategy: ChunkStrategy | str = ChunkStrategy.SYMBOL,
        include_private: bool = False,
        include_tests: bool = False,
        include_dunder: bool = False,
        entrypoints: list[str] | None = None,
    ):
        """Initialize the Python adapter.
        
        Args:
            source_id: Unique identifier for the source
            source_root: Root path of the source repository
            chunk_strategy: How to chunk Python files (file, symbol, module)
            include_private: Whether to include _private symbols
            include_tests: Whether to include test files (test_*.py, *_test.py)
            include_dunder: Whether to include __dunder__ methods
            entrypoints: List of high-value files to boost
        """
        self.source_id = source_id
        self.source_root = source_root
        self.chunk_strategy = (
            ChunkStrategy(chunk_strategy)
            if isinstance(chunk_strategy, str)
            else chunk_strategy
        )
        self.include_private = include_private
        self.include_tests = include_tests
        self.include_dunder = include_dunder
        self.entrypoints = set(entrypoints or [])

    def supports_extension(self, extension: str) -> bool:
        """Check if this adapter supports the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        """Parse a Python file and return normalized chunks."""
        extension = file_path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            return []

        # Skip test files if configured
        if not self.include_tests:
            filename = file_path.name
            if filename.startswith("test_") or filename.endswith("_test.py"):
                return []

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Skip files with syntax errors
            return []

        relative_path = file_path.relative_to(self.source_root).as_posix()
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Extract module-level information
        module_docstring = ast.get_docstring(tree)
        imports = self._extract_imports(tree)
        symbols = self._extract_symbols(tree, content)

        if self.chunk_strategy == ChunkStrategy.FILE:
            return [self._create_file_chunk(
                relative_path=relative_path,
                content=content,
                file_modified=file_modified,
                module_docstring=module_docstring,
                imports=imports,
                symbols=symbols,
            )]
        elif self.chunk_strategy == ChunkStrategy.SYMBOL:
            return self._create_symbol_chunks(
                relative_path=relative_path,
                content=content,
                file_modified=file_modified,
                module_docstring=module_docstring,
                imports=imports,
                symbols=symbols,
            )
        else:  # MODULE
            return self._create_module_chunks(
                relative_path=relative_path,
                content=content,
                file_modified=file_modified,
                module_docstring=module_docstring,
                imports=imports,
                symbols=symbols,
            )

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract all import statements from the AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports

    def _extract_symbols(self, tree: ast.Module, content: str) -> list[ExtractedSymbol]:
        """Extract all classes and functions from the AST."""
        symbols = []
        lines = content.split("\n")

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                symbol = self._extract_class(node, lines)
                if self._should_include_symbol(symbol):
                    symbols.append(symbol)
                    # Extract methods
                    for method in self._extract_methods(node, lines):
                        if self._should_include_symbol(method):
                            symbols.append(method)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = self._extract_function(node, lines, is_method=False)
                if self._should_include_symbol(symbol):
                    symbols.append(symbol)

        return symbols

    def _extract_class(self, node: ast.ClassDef, lines: list[str]) -> ExtractedSymbol:
        """Extract class information from AST node."""
        decorators = self._get_decorators(node)
        bases = [self._unparse_node(base) for base in node.bases]
        docstring = ast.get_docstring(node)

        # Build class signature
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"
        signature += ":"

        return ExtractedSymbol(
            name=node.name,
            kind="class",
            lineno=node.lineno,
            docstring=docstring,
            signature=signature,
            decorators=decorators,
            bases=bases,
            is_private=node.name.startswith("_") and not node.name.startswith("__"),
        )

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        is_method: bool = False,
    ) -> ExtractedSymbol:
        """Extract function/method information from AST node."""
        decorators = self._get_decorators(node)
        docstring = ast.get_docstring(node)
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Extract parameters
        parameters = self._extract_parameters(node.args)

        # Extract return type
        return_type = self._unparse_node(node.returns) if node.returns else None

        # Build signature
        signature = self._build_signature(node, is_async)

        # Determine kind
        if is_method:
            kind = "async_method" if is_async else "method"
        else:
            kind = "async_function" if is_async else "function"

        # Check if private or dunder
        is_private = node.name.startswith("_") and not node.name.startswith("__")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")

        return ExtractedSymbol(
            name=node.name,
            kind=kind,
            lineno=node.lineno,
            docstring=docstring,
            signature=signature,
            decorators=decorators,
            bases=[],
            is_async=is_async,
            is_private=is_private or is_dunder,
            return_type=return_type,
            parameters=parameters,
        )

    def _extract_methods(
        self, class_node: ast.ClassDef, lines: list[str]
    ) -> list[ExtractedSymbol]:
        """Extract all methods from a class."""
        methods = []
        for node in class_node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method = self._extract_function(node, lines, is_method=True)
                method.name = f"{class_node.name}.{method.name}"
                methods.append(method)
        return methods

    def _extract_parameters(self, args: ast.arguments) -> list[dict]:
        """Extract parameter information from function arguments."""
        params = []

        # Calculate default value offset
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for i, arg in enumerate(args.args):
            param = {
                "name": arg.arg,
                "annotation": self._unparse_node(arg.annotation) if arg.annotation else None,
                "default": None,
                "kind": "positional_or_keyword",
            }
            # Check if this arg has a default
            default_idx = i - default_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                param["default"] = self._unparse_node(args.defaults[default_idx])
            params.append(param)

        # *args
        if args.vararg:
            params.append({
                "name": args.vararg.arg,
                "annotation": self._unparse_node(args.vararg.annotation) if args.vararg.annotation else None,
                "default": None,
                "kind": "var_positional",
            })

        # Keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            default = args.kw_defaults[i] if i < len(args.kw_defaults) and args.kw_defaults[i] else None
            params.append({
                "name": arg.arg,
                "annotation": self._unparse_node(arg.annotation) if arg.annotation else None,
                "default": self._unparse_node(default) if default else None,
                "kind": "keyword_only",
            })

        # **kwargs
        if args.kwarg:
            params.append({
                "name": args.kwarg.arg,
                "annotation": self._unparse_node(args.kwarg.annotation) if args.kwarg.annotation else None,
                "default": None,
                "kind": "var_keyword",
            })

        return params

    def _get_decorators(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract decorator names from a node."""
        decorators = []
        for decorator in node.decorator_list:
            decorators.append(self._unparse_node(decorator))
        return decorators

    def _build_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> str:
        """Build a human-readable function signature."""
        prefix = "async def" if is_async else "def"
        
        # Use ast.unparse for the whole function definition (just the signature part)
        try:
            # Build parameter string
            params = []
            args = node.args

            # Regular args
            num_defaults = len(args.defaults)
            default_offset = len(args.args) - num_defaults

            for i, arg in enumerate(args.args):
                param_str = arg.arg
                if arg.annotation:
                    param_str += f": {self._unparse_node(arg.annotation)}"
                default_idx = i - default_offset
                if default_idx >= 0 and default_idx < len(args.defaults):
                    param_str += f" = {self._unparse_node(args.defaults[default_idx])}"
                params.append(param_str)

            # *args
            if args.vararg:
                param_str = f"*{args.vararg.arg}"
                if args.vararg.annotation:
                    param_str += f": {self._unparse_node(args.vararg.annotation)}"
                params.append(param_str)
            elif args.kwonlyargs:
                params.append("*")

            # Keyword-only args
            for i, arg in enumerate(args.kwonlyargs):
                param_str = arg.arg
                if arg.annotation:
                    param_str += f": {self._unparse_node(arg.annotation)}"
                if i < len(args.kw_defaults) and args.kw_defaults[i]:
                    param_str += f" = {self._unparse_node(args.kw_defaults[i])}"
                params.append(param_str)

            # **kwargs
            if args.kwarg:
                param_str = f"**{args.kwarg.arg}"
                if args.kwarg.annotation:
                    param_str += f": {self._unparse_node(args.kwarg.annotation)}"
                params.append(param_str)

            signature = f"{prefix} {node.name}({', '.join(params)})"
            if node.returns:
                signature += f" -> {self._unparse_node(node.returns)}"
            
            return signature
        except Exception:
            return f"{prefix} {node.name}(...)"

    def _unparse_node(self, node: ast.AST | None) -> str:
        """Convert AST node back to source code string."""
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return str(node)

    def _should_include_symbol(self, symbol: ExtractedSymbol) -> bool:
        """Check if a symbol should be included based on configuration."""
        if symbol.is_private and not self.include_private:
            return False
        if symbol.name.startswith("__") and symbol.name.endswith("__") and not self.include_dunder:
            # Always include __init__
            if symbol.name not in ("__init__", "__new__", "__call__"):
                return False
        return True

    def _detect_docstring_style(self, docstring: str | None) -> DocstringStyle:
        """Auto-detect docstring style."""
        if not docstring:
            return DocstringStyle.GOOGLE

        if self.NUMPY_PATTERN.search(docstring):
            return DocstringStyle.NUMPY
        if self.SPHINX_PATTERN.search(docstring):
            return DocstringStyle.SPHINX
        if self.GOOGLE_PATTERN.search(docstring):
            return DocstringStyle.GOOGLE

        return DocstringStyle.GOOGLE  # Default

    def _create_file_chunk(
        self,
        relative_path: str,
        content: str,
        file_modified: datetime,
        module_docstring: str | None,
        imports: list[str],
        symbols: list[ExtractedSymbol],
    ) -> SourceChunk:
        """Create a single chunk for the entire file."""
        module_name = Path(relative_path).stem

        # Build title
        title = module_name
        if module_docstring:
            # Use first line of docstring as title
            first_line = module_docstring.split("\n")[0].strip()
            if first_line:
                title = f"{module_name} - {first_line[:60]}"

        # Extract symbol summary
        symbols_extracted = [
            {
                "name": s.name,
                "type": s.kind,
                "signature": s.signature,
                "has_docstring": bool(s.docstring),
            }
            for s in symbols
        ]

        return SourceChunk(
            id=self._generate_id(relative_path),
            source_id=self.source_id,
            path=relative_path,
            anchor=None,
            title=title,
            content=content,
            kind="source",
            depth=1,
            is_entrypoint=relative_path in self.entrypoints,
            code_blocks=["python"],
            file_modified=file_modified,
            language="python",
            file_type="module",
            imports=imports,
            exports=[s.name.split(".")[-1] for s in symbols if not s.is_private],
            symbols_extracted=symbols_extracted,
        )

    def _create_symbol_chunks(
        self,
        relative_path: str,
        content: str,
        file_modified: datetime,
        module_docstring: str | None,
        imports: list[str],
        symbols: list[ExtractedSymbol],
    ) -> list[NormalizedChunk]:
        """Create one chunk per symbol (class/function)."""
        chunks = []

        # Module overview chunk if there's a module docstring
        if module_docstring:
            chunks.append(SourceChunk(
                id=self._generate_id(f"{relative_path}:module"),
                source_id=self.source_id,
                path=relative_path,
                anchor="module",
                title=f"{Path(relative_path).stem} (module)",
                content=module_docstring,
                kind="api",
                depth=1,
                is_entrypoint=relative_path in self.entrypoints,
                code_blocks=["python"],
                file_modified=file_modified,
                language="python",
                file_type="module",
                imports=imports,
            ))

        # One chunk per symbol
        for symbol in symbols:
            # Build content: signature + docstring
            symbol_content = symbol.signature or symbol.name
            if symbol.docstring:
                symbol_content += f"\n\n{symbol.docstring}"

            # Determine chunk kind based on symbol type
            chunk_kind: ChunkKind = "api" if symbol.docstring else "source"

            # Build title
            title = symbol.name
            if symbol.kind == "class":
                title = f"class {symbol.name}"
            elif symbol.kind in ("function", "async_function"):
                title = f"def {symbol.name.split('.')[-1]}()"
            elif symbol.kind in ("method", "async_method"):
                title = f"{symbol.name}()"

            chunk = SourceChunk(
                id=self._generate_id(f"{relative_path}:{symbol.name}"),
                source_id=self.source_id,
                path=relative_path,
                anchor=symbol.name.lower().replace(".", "-"),
                title=title,
                content=symbol_content,
                kind=chunk_kind,
                depth=2 if "." in symbol.name else 1,  # Methods are depth 2
                is_entrypoint=False,
                code_blocks=["python"],
                file_modified=file_modified,
                language="python",
                file_type=symbol.kind,
                class_name=symbol.name.split(".")[0] if "." in symbol.name else None,
                decorators=symbol.decorators,
                symbols_extracted=[{
                    "name": symbol.name,
                    "type": symbol.kind,
                    "signature": symbol.signature,
                    "return_type": symbol.return_type,
                    "parameters": symbol.parameters,
                    "bases": symbol.bases,
                    "is_async": symbol.is_async,
                }],
            )
            chunks.append(chunk)

        # Fallback: if no symbols, create file chunk
        if not chunks:
            chunks.append(self._create_file_chunk(
                relative_path=relative_path,
                content=content,
                file_modified=file_modified,
                module_docstring=module_docstring,
                imports=imports,
                symbols=symbols,
            ))

        return chunks

    def _create_module_chunks(
        self,
        relative_path: str,
        content: str,
        file_modified: datetime,
        module_docstring: str | None,
        imports: list[str],
        symbols: list[ExtractedSymbol],
    ) -> list[NormalizedChunk]:
        """Create module overview + top-level symbol chunks."""
        chunks = []

        # Module overview chunk
        module_name = Path(relative_path).stem

        # Build module summary
        summary_parts = []
        if module_docstring:
            summary_parts.append(module_docstring)

        # Add symbol listing
        classes = [s for s in symbols if s.kind == "class"]
        functions = [s for s in symbols if s.kind in ("function", "async_function")]

        if classes:
            summary_parts.append("\n## Classes\n")
            for cls in classes:
                summary_parts.append(f"- `{cls.name}`: {cls.docstring.split(chr(10))[0] if cls.docstring else 'No description'}")

        if functions:
            summary_parts.append("\n## Functions\n")
            for func in functions:
                summary_parts.append(f"- `{func.name}()`: {func.docstring.split(chr(10))[0] if func.docstring else 'No description'}")

        overview_content = "\n".join(summary_parts) if summary_parts else content[:2000]

        chunks.append(SourceChunk(
            id=self._generate_id(f"{relative_path}:overview"),
            source_id=self.source_id,
            path=relative_path,
            anchor="overview",
            title=f"{module_name} (module overview)",
            content=overview_content,
            kind="api",
            depth=1,
            is_entrypoint=relative_path in self.entrypoints,
            code_blocks=["python"],
            file_modified=file_modified,
            language="python",
            file_type="module",
            imports=imports,
            exports=[s.name for s in symbols if not s.is_private and s.kind in ("class", "function", "async_function")],
            symbols_extracted=[
                {"name": s.name, "type": s.kind}
                for s in symbols if s.kind in ("class", "function", "async_function")
            ],
        ))

        # Add chunks for classes and top-level functions only (not methods)
        for symbol in symbols:
            if symbol.kind not in ("class", "function", "async_function"):
                continue

            symbol_content = symbol.signature or symbol.name
            if symbol.docstring:
                symbol_content += f"\n\n{symbol.docstring}"

            title = symbol.name
            if symbol.kind == "class":
                title = f"class {symbol.name}"
            else:
                title = f"def {symbol.name}()"

            chunk = SourceChunk(
                id=self._generate_id(f"{relative_path}:{symbol.name}"),
                source_id=self.source_id,
                path=relative_path,
                anchor=symbol.name.lower(),
                title=title,
                content=symbol_content,
                kind="api" if symbol.docstring else "source",
                depth=2,
                code_blocks=["python"],
                file_modified=file_modified,
                language="python",
                file_type=symbol.kind,
                decorators=symbol.decorators,
                symbols_extracted=[{
                    "name": symbol.name,
                    "type": symbol.kind,
                    "signature": symbol.signature,
                    "bases": symbol.bases,
                }],
            )
            chunks.append(chunk)

        return chunks

    def _generate_id(self, path: str) -> str:
        """Generate unique chunk ID."""
        id_source = f"{self.source_id}:python:{path}"
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]
