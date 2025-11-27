"""
Content Quality Detector
Detects content quality issues in page snapshots

This detector analyzes content.page_snapshots table to identify:
- Low readability scores (Flesch Reading Ease < 60)
- Missing or short meta descriptions (< 120 chars)
- Title length issues (< 30 or > 60 chars)
- Missing H1 tags
- Thin content (< 300 words)
- Content cannibalization (similar pages competing for same keywords)

Each detected issue generates either a RISK insight (quality issues) or
DIAGNOSIS insight (cannibalization).
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
import asyncio

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    EntityType,
    InsightCategory,
    InsightSeverity,
    InsightMetrics
)

logger = logging.getLogger(__name__)


class ContentQualityDetector(BaseDetector):
    """
    Detects content quality issues from page snapshots

    Checks performed:
    1. Low readability (flesch_reading_ease < 60) - Indicates difficult-to-read content
    2. Missing meta description (NULL or length < 120) - SEO best practice violation
    3. Title too short (< 30 chars) - SEO best practice violation
    4. Title too long (> 60 chars) - May be truncated in search results
    5. Missing H1 tags (empty or NULL) - Poor content structure
    6. Thin content (word_count < 300) - Insufficient content depth

    Example insight structure:
    {
        "property": "sc-domain:example.com",
        "entity_type": "page",
        "entity_id": "/blog/my-post",
        "category": "risk",
        "title": "Low Readability Score",
        "description": "Page has low readability score (45.2). Consider simplifying content...",
        "severity": "high",
        "confidence": 0.85,
        "metrics": {
            "flesch_reading_ease": 45.2,
            "word_count": 850,
            "issue_type": "low_readability"
        },
        "window_days": 30,
        "source": "ContentQualityDetector"
    }
    """

    # Thresholds for quality checks
    MIN_READABILITY_SCORE = 60  # Flesch Reading Ease minimum
    MIN_META_DESCRIPTION_LENGTH = 120  # Minimum meta description length
    MIN_TITLE_LENGTH = 30  # Minimum title length
    MAX_TITLE_LENGTH = 60  # Maximum title length
    MIN_WORD_COUNT = 300  # Minimum word count for non-thin content

    # Cannibalization thresholds
    SIMILARITY_THRESHOLD = 0.8  # Minimum embedding similarity to flag cannibalization
    MIN_SHARED_KEYWORDS = 5  # Minimum shared ranking keywords to confirm cannibalization

    def __init__(self, repository, config):
        """
        Initialize ContentQualityDetector with embeddings support

        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
        """
        super().__init__(repository, config)

        # Initialize EmbeddingGenerator for cannibalization detection
        try:
            from insights_core.embeddings import EmbeddingGenerator
            self.embedder = EmbeddingGenerator(db_dsn=config.warehouse_dsn)
            logger.info("EmbeddingGenerator initialized for cannibalization detection")
        except ImportError as e:
            logger.warning(f"EmbeddingGenerator not available: {e}")
            logger.warning("Cannibalization detection will be skipped")
            self.embedder = None
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingGenerator: {e}")
            self.embedder = None

    def detect(self, property: str = None) -> int:
        """
        Run content quality detection

        Args:
            property: Optional property filter (e.g., "sc-domain:example.com")

        Returns:
            Number of insights created
        """
        logger.info("Starting ContentQualityDetector")

        try:
            insights_created = 0

            # Get content data from database
            pages = self._get_content_data(property)

            if pages:
                logger.debug(f"Analyzing {len(pages)} pages for content quality issues")

                # Check each page for quality issues
                for page in pages:
                    page_path = page.get('page_path', 'unknown')
                    page_property = page.get('property', property or 'unknown')

                    # Check 1: Low readability
                    if self._has_low_readability(page):
                        insight = self._create_readability_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: low_readability")

                    # Check 2: Missing or short meta description
                    if self._has_meta_description_issue(page):
                        insight = self._create_meta_description_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: missing_meta_description")

                    # Check 3: Title too short
                    if self._has_short_title(page):
                        insight = self._create_short_title_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: title_too_short")

                    # Check 4: Title too long
                    if self._has_long_title(page):
                        insight = self._create_long_title_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: title_too_long")

                    # Check 5: Missing H1 tags
                    if self._has_missing_h1(page):
                        insight = self._create_missing_h1_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: missing_h1")

                    # Check 6: Thin content
                    if self._has_thin_content(page):
                        insight = self._create_thin_content_insight(page, page_property)
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(f"Content quality issue detected: {page_path}, issue: thin_content")
            else:
                logger.info(f"No page snapshots found for property: {property}")

            # Check 7: Content cannibalization (if embedder available)
            # This runs independently of page snapshot checks
            if self.embedder and property:
                cannibalization_insights = self._detect_cannibalization(property)
                insights_created += cannibalization_insights
                logger.info(f"Cannibalization detection created {cannibalization_insights} insights")

            logger.info(f"ContentQualityDetector created {insights_created} insights")
            return insights_created

        except Exception as e:
            logger.error(f"Error in ContentQualityDetector: {e}", exc_info=True)
            return 0

    def _get_content_data(self, property: str = None) -> List[Dict]:
        """
        Query database for page snapshots with content quality data

        Args:
            property: Optional property filter

        Returns:
            List of page snapshot dictionaries
        """
        conn = None
        cursor = None

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Query for most recent snapshot of each page
            query = """
                SELECT DISTINCT ON (property, page_path)
                    property,
                    page_path,
                    title,
                    meta_description,
                    h1_tags,
                    word_count,
                    flesch_reading_ease,
                    flesch_kincaid_grade,
                    snapshot_date
                FROM content.page_snapshots
                WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
            """

            params = []
            if property:
                query += " AND property = %s"
                params.append(property)

            query += " ORDER BY property, page_path, snapshot_date DESC"

            cursor.execute(query, params)
            results = cursor.fetchall()

            logger.debug(f"Fetched {len(results)} page snapshots from database")

            return [dict(row) for row in results]

        except psycopg2.Error as e:
            logger.error(f"Database error fetching content data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching content data: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # === Quality Check Methods ===

    def _has_low_readability(self, page: Dict) -> bool:
        """Check if page has low readability score"""
        score = page.get('flesch_reading_ease')
        return score is not None and score < self.MIN_READABILITY_SCORE

    def _has_meta_description_issue(self, page: Dict) -> bool:
        """Check if page has missing or short meta description"""
        meta_desc = page.get('meta_description')
        return not meta_desc or len(meta_desc.strip()) < self.MIN_META_DESCRIPTION_LENGTH

    def _has_short_title(self, page: Dict) -> bool:
        """Check if page title is too short"""
        title = page.get('title')
        return title and len(title.strip()) < self.MIN_TITLE_LENGTH

    def _has_long_title(self, page: Dict) -> bool:
        """Check if page title is too long"""
        title = page.get('title')
        return title and len(title.strip()) > self.MAX_TITLE_LENGTH

    def _has_missing_h1(self, page: Dict) -> bool:
        """Check if page has missing H1 tags"""
        h1_tags = page.get('h1_tags')
        # h1_tags is a PostgreSQL array, could be None, [], or empty list
        return not h1_tags or len(h1_tags) == 0

    def _has_thin_content(self, page: Dict) -> bool:
        """Check if page has thin content"""
        word_count = page.get('word_count')
        return word_count is not None and word_count < self.MIN_WORD_COUNT

    # === Insight Creation Methods ===

    def _create_readability_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for low readability"""
        page_path = page.get('page_path', 'unknown')
        score = page.get('flesch_reading_ease', 0)
        word_count = page.get('word_count', 0)

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Low Readability Score",
            description=(
                f"Page '{page_path}' has a low readability score ({score:.1f}/100). "
                f"This indicates the content may be difficult for users to read and understand. "
                f"Consider simplifying sentences, using shorter words, and breaking up long paragraphs. "
                f"Target: 60+ (Standard), Current: {score:.1f} (Difficult)."
            ),
            severity=InsightSeverity.HIGH,  # Impacts user experience directly
            confidence=0.85,  # High confidence for objective metric
            metrics=InsightMetrics(
                **{
                    'flesch_reading_ease': float(score),
                    'word_count': word_count,
                    'issue_type': 'low_readability',
                    'threshold': float(self.MIN_READABILITY_SCORE)
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _create_meta_description_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for missing or short meta description"""
        page_path = page.get('page_path', 'unknown')
        meta_desc = page.get('meta_description', '')
        current_length = len(meta_desc.strip()) if meta_desc else 0

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Missing or Short Meta Description",
            description=(
                f"Page '{page_path}' has {'no meta description' if current_length == 0 else f'a short meta description ({current_length} chars)'}. "
                f"Meta descriptions are important for SEO and click-through rates in search results. "
                f"Recommended: 120-160 characters with compelling copy that includes target keywords. "
                f"Current: {current_length} characters."
            ),
            severity=InsightSeverity.MEDIUM,  # SEO impact, not UX blocking
            confidence=0.9,  # Very high confidence for presence check
            metrics=InsightMetrics(
                **{
                    'meta_description_length': current_length,
                    'issue_type': 'missing_meta_description',
                    'min_recommended': self.MIN_META_DESCRIPTION_LENGTH,
                    'max_recommended': 160
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _create_short_title_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for title that's too short"""
        page_path = page.get('page_path', 'unknown')
        title = page.get('title', '')
        title_length = len(title.strip()) if title else 0

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Title Too Short",
            description=(
                f"Page '{page_path}' has a short title ({title_length} chars). "
                f"Short titles may not provide enough context for search engines and users. "
                f"Recommended: 30-60 characters with relevant keywords. "
                f"Current title: \"{title}\""
            ),
            severity=InsightSeverity.MEDIUM,  # SEO best practice
            confidence=0.85,
            metrics=InsightMetrics(
                **{
                    'title_length': title_length,
                    'issue_type': 'title_too_short',
                    'min_recommended': self.MIN_TITLE_LENGTH,
                    'max_recommended': self.MAX_TITLE_LENGTH
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _create_long_title_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for title that's too long"""
        page_path = page.get('page_path', 'unknown')
        title = page.get('title', '')
        title_length = len(title.strip()) if title else 0

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Title Too Long",
            description=(
                f"Page '{page_path}' has a long title ({title_length} chars). "
                f"Long titles may be truncated in search results, reducing effectiveness. "
                f"Recommended: 30-60 characters for optimal display. "
                f"Current title: \"{title[:80]}{'...' if len(title) > 80 else ''}\""
            ),
            severity=InsightSeverity.MEDIUM,  # SEO best practice
            confidence=0.85,
            metrics=InsightMetrics(
                **{
                    'title_length': title_length,
                    'issue_type': 'title_too_long',
                    'min_recommended': self.MIN_TITLE_LENGTH,
                    'max_recommended': self.MAX_TITLE_LENGTH
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _create_missing_h1_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for missing H1 tags"""
        page_path = page.get('page_path', 'unknown')

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Missing H1 Tag",
            description=(
                f"Page '{page_path}' is missing an H1 tag. "
                f"H1 tags are important for content structure and SEO. They help search engines "
                f"understand the main topic of the page and improve accessibility for screen readers. "
                f"Every page should have exactly one descriptive H1 tag."
            ),
            severity=InsightSeverity.MEDIUM,  # SEO and accessibility concern
            confidence=0.9,  # High confidence for presence check
            metrics=InsightMetrics(
                **{
                    'h1_count': 0,
                    'issue_type': 'missing_h1',
                    'recommended_count': 1
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _create_thin_content_insight(self, page: Dict, property: str) -> InsightCreate:
        """Create insight for thin content"""
        page_path = page.get('page_path', 'unknown')
        word_count = page.get('word_count', 0)

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Thin Content",
            description=(
                f"Page '{page_path}' has thin content with only {word_count} words. "
                f"Thin content may not provide enough value to users and can negatively impact SEO. "
                f"Search engines prefer comprehensive, in-depth content that thoroughly covers topics. "
                f"Recommended: At least 300 words for standard pages, 1000+ for pillar content. "
                f"Current: {word_count} words."
            ),
            severity=InsightSeverity.HIGH,  # Impacts both UX and SEO
            confidence=0.85,
            metrics=InsightMetrics(
                **{
                    'word_count': word_count,
                    'issue_type': 'thin_content',
                    'min_recommended': self.MIN_WORD_COUNT
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )

    def _detect_cannibalization(self, property: str) -> int:
        """
        Detect content cannibalization using embeddings

        Finds pairs of pages with high embedding similarity (>=0.8) and
        significant query overlap (>5 shared ranking keywords).

        Args:
            property: Property to analyze

        Returns:
            Number of cannibalization insights created
        """
        logger.info("Starting cannibalization detection")

        try:
            # Use asyncio to call async embedder methods
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                cannibalization_pairs = loop.run_until_complete(
                    self.embedder.find_cannibalization(
                        property,
                        similarity_threshold=self.SIMILARITY_THRESHOLD
                    )
                )
            finally:
                loop.close()

            if not cannibalization_pairs:
                logger.info("No cannibalization pairs found")
                return 0

            logger.info(f"Found {len(cannibalization_pairs)} potential cannibalization pairs")

            insights_created = 0

            for pair in cannibalization_pairs:
                try:
                    page_a = pair['page_a']
                    page_b = pair['page_b']
                    similarity = float(pair['similarity'])

                    # Check query overlap
                    shared_keywords_count = self._get_shared_keywords_count(
                        property,
                        page_a,
                        page_b
                    )

                    # Only create insight if query overlap exceeds threshold
                    if shared_keywords_count >= self.MIN_SHARED_KEYWORDS:
                        insight = self._create_cannibalization_insight(
                            property,
                            page_a,
                            page_b,
                            similarity,
                            shared_keywords_count
                        )

                        self.repository.create(insight)
                        insights_created += 1

                        logger.info(
                            f"Cannibalization detected: {page_a} vs {page_b}, "
                            f"similarity={similarity:.2f}, shared_keywords={shared_keywords_count}"
                        )

                except Exception as e:
                    logger.warning(f"Error processing cannibalization pair: {e}")
                    continue

            logger.info(f"Created {insights_created} cannibalization insights")
            return insights_created

        except Exception as e:
            logger.error(f"Error in cannibalization detection: {e}", exc_info=True)
            return 0

    def _get_shared_keywords_count(
        self,
        property: str,
        page_a: str,
        page_b: str
    ) -> int:
        """
        Count shared ranking keywords between two pages

        Checks GSC data to find queries that rank for both pages.

        Args:
            property: Property URL
            page_a: First page path
            page_b: Second page path

        Returns:
            Number of shared ranking keywords
        """
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cur:
                # Find queries that rank for both pages
                cur.execute("""
                    WITH page_a_queries AS (
                        SELECT DISTINCT query
                        FROM fact_gsc_daily
                        WHERE property = %s
                          AND page_path = %s
                          AND date >= CURRENT_DATE - INTERVAL '30 days'
                          AND position <= 20  -- Only consider ranking keywords
                    ),
                    page_b_queries AS (
                        SELECT DISTINCT query
                        FROM fact_gsc_daily
                        WHERE property = %s
                          AND page_path = %s
                          AND date >= CURRENT_DATE - INTERVAL '30 days'
                          AND position <= 20
                    )
                    SELECT COUNT(*) as shared_count
                    FROM page_a_queries
                    INNER JOIN page_b_queries
                    ON page_a_queries.query = page_b_queries.query
                """, (property, page_a, property, page_b))

                result = cur.fetchone()
                conn.close()

                return result[0] if result else 0

        except Exception as e:
            logger.error(f"Error counting shared keywords: {e}")
            return 0

    def _create_cannibalization_insight(
        self,
        property: str,
        page_a: str,
        page_b: str,
        similarity: float,
        shared_keywords_count: int
    ) -> InsightCreate:
        """
        Create DIAGNOSIS insight for content cannibalization

        Args:
            property: Property URL
            page_a: First page path (entity_id)
            page_b: Competing page path
            similarity: Embedding similarity score (0-1)
            shared_keywords_count: Number of shared ranking keywords

        Returns:
            InsightCreate object with DIAGNOSIS category
        """
        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_a,
            category=InsightCategory.DIAGNOSIS,  # Diagnosis, not risk
            title="Content Cannibalization Detected",
            description=(
                f"Page '{page_a}' is cannibalizing with '{page_b}'. "
                f"These pages have very similar content (similarity: {similarity:.1%}) and "
                f"compete for {shared_keywords_count} shared ranking keywords. "
                f"Content cannibalization occurs when multiple pages target the same or very similar topics, "
                f"causing them to compete against each other in search results. "
                f"This can dilute ranking potential and confuse search engines about which page to rank. "
                f"Recommended actions: Consider consolidating the content into a single authoritative page, "
                f"or differentiate the pages by targeting distinct keyword sets and user intents."
            ),
            severity=InsightSeverity.MEDIUM,
            confidence=0.85,
            metrics=InsightMetrics(
                **{
                    'similar_page': page_b,
                    'similarity': similarity,
                    'shared_keywords': shared_keywords_count,
                    'issue_type': 'content_cannibalization',
                    'recommendation': 'consolidate_or_differentiate'
                }
            ),
            window_days=30,
            source="ContentQualityDetector"
        )
