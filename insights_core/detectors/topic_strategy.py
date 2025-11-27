"""
Topic Strategy Detector - Generates insights about topic coverage and strategy

Uses TopicClusterer to analyze topic performance and identify:
1. Underrepresented topics (high impressions, low page count)
2. Topic cannibalization (multiple pages competing for same keywords)

Example:
    >>> from insights_core.detectors.topic_strategy import TopicStrategyDetector
    >>> detector = TopicStrategyDetector(repository, config)
    >>> insights_created = detector.detect(property="sc-domain:example.com")
    >>> print(f"Created {insights_created} topic strategy insights")
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)

logger = logging.getLogger(__name__)

# Try to import TopicClusterer - gracefully handle if not available
try:
    from insights_core.topic_clustering import TopicClusterer
    TOPIC_CLUSTERER_AVAILABLE = True
except ImportError:
    TOPIC_CLUSTERER_AVAILABLE = False
    logger.warning("TopicClusterer not available - topic strategy detection disabled")

# Thresholds for insight generation
OPPORTUNITY_MIN_IMPRESSIONS = 1000  # Minimum total clicks to consider high impressions
OPPORTUNITY_MAX_PAGE_COUNT = 5      # Maximum pages for underrepresented topic
CANNIBALIZATION_MIN_PAGE_COUNT = 3  # Minimum pages for cannibalization
CANNIBALIZATION_MAX_CTR = 0.02      # Maximum CTR indicating cannibalization (2%)
CANNIBALIZATION_THRESHOLD = 0.7     # Threshold for cannibalization score


class TopicStrategyDetector(BaseDetector):
    """
    Detects topic strategy opportunities and issues.

    Analyzes clustered content topics to identify:
    1. Underrepresented topics: High impressions/clicks but few pages
       (opportunity to create more content)
    2. Topic cannibalization: Multiple pages competing for same topic
       with poor individual performance

    Uses EntityType.DIRECTORY with entity_id format "topic:{topic_name}"

    Attributes:
        repository: InsightRepository for persisting insights
        config: InsightsConfig with thresholds and settings
        topic_clusterer: TopicClusterer for topic analysis
        use_topic_clustering: Whether TopicClusterer is available

    Example:
        >>> detector = TopicStrategyDetector(repository, config)
        >>> count = detector.detect(property="sc-domain:example.com")
        >>> print(f"Created {count} topic insights")
    """

    def __init__(self, repository, config, use_topic_clustering: bool = True):
        """
        Initialize TopicStrategyDetector.

        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
            use_topic_clustering: Whether to use TopicClusterer (default: True)
        """
        super().__init__(repository, config)

        self.use_topic_clustering = use_topic_clustering and TOPIC_CLUSTERER_AVAILABLE
        self.topic_clusterer: Optional['TopicClusterer'] = None

        if self.use_topic_clustering:
            try:
                self.topic_clusterer = TopicClusterer(db_dsn=config.warehouse_dsn)
                logger.info("TopicStrategyDetector initialized with TopicClusterer")
            except Exception as e:
                logger.warning(f"Failed to initialize TopicClusterer: {e}")
                self.use_topic_clustering = False
                self.topic_clusterer = None

    def detect(self, property: str = None) -> int:
        """
        Detect topic strategy insights.

        Analyzes topic performance to find:
        - Underrepresented topics (opportunities)
        - Topic cannibalization (diagnosis)

        Args:
            property: Property to analyze (required for topic analysis)

        Returns:
            Number of insights created
        """
        if not property:
            logger.warning("TopicStrategyDetector requires a property filter")
            return 0

        if not self.use_topic_clustering or not self.topic_clusterer:
            logger.warning("TopicClusterer not available, skipping topic strategy detection")
            return 0

        logger.info(f"Starting topic strategy detection for {property}")

        try:
            # Run async analysis in sync context
            insights_created = asyncio.run(
                self._detect_async(property)
            )
            return insights_created
        except Exception as e:
            logger.error(f"Error in topic strategy detection: {e}")
            return 0

    async def _detect_async(self, property: str) -> int:
        """
        Async implementation of topic strategy detection.

        Args:
            property: Property to analyze

        Returns:
            Number of insights created
        """
        try:
            # Get topic performance data
            topic_performance = await self.topic_clusterer.analyze_topic_performance(property)

            if not topic_performance:
                logger.info(f"No topics found for {property}")
                return 0

            logger.info(f"Analyzing {len(topic_performance)} topics for {property}")

            insights_created = 0

            for topic in topic_performance:
                # Check for underrepresented topic (opportunity)
                opportunity_insight = self._check_underrepresented_topic(topic, property)
                if opportunity_insight:
                    self.repository.create(opportunity_insight)
                    insights_created += 1
                    logger.info(f"Created opportunity insight for topic: {topic['name']}")

                # Check for topic cannibalization (diagnosis)
                cannibalization_score = self._calculate_cannibalization_score(topic)
                if cannibalization_score > CANNIBALIZATION_THRESHOLD:
                    cannibalization_insight = self._create_cannibalization_insight(
                        topic, property, cannibalization_score
                    )
                    self.repository.create(cannibalization_insight)
                    insights_created += 1
                    logger.info(
                        f"Created cannibalization insight for topic: {topic['name']} "
                        f"(score: {cannibalization_score:.2f})"
                    )

            logger.info(f"Topic strategy detection complete: {insights_created} insights created")
            return insights_created

        except Exception as e:
            logger.error(f"Error in async topic detection: {e}")
            return 0

    def _check_underrepresented_topic(
        self,
        topic: Dict[str, Any],
        property: str
    ) -> Optional[InsightCreate]:
        """
        Check if topic is underrepresented (high impressions, low page count).

        Args:
            topic: Topic performance data
            property: Property URL

        Returns:
            InsightCreate for opportunity, or None if not underrepresented
        """
        page_count = topic.get('page_count', 0)
        total_clicks = topic.get('total_clicks', 0)
        avg_clicks = topic.get('avg_clicks', 0)

        # Check opportunity threshold: low page count AND high traffic
        if page_count < OPPORTUNITY_MAX_PAGE_COUNT and total_clicks >= OPPORTUNITY_MIN_IMPRESSIONS:
            topic_name = topic.get('name', 'Unknown Topic')
            topic_slug = topic.get('slug', topic_name.lower().replace(' ', '-'))

            # Calculate opportunity score (higher is better)
            opportunity_score = (total_clicks / max(page_count, 1)) / OPPORTUNITY_MIN_IMPRESSIONS

            # Determine severity based on opportunity size
            if opportunity_score > 5:
                severity = InsightSeverity.HIGH
            elif opportunity_score > 2:
                severity = InsightSeverity.MEDIUM
            else:
                severity = InsightSeverity.LOW

            return InsightCreate(
                property=property,
                entity_type=EntityType.DIRECTORY,
                entity_id=f"topic:{topic_slug}",
                category=InsightCategory.OPPORTUNITY,
                title=f"Underrepresented Topic: {topic_name}",
                description=(
                    f"Topic '{topic_name}' shows strong demand ({total_clicks:,} clicks) "
                    f"but has only {page_count} page(s). Consider creating more content "
                    f"in this topic area to capture additional traffic. "
                    f"Average clicks per page: {avg_clicks:.1f}."
                ),
                severity=severity,
                confidence=min(0.9, 0.6 + opportunity_score * 0.1),
                metrics=InsightMetrics(
                    topic=topic_name,
                    page_count=page_count,
                    total_clicks=total_clicks,
                    avg_clicks=avg_clicks,
                    opportunity_score=round(opportunity_score, 2),
                    avg_position=topic.get('avg_position'),
                    avg_ctr=topic.get('avg_ctr'),
                ),
                window_days=30,
                source="TopicStrategyDetector",
            )

        return None

    def _calculate_cannibalization_score(self, topic: Dict[str, Any]) -> float:
        """
        Calculate cannibalization score for a topic.

        Cannibalization indicators:
        - Multiple pages (page_count > 3)
        - Low CTR (pages competing for same keywords)
        - High average position (poor ranking due to competition)
        - High page count with low avg clicks (diluted performance)

        Score ranges from 0.0 to 1.0 where higher = more cannibalization.

        Args:
            topic: Topic performance data

        Returns:
            Cannibalization score (0.0 - 1.0)
        """
        page_count = topic.get('page_count', 0)
        avg_ctr = topic.get('avg_ctr', 0)
        avg_position = topic.get('avg_position', 0)
        avg_clicks = topic.get('avg_clicks', 0)
        total_clicks = topic.get('total_clicks', 0)

        # Require minimum pages for cannibalization
        if page_count < CANNIBALIZATION_MIN_PAGE_COUNT:
            return 0.0

        score = 0.0

        # Factor 1: Many pages (more pages = higher chance of cannibalization)
        # Scale: 3-5 pages = 0.1-0.2, 6-10 pages = 0.2-0.3, 10+ pages = 0.3
        if page_count >= 10:
            score += 0.3
        elif page_count >= 6:
            score += 0.2 + (page_count - 6) * 0.025
        else:
            score += 0.1 + (page_count - 3) * 0.05

        # Factor 2: Low CTR indicates keyword competition
        # CTR < 1% = 0.3, CTR 1-2% = 0.2, CTR 2-3% = 0.1
        if avg_ctr < 0.01:
            score += 0.3
        elif avg_ctr < 0.02:
            score += 0.2
        elif avg_ctr < 0.03:
            score += 0.1

        # Factor 3: Poor average position (position > 10)
        # Position > 30 = 0.2, 20-30 = 0.15, 10-20 = 0.1
        if avg_position > 30:
            score += 0.2
        elif avg_position > 20:
            score += 0.15
        elif avg_position > 10:
            score += 0.1

        # Factor 4: Low clicks per page relative to page count
        # If pages are cannibalizing, clicks get diluted
        clicks_per_page = total_clicks / max(page_count, 1)
        if clicks_per_page < 10:
            score += 0.2
        elif clicks_per_page < 50:
            score += 0.1

        # Cap at 1.0
        return min(1.0, score)

    def _create_cannibalization_insight(
        self,
        topic: Dict[str, Any],
        property: str,
        cannibalization_score: float
    ) -> InsightCreate:
        """
        Create a diagnosis insight for topic cannibalization.

        Args:
            topic: Topic performance data
            property: Property URL
            cannibalization_score: Calculated cannibalization score

        Returns:
            InsightCreate for cannibalization diagnosis
        """
        topic_name = topic.get('name', 'Unknown Topic')
        topic_slug = topic.get('slug', topic_name.lower().replace(' ', '-'))
        page_count = topic.get('page_count', 0)
        avg_ctr = topic.get('avg_ctr', 0)
        avg_position = topic.get('avg_position', 0)
        total_clicks = topic.get('total_clicks', 0)

        # Determine severity based on cannibalization score
        if cannibalization_score > 0.9:
            severity = InsightSeverity.HIGH
        elif cannibalization_score > 0.8:
            severity = InsightSeverity.MEDIUM
        else:
            severity = InsightSeverity.LOW

        return InsightCreate(
            property=property,
            entity_type=EntityType.DIRECTORY,
            entity_id=f"topic:{topic_slug}",
            category=InsightCategory.DIAGNOSIS,
            title=f"Topic Cannibalization Detected: {topic_name}",
            description=(
                f"Topic '{topic_name}' shows signs of keyword cannibalization. "
                f"With {page_count} pages competing for similar keywords, performance is diluted. "
                f"Average CTR: {avg_ctr * 100:.2f}%, Average Position: {avg_position:.1f}. "
                f"Consider consolidating content or differentiating page focus. "
                f"Cannibalization score: {cannibalization_score:.0%}."
            ),
            severity=severity,
            confidence=cannibalization_score,
            metrics=InsightMetrics(
                topic=topic_name,
                page_count=page_count,
                total_clicks=total_clicks,
                avg_clicks=topic.get('avg_clicks'),
                avg_position=avg_position,
                avg_ctr=avg_ctr,
                cannibalization_score=round(cannibalization_score, 2),
                avg_quality=topic.get('avg_quality'),
            ),
            window_days=30,
            source="TopicStrategyDetector",
        )

    def get_topic_summary(self, property: str) -> Dict[str, Any]:
        """
        Get a summary of topic analysis for a property.

        Convenience method for ad-hoc analysis without creating insights.

        Args:
            property: Property to analyze

        Returns:
            Dictionary with topic analysis summary
        """
        if not self.use_topic_clustering or not self.topic_clusterer:
            return {
                'available': False,
                'error': 'TopicClusterer not available'
            }

        try:
            topic_performance = asyncio.run(
                self.topic_clusterer.analyze_topic_performance(property)
            )

            if not topic_performance:
                return {
                    'available': True,
                    'topics_found': 0,
                    'opportunities': [],
                    'cannibalization_risks': []
                }

            opportunities = []
            cannibalization_risks = []

            for topic in topic_performance:
                page_count = topic.get('page_count', 0)
                total_clicks = topic.get('total_clicks', 0)

                # Check for opportunities
                if page_count < OPPORTUNITY_MAX_PAGE_COUNT and total_clicks >= OPPORTUNITY_MIN_IMPRESSIONS:
                    opportunities.append({
                        'name': topic.get('name'),
                        'page_count': page_count,
                        'total_clicks': total_clicks,
                    })

                # Check for cannibalization
                score = self._calculate_cannibalization_score(topic)
                if score > CANNIBALIZATION_THRESHOLD:
                    cannibalization_risks.append({
                        'name': topic.get('name'),
                        'page_count': page_count,
                        'score': round(score, 2),
                    })

            return {
                'available': True,
                'topics_found': len(topic_performance),
                'opportunities': opportunities,
                'opportunities_count': len(opportunities),
                'cannibalization_risks': cannibalization_risks,
                'cannibalization_count': len(cannibalization_risks),
            }

        except Exception as e:
            logger.error(f"Error in topic summary: {e}")
            return {
                'available': True,
                'error': str(e)
            }
