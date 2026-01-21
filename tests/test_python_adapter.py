"""Tests for the Python adapter."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from indexa.adapters.python import (
    ChunkStrategy,
    DocstringStyle,
    ExtractedSymbol,
    PythonAdapter,
)


class TestPythonAdapterBasics:
    """Test basic PythonAdapter functionality."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> PythonAdapter:
        """Create a PythonAdapter for testing."""
        return PythonAdapter(
            source_id="test_source",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )

    @pytest.fixture
    def simple_module(self, tmp_path: Path) -> Path:
        """Create a simple Python module for testing."""
        module_path = tmp_path / "simple.py"
        module_path.write_text(dedent('''
            """A simple module for testing.
            
            This module contains basic classes and functions.
            """
            
            import os
            from pathlib import Path
            
            
            def hello(name: str) -> str:
                """Say hello to someone.
                
                Args:
                    name: The person's name
                    
                Returns:
                    A greeting message
                """
                return f"Hello, {name}!"
            
            
            class Greeter:
                """A class that greets people.
                
                Attributes:
                    greeting: The greeting to use
                """
                
                def __init__(self, greeting: str = "Hello"):
                    """Initialize the greeter.
                    
                    Args:
                        greeting: The greeting word to use
                    """
                    self.greeting = greeting
                
                def greet(self, name: str) -> str:
                    """Greet someone by name.
                    
                    Args:
                        name: The person's name
                        
                    Returns:
                        The greeting message
                    """
                    return f"{self.greeting}, {name}!"
        ''').strip())
        return module_path

    def test_supports_extension(self, adapter: PythonAdapter):
        """Test file extension support."""
        assert adapter.supports_extension(".py")
        assert adapter.supports_extension(".pyw")
        assert not adapter.supports_extension(".js")
        assert not adapter.supports_extension(".ts")

    def test_parse_simple_module(self, adapter: PythonAdapter, simple_module: Path):
        """Test parsing a simple module."""
        chunks = adapter.parse_file(simple_module)
        
        # Should have chunks for: module, hello function, Greeter class, __init__, greet
        assert len(chunks) >= 3
        
        # Check we have the module docstring
        module_chunks = [c for c in chunks if c.anchor == "module"]
        assert len(module_chunks) == 1
        assert "simple module for testing" in module_chunks[0].content.lower()

    def test_extracts_function(self, adapter: PythonAdapter, simple_module: Path):
        """Test function extraction."""
        chunks = adapter.parse_file(simple_module)
        
        hello_chunks = [c for c in chunks if "hello" in c.title.lower()]
        assert len(hello_chunks) >= 1
        
        hello = hello_chunks[0]
        assert hello.language == "python"
        assert "name: str" in hello.content or "name" in hello.content

    def test_extracts_class(self, adapter: PythonAdapter, simple_module: Path):
        """Test class extraction."""
        chunks = adapter.parse_file(simple_module)
        
        greeter_chunks = [c for c in chunks if "greeter" in c.title.lower() and "class" in c.title.lower()]
        assert len(greeter_chunks) >= 1
        
        greeter = greeter_chunks[0]
        assert greeter.language == "python"


class TestPythonAdapterChunkStrategies:
    """Test different chunking strategies."""

    @pytest.fixture
    def module_content(self) -> str:
        """Sample module content."""
        return dedent('''
            """Module docstring."""
            
            def func1():
                """Function 1."""
                pass
            
            def func2():
                """Function 2."""
                pass
            
            class MyClass:
                """My class."""
                
                def method1(self):
                    """Method 1."""
                    pass
        ''').strip()

    def test_file_strategy(self, tmp_path: Path, module_content: str):
        """Test FILE chunking strategy - one chunk per file."""
        module_path = tmp_path / "test_module.py"
        module_path.write_text(module_content)
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.FILE,
        )
        
        chunks = adapter.parse_file(module_path)
        
        # Should have exactly 1 chunk
        assert len(chunks) == 1
        assert chunks[0].file_type == "module"

    def test_symbol_strategy(self, tmp_path: Path, module_content: str):
        """Test SYMBOL chunking strategy - one chunk per symbol."""
        module_path = tmp_path / "test_module.py"
        module_path.write_text(module_content)
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(module_path)
        
        # Should have multiple chunks: module + func1 + func2 + MyClass + method1
        assert len(chunks) >= 4
        
        # Check we have different symbol types
        titles = [c.title for c in chunks]
        assert any("func1" in t.lower() for t in titles)
        assert any("func2" in t.lower() for t in titles)
        assert any("myclass" in t.lower() for t in titles)

    def test_module_strategy(self, tmp_path: Path, module_content: str):
        """Test MODULE chunking strategy - overview + top-level symbols."""
        module_path = tmp_path / "test_module.py"
        module_path.write_text(module_content)
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.MODULE,
        )
        
        chunks = adapter.parse_file(module_path)
        
        # Should have overview + top-level symbols (not methods)
        assert len(chunks) >= 3
        
        # Check we have an overview chunk
        overview_chunks = [c for c in chunks if "overview" in c.anchor.lower()]
        assert len(overview_chunks) == 1


class TestPythonAdapterTypeHints:
    """Test type hint extraction."""

    @pytest.fixture
    def typed_module(self, tmp_path: Path) -> Path:
        """Create a module with type hints."""
        module_path = tmp_path / "typed.py"
        module_path.write_text(dedent('''
            """Module with type hints."""
            
            from typing import Optional, List, Dict, Union
            
            def simple_types(a: int, b: str) -> bool:
                """Function with simple types."""
                return True
            
            def complex_types(
                items: List[str],
                mapping: Dict[str, int],
                optional: Optional[str] = None,
            ) -> Union[int, None]:
                """Function with complex types."""
                return None
            
            async def async_func(data: bytes) -> str:
                """Async function."""
                return data.decode()
            
            class TypedClass:
                """Class with typed methods."""
                
                def method(self, value: float) -> int:
                    """Typed method."""
                    return int(value)
        ''').strip())
        return module_path

    def test_extracts_simple_types(self, tmp_path: Path, typed_module: Path):
        """Test extraction of simple type hints."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(typed_module)
        
        simple_chunks = [c for c in chunks if "simple_types" in c.title]
        assert len(simple_chunks) >= 1
        
        chunk = simple_chunks[0]
        # Check signature contains type hints
        assert "int" in chunk.content
        assert "str" in chunk.content
        assert "bool" in chunk.content

    def test_extracts_complex_types(self, tmp_path: Path, typed_module: Path):
        """Test extraction of complex type hints."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(typed_module)
        
        complex_chunks = [c for c in chunks if "complex_types" in c.title]
        assert len(complex_chunks) >= 1
        
        chunk = complex_chunks[0]
        # Check complex types are in content
        assert "List" in chunk.content or "list" in chunk.content

    def test_extracts_async_functions(self, tmp_path: Path, typed_module: Path):
        """Test extraction of async functions."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(typed_module)
        
        async_chunks = [c for c in chunks if "async_func" in c.title]
        assert len(async_chunks) >= 1
        
        chunk = async_chunks[0]
        # Check it's marked as async
        assert "async" in chunk.content.lower()


class TestPythonAdapterDecorators:
    """Test decorator extraction."""

    @pytest.fixture
    def decorated_module(self, tmp_path: Path) -> Path:
        """Create a module with decorators."""
        module_path = tmp_path / "decorated.py"
        module_path.write_text(dedent('''
            """Module with decorators."""
            
            from functools import wraps
            from dataclasses import dataclass
            
            def my_decorator(func):
                """A custom decorator."""
                @wraps(func)
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                return wrapper
            
            @my_decorator
            def decorated_function():
                """A decorated function."""
                pass
            
            @dataclass
            class DataClass:
                """A dataclass."""
                name: str
                value: int
            
            class RegularClass:
                """A regular class."""
                
                @staticmethod
                def static_method():
                    """A static method."""
                    pass
                
                @classmethod
                def class_method(cls):
                    """A class method."""
                    pass
                
                @property
                def my_property(self):
                    """A property."""
                    return self._value
        ''').strip())
        return module_path

    def test_extracts_function_decorators(self, tmp_path: Path, decorated_module: Path):
        """Test extraction of function decorators."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(decorated_module)
        
        decorated_chunks = [c for c in chunks if "decorated_function" in c.title]
        assert len(decorated_chunks) >= 1
        
        chunk = decorated_chunks[0]
        # Check decorator is recorded
        assert chunk.decorators or "my_decorator" in chunk.content

    def test_extracts_class_decorators(self, tmp_path: Path, decorated_module: Path):
        """Test extraction of class decorators."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        
        chunks = adapter.parse_file(decorated_module)
        
        dataclass_chunks = [c for c in chunks if "dataclass" in c.title.lower()]
        assert len(dataclass_chunks) >= 1


class TestPythonAdapterPrivateFiltering:
    """Test private symbol filtering."""

    @pytest.fixture
    def private_module(self, tmp_path: Path) -> Path:
        """Create a module with private symbols."""
        module_path = tmp_path / "private.py"
        module_path.write_text(dedent('''
            """Module with private symbols."""
            
            def public_function():
                """A public function."""
                pass
            
            def _private_function():
                """A private function."""
                pass
            
            def __dunder_function__():
                """A dunder function."""
                pass
            
            class PublicClass:
                """A public class."""
                
                def public_method(self):
                    """A public method."""
                    pass
                
                def _private_method(self):
                    """A private method."""
                    pass
                
                def __init__(self):
                    """Constructor."""
                    pass
        ''').strip())
        return module_path

    def test_excludes_private_by_default(self, tmp_path: Path, private_module: Path):
        """Test that private symbols are excluded by default."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
            include_private=False,
        )
        
        chunks = adapter.parse_file(private_module)
        titles = [c.title.lower() for c in chunks]
        
        # Private function should be excluded
        assert not any("_private_function" in t for t in titles)
        
        # Public function should be included
        assert any("public_function" in t for t in titles)

    def test_includes_init(self, tmp_path: Path, private_module: Path):
        """Test that __init__ is always included."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
            include_private=False,
            include_dunder=False,
        )
        
        chunks = adapter.parse_file(private_module)
        
        # __init__ should be included even with include_dunder=False
        init_chunks = [c for c in chunks if "__init__" in c.title or "init" in c.anchor]
        assert len(init_chunks) >= 1

    def test_includes_private_when_enabled(self, tmp_path: Path, private_module: Path):
        """Test that private symbols are included when enabled."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.SYMBOL,
            include_private=True,
        )
        
        chunks = adapter.parse_file(private_module)
        titles = [c.title.lower() for c in chunks]
        
        # Private function should be included
        assert any("_private_function" in t for t in titles)


class TestPythonAdapterTestFileSkipping:
    """Test test file filtering."""

    def test_skips_test_files_by_default(self, tmp_path: Path):
        """Test that test files are skipped by default."""
        test_file = tmp_path / "test_something.py"
        test_file.write_text('"""Test module."""\ndef test_foo(): pass')
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            include_tests=False,
        )
        
        chunks = adapter.parse_file(test_file)
        assert len(chunks) == 0

    def test_includes_test_files_when_enabled(self, tmp_path: Path):
        """Test that test files are included when enabled."""
        test_file = tmp_path / "test_something.py"
        test_file.write_text('"""Test module."""\ndef test_foo(): pass')
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            include_tests=True,
        )
        
        chunks = adapter.parse_file(test_file)
        assert len(chunks) >= 1


class TestPythonAdapterDocstringStyles:
    """Test docstring style detection."""

    def test_detect_google_style(self):
        """Test Google style detection."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=Path("."),
        )
        
        google_docstring = '''
        Do something.
        
        Args:
            x: The x value
            
        Returns:
            The result
        '''
        
        style = adapter._detect_docstring_style(google_docstring)
        assert style == DocstringStyle.GOOGLE

    def test_detect_numpy_style(self):
        """Test NumPy style detection."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=Path("."),
        )
        
        numpy_docstring = '''
        Do something.
        
        Parameters
        ----------
        x : int
            The x value
            
        Returns
        -------
        int
            The result
        '''
        
        style = adapter._detect_docstring_style(numpy_docstring)
        assert style == DocstringStyle.NUMPY

    def test_detect_sphinx_style(self):
        """Test Sphinx style detection."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=Path("."),
        )
        
        sphinx_docstring = '''
        Do something.
        
        :param x: The x value
        :type x: int
        :returns: The result
        :rtype: int
        '''
        
        style = adapter._detect_docstring_style(sphinx_docstring)
        assert style == DocstringStyle.SPHINX


class TestPythonAdapterImports:
    """Test import extraction."""

    @pytest.fixture
    def module_with_imports(self, tmp_path: Path) -> Path:
        """Create a module with various imports."""
        module_path = tmp_path / "imports.py"
        module_path.write_text(dedent('''
            """Module with imports."""
            
            import os
            import sys
            from pathlib import Path
            from typing import List, Dict, Optional
            from collections.abc import Callable
            from . import local_module
            from ..parent import something
            
            def use_imports():
                pass
        ''').strip())
        return module_path

    def test_extracts_imports(self, tmp_path: Path, module_with_imports: Path):
        """Test that imports are extracted."""
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
            chunk_strategy=ChunkStrategy.FILE,
        )
        
        chunks = adapter.parse_file(module_with_imports)
        assert len(chunks) == 1
        
        chunk = chunks[0]
        # Check imports are recorded
        assert "os" in chunk.imports
        assert "sys" in chunk.imports
        assert any("Path" in imp for imp in chunk.imports)


class TestPythonAdapterEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_syntax_error(self, tmp_path: Path):
        """Test handling of files with syntax errors."""
        bad_file = tmp_path / "bad_syntax.py"
        bad_file.write_text("def broken(:\n    pass")
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        
        chunks = adapter.parse_file(bad_file)
        assert len(chunks) == 0  # Should return empty, not raise

    def test_handles_empty_file(self, tmp_path: Path):
        """Test handling of empty files."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        
        chunks = adapter.parse_file(empty_file)
        # Empty file might produce 0 or 1 chunk depending on strategy
        assert isinstance(chunks, list)

    def test_handles_non_python_file(self, tmp_path: Path):
        """Test handling of non-Python files."""
        js_file = tmp_path / "script.js"
        js_file.write_text("console.log('hello');")
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        
        chunks = adapter.parse_file(js_file)
        assert len(chunks) == 0

    def test_handles_encoding_issues(self, tmp_path: Path):
        """Test handling of files with encoding issues."""
        # Create file with latin-1 encoding
        encoded_file = tmp_path / "encoded.py"
        encoded_file.write_bytes(b'"""Module with \xe9 accent."""\ndef func(): pass')
        
        adapter = PythonAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        
        chunks = adapter.parse_file(encoded_file)
        # Should handle gracefully
        assert isinstance(chunks, list)
