"""Tests for QueryExpander."""

import pytest

from indexa.retrieval.query_expander import QueryExpander


class TestQueryExpander:
    """Test suite for QueryExpander."""

    @pytest.fixture
    def expander(self) -> QueryExpander:
        return QueryExpander()

    def test_expand_abbreviation(self, expander: QueryExpander):
        """Test that abbreviations are expanded."""
        result = expander.expand("btn click")
        assert "button" in result
        assert "btn" in result
        assert "click" in result

    def test_expand_full_form_to_abbreviation(self, expander: QueryExpander):
        """Test that full forms expand to abbreviations."""
        result = expander.expand("button style")
        assert "btn" in result
        assert "button" in result

    def test_expand_synonym(self, expander: QueryExpander):
        """Test that synonyms are expanded."""
        result = expander.expand("modal popup")
        assert "dialog" in result or "modal" in result

    def test_get_expansions_btn(self, expander: QueryExpander):
        """Test get_expansions for 'btn'."""
        expansions = expander.get_expansions("btn")
        assert "button" in expansions

    def test_get_expansions_button(self, expander: QueryExpander):
        """Test get_expansions for 'button'."""
        expansions = expander.get_expansions("button")
        assert "btn" in expansions

    def test_get_expansions_unknown_term(self, expander: QueryExpander):
        """Test get_expansions for unknown term."""
        expansions = expander.get_expansions("xyzunknownterm")
        assert expansions == []

    def test_get_all_terms(self, expander: QueryExpander):
        """Test get_all_terms includes original and expanded."""
        terms = expander.get_all_terms("btn config")
        assert "btn" in terms
        assert "button" in terms
        assert "config" in terms
        assert "configuration" in terms

    def test_no_duplicates_in_expand(self, expander: QueryExpander):
        """Test that expanded query has no duplicate terms."""
        result = expander.expand("button btn")
        terms = result.split()
        assert len(terms) == len(set(terms))

    def test_case_insensitive(self, expander: QueryExpander):
        """Test that expansion is case insensitive."""
        expansions = expander.get_expansions("BTN")
        assert "button" in expansions

    def test_add_custom_abbreviation(self, expander: QueryExpander):
        """Test adding custom abbreviations."""
        expander.add_abbreviation("foo", "foobar")
        expansions = expander.get_expansions("foo")
        assert "foobar" in expansions

        # Also test reverse
        expansions_rev = expander.get_expansions("foobar")
        assert "foo" in expansions_rev

    def test_add_custom_synonyms(self, expander: QueryExpander):
        """Test adding custom synonyms."""
        expander.add_synonyms("apple", "orange", "banana")

        expansions = expander.get_expansions("apple")
        assert "orange" in expansions
        assert "banana" in expansions

    def test_common_abbreviations(self, expander: QueryExpander):
        """Test that common programming abbreviations work."""
        test_cases = [
            ("cfg", "configuration"),
            ("auth", "authentication"),
            ("msg", "message"),
            ("err", "error"),
            ("req", "request"),
            ("res", "response"),
            ("fn", "function"),
            ("param", "parameter"),
            ("args", "arguments"),
            ("env", "environment"),
            ("dev", "development"),
            ("prod", "production"),
            ("db", "database"),
        ]

        for abbrev, full in test_cases:
            expansions = expander.get_expansions(abbrev)
            assert full in expansions, f"Expected '{full}' in expansions of '{abbrev}'"

    def test_ui_component_synonyms(self, expander: QueryExpander):
        """Test that UI component synonyms work."""
        # Modal/Dialog synonyms
        expansions = expander.get_expansions("modal")
        assert "dialog" in expansions or "popup" in expansions

        # Input synonyms
        expansions = expander.get_expansions("textfield")
        assert "input" in expansions or "field" in expansions

    def test_empty_query(self, expander: QueryExpander):
        """Test that empty query returns empty string."""
        result = expander.expand("")
        assert result == ""

    def test_query_with_special_chars(self, expander: QueryExpander):
        """Test that special characters are handled."""
        result = expander.expand("btn-click")
        # Should tokenize and expand
        assert "button" in result or "btn" in result
