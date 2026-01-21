"""BM25 search using SQLite FTS5."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from indexa.indexing.chunk import NormalizedChunk


@dataclass
class BM25Result:
    """A single BM25 search result."""

    chunk_id: str
    score: float
    snippet: str


class BM25Index:
    """BM25 search index using SQLite FTS5.

    SQLite FTS5 provides built-in BM25 ranking, which is the industry
    standard for lexical search. It's fast, reliable, and well-tested.

    Features:
    - Porter stemming for morphological normalization
    - Built-in BM25 ranking
    - Efficient incremental updates
    - Persistent storage
    """

    # Stopwords to filter out (common English words)
    STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "again", "further", "then", "once",
        "here", "there", "when", "where", "why", "how", "all", "each", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "and", "but",
        "or", "if", "because", "until", "while", "this", "that", "these",
        "those", "it", "its", "they", "them", "their", "what", "which", "who",
        "whom", "whose", "we", "you", "your", "he", "him", "his", "she", "her",
    })

    def __init__(self, db_path: Path | str) -> None:
        """Initialize BM25 index.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def create_index(self) -> None:
        """Create the FTS5 virtual table.

        Uses porter tokenizer for stemming, which handles:
        - running -> run
        - buttons -> button
        - configuration -> configur
        """
        conn = self._get_connection()

        # Drop existing table if any
        conn.execute("DROP TABLE IF EXISTS chunks_fts")

        # Create FTS5 table with porter stemmer
        # Note: FTS5 is available in Python's sqlite3 by default
        conn.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id,
                title,
                content,
                source_id,
                path,
                tokenize='porter unicode61'
            )
        """)

        # Create metadata table
        conn.execute("DROP TABLE IF EXISTS bm25_metadata")
        conn.execute("""
            CREATE TABLE bm25_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()

    def add_chunks(self, chunks: list[NormalizedChunk]) -> None:
        """Add chunks to the index.

        Args:
            chunks: List of chunks to index
        """
        conn = self._get_connection()

        # Prepare batch insert
        rows = []
        for chunk in chunks:
            # Preprocess text for better matching
            title = self._preprocess(chunk.title)
            content = self._preprocess(chunk.content)

            rows.append((
                chunk.id,
                title,
                content,
                chunk.source_id,
                chunk.path,
            ))

        # Bulk insert
        conn.executemany(
            "INSERT INTO chunks_fts (chunk_id, title, content, source_id, path) VALUES (?, ?, ?, ?, ?)",
            rows,
        )

        # Update metadata
        conn.execute(
            "INSERT OR REPLACE INTO bm25_metadata (key, value) VALUES (?, ?)",
            ("chunk_count", str(len(chunks))),
        )

        conn.commit()

    def search(
        self,
        query: str,
        source_id: str | None = None,
        top_k: int = 20,
    ) -> list[BM25Result]:
        """Search the index using BM25 ranking.

        Args:
            query: Search query
            source_id: Optional source filter
            top_k: Maximum results to return

        Returns:
            List of BM25Result objects sorted by score (descending)
        """
        conn = self._get_connection()

        # Preprocess query
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Build FTS5 query - use OR to match any term
        # This is more forgiving than AND for user queries
        fts_query = " OR ".join(query_terms)

        # Build SQL with optional source filter
        if source_id:
            sql = """
                SELECT
                    chunk_id,
                    bm25(chunks_fts) as score,
                    snippet(chunks_fts, 2, '**', '**', '...', 32) as snippet
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                AND source_id = ?
                ORDER BY score
                LIMIT ?
            """
            params = (fts_query, source_id, top_k)
        else:
            sql = """
                SELECT
                    chunk_id,
                    bm25(chunks_fts) as score,
                    snippet(chunks_fts, 2, '**', '**', '...', 32) as snippet
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            params = (fts_query, top_k)

        try:
            cursor = conn.execute(sql, params)
            results = []

            for row in cursor:
                # BM25 returns negative scores (lower = better match)
                # Convert to positive scores for consistency
                score = -row["score"]

                results.append(BM25Result(
                    chunk_id=row["chunk_id"],
                    score=score,
                    snippet=row["snippet"],
                ))

            return results

        except sqlite3.OperationalError as e:
            # Handle case where query has no valid terms
            if "no such column" in str(e) or "syntax error" in str(e):
                return []
            raise

    def search_expanded(
        self,
        terms: list[str],
        source_id: str | None = None,
        top_k: int = 20,
    ) -> list[BM25Result]:
        """Search with pre-expanded query terms.

        Useful when QueryExpander has already expanded the query.

        Args:
            terms: List of search terms (already expanded)
            source_id: Optional source filter
            top_k: Maximum results

        Returns:
            List of BM25Result objects
        """
        if not terms:
            return []

        # Filter and clean terms
        clean_terms = [self._clean_term(t) for t in terms]
        clean_terms = [t for t in clean_terms if t and t not in self.STOPWORDS]

        if not clean_terms:
            return []

        # Build FTS query
        fts_query = " OR ".join(clean_terms)

        conn = self._get_connection()

        if source_id:
            sql = """
                SELECT
                    chunk_id,
                    bm25(chunks_fts) as score,
                    snippet(chunks_fts, 2, '**', '**', '...', 32) as snippet
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                AND source_id = ?
                ORDER BY score
                LIMIT ?
            """
            params = (fts_query, source_id, top_k)
        else:
            sql = """
                SELECT
                    chunk_id,
                    bm25(chunks_fts) as score,
                    snippet(chunks_fts, 2, '**', '**', '...', 32) as snippet
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            params = (fts_query, top_k)

        try:
            cursor = conn.execute(sql, params)
            results = []

            for row in cursor:
                score = -row["score"]
                results.append(BM25Result(
                    chunk_id=row["chunk_id"],
                    score=score,
                    snippet=row["snippet"],
                ))

            return results

        except sqlite3.OperationalError:
            return []

    def get_stats(self) -> dict:
        """Get index statistics.

        Returns:
            Dict with index stats
        """
        conn = self._get_connection()

        try:
            # Get chunk count
            cursor = conn.execute(
                "SELECT value FROM bm25_metadata WHERE key = 'chunk_count'"
            )
            row = cursor.fetchone()
            chunk_count = int(row["value"]) if row else 0

            # Get actual row count
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM chunks_fts")
            row = cursor.fetchone()
            actual_count = row["cnt"] if row else 0

            return {
                "chunk_count": chunk_count,
                "actual_count": actual_count,
                "db_path": str(self._db_path),
                "db_size_bytes": self._db_path.stat().st_size if self._db_path.exists() else 0,
            }
        except sqlite3.OperationalError:
            return {
                "chunk_count": 0,
                "actual_count": 0,
                "db_path": str(self._db_path),
                "db_size_bytes": 0,
            }

    def clear(self) -> None:
        """Clear all data from the index."""
        conn = self._get_connection()
        conn.execute("DELETE FROM chunks_fts")
        conn.execute("DELETE FROM bm25_metadata")
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _preprocess(self, text: str) -> str:
        """Preprocess text for indexing.

        - Lowercase
        - Remove excessive whitespace
        - Keep alphanumeric and common punctuation
        """
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for search query.

        Args:
            text: Text to tokenize

        Returns:
            List of clean tokens
        """
        text = text.lower()
        tokens = re.findall(r"\w+", text)

        # Filter stopwords and short tokens
        return [t for t in tokens if len(t) > 1 and t not in self.STOPWORDS]

    def _clean_term(self, term: str) -> str:
        """Clean a single term for FTS query."""
        # Remove non-word characters except underscores
        clean = re.sub(r"[^\w]", "", term.lower())
        return clean

    def exists(self) -> bool:
        """Check if the index database exists."""
        return self._db_path.exists()
