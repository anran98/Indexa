"""Tests for BM25Index."""

import shutil
import tempfile
from pathlib import Path

import pytest

from indexa.indexing.chunk import NormalizedChunk
from indexa.retrieval.bm25 import BM25Index


class TestBM25Index:
    """Test suite for BM25Index."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> Path:
        """Create a temporary database path using pytest's tmp_path."""
        return tmp_path / "test_bm25.db"

    @pytest.fixture
    def sample_chunks(self) -> list[NormalizedChunk]:
        """Create sample chunks for testing."""
        return [
            NormalizedChunk(
                id="chunk1",
                source_id="test",
                path="button.md",
                anchor="overview",
                title="Button Component",
                content="The Button component is used to trigger actions. Click the button to submit forms.",
                kind="section",
                depth=1,
                is_entrypoint=True,
            ),
            NormalizedChunk(
                id="chunk2",
                source_id="test",
                path="button.md",
                anchor="props",
                title="Button Props",
                content="The Button accepts onClick, disabled, and variant props for customization.",
                kind="section",
                depth=2,
                is_entrypoint=False,
            ),
            NormalizedChunk(
                id="chunk3",
                source_id="test",
                path="modal.md",
                anchor="overview",
                title="Modal Component",
                content="The Modal component displays content in a dialog overlay. Modals are used for confirmations.",
                kind="section",
                depth=1,
                is_entrypoint=True,
            ),
            NormalizedChunk(
                id="chunk4",
                source_id="other",
                path="input.md",
                anchor="overview",
                title="Input Component",
                content="The Input component is a form field for text entry.",
                kind="section",
                depth=1,
                is_entrypoint=False,
            ),
        ]

    @pytest.fixture
    def index(self, temp_db: Path, sample_chunks: list[NormalizedChunk]) -> BM25Index:
        """Create a populated BM25 index."""
        idx = BM25Index(temp_db)
        idx.create_index()
        idx.add_chunks(sample_chunks)
        return idx

    def test_create_index(self, temp_db: Path):
        """Test index creation."""
        idx = BM25Index(temp_db)
        idx.create_index()
        assert temp_db.exists()

    def test_add_chunks(self, temp_db: Path, sample_chunks: list[NormalizedChunk]):
        """Test adding chunks to index."""
        idx = BM25Index(temp_db)
        idx.create_index()
        idx.add_chunks(sample_chunks)

        stats = idx.get_stats()
        assert stats["chunk_count"] == len(sample_chunks)
        assert stats["actual_count"] == len(sample_chunks)

    def test_search_basic(self, index: BM25Index):
        """Test basic search functionality."""
        results = index.search("button")
        assert len(results) > 0
        assert results[0].chunk_id in ["chunk1", "chunk2"]

    def test_search_returns_ranked_results(self, index: BM25Index):
        """Test that results are ranked by relevance."""
        results = index.search("button component")

        # Should return results sorted by score
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_search_with_source_filter(self, index: BM25Index):
        """Test search with source ID filter."""
        results = index.search("component", source_id="test")

        # All results should be from "test" source
        assert len(results) > 0
        for r in results:
            assert r.chunk_id != "chunk4"  # chunk4 is from "other" source

    def test_search_returns_snippets(self, index: BM25Index):
        """Test that search returns snippets."""
        results = index.search("button")
        assert len(results) > 0
        assert results[0].snippet != ""

    def test_search_top_k(self, index: BM25Index):
        """Test top_k limit."""
        results = index.search("component", top_k=2)
        assert len(results) <= 2

    def test_search_no_results(self, index: BM25Index):
        """Test search with no matching terms."""
        results = index.search("xyznonexistent")
        assert len(results) == 0

    def test_search_empty_query(self, index: BM25Index):
        """Test search with empty query."""
        results = index.search("")
        assert len(results) == 0

    def test_search_stopwords_only(self, index: BM25Index):
        """Test search with only stopwords."""
        results = index.search("the and or")
        assert len(results) == 0

    def test_search_expanded(self, index: BM25Index):
        """Test search with pre-expanded terms."""
        results = index.search_expanded(["button", "btn", "click"])
        assert len(results) > 0

    def test_get_stats(self, index: BM25Index):
        """Test statistics retrieval."""
        stats = index.get_stats()
        assert "chunk_count" in stats
        assert "actual_count" in stats
        assert "db_path" in stats
        assert "db_size_bytes" in stats

    def test_clear(self, index: BM25Index):
        """Test clearing the index."""
        index.clear()
        stats = index.get_stats()
        assert stats["actual_count"] == 0

    def test_exists(self, temp_db: Path):
        """Test exists check."""
        idx = BM25Index(temp_db)
        assert not idx.exists()

        idx.create_index()
        assert idx.exists()

    def test_porter_stemming(self, index: BM25Index):
        """Test that porter stemming works (e.g., 'buttons' matches 'button')."""
        # FTS5 with porter tokenizer should stem words
        results = index.search("buttons")
        # Should find "Button" chunks due to stemming
        assert len(results) > 0

    def test_close(self, index: BM25Index):
        """Test closing the index."""
        index.close()
        # Should be able to reopen
        results = index.search("button")
        assert len(results) > 0
