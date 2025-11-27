"""
Tests for Topic Clustering Module
==================================
Tests automatic content organization into strategic topics.
"""
import asyncio
import os
import pytest
import numpy as np
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from insights_core.topic_clustering import TopicClusterer


@pytest.fixture
async def clusterer():
    """Create TopicClusterer instance"""
    clusterer = TopicClusterer(
        db_dsn=os.getenv('TEST_WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db'),
        ollama_url='http://localhost:11434'
    )
    yield clusterer
    await clusterer.close()


@pytest.fixture
def sample_embeddings():
    """Create sample embeddings for testing"""
    # Create 50 embeddings in 3 distinct clusters
    np.random.seed(42)

    # Cluster 1: Python content (embeddings around [1, 0, 0, ...])
    cluster1 = np.random.randn(15, 768) * 0.1
    cluster1[:, 0] += 1.0

    # Cluster 2: Java content (embeddings around [0, 1, 0, ...])
    cluster2 = np.random.randn(20, 768) * 0.1
    cluster2[:, 1] += 1.0

    # Cluster 3: JavaScript content (embeddings around [0, 0, 1, ...])
    cluster3 = np.random.randn(15, 768) * 0.1
    cluster3[:, 2] += 1.0

    return np.vstack([cluster1, cluster2, cluster3])


@pytest.fixture
def sample_page_paths():
    """Create sample page paths"""
    return [
        f'/python/tutorial-{i}/' for i in range(15)
    ] + [
        f'/java/guide-{i}/' for i in range(20)
    ] + [
        f'/javascript/howto-{i}/' for i in range(15)
    ]


# =============================================
# CLUSTERING ALGORITHM TESTS
# =============================================

def test_find_optimal_clusters(clusterer, sample_embeddings):
    """Test optimal cluster count detection"""
    optimal_k = clusterer.find_optimal_clusters(
        sample_embeddings,
        min_clusters=2,
        max_clusters=10
    )

    # Should find 3 clusters (our sample data has 3)
    assert 2 <= optimal_k <= 5, f"Expected 2-5 clusters, got {optimal_k}"


def test_find_optimal_clusters_small_dataset(clusterer):
    """Test with very small dataset"""
    small_embeddings = np.random.randn(3, 768)

    optimal_k = clusterer.find_optimal_clusters(
        small_embeddings,
        min_clusters=2,
        max_clusters=10
    )

    # Should return a reasonable small number
    assert optimal_k >= 2
    assert optimal_k <= len(small_embeddings)


def test_cluster_embeddings(clusterer, sample_embeddings):
    """Test K-means clustering"""
    labels, centroids, model = clusterer.cluster_embeddings(
        sample_embeddings,
        n_clusters=3
    )

    assert len(labels) == len(sample_embeddings)
    assert centroids.shape == (3, 768)
    assert len(np.unique(labels)) == 3

    # Check that labels are valid cluster IDs
    assert set(labels) == {0, 1, 2}


def test_cluster_embeddings_auto_detect(clusterer, sample_embeddings):
    """Test automatic cluster count detection"""
    labels, centroids, model = clusterer.cluster_embeddings(
        sample_embeddings,
        n_clusters=None  # Auto-detect
    )

    assert len(labels) == len(sample_embeddings)
    assert len(centroids) > 0

    # Should find reasonable number of clusters
    n_clusters = len(np.unique(labels))
    assert 2 <= n_clusters <= 10


# =============================================
# LLM TOPIC NAMING TESTS
# =============================================

@pytest.mark.asyncio
async def test_name_topic_with_llm(clusterer):
    """Test LLM-based topic naming"""
    page_titles = [
        "Python Tutorial: Getting Started",
        "Python Advanced Features",
        "Python Data Structures",
        "Learn Python Programming",
        "Python Best Practices"
    ]

    with patch('httpx.AsyncClient') as mock_client:
        # Mock Ollama response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '{"topic_name": "Python Programming", "description": "Content about Python programming language", "keywords": ["python", "programming", "tutorial"]}'
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await clusterer.name_topic_with_llm(page_titles)

    assert 'name' in result
    assert 'description' in result
    assert 'keywords' in result
    assert isinstance(result['keywords'], list)


@pytest.mark.asyncio
async def test_name_topic_with_llm_fallback(clusterer):
    """Test fallback when LLM fails"""
    page_titles = [
        "Python Tutorial Advanced",
        "Python Programming Guide",
        "Python Development"
    ]

    with patch('httpx.AsyncClient') as mock_client:
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await clusterer.name_topic_with_llm(page_titles)

    # Should fall back to word frequency
    assert 'name' in result
    assert 'python' in result['name'].lower()
    assert isinstance(result['keywords'], list)


# =============================================
# DATABASE OPERATIONS TESTS
# =============================================

@pytest.mark.asyncio
async def test_fetch_embeddings(clusterer):
    """Test fetching embeddings from database"""
    with patch.object(clusterer, 'get_pool') as mock_pool:
        # Mock database response
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                'page_path': '/page1/',
                'content_embedding': np.random.randn(768).tolist(),
                'title': 'Page 1',
                'word_count': 500
            },
            {
                'page_path': '/page2/',
                'content_embedding': np.random.randn(768).tolist(),
                'title': 'Page 2',
                'word_count': 600
            }
        ]

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        page_paths, embeddings = await clusterer.fetch_embeddings('https://example.com')

    assert len(page_paths) == 2
    assert embeddings.shape == (2, 768)
    assert page_paths[0] == '/page1/'


@pytest.mark.asyncio
async def test_fetch_embeddings_empty(clusterer):
    """Test fetching embeddings when none exist"""
    with patch.object(clusterer, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        page_paths, embeddings = await clusterer.fetch_embeddings('https://example.com')

    assert len(page_paths) == 0
    assert len(embeddings) == 0


@pytest.mark.asyncio
async def test_store_topics(clusterer, sample_page_paths):
    """Test storing topics in database"""
    labels = np.array([0] * 15 + [1] * 20 + [2] * 15)
    centroids = np.random.randn(3, 768)

    with patch.object(clusterer, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()

        # Mock title fetches
        mock_conn.fetchval.side_effect = [
            f"Title for {path}" for path in sample_page_paths
        ]

        # Mock topic inserts
        mock_conn.fetchval.return_value = 'topic-uuid-123'
        mock_conn.execute.return_value = None

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        with patch.object(clusterer, 'name_topic_with_llm') as mock_name:
            mock_name.return_value = {
                'name': 'Test Topic',
                'description': 'Test description',
                'keywords': ['test', 'topic']
            }

            result = await clusterer.store_topics(
                'https://example.com',
                sample_page_paths,
                labels,
                centroids
            )

    assert result['topics_created'] == 3
    assert result['pages_assigned'] == 50


@pytest.mark.asyncio
async def test_analyze_topic_performance(clusterer):
    """Test topic performance analysis"""
    with patch.object(clusterer, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                'id': 'topic-1',
                'name': 'Python Programming',
                'slug': 'python-programming',
                'page_count': 25,
                'pages_with_data': 20,
                'avg_clicks': 150.5,
                'total_clicks': 3010,
                'avg_position': 12.3,
                'avg_ctr': 0.034,
                'avg_quality': 78.5
            }
        ]

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        performance = await clusterer.analyze_topic_performance('https://example.com')

    assert len(performance) == 1
    assert performance[0]['name'] == 'Python Programming'
    assert performance[0]['avg_clicks'] == 150.5
    assert performance[0]['total_clicks'] == 3010


# =============================================
# END-TO-END WORKFLOW TESTS
# =============================================

@pytest.mark.asyncio
async def test_auto_cluster_property_success(clusterer, sample_embeddings, sample_page_paths):
    """Test complete auto-clustering workflow"""
    with patch.object(clusterer, 'fetch_embeddings') as mock_fetch:
        mock_fetch.return_value = (sample_page_paths, sample_embeddings)

        with patch.object(clusterer, 'store_topics') as mock_store:
            mock_store.return_value = {
                'topics_created': 3,
                'pages_assigned': 50
            }

            with patch.object(clusterer, 'analyze_topic_performance') as mock_analyze:
                mock_analyze.return_value = [
                    {'topic_id': '1', 'name': 'Topic 1', 'total_clicks': 1000}
                ]

                result = await clusterer.auto_cluster_property(
                    'https://example.com',
                    n_clusters=3
                )

    assert result['success'] is True
    assert result['pages_clustered'] == 50
    assert result['topics_created'] == 3
    assert len(result['topic_performance']) == 1


@pytest.mark.asyncio
async def test_auto_cluster_property_no_embeddings(clusterer):
    """Test auto-clustering with no embeddings"""
    with patch.object(clusterer, 'fetch_embeddings') as mock_fetch:
        mock_fetch.return_value = ([], np.array([]))

        result = await clusterer.auto_cluster_property('https://example.com')

    assert result['error'] == 'no_embeddings'


def test_auto_cluster_sync(clusterer, sample_embeddings, sample_page_paths):
    """Test synchronous wrapper for Celery"""
    with patch.object(clusterer, 'fetch_embeddings') as mock_fetch:
        mock_fetch.return_value = (sample_page_paths, sample_embeddings)

        with patch.object(clusterer, 'store_topics') as mock_store:
            mock_store.return_value = {'topics_created': 3, 'pages_assigned': 50}

            with patch.object(clusterer, 'analyze_topic_performance') as mock_analyze:
                mock_analyze.return_value = []

                result = clusterer.auto_cluster_sync('https://example.com', n_clusters=3)

    assert result['success'] is True


# =============================================
# EDGE CASES
# =============================================

def test_cluster_embeddings_single_cluster(clusterer):
    """Test with only 1 cluster requested"""
    embeddings = np.random.randn(10, 768)

    # K-means requires n_clusters >= 2
    with pytest.raises(Exception):
        clusterer.cluster_embeddings(embeddings, n_clusters=1)


def test_cluster_embeddings_more_clusters_than_samples(clusterer):
    """Test when requesting more clusters than samples"""
    embeddings = np.random.randn(5, 768)

    # Should handle gracefully
    labels, centroids, model = clusterer.cluster_embeddings(embeddings, n_clusters=3)

    assert len(labels) == 5
    assert len(centroids) <= 5


@pytest.mark.asyncio
async def test_name_topic_empty_titles(clusterer):
    """Test topic naming with empty title list"""
    result = await clusterer.name_topic_with_llm([])

    assert 'name' in result
    assert result['name'] == 'Unnamed Topic'


# =============================================
# INTEGRATION TESTS
# =============================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_clustering_workflow():
    """Integration test for complete clustering workflow"""
    # This test requires actual database and Ollama
    # Skip if not in integration test mode
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    clusterer = TopicClusterer()

    try:
        # Fetch real embeddings
        page_paths, embeddings = await clusterer.fetch_embeddings('https://blog.aspose.net')

        if len(embeddings) > 0:
            # Cluster
            labels, centroids, model = clusterer.cluster_embeddings(embeddings)

            # Store (in test mode, would rollback)
            # result = await clusterer.store_topics(...)

            assert len(labels) == len(page_paths)
            assert len(centroids) > 0

    finally:
        await clusterer.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
