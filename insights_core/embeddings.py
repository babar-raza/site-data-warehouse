"""
Embedding Generator - Semantic Search & Content Clustering
==========================================================
Generates and stores vector embeddings for content using:
- sentence-transformers (default: all-MiniLM-L6-v2)
- Ollama (optional: nomic-embed-text)

Features:
- Generate embeddings for page content
- Store in PostgreSQL with pgvector
- Semantic similarity search
- Cannibalization detection
- Topic clustering
"""
import hashlib
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import asyncpg
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates and manages content embeddings for semantic search
    """

    def __init__(
        self,
        db_dsn: str = None,
        model_name: str = 'all-MiniLM-L6-v2',
        use_ollama: bool = False
    ):
        """
        Initialize embedding generator

        Args:
            db_dsn: Database connection string
            model_name: Sentence transformer model name
            use_ollama: Use Ollama instead of sentence-transformers
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.model_name = model_name
        self.use_ollama = use_ollama
        self._pool: Optional[asyncpg.Pool] = None

        # Initialize model
        if use_ollama:
            self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
            self.model = None
            logger.info(f"Using Ollama for embeddings at {self.ollama_url}")
        else:
            logger.info(f"Loading sentence-transformer model: {model_name}")
            self.model = SentenceTransformer(model_name)
            logger.info("Model loaded successfully")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for text

        Args:
            text: Input text

        Returns:
            768-dimensional embedding vector
        """
        if not text or len(text.strip()) == 0:
            # Return zero vector for empty text
            return np.zeros(768)

        if self.use_ollama:
            return self._generate_ollama_embedding(text)
        else:
            return self._generate_transformer_embedding(text)

    def _generate_transformer_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using sentence-transformers"""
        try:
            # Truncate if too long (model limit is typically 512 tokens)
            if len(text) > 5000:
                text = text[:5000]

            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding

        except Exception as e:
            logger.error(f"Error generating transformer embedding: {e}")
            return np.zeros(768)

    def _generate_ollama_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using Ollama"""
        try:
            import httpx

            response = httpx.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text[:2000]  # Limit input size
                },
                timeout=30.0
            )

            if response.status_code == 200:
                embedding = response.json()['embedding']
                return np.array(embedding, dtype=np.float32)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return np.zeros(768)

        except Exception as e:
            logger.error(f"Error generating Ollama embedding: {e}")
            return np.zeros(768)

    async def store_embedding(
        self,
        property: str,
        page_path: str,
        content: str,
        title: str = None,
        html: str = None
    ) -> bool:
        """
        Store page content with embedding in database

        Args:
            property: Property URL
            page_path: Page path
            content: Text content for embedding
            title: Page title
            html: Raw HTML (optional)

        Returns:
            True if successful
        """
        try:
            pool = await self.get_pool()

            # Generate embeddings
            content_embedding = self.generate_embedding(content)
            title_embedding = self.generate_embedding(title) if title else None

            # Calculate content hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # Calculate metrics
            word_count = len(content.split())
            char_count = len(content)

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO content.page_snapshots (
                        property,
                        page_path,
                        url,
                        text_content,
                        html_content,
                        title,
                        word_count,
                        character_count,
                        content_hash,
                        content_embedding,
                        title_embedding,
                        embedding_model,
                        analyzed_at,
                        snapshot_date
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (property, page_path, snapshot_date)
                    DO UPDATE SET
                        text_content = EXCLUDED.text_content,
                        content_embedding = EXCLUDED.content_embedding,
                        title_embedding = EXCLUDED.title_embedding,
                        word_count = EXCLUDED.word_count,
                        content_hash = EXCLUDED.content_hash,
                        analyzed_at = EXCLUDED.analyzed_at
                """,
                    property,
                    page_path,
                    f"{property}{page_path}",
                    content,
                    html,
                    title,
                    word_count,
                    char_count,
                    content_hash,
                    content_embedding.tolist(),
                    title_embedding.tolist() if title_embedding is not None else None,
                    self.model_name if not self.use_ollama else 'nomic-embed-text',
                    datetime.utcnow(),
                    datetime.utcnow().date()
                )

            logger.info(f"Stored embedding for {property}{page_path}")
            return True

        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            return False

    async def find_similar_pages(
        self,
        property: str,
        page_path: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict]:
        """
        Find similar pages using vector similarity

        Args:
            property: Property URL
            page_path: Reference page path
            limit: Max results to return
            threshold: Minimum similarity (0-1)

        Returns:
            List of similar pages with scores
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        s2.page_path,
                        s2.title,
                        s2.word_count,
                        1 - (s1.content_embedding <=> s2.content_embedding) AS similarity
                    FROM content.page_snapshots s1
                    CROSS JOIN LATERAL (
                        SELECT *
                        FROM content.page_snapshots
                        WHERE property = $1
                            AND page_path != $2
                            AND content_embedding IS NOT NULL
                        ORDER BY content_embedding <=> s1.content_embedding
                        LIMIT $3 * 2  -- Get more then filter
                    ) s2
                    WHERE s1.property = $1
                        AND s1.page_path = $2
                        AND s1.content_embedding IS NOT NULL
                        AND (1 - (s1.content_embedding <=> s2.content_embedding)) >= $4
                    ORDER BY similarity DESC
                    LIMIT $3
                """, property, page_path, limit, threshold)

                return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"Error finding similar pages: {e}")
            return []

    async def find_cannibalization(
        self,
        property: str,
        similarity_threshold: float = 0.8
    ) -> List[Dict]:
        """
        Detect content cannibalization (pages with very similar content)

        Args:
            property: Property URL
            similarity_threshold: Minimum similarity to flag (0-1)

        Returns:
            List of cannibalization pairs
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Find pairs with high similarity
                results = await conn.fetch("""
                    SELECT
                        s1.page_path AS page_a,
                        s2.page_path AS page_b,
                        1 - (s1.content_embedding <=> s2.content_embedding) AS similarity,
                        s1.title AS title_a,
                        s2.title AS title_b,
                        s1.word_count AS words_a,
                        s2.word_count AS words_b
                    FROM content.vw_latest_snapshots s1
                    JOIN content.vw_latest_snapshots s2
                        ON s1.property = s2.property
                        AND s1.page_path < s2.page_path  -- Avoid duplicates
                        AND s1.content_embedding IS NOT NULL
                        AND s2.content_embedding IS NOT NULL
                    WHERE s1.property = $1
                        AND (1 - (s1.content_embedding <=> s2.content_embedding)) >= $2
                    ORDER BY similarity DESC
                    LIMIT 100
                """, property, similarity_threshold)

                cannibalization_pairs = []

                for row in results:
                    # Insert or update cannibalization table
                    await conn.execute("""
                        INSERT INTO content.cannibalization_pairs (
                            property,
                            page_a,
                            page_b,
                            similarity_score,
                            conflict_severity,
                            detected_at,
                            last_checked
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (property, page_a, page_b)
                        DO UPDATE SET
                            similarity_score = EXCLUDED.similarity_score,
                            last_checked = EXCLUDED.last_checked
                    """,
                        property,
                        row['page_a'],
                        row['page_b'],
                        float(row['similarity']),
                        'high' if row['similarity'] >= 0.9 else 'medium',
                        datetime.utcnow(),
                        datetime.utcnow()
                    )

                    cannibalization_pairs.append(dict(row))

                logger.info(f"Found {len(cannibalization_pairs)} cannibalization pairs for {property}")
                return cannibalization_pairs

        except Exception as e:
            logger.error(f"Error detecting cannibalization: {e}")
            return []

    async def cluster_content(
        self,
        property: str,
        n_clusters: int = 10
    ) -> Dict:
        """
        Cluster content into topics using K-means

        Args:
            property: Property URL
            n_clusters: Number of clusters

        Returns:
            Clustering results
        """
        try:
            from sklearn.cluster import KMeans

            pool = await self.get_pool()

            # Get all embeddings
            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT page_path, content_embedding
                    FROM content.vw_latest_snapshots
                    WHERE property = $1
                        AND content_embedding IS NOT NULL
                """, property)

            if len(results) < n_clusters:
                logger.warning(f"Not enough pages ({len(results)}) for {n_clusters} clusters")
                return {'error': 'insufficient_data'}

            # Extract embeddings
            page_paths = [r['page_path'] for r in results]
            embeddings = np.array([r['content_embedding'] for r in results])

            # Perform clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            labels = kmeans.fit_predict(embeddings)

            # Group pages by cluster
            clusters = {}
            for page_path, label in zip(page_paths, labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(page_path)

            logger.info(f"Clustered {len(page_paths)} pages into {n_clusters} topics")

            return {
                'n_clusters': n_clusters,
                'n_pages': len(page_paths),
                'clusters': clusters,
                'centroids': kmeans.cluster_centers_.tolist()
            }

        except Exception as e:
            logger.error(f"Error clustering content: {e}")
            return {'error': str(e)}

    def generate_for_property(
        self,
        property: str,
        page_paths: List[str] = None
    ) -> Dict:
        """
        Sync wrapper for generating embeddings (for Celery)

        Args:
            property: Property URL
            page_paths: Optional specific pages

        Returns:
            Results dict
        """
        import asyncio
        return asyncio.run(self._generate_for_property_async(property, page_paths))

    async def _generate_for_property_async(
        self,
        property: str,
        page_paths: List[str] = None
    ) -> Dict:
        """Async implementation of generate_for_property"""
        try:
            pool = await self.get_pool()

            # Get pages to process
            async with pool.acquire() as conn:
                if page_paths:
                    query = """
                        SELECT page_path, title, text_content
                        FROM content.page_snapshots
                        WHERE property = $1 AND page_path = ANY($2)
                    """
                    results = await conn.fetch(query, property, page_paths)
                else:
                    query = """
                        SELECT DISTINCT ON (page_path) page_path, title, text_content
                        FROM content.page_snapshots
                        WHERE property = $1
                        ORDER BY page_path, snapshot_date DESC
                    """
                    results = await conn.fetch(query, property)

            embeddings_created = 0

            for row in results:
                success = await self.store_embedding(
                    property,
                    row['page_path'],
                    row['text_content'] or '',
                    row['title']
                )
                if success:
                    embeddings_created += 1

            return {
                'property': property,
                'pages_processed': len(results),
                'embeddings_created': embeddings_created
            }

        except Exception as e:
            logger.error(f"Error generating embeddings for property: {e}")
            return {'error': str(e)}
