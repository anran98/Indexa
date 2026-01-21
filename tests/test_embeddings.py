"""Tests for embedding providers."""

import os
from unittest.mock import MagicMock, patch

import pytest

from indexa.retrieval.embeddings import (
    EmbeddingProvider,
    LocalEmbeddings,
    OpenAIEmbeddings,
    get_embedding_provider,
)


class TestEmbeddingProvider:
    """Test the abstract EmbeddingProvider interface."""

    def test_abstract_methods(self):
        """Test that EmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore


class TestOpenAIEmbeddings:
    """Test OpenAI embedding provider."""

    def test_requires_api_key(self):
        """Test that OpenAI provider requires API key."""
        # Temporarily unset the env var
        original = os.environ.get("OPENAI_API_KEY")
        if original:
            del os.environ["OPENAI_API_KEY"]

        try:
            with pytest.raises(ValueError, match="API key required"):
                OpenAIEmbeddings()
        finally:
            if original:
                os.environ["OPENAI_API_KEY"] = original

    def test_accepts_api_key_parameter(self):
        """Test that API key can be passed as parameter."""
        with patch("openai.OpenAI"):
            provider = OpenAIEmbeddings(api_key="test-key")
            assert provider.model_name == "text-embedding-3-small"
            assert provider.dimension == 1536

    def test_custom_model(self):
        """Test custom model name."""
        with patch("openai.OpenAI"):
            provider = OpenAIEmbeddings(
                api_key="test-key",
                model="text-embedding-3-large",
            )
            assert provider.model_name == "text-embedding-3-large"

    @patch("openai.OpenAI")
    def test_embed_texts(self, mock_openai):
        """Test embedding multiple texts."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock the embeddings response
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]
        mock_client.embeddings.create.return_value = mock_response

        provider = OpenAIEmbeddings(api_key="test-key")
        embeddings = provider.embed_texts(["hello", "world"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        mock_client.embeddings.create.assert_called_once()

    @patch("openai.OpenAI")
    def test_embed_query(self, mock_openai):
        """Test embedding a single query."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        provider = OpenAIEmbeddings(api_key="test-key")
        embedding = provider.embed_query("hello")

        assert len(embedding) == 1536

    @patch("openai.OpenAI")
    def test_empty_texts(self, mock_openai):
        """Test embedding empty list."""
        provider = OpenAIEmbeddings(api_key="test-key")
        embeddings = provider.embed_texts([])
        assert embeddings == []


class TestLocalEmbeddings:
    """Test local embedding provider."""

    @pytest.fixture
    def mock_sentence_transformer(self):
        """Mock SentenceTransformer for testing."""
        with patch("sentence_transformers.SentenceTransformer") as mock:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = MagicMock(
                tolist=lambda: [[0.1] * 384, [0.2] * 384]
            )
            mock.return_value = mock_model
            yield mock

    def test_default_model(self, mock_sentence_transformer):
        """Test default model name."""
        provider = LocalEmbeddings()
        assert provider.model_name == "all-MiniLM-L6-v2"
        assert provider.dimension == 384

    def test_custom_model(self, mock_sentence_transformer):
        """Test custom model name."""
        provider = LocalEmbeddings(model="paraphrase-MiniLM-L6-v2")
        assert provider.model_name == "paraphrase-MiniLM-L6-v2"

    def test_embed_texts(self, mock_sentence_transformer):
        """Test embedding multiple texts."""
        provider = LocalEmbeddings()
        embeddings = provider.embed_texts(["hello", "world"])

        assert len(embeddings) == 2
        mock_sentence_transformer.return_value.encode.assert_called_once()

    def test_empty_texts(self, mock_sentence_transformer):
        """Test embedding empty list."""
        provider = LocalEmbeddings()
        embeddings = provider.embed_texts([])
        assert embeddings == []


class TestGetEmbeddingProvider:
    """Test the factory function."""

    def test_get_openai_provider(self):
        """Test getting OpenAI provider."""
        with patch("openai.OpenAI"):
            provider = get_embedding_provider(
                provider="openai",
                api_key="test-key",
            )
            assert isinstance(provider, OpenAIEmbeddings)

    def test_get_local_provider(self):
        """Test getting local provider."""
        with patch("sentence_transformers.SentenceTransformer") as mock:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock.return_value = mock_model

            provider = get_embedding_provider(provider="local")
            assert isinstance(provider, LocalEmbeddings)

    def test_unknown_provider(self):
        """Test error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider(provider="unknown")

    def test_default_provider(self):
        """Test default provider is OpenAI."""
        with patch("openai.OpenAI"):
            provider = get_embedding_provider(api_key="test-key")
            assert isinstance(provider, OpenAIEmbeddings)
