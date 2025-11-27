"""
Tests for Embedding Generator
"""
import pytest
import numpy as np
from insights_core.embeddings import EmbeddingGenerator


class TestEmbeddingGenerator:
    """Test embedding generation and storage"""

    def test_initialization(self):
        """Test embedding generator initialization"""
        generator = EmbeddingGenerator(model_name='all-MiniLM-L6-v2')
        assert generator.model is not None
        assert generator.model_name == 'all-MiniLM-L6-v2'

    def test_generate_embedding_basic(self):
        """Test basic embedding generation"""
        generator = EmbeddingGenerator()
        text = "This is a test sentence for embedding generation."

        embedding = generator.generate_embedding(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (768,)  # 768-dimensional vector
        assert not np.all(embedding == 0)  # Not all zeros

    def test_generate_embedding_empty(self):
        """Test embedding generation with empty text"""
        generator = EmbeddingGenerator()
        embedding = generator.generate_embedding("")

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (768,)
        assert np.all(embedding == 0)  # Should be zero vector

    def test_generate_embedding_long_text(self):
        """Test embedding generation with long text"""
        generator = EmbeddingGenerator()
        long_text = "Test sentence. " * 1000  # Very long text

        embedding = generator.generate_embedding(long_text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (768,)

    def test_embedding_similarity(self):
        """Test that similar texts have similar embeddings"""
        generator = EmbeddingGenerator()

        text1 = "The cat sat on the mat"
        text2 = "A feline rested on the rug"
        text3 = "Machine learning is fascinating"

        emb1 = generator.generate_embedding(text1)
        emb2 = generator.generate_embedding(text2)
        emb3 = generator.generate_embedding(text3)

        # Calculate cosine similarity
        sim_12 = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        sim_13 = np.dot(emb1, emb3) / (np.linalg.norm(emb1) * np.linalg.norm(emb3))

        # Similar texts should be more similar
        assert sim_12 > sim_13

    @pytest.mark.asyncio
    async def test_store_embedding_mock(self, mocker):
        """Test storing embedding (mocked database)"""
        generator = EmbeddingGenerator()

        # Mock database pool
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        generator._pool = mock_pool

        success = await generator.store_embedding(
            property="https://example.com",
            page_path="/test-page/",
            content="This is test content for embedding storage.",
            title="Test Page"
        )

        assert success
        mock_conn.execute.assert_called_once()

    def test_ollama_initialization(self):
        """Test Ollama-based embedding initialization"""
        generator = EmbeddingGenerator(use_ollama=True)

        assert generator.use_ollama
        assert generator.model is None  # No transformer model loaded
        assert generator.ollama_url is not None


class TestEmbeddingSimilarity:
    """Test semantic similarity features"""

    @pytest.mark.asyncio
    async def test_find_similar_pages_mock(self, mocker):
        """Test finding similar pages (mocked)"""
        generator = EmbeddingGenerator()

        # Mock database
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock query results
        mock_conn.fetch.return_value = [
            {
                'page_path': '/similar-page-1/',
                'title': 'Similar Page 1',
                'word_count': 500,
                'similarity': 0.85
            },
            {
                'page_path': '/similar-page-2/',
                'title': 'Similar Page 2',
                'word_count': 600,
                'similarity': 0.78
            }
        ]

        generator._pool = mock_pool

        results = await generator.find_similar_pages(
            property="https://example.com",
            page_path="/test-page/",
            limit=10,
            threshold=0.7
        )

        assert len(results) == 2
        assert results[0]['similarity'] == 0.85
        assert results[1]['page_path'] == '/similar-page-2/'

    @pytest.mark.asyncio
    async def test_find_cannibalization_mock(self, mocker):
        """Test cannibalization detection (mocked)"""
        generator = EmbeddingGenerator()

        # Mock database
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock cannibalization pairs
        mock_conn.fetch.return_value = [
            {
                'page_a': '/page-1/',
                'page_b': '/page-2/',
                'similarity': 0.92,
                'title_a': 'Page 1',
                'title_b': 'Page 2',
                'words_a': 500,
                'words_b': 550
            }
        ]

        generator._pool = mock_pool

        results = await generator.find_cannibalization(
            property="https://example.com",
            similarity_threshold=0.85
        )

        assert len(results) == 1
        assert results[0]['similarity'] == 0.92
        assert results[0]['page_a'] == '/page-1/'
