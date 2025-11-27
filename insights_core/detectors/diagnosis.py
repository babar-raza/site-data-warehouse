"""
Diagnosis Detector - Analyzes existing risks to find root causes

Integrates with EventCorrelationEngine to identify trigger events
(content changes, algorithm updates, technical issues) that may have
caused ranking or traffic changes.

Also integrates with CausalAnalyzer for Bayesian causal impact analysis
to determine if changes are statistically significant and measure
the causal effect of potential interventions.

Also integrates with GoogleCSEAnalyzer for SERP-based diagnosis and
competitor analysis to enrich diagnosis insights with real-time SERP data.

Example:
    >>> from insights_core.detectors.diagnosis import DiagnosisDetector
    >>> detector = DiagnosisDetector(repository, config)
    >>> insights_created = detector.detect(property="sc-domain:example.com")
    >>> print(f"Created {insights_created} diagnosis insights")
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)

logger = logging.getLogger(__name__)

# Try to import EventCorrelationEngine - gracefully handle if not available
try:
    from insights_core.event_correlation_engine import (
        EventCorrelationEngine,
        CorrelatedEvent,
        EVENT_TYPE_CONTENT_CHANGE,
        EVENT_TYPE_ALGORITHM_UPDATE,
        EVENT_TYPE_TECHNICAL_ISSUE,
    )
    EVENT_CORRELATION_AVAILABLE = True
except ImportError:
    EVENT_CORRELATION_AVAILABLE = False
    logger.warning("EventCorrelationEngine not available - trigger event detection disabled")

# Try to import CausalAnalyzer - gracefully handle if not available
try:
    from insights_core.causal_analyzer import CausalAnalyzer
    CAUSAL_ANALYZER_AVAILABLE = True
except ImportError:
    CAUSAL_ANALYZER_AVAILABLE = False
    logger.warning("CausalAnalyzer not available - causal impact analysis disabled")

# Try to import GoogleCSEAnalyzer - gracefully handle if not available
try:
    from services.serp_analyzer import GoogleCSEAnalyzer
    CSE_ANALYZER_AVAILABLE = True
except ImportError:
    CSE_ANALYZER_AVAILABLE = False
    logger.warning("GoogleCSEAnalyzer not available - SERP-based diagnosis disabled")

# Try to import TrendsAnalyzer - gracefully handle if not available
try:
    from insights_core.trends_analyzer import TrendsAnalyzer
    TRENDS_ANALYZER_AVAILABLE = True
except ImportError:
    TRENDS_ANALYZER_AVAILABLE = False
    logger.warning("TrendsAnalyzer not available - trends-based diagnosis disabled")

# Significance threshold for causal analysis
CAUSAL_SIGNIFICANCE_THRESHOLD = 0.05

# Minimum quota to keep for CSE analysis (reserve some quota)
CSE_MIN_QUOTA_THRESHOLD = 5


class DiagnosisDetector(BaseDetector):
    """
    Diagnoses existing risk insights and identifies trigger events.

    Analyzes RISK category insights to determine root causes:
    1. Ranking issue: Position worsened significantly
    2. Engagement issue: User engagement declined
    3. Content change: Recent modifications to the page

    When ranking issues are detected, the detector uses EventCorrelationEngine
    to find potential trigger events such as:
    - Git commits modifying page content
    - Google algorithm updates
    - Technical issues (CWV degradation, errors)

    When causal analysis is enabled, the detector uses CausalAnalyzer to
    measure the statistical significance of performance changes using
    Bayesian structural time series analysis. This helps distinguish
    true causal effects from random variation.

    When CSE is enabled, the detector uses GoogleCSEAnalyzer to enrich
    diagnosis insights with real-time SERP data including competitor
    analysis and SERP feature detection.

    Attributes:
        repository: InsightRepository for persisting insights
        config: InsightsConfig with thresholds and settings
        correlation_engine: EventCorrelationEngine for trigger event detection
        use_correlation: Whether to use EventCorrelationEngine
        causal_analyzer: CausalAnalyzer for causal impact analysis
        use_causal_analysis: Whether to use CausalAnalyzer
        use_cse: Whether to use GoogleCSEAnalyzer
        _cse_analyzer: Lazy-loaded GoogleCSEAnalyzer instance

    Example:
        >>> detector = DiagnosisDetector(repository, config)
        >>> count = detector.detect(property="sc-domain:example.com")
        >>> print(f"Diagnosed {count} risks")

        >>> # With causal analysis and CSE
        >>> detector = DiagnosisDetector(repository, config, use_causal_analysis=True, use_cse=True)
        >>> count = detector.detect(property="sc-domain:example.com")
        >>> print(f"Diagnosed {count} risks with enhanced analysis")
    """

    def __init__(
        self,
        repository,
        config,
        use_correlation: bool = True,
        use_causal_analysis: bool = True,
        use_cse: bool = True,
        use_trends: bool = True
    ):
        """
        Initialize DiagnosisDetector.

        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
            use_correlation: Whether to use EventCorrelationEngine (default: True)
            use_causal_analysis: Whether to use CausalAnalyzer (default: True)
            use_cse: Whether to use GoogleCSEAnalyzer (default: True)
            use_trends: Whether to use TrendsAnalyzer (default: True)
        """
        super().__init__(repository, config)

        # Initialize EventCorrelationEngine
        self.use_correlation = use_correlation and EVENT_CORRELATION_AVAILABLE
        self.correlation_engine: Optional[EventCorrelationEngine] = None

        if self.use_correlation:
            try:
                self.correlation_engine = EventCorrelationEngine(
                    db_dsn=config.warehouse_dsn
                )
                logger.info("DiagnosisDetector initialized with EventCorrelationEngine")
            except Exception as e:
                logger.warning(f"Failed to initialize EventCorrelationEngine: {e}")
                self.use_correlation = False
                self.correlation_engine = None

        # Initialize CausalAnalyzer
        self.use_causal_analysis = use_causal_analysis and CAUSAL_ANALYZER_AVAILABLE
        self.causal_analyzer: Optional['CausalAnalyzer'] = None

        if self.use_causal_analysis:
            try:
                self.causal_analyzer = CausalAnalyzer(db_dsn=config.warehouse_dsn)
                logger.info("DiagnosisDetector initialized with CausalAnalyzer")
            except Exception as e:
                logger.warning(f"Failed to initialize CausalAnalyzer: {e}")
                self.use_causal_analysis = False
                self.causal_analyzer = None

        # CSE is lazy loaded
        self.use_cse = use_cse and CSE_ANALYZER_AVAILABLE
        self._cse_analyzer: Optional['GoogleCSEAnalyzer'] = None

        # Initialize TrendsAnalyzer
        self.use_trends = use_trends and TRENDS_ANALYZER_AVAILABLE
        self.trends_analyzer: Optional['TrendsAnalyzer'] = None

        if self.use_trends:
            try:
                self.trends_analyzer = TrendsAnalyzer(db_dsn=config.warehouse_dsn)
                logger.info("DiagnosisDetector initialized with TrendsAnalyzer")
            except Exception as e:
                logger.warning(f"Failed to initialize TrendsAnalyzer: {e}")
                self.use_trends = False
                self.trends_analyzer = None

    @property
    def cse_analyzer(self) -> Optional['GoogleCSEAnalyzer']:
        """
        Lazy load CSE analyzer.

        Returns:
            GoogleCSEAnalyzer instance or None if not available
        """
        if not self.use_cse:
            return None

        if self._cse_analyzer is None:
            try:
                self._cse_analyzer = GoogleCSEAnalyzer()
                logger.info("GoogleCSEAnalyzer lazy loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize GoogleCSEAnalyzer: {e}")
                self.use_cse = False
                return None

        return self._cse_analyzer

    @staticmethod
    def _to_float(val):
        """Convert Decimal/numeric to float for JSON serialization."""
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return val

    def detect(self, property: str = None) -> int:
        """
        Run diagnosis on existing risk insights.

        Retrieves all NEW risk insights, analyzes them to determine root causes,
        and creates diagnosis insights with trigger event information when available.

        Args:
            property: Optional property filter (e.g., "sc-domain:example.com")

        Returns:
            Number of diagnosis insights created
        """
        logger.info("Starting diagnosis detection...")

        # Get all NEW risk insights
        risks = self.repository.get_by_status(
            InsightStatus.NEW,
            property=property
        )
        risks = [r for r in risks if r.category == InsightCategory.RISK]

        logger.info(f"Found {len(risks)} new risks to diagnose")

        insights_created = 0

        for risk in risks:
            try:
                diagnosis = self._diagnose_risk(risk)
                if diagnosis:
                    # Create diagnosis insight
                    created = self.repository.create(diagnosis)
                    insights_created += 1

                    # Update original risk to diagnosed status
                    self.repository.update(
                        risk.id,
                        InsightUpdate(
                            status=InsightStatus.DIAGNOSED,
                            linked_insight_id=created.id
                        )
                    )
                    logger.info(f"Diagnosed risk {risk.id}: {diagnosis.title}")
            except Exception as e:
                logger.error(f"Failed to diagnose risk {risk.id}: {e}")

        return insights_created

    def _diagnose_risk(self, risk) -> Optional[InsightCreate]:
        """
        Diagnose a single risk insight.

        Analyzes the risk to determine root cause using multiple hypotheses:
        1. Ranking dropped significantly
        2. User engagement declined
        3. Recent content changes

        For ranking issues, attempts to find correlated trigger events.

        Args:
            risk: Risk insight to diagnose

        Returns:
            InsightCreate for diagnosis, or None if no clear diagnosis
        """
        conn = self._get_db_connection()

        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get latest data for this page
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_unified_page_performance
                    WHERE property = %s
                    AND page_path = %s
                    AND date >= CURRENT_DATE - INTERVAL '14 days'
                    ORDER BY date DESC
                    LIMIT 1
                """, (risk.property, risk.entity_id))

                row = cur.fetchone()

                if not row:
                    return None

                row = dict(row)
        finally:
            conn.close()

        # Hypothesis 1: Ranking dropped
        position_change = row.get('gsc_position_change_wow') or 0
        if position_change > 10:  # Position worsened by >10
            return self._create_ranking_diagnosis(risk, row, position_change)

        # Hypothesis 2: Engagement issue
        engagement_current = row.get('ga_engagement_rate') or 0
        engagement_prev = row.get('ga_engagement_rate_7d_ago') or 0
        engagement_drop = ((engagement_current - engagement_prev) / engagement_prev * 100) if engagement_prev > 0 else 0

        if engagement_drop < -15:  # Engagement dropped >15%
            return InsightCreate(
                property=risk.property,
                entity_type=EntityType.PAGE,
                entity_id=risk.entity_id,
                category=InsightCategory.DIAGNOSIS,
                title="Engagement Issue Detected",
                description=(
                    f"Root cause identified: User engagement declined. "
                    f"Engagement rate dropped {abs(engagement_drop):.1f}% while traffic remained stable. "
                    f"Content quality or relevance may be an issue."
                ),
                severity=risk.severity,
                confidence=0.75,
                metrics=InsightMetrics(
                    ga_engagement_rate=self._to_float(engagement_current),
                    ga_conversions=self._to_float(row.get('ga_conversions')),
                    ga_conversions_change=self._to_float(row.get('ga_conversions_change_wow')),
                ),
                window_days=7,
                source="DiagnosisDetector",
                linked_insight_id=risk.id,
            )

        # Hypothesis 3: Recent content change
        modified_within_48h = row.get('modified_within_48h', False)
        if modified_within_48h:
            last_modified = row.get('last_modified_date')
            last_modified_str = last_modified.isoformat() if last_modified else "recently"

            return InsightCreate(
                property=risk.property,
                entity_type=EntityType.PAGE,
                entity_id=risk.entity_id,
                category=InsightCategory.DIAGNOSIS,
                title="Recent Content Change",
                description=(
                    f"Root cause identified: Page was modified within 48 hours of traffic drop. "
                    f"Last modified: {last_modified_str}. "
                    f"Recent content changes may have impacted performance."
                ),
                severity=InsightSeverity.MEDIUM,
                confidence=0.7,
                metrics=InsightMetrics(
                    gsc_clicks=self._to_float(row.get('gsc_clicks')),
                    gsc_clicks_change=self._to_float(row.get('gsc_clicks_change_wow')),
                ),
                window_days=7,
                source="DiagnosisDetector",
                linked_insight_id=risk.id,
            )

        return None

    def _get_serp_context(self, property: str, query: str) -> Optional[Dict]:
        """
        Get SERP context for a query using CSE.

        Checks quota before making CSE calls to avoid exhausting the daily limit.
        Returns None if CSE is not available or quota is too low.

        Args:
            property: Property URL (e.g., "sc-domain:example.com")
            query: Search query to analyze

        Returns:
            SERP analysis dict or None if unavailable
        """
        if not self.cse_analyzer:
            return None

        # Check quota
        try:
            status = self.cse_analyzer.get_quota_status()
            remaining = status.get('remaining', 0)

            if remaining < CSE_MIN_QUOTA_THRESHOLD:
                logger.warning(
                    f"CSE quota too low ({remaining} remaining), skipping SERP analysis"
                )
                return None
        except Exception as e:
            logger.warning(f"Failed to check CSE quota: {e}")
            return None

        try:
            # Extract domain from property
            # Handle formats like "sc-domain:example.com" or "sc-https://example.com"
            domain = property.replace('sc-domain:', '').replace('sc-', '')
            if domain.startswith('https://') or domain.startswith('http://'):
                domain = domain.split('://')[1].rstrip('/')

            logger.info(f"Analyzing SERP for query '{query}' and domain '{domain}'")

            # Get SERP analysis
            analysis = self.cse_analyzer.analyze_serp(query, domain)

            logger.info(
                f"SERP analysis completed: position={analysis.get('target_position')}, "
                f"competitors={len(analysis.get('competitors', []))}"
            )

            return analysis

        except Exception as e:
            logger.warning(f"CSE analysis failed for query '{query}': {e}")
            return None

    def _create_ranking_diagnosis(
        self,
        risk,
        row: Dict[str, Any],
        position_change: float
    ) -> InsightCreate:
        """
        Create a diagnosis insight for ranking issues with trigger event correlation,
        causal impact analysis, and SERP context.

        Uses EventCorrelationEngine to find potential trigger events,
        CausalAnalyzer to measure statistical significance, and GoogleCSEAnalyzer
        to provide real-time SERP insights.

        Args:
            risk: Original risk insight
            row: Database row with page metrics
            position_change: Position change value (positive = worse)

        Returns:
            InsightCreate with diagnosis, trigger events, causal analysis, and SERP data
        """
        # Base description
        description = (
            f"Root cause identified: Search ranking declined significantly. "
            f"Average position worsened by {position_change:.1f} spots week-over-week. "
            f"This explains the traffic drop."
        )

        # Base metrics - convert Decimal to float for JSON serialization
        metrics_dict = {
            'gsc_position': self._to_float(row.get('gsc_position')),
            'gsc_position_change': self._to_float(position_change),
            'gsc_clicks': self._to_float(row.get('gsc_clicks')),
            'gsc_clicks_change': self._to_float(row.get('gsc_clicks_change_wow')),
        }

        # Try to get SERP context for top query
        serp_context = None
        top_query = row.get('top_query')  # Assuming this field exists

        if top_query and self.use_cse:
            serp_context = self._get_serp_context(risk.property, top_query)

            if serp_context:
                # Enrich description with SERP insights
                target_position = serp_context.get('target_position')
                competitors = serp_context.get('competitors', [])
                serp_features = serp_context.get('serp_features', [])

                if target_position:
                    description += (
                        f"\n\nCurrent SERP position for '{top_query}': #{target_position}. "
                    )
                elif competitors:
                    description += (
                        f"\n\nDomain not found in top {serp_context.get('total_results', 10)} "
                        f"results for '{top_query}'. "
                    )

                # Add competitor insights
                if competitors:
                    top_competitors = competitors[:3]
                    competitor_names = [c.get('domain', 'unknown') for c in top_competitors]
                    description += (
                        f"Top competitors: {', '.join(competitor_names)}. "
                    )

                    # Check for competitors with rich snippets
                    rich_competitors = [
                        c for c in top_competitors
                        if c.get('has_rich_snippet')
                    ]
                    if rich_competitors:
                        description += (
                            f"{len(rich_competitors)} of top 3 competitors have rich snippets. "
                        )

                # Add SERP feature insights
                if serp_features:
                    description += (
                        f"SERP features detected: {', '.join(serp_features)}. "
                    )

                # Add SERP data to metrics
                metrics_dict['serp_query'] = top_query
                metrics_dict['serp_position'] = target_position
                metrics_dict['serp_competitors_count'] = len(competitors)
                metrics_dict['serp_features'] = serp_features
                metrics_dict['serp_top_competitors'] = [
                    {
                        'domain': c.get('domain'),
                        'position': c.get('position'),
                        'has_rich_snippet': c.get('has_rich_snippet', False)
                    }
                    for c in competitors[:5]
                ]
                metrics_dict['serp_analyzed_at'] = serp_context.get('analyzed_at')

                logger.info(
                    f"SERP context added to diagnosis for {risk.entity_id}: "
                    f"position={target_position}, competitors={len(competitors)}"
                )

        # Try to get trends context for top query
        trends_context = None
        if top_query and self.use_trends:
            trends_context = self._get_trends_context(risk.property, top_query)

            if trends_context:
                # Add trends insights to description
                trend_direction = trends_context.get('trend_direction')
                change_ratio = trends_context.get('change_ratio', 1.0)

                if trend_direction == 'down':
                    description += (
                        f"\n\nSearch interest analysis shows declining trends for '{top_query}' "
                        f"({int((1 - change_ratio) * 100)}% decrease in search interest). "
                        f"The ranking drop may be partly due to reduced demand."
                    )
                elif trend_direction == 'up':
                    description += (
                        f"\n\nSearch interest for '{top_query}' is trending upward "
                        f"({int((change_ratio - 1) * 100)}% increase), yet rankings declined. "
                        f"This suggests a content or technical issue rather than demand change."
                    )
                else:
                    description += (
                        f"\n\nSearch interest for '{top_query}' remains stable, "
                        f"indicating the ranking issue is not demand-related."
                    )

                # Add trends metrics
                metrics_dict['trends_query'] = top_query
                metrics_dict['trends_direction'] = trend_direction
                metrics_dict['trends_change_ratio'] = change_ratio
                metrics_dict['trends_recent_avg'] = trends_context.get('recent_avg')
                metrics_dict['trends_historical_avg'] = trends_context.get('historical_avg')
                metrics_dict['trends_volatility'] = trends_context.get('volatility')
                metrics_dict['trends_current_score'] = trends_context.get('current_score')

                logger.info(
                    f"Trends context added to diagnosis for {risk.entity_id}: "
                    f"direction={trend_direction}, change_ratio={change_ratio}"
                )

        # Try to find trigger events
        trigger_events = self._find_trigger_events(
            risk.property,
            risk.entity_id,
            row.get('date')
        )

        if trigger_events:
            # Enhance description with trigger event info
            top_event = trigger_events[0]
            event_type_display = self._get_event_type_display(top_event.event_type)

            description += (
                f"\n\nPotential trigger identified: {event_type_display} "
                f"({top_event.days_before_change} days before ranking change, "
                f"confidence: {top_event.confidence:.0%})."
            )

            # Add trigger event details to description
            if top_event.event_type == EVENT_TYPE_CONTENT_CHANGE:
                commit_msg = top_event.details.get('message', 'Unknown commit')
                description += f"\nCommit: {commit_msg}"
            elif top_event.event_type == EVENT_TYPE_ALGORITHM_UPDATE:
                update_name = top_event.details.get('update_name', 'Unknown update')
                description += f"\nGoogle update: {update_name}"
            elif top_event.event_type == EVENT_TYPE_TECHNICAL_ISSUE:
                issue_type = top_event.details.get('issue_type', 'Unknown issue')
                description += f"\nTechnical issue: {issue_type}"

            # Add trigger event metadata to metrics
            metrics_dict['trigger_event_type'] = top_event.event_type
            metrics_dict['trigger_event_date'] = (
                top_event.event_date.isoformat()
                if isinstance(top_event.event_date, date)
                else top_event.event_date
            )
            metrics_dict['trigger_event_confidence'] = top_event.confidence
            metrics_dict['trigger_event_details'] = top_event.details
            metrics_dict['trigger_events_found'] = len(trigger_events)

            # Include all trigger events summary
            all_events_summary = [
                {
                    'type': e.event_type,
                    'date': e.event_date.isoformat() if isinstance(e.event_date, date) else e.event_date,
                    'confidence': e.confidence,
                    'days_before': e.days_before_change
                }
                for e in trigger_events[:5]  # Top 5 events
            ]
            metrics_dict['all_trigger_events'] = all_events_summary

            logger.info(
                f"Found {len(trigger_events)} trigger events for {risk.entity_id}, "
                f"top: {top_event.event_type} (confidence: {top_event.confidence:.2f})"
            )

        # Run causal impact analysis
        causal_result = self._run_causal_analysis(
            property=risk.property,
            page_path=risk.entity_id,
            change_date=row.get('date'),
            metric='clicks'
        )

        # Default confidence
        confidence = 0.85

        if causal_result and causal_result.get('success'):
            # Add causal analysis to description
            if causal_result['is_significant']:
                description += (
                    f"\n\nCausal analysis confirms this is a statistically significant change "
                    f"(p={causal_result['p_value']:.4f}, causal probability: "
                    f"{causal_result['causal_probability']:.2%}). "
                    f"Estimated effect: {causal_result['relative_effect_pct']:.1f}% change in clicks."
                )
                # Increase confidence when causal analysis confirms significance
                confidence = min(0.95, 0.85 + causal_result['causal_probability'] * 0.1)
            else:
                description += (
                    f"\n\nNote: Causal analysis indicates this change may not be statistically "
                    f"significant (p={causal_result['p_value']:.4f}). The observed variation "
                    f"could be due to normal fluctuations."
                )
                # Decrease confidence when causal analysis doesn't confirm
                confidence = max(0.5, 0.85 - (1 - causal_result['causal_probability']) * 0.2)

            # Add causal metrics
            metrics_dict['causal_probability'] = causal_result['causal_probability']
            metrics_dict['relative_effect_pct'] = causal_result['relative_effect_pct']
            metrics_dict['p_value'] = causal_result['p_value']
            metrics_dict['causal_is_significant'] = causal_result['is_significant']
            metrics_dict['causal_absolute_effect'] = causal_result['absolute_effect']
            metrics_dict['causal_data_points'] = causal_result['data_points']

            logger.info(
                f"Causal analysis for {risk.entity_id}: "
                f"significant={causal_result['is_significant']}, "
                f"p={causal_result['p_value']:.4f}"
            )

        return InsightCreate(
            property=risk.property,
            entity_type=EntityType.PAGE,
            entity_id=risk.entity_id,
            category=InsightCategory.DIAGNOSIS,
            title="Ranking Issue Detected",
            description=description,
            severity=risk.severity,
            confidence=confidence,
            metrics=InsightMetrics(**metrics_dict),
            window_days=7,
            source="DiagnosisDetector",
            linked_insight_id=risk.id,
        )

    def _get_trends_context(self, property: str, keyword: str) -> Optional[Dict]:
        """
        Get trends context for a keyword

        Analyzes Google Trends data to provide context about search interest
        patterns for the keyword.

        Args:
            property: GSC property
            keyword: Keyword to analyze

        Returns:
            Dict with trends analysis or None if unavailable
        """
        if not self.use_trends or not self.trends_analyzer:
            return None

        try:
            analysis = self.trends_analyzer.analyze_keyword_trends(
                property=property,
                keyword=keyword,
                days=90
            )

            if not analysis.get('has_data'):
                return None

            logger.info(
                f"Trends context for '{keyword}': "
                f"direction={analysis.get('trend_direction')}, "
                f"change_ratio={analysis.get('change_ratio')}"
            )

            return analysis

        except Exception as e:
            logger.warning(f"Failed to get trends context for '{keyword}': {e}")
            return None

    def _find_trigger_events(
        self,
        property: str,
        page_path: str,
        ranking_change_date: Optional[date]
    ) -> List['CorrelatedEvent']:
        """
        Find potential trigger events for a ranking change.

        Uses EventCorrelationEngine to search for events within the lookback
        window that may have caused the ranking change.

        Args:
            property: Property URL
            page_path: Page path that experienced ranking change
            ranking_change_date: Date when ranking change was detected

        Returns:
            List of CorrelatedEvent objects sorted by confidence
        """
        if not self.use_correlation or not self.correlation_engine:
            return []

        if not ranking_change_date:
            ranking_change_date = date.today()

        try:
            events = self.correlation_engine.find_trigger_events(
                page_path=page_path,
                ranking_change_date=ranking_change_date,
                property=property
            )
            return events
        except Exception as e:
            logger.warning(f"Error finding trigger events for {page_path}: {e}")
            return []

    def _run_causal_analysis(
        self,
        property: str,
        page_path: str,
        change_date: Optional[date],
        metric: str = 'clicks',
        pre_period_days: int = 30,
        post_period_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Run causal impact analysis for a page.

        Uses CausalAnalyzer to perform Bayesian structural time series
        analysis to determine if the observed change is statistically
        significant and measure the causal effect.

        Args:
            property: Property URL
            page_path: Page path to analyze
            change_date: Estimated date when the change occurred
            metric: Metric to analyze (default: 'clicks')
            pre_period_days: Days before change for baseline (default: 30)
            post_period_days: Days after change to measure (default: 7)

        Returns:
            Dictionary with causal analysis results, or None if unavailable
        """
        if not self.use_causal_analysis or not self.causal_analyzer:
            return None

        if not change_date:
            change_date = date.today() - timedelta(days=7)

        try:
            # Run async causal analysis in sync context
            result = asyncio.run(
                self._run_causal_analysis_async(
                    property=property,
                    page_path=page_path,
                    change_date=change_date,
                    metric=metric,
                    pre_period_days=pre_period_days,
                    post_period_days=post_period_days
                )
            )
            return result
        except Exception as e:
            logger.warning(f"Error running causal analysis for {page_path}: {e}")
            return None

    async def _run_causal_analysis_async(
        self,
        property: str,
        page_path: str,
        change_date: date,
        metric: str,
        pre_period_days: int,
        post_period_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Async implementation of causal impact analysis.

        Fetches time series data and runs CausalImpact analysis to
        measure the effect of performance changes.

        Args:
            property: Property URL
            page_path: Page path to analyze
            change_date: Estimated date when the change occurred
            metric: Metric to analyze
            pre_period_days: Days before change for baseline
            post_period_days: Days after change to measure

        Returns:
            Dictionary with analysis results or None
        """
        try:
            # Define date ranges
            pre_start = change_date - timedelta(days=pre_period_days)
            pre_end = change_date - timedelta(days=1)
            post_start = change_date
            post_end = date.today()

            # Use CausalAnalyzer's fetch method
            df = await self.causal_analyzer.fetch_time_series_data(
                property=property,
                page_path=page_path,
                metric=metric,
                start_date=pre_start,
                end_date=post_end
            )

            if df.empty or len(df) < pre_period_days + 3:
                logger.debug(
                    f"Insufficient data for causal analysis: {len(df)} days available"
                )
                return None

            # Import CausalImpact for analysis
            try:
                from causalimpact import CausalImpact
                import pandas as pd
            except ImportError:
                logger.warning("CausalImpact library not available")
                return None

            # Define pre and post periods
            pre_period = [df.index.min(), pd.Timestamp(pre_end)]
            post_period = [pd.Timestamp(post_start), df.index.max()]

            # Run causal impact analysis
            ci = CausalImpact(
                df,
                pre_period,
                post_period,
                alpha=CAUSAL_SIGNIFICANCE_THRESHOLD
            )

            # Extract results
            summary = ci.summary_data

            absolute_effect = float(summary.loc['average', 'abs_effect'])
            relative_effect = float(summary.loc['average', 'rel_effect'])
            p_value = float(summary.loc['average', 'p'])

            is_significant = p_value < CAUSAL_SIGNIFICANCE_THRESHOLD

            # Calculate causal probability (inverse of p-value as percentage)
            causal_probability = 1 - p_value

            logger.info(
                f"Causal analysis for {page_path}: "
                f"effect={absolute_effect:.2f} ({relative_effect:.1%}), "
                f"p={p_value:.4f}, significant={is_significant}"
            )

            if is_significant:
                logger.info(
                    f"Causal impact confirmed: {page_path}, "
                    f"probability {causal_probability:.2%}"
                )

            return {
                'success': True,
                'page_path': page_path,
                'property': property,
                'metric': metric,
                'absolute_effect': round(absolute_effect, 2),
                'relative_effect_pct': round(relative_effect * 100, 2),
                'p_value': round(p_value, 4),
                'is_significant': is_significant,
                'causal_probability': round(causal_probability, 4),
                'pre_period_days': pre_period_days,
                'post_period_days': post_period_days,
                'data_points': len(df),
            }

        except Exception as e:
            logger.error(f"Error in async causal analysis: {e}")
            return None

    def _get_event_type_display(self, event_type: str) -> str:
        """
        Get human-readable display name for event type.

        Args:
            event_type: Event type constant

        Returns:
            Human-readable event type name
        """
        display_names = {
            EVENT_TYPE_CONTENT_CHANGE: "Content Change",
            EVENT_TYPE_ALGORITHM_UPDATE: "Google Algorithm Update",
            EVENT_TYPE_TECHNICAL_ISSUE: "Technical Issue",
        }
        return display_names.get(event_type, event_type.replace('_', ' ').title())

    def diagnose_with_correlation(
        self,
        page_path: str,
        property: str,
        ranking_change_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Diagnose a page directly with correlation analysis.

        Convenience method for directly analyzing a page without going through
        the normal insight workflow. Useful for ad-hoc analysis.

        Args:
            page_path: Page path to analyze
            property: Property URL
            ranking_change_date: Date of ranking change (default: today)

        Returns:
            Dictionary with diagnosis and trigger events

        Example:
            >>> result = detector.diagnose_with_correlation(
            ...     page_path='/blog/seo-tips/',
            ...     property='sc-domain:example.com'
            ... )
            >>> print(f"Found {result['trigger_events_count']} trigger events")
        """
        if not ranking_change_date:
            ranking_change_date = date.today()

        result = {
            'page_path': page_path,
            'property': property,
            'ranking_change_date': ranking_change_date.isoformat(),
            'trigger_events': [],
            'trigger_events_count': 0,
            'top_trigger_event': None,
            'correlation_available': self.use_correlation,
        }

        if not self.use_correlation or not self.correlation_engine:
            return result

        try:
            events = self.correlation_engine.find_trigger_events(
                page_path=page_path,
                ranking_change_date=ranking_change_date,
                property=property
            )

            result['trigger_events'] = [e.to_dict() for e in events]
            result['trigger_events_count'] = len(events)

            if events:
                result['top_trigger_event'] = events[0].to_dict()

        except Exception as e:
            logger.error(f"Error in diagnose_with_correlation: {e}")
            result['error'] = str(e)

        return result

    def diagnose_with_causal_analysis(
        self,
        page_path: str,
        property: str,
        change_date: Optional[date] = None,
        metric: str = 'clicks',
        pre_period_days: int = 30,
        post_period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Diagnose a page directly with causal impact analysis.

        Convenience method for running Bayesian structural time series
        analysis to determine statistical significance of performance changes.

        Args:
            page_path: Page path to analyze
            property: Property URL
            change_date: Estimated date of change (default: 7 days ago)
            metric: Metric to analyze (default: 'clicks')
            pre_period_days: Days before change for baseline (default: 30)
            post_period_days: Days after change to measure (default: 7)

        Returns:
            Dictionary with causal analysis results

        Example:
            >>> result = detector.diagnose_with_causal_analysis(
            ...     page_path='/blog/seo-tips/',
            ...     property='sc-domain:example.com',
            ...     change_date=date(2025, 1, 15)
            ... )
            >>> if result['is_significant']:
            ...     print(f"Significant change: {result['relative_effect_pct']:.1f}%")
        """
        if not change_date:
            change_date = date.today() - timedelta(days=7)

        result = {
            'page_path': page_path,
            'property': property,
            'change_date': change_date.isoformat(),
            'metric': metric,
            'causal_analysis_available': self.use_causal_analysis,
            'is_significant': False,
            'causal_probability': None,
            'relative_effect_pct': None,
            'p_value': None,
        }

        if not self.use_causal_analysis or not self.causal_analyzer:
            return result

        causal_result = self._run_causal_analysis(
            property=property,
            page_path=page_path,
            change_date=change_date,
            metric=metric,
            pre_period_days=pre_period_days,
            post_period_days=post_period_days
        )

        if causal_result and causal_result.get('success'):
            result.update({
                'success': True,
                'is_significant': causal_result['is_significant'],
                'causal_probability': causal_result['causal_probability'],
                'relative_effect_pct': causal_result['relative_effect_pct'],
                'absolute_effect': causal_result['absolute_effect'],
                'p_value': causal_result['p_value'],
                'data_points': causal_result['data_points'],
            })
        else:
            result['error'] = 'Causal analysis failed or insufficient data'

        return result
