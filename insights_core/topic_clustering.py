"""
Topic Clustering - Automatic Content Organization
================================================
Automatically clusters content into strategic topics using:
- K-means clustering on embeddings
- Hierarchical topic taxonomy
- Topic performance analytics
- Content gap identification
- Topic-based recommendations

Features:
- Auto-discover optimal number of clusters
- Name topics using LLM
- Track topic performance
- Identify content gaps
- Generate topic strategies
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import asyncpg
import httpx
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score
from collections import Counter

logger = logging.getLogger(__name__)


class TopicClusterer:
    """
    Clusters content into strategic topics using embeddings
    """

    def __init__(self, db_dsn: str = None, ollama_url: str = None):
        """
        Initialize topic clusterer

        Args:
            db_dsn: Database connection string
            ollama_url: Ollama API URL
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.ollama_url = ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("TopicClusterer initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def fetch_embeddings(self, property: str) -> Tuple[List[str], np.ndarray]:
        """
        Fetch all embeddings for a property

        Args:
            property: Property URL

        Returns:
            Tuple of (page_paths, embeddings_matrix)
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        page_path,
                        content_embedding,
                        title,
                        word_count
                    FROM content.vw_latest_snapshots
                    WHERE property = $1
                        AND content_embedding IS NOT NULL
                        AND word_count > 100
                    ORDER BY page_path
                """, property)

            if not results:
                logger.warning(f"No embeddings found for {property}")
                return [], np.array([])

            page_paths = [r['page_path'] for r in results]
            embeddings = np.array([r['content_embedding'] for r in results])

            logger.info(f"Fetched {len(page_paths)} embeddings for {property}")
            return page_paths, embeddings

        except Exception as e:
            logger.error(f"Error fetching embeddings: {e}")
            return [], np.array([])

    def find_optimal_clusters(
        self,
        embeddings: np.ndarray,
        min_clusters: int = 5,
        max_clusters: int = 20
    ) -> int:
        """
        Find optimal number of clusters using silhouette score

        Args:
            embeddings: Embedding matrix
            min_clusters: Minimum clusters to test
            max_clusters: Maximum clusters to test

        Returns:
            Optimal number of clusters
        """
        if len(embeddings) < min_clusters:
            return max(2, len(embeddings) // 2)

        best_score = -1
        best_k = min_clusters

        for k in range(min_clusters, min(max_clusters + 1, len(embeddings))):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            try:
                score = silhouette_score(embeddings, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except Exception as e:
                logger.warning(f"Silhouette score failed for k={k}: {e}")
                continue

        logger.info(f"Optimal clusters: {best_k} (silhouette score: {best_score:.3f})")
        return best_k

    def cluster_embeddings(
        self,
        embeddings: np.ndarray,
        n_clusters: int = None
    ) -> Tuple[np.ndarray, np.ndarray, KMeans]:
        """
        Cluster embeddings using K-means

        Args:
            embeddings: Embedding matrix
            n_clusters: Number of clusters (auto-detect if None)

        Returns:
            Tuple of (labels, centroids, model)
        """
        try:
            if n_clusters is None:
                n_clusters = self.find_optimal_clusters(embeddings)

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            centroids = kmeans.cluster_centers_

            logger.info(f"Clustered into {n_clusters} topics")
            return labels, centroids, kmeans

        except Exception as e:
            logger.error(f"Error clustering: {e}")
            raise

    async def name_topic_with_llm(
        self,
        page_titles: List[str],
        sample_size: int = 10
    ) -> Dict:
        """
        Use LLM to generate topic name and description

        Args:
            page_titles: List of page titles in this cluster
            sample_size: Number of titles to use for naming

        Returns:
            Dict with name, description, keywords
        """
        try:
            # Sample titles
            sample = page_titles[:sample_size] if len(page_titles) > sample_size else page_titles

            prompt = f"""Analyze these page titles and identify the common topic:

Titles:
{chr(10).join(['- ' + title for title in sample])}

Provide a concise response in JSON format:
{{
    "topic_name": "Brief topic name (2-4 words)",
    "description": "One sentence description",
    "keywords": ["key", "words", "list"]
}}"""

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:8b",
                        "prompt": prompt,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('response', '')

                    # Try to parse JSON
                    import json
                    import re

                    json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group())
                        return {
                            'name': parsed.get('topic_name', 'Unnamed Topic'),
                            'description': parsed.get('description', ''),
                            'keywords': parsed.get('keywords', [])
                        }

            # Fallback: generate from most common words
            all_words = ' '.join(page_titles).lower().split()
            word_counts = Counter(all_words)
            top_words = [word for word, _ in word_counts.most_common(3) if len(word) > 3]

            return {
                'name': ' '.join(top_words[:3]).title(),
                'description': f'Content related to {", ".join(top_words[:5])}',
                'keywords': top_words[:10]
            }

        except Exception as e:
            logger.error(f"Error naming topic: {e}")
            return {
                'name': 'Unnamed Topic',
                'description': '',
                'keywords': []
            }

    async def store_topics(
        self,
        property: str,
        page_paths: List[str],
        labels: np.ndarray,
        centroids: np.ndarray
    ) -> Dict:
        """
        Store topics and page assignments in database

        Args:
            property: Property URL
            page_paths: List of page paths
            labels: Cluster labels for each page
            centroids: Cluster centroids (topic embeddings)

        Returns:
            Dict with topic IDs and assignments
        """
        try:
            pool = await self.get_pool()

            # Get page titles for naming
            async with pool.acquire() as conn:
                page_titles_dict = {}
                for page_path in page_paths:
                    title = await conn.fetchval("""
                        SELECT title
                        FROM content.vw_latest_snapshots
                        WHERE property = $1 AND page_path = $2
                    """, property, page_path)
                    page_titles_dict[page_path] = title or page_path

            # Group pages by cluster
            clusters = {}
            for page_path, label in zip(page_paths, labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(page_path)

            topic_ids = {}

            async with pool.acquire() as conn:
                for cluster_id, pages in clusters.items():
                    # Get titles for this cluster
                    cluster_titles = [page_titles_dict[p] for p in pages]

                    # Generate topic name using LLM
                    topic_info = await self.name_topic_with_llm(cluster_titles)

                    # Create slug
                    slug = topic_info['name'].lower().replace(' ', '-')

                    # Store topic
                    topic_id = await conn.fetchval("""
                        INSERT INTO content.topics (
                            name,
                            slug,
                            description,
                            topic_embedding,
                            page_count,
                            is_active
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (slug)
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            topic_embedding = EXCLUDED.topic_embedding,
                            page_count = EXCLUDED.page_count,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    """,
                        topic_info['name'],
                        slug,
                        topic_info['description'],
                        centroids[cluster_id].tolist(),
                        len(pages),
                        True
                    )

                    topic_ids[cluster_id] = topic_id

                    # Assign pages to topic
                    for page_path in pages:
                        await conn.execute("""
                            INSERT INTO content.page_topics (
                                page_path,
                                property,
                                topic_id,
                                relevance_score,
                                assignment_method
                            ) VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (page_path, property, topic_id)
                            DO UPDATE SET
                                relevance_score = EXCLUDED.relevance_score,
                                assigned_at = CURRENT_TIMESTAMP
                        """,
                            page_path,
                            property,
                            topic_id,
                            1.0,  # Full relevance for primary assignment
                            'auto'
                        )

            logger.info(f"Stored {len(topic_ids)} topics with {len(page_paths)} page assignments")

            return {
                'topics_created': len(topic_ids),
                'pages_assigned': len(page_paths),
                'topic_ids': topic_ids
            }

        except Exception as e:
            logger.error(f"Error storing topics: {e}")
            raise

    async def analyze_topic_performance(self, property: str) -> List[Dict]:
        """
        Analyze performance of each topic

        Args:
            property: Property URL

        Returns:
            List of topic performance metrics
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        t.id,
                        t.name,
                        t.slug,
                        t.page_count,
                        COUNT(DISTINCT pt.page_path) AS pages_with_data,
                        AVG(v.gsc_clicks) AS avg_clicks,
                        SUM(v.gsc_clicks) AS total_clicks,
                        AVG(v.gsc_position) AS avg_position,
                        AVG(v.gsc_ctr) AS avg_ctr,
                        AVG(q.overall_score) AS avg_quality
                    FROM content.topics t
                    LEFT JOIN content.page_topics pt
                        ON t.id = pt.topic_id
                    LEFT JOIN gsc.vw_unified_page_performance v
                        ON pt.property = v.property
                        AND pt.page_path = v.page_path
                        AND v.date >= CURRENT_DATE - INTERVAL '30 days'
                    LEFT JOIN content.quality_scores q
                        ON pt.property = q.property
                        AND pt.page_path = q.page_path
                    WHERE t.is_active = true
                    GROUP BY t.id, t.name, t.slug, t.page_count
                    ORDER BY total_clicks DESC NULLS LAST
                """)

                topics = []
                for row in results:
                    topics.append({
                        'topic_id': row['id'],
                        'name': row['name'],
                        'slug': row['slug'],
                        'page_count': row['page_count'],
                        'avg_clicks': round(float(row['avg_clicks']), 2) if row['avg_clicks'] else 0,
                        'total_clicks': int(row['total_clicks']) if row['total_clicks'] else 0,
                        'avg_position': round(float(row['avg_position']), 2) if row['avg_position'] else 0,
                        'avg_ctr': round(float(row['avg_ctr']), 2) if row['avg_ctr'] else 0,
                        'avg_quality': round(float(row['avg_quality']), 2) if row['avg_quality'] else 0
                    })

                logger.info(f"Analyzed {len(topics)} topics")
                return topics

        except Exception as e:
            logger.error(f"Error analyzing topic performance: {e}")
            return []

    async def auto_cluster_property(
        self,
        property: str,
        n_clusters: int = None
    ) -> Dict:
        """
        Complete auto-clustering workflow for a property

        Args:
            property: Property URL
            n_clusters: Number of clusters (auto-detect if None)

        Returns:
            Complete clustering results
        """
        try:
            logger.info(f"Starting auto-clustering for {property}")

            # Fetch embeddings
            page_paths, embeddings = await self.fetch_embeddings(property)

            if len(embeddings) == 0:
                return {'error': 'no_embeddings'}

            # Cluster
            labels, centroids, model = self.cluster_embeddings(embeddings, n_clusters)

            # Store topics
            store_result = await self.store_topics(property, page_paths, labels, centroids)

            # Analyze performance
            performance = await self.analyze_topic_performance(property)

            logger.info(f"Auto-clustering complete for {property}")

            return {
                'property': property,
                'pages_clustered': len(page_paths),
                'topics_created': store_result['topics_created'],
                'topic_performance': performance,
                'success': True
            }

        except Exception as e:
            logger.error(f"Error in auto-clustering: {e}")
            return {'error': str(e), 'success': False}

    def auto_cluster_sync(self, property: str, n_clusters: int = None) -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.auto_cluster_property(property, n_clusters))
