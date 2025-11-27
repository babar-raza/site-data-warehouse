"""
CWV Quality Detector - Generates insights for Core Web Vitals issues

Uses CoreWebVitalsMonitor to analyze page performance and identify:
1. Poor LCP (Largest Contentful Paint) > 4000ms
2. Poor FID/INP (First Input Delay / Interaction to Next Paint) > 300ms
3. Poor CLS (Cumulative Layout Shift) > 0.25

Example:
    >>> from insights_core.detectors.cwv_quality import CWVQualityDetector
    >>> detector = CWVQualityDetector(repository, config)
    >>> insights_created = detector.detect(property="sc-domain:example.com")
    >>> print(f"Created {insights_created} CWV quality insights")
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)

logger = logging.getLogger(__name__)

# Try to import CoreWebVitalsMonitor - gracefully handle if not available
try:
    from insights_core.cwv_monitor import CoreWebVitalsMonitor
    CWV_MONITOR_AVAILABLE = True
except ImportError:
    CWV_MONITOR_AVAILABLE = False
    logger.warning("CoreWebVitalsMonitor not available - CWV quality detection disabled")

# Core Web Vitals thresholds (Google's official thresholds)
# Good: All metrics in green zone
# Needs Improvement: At least one metric in yellow zone
# Poor: At least one metric in red zone

# LCP (Largest Contentful Paint) - milliseconds
LCP_GOOD_THRESHOLD = 2500  # Good: <= 2500ms
LCP_POOR_THRESHOLD = 4000  # Poor: > 4000ms

# FID (First Input Delay) / INP (Interaction to Next Paint) - milliseconds
FID_GOOD_THRESHOLD = 100   # Good: <= 100ms
FID_POOR_THRESHOLD = 300   # Poor: > 300ms

# CLS (Cumulative Layout Shift) - unitless score
CLS_GOOD_THRESHOLD = 0.1   # Good: <= 0.1
CLS_POOR_THRESHOLD = 0.25  # Poor: > 0.25

# Metric display names for user-friendly titles
METRIC_DISPLAY_NAMES = {
    'lcp': 'LCP (Largest Contentful Paint)',
    'fid': 'FID (First Input Delay)',
    'inp': 'INP (Interaction to Next Paint)',
    'cls': 'CLS (Cumulative Layout Shift)',
}


class CWVQualityDetector(BaseDetector):
    """
    Detects Core Web Vitals quality issues.

    Analyzes CWV data from performance.core_web_vitals table to identify:
    1. Poor LCP: Pages taking > 4000ms to load the largest content element
    2. Poor FID/INP: Pages with input delay > 300ms
    3. Poor CLS: Pages with layout shift score > 0.25

    Each poor metric generates a RISK insight with HIGH severity.

    Uses EntityType.PAGE with entity_id as the page_path.

    Attributes:
        repository: InsightRepository for persisting insights
        config: InsightsConfig with thresholds and settings
        cwv_monitor: CoreWebVitalsMonitor instance (optional)
        use_cwv_monitor: Whether CoreWebVitalsMonitor is available

    Example:
        >>> detector = CWVQualityDetector(repository, config)
        >>> count = detector.detect(property="sc-domain:example.com")
        >>> print(f"Created {count} CWV insights")
    """

    def __init__(self, repository, config, use_cwv_monitor: bool = True):
        """
        Initialize CWVQualityDetector.

        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
            use_cwv_monitor: Whether to use CoreWebVitalsMonitor (default: True)
        """
        super().__init__(repository, config)

        self.use_cwv_monitor = use_cwv_monitor and CWV_MONITOR_AVAILABLE
        self.cwv_monitor: Optional['CoreWebVitalsMonitor'] = None

        if self.use_cwv_monitor:
            try:
                self.cwv_monitor = CoreWebVitalsMonitor(db_dsn=config.warehouse_dsn)
                logger.info("CWVQualityDetector initialized with CoreWebVitalsMonitor")
            except Exception as e:
                logger.warning(f"Failed to initialize CoreWebVitalsMonitor: {e}")
                self.use_cwv_monitor = False
                self.cwv_monitor = None
        else:
            logger.info("CWVQualityDetector initialized without CoreWebVitalsMonitor (direct DB queries)")

    def detect(self, property: str = None) -> int:
        """
        Detect CWV quality issues.

        Analyzes Core Web Vitals metrics for all pages with CWV data,
        creating RISK insights for any metric in the "poor" zone.

        Args:
            property: Property to analyze (e.g., "sc-domain:example.com")

        Returns:
            Number of insights created
        """
        logger.info(f"Starting CWV quality detection for {property or 'all properties'}")

        try:
            # Get CWV data from database
            cwv_data = self._get_cwv_data(property)

            if not cwv_data:
                logger.info(f"No CWV data found for {property or 'any property'}")
                return 0

            logger.info(f"Analyzing {len(cwv_data)} CWV records for quality issues")

            insights_created = 0

            for record in cwv_data:
                page_path = record.get('page_path', '/')
                strategy = record.get('strategy', 'mobile')
                record_property = record.get('property', property or 'unknown')

                # Check each CWV metric for poor performance
                # LCP check
                lcp = record.get('lcp')
                if lcp is not None and lcp > LCP_POOR_THRESHOLD:
                    insight = self._create_cwv_insight(
                        property=record_property,
                        page_path=page_path,
                        metric='lcp',
                        value=lcp,
                        threshold=LCP_POOR_THRESHOLD,
                        device=strategy,
                        unit='ms'
                    )
                    self.repository.create(insight)
                    insights_created += 1
                    logger.info(f"Poor LCP detected: {page_path} ({strategy}): {lcp}ms > {LCP_POOR_THRESHOLD}ms")

                # FID check (or INP as replacement)
                fid = record.get('fid') or record.get('inp')
                metric_name = 'inp' if record.get('inp') else 'fid'
                if fid is not None and fid > FID_POOR_THRESHOLD:
                    insight = self._create_cwv_insight(
                        property=record_property,
                        page_path=page_path,
                        metric=metric_name,
                        value=fid,
                        threshold=FID_POOR_THRESHOLD,
                        device=strategy,
                        unit='ms'
                    )
                    self.repository.create(insight)
                    insights_created += 1
                    logger.info(f"Poor {metric_name.upper()} detected: {page_path} ({strategy}): {fid}ms > {FID_POOR_THRESHOLD}ms")

                # CLS check
                cls = record.get('cls')
                if cls is not None and cls > CLS_POOR_THRESHOLD:
                    insight = self._create_cwv_insight(
                        property=record_property,
                        page_path=page_path,
                        metric='cls',
                        value=cls,
                        threshold=CLS_POOR_THRESHOLD,
                        device=strategy,
                        unit=''  # CLS is unitless
                    )
                    self.repository.create(insight)
                    insights_created += 1
                    logger.info(f"Poor CLS detected: {page_path} ({strategy}): {cls} > {CLS_POOR_THRESHOLD}")

            logger.info(f"CWV quality detection complete: {insights_created} insights created")
            return insights_created

        except Exception as e:
            logger.error(f"Error in CWV quality detection: {e}", exc_info=True)
            return 0

    def _get_cwv_data(self, property: str = None) -> List[Dict[str, Any]]:
        """
        Get Core Web Vitals data from database.

        Queries the performance.core_web_vitals table for recent CWV data.

        Args:
            property: Optional property filter

        Returns:
            List of CWV records as dictionaries
        """
        conn = None
        cursor = None

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Query for most recent CWV data for each page/strategy
            query = """
                SELECT DISTINCT ON (property, page_path, strategy)
                    property,
                    page_path,
                    check_date,
                    strategy,
                    lcp,
                    fid,
                    cls,
                    fcp,
                    inp,
                    ttfb,
                    performance_score,
                    cwv_assessment
                FROM performance.core_web_vitals
                WHERE check_date >= CURRENT_DATE - INTERVAL '7 days'
            """

            params = []
            if property:
                query += " AND property = %s"
                params.append(property)

            query += " ORDER BY property, page_path, strategy, check_date DESC"

            cursor.execute(query, params)
            results = cursor.fetchall()

            logger.debug(f"Fetched {len(results)} CWV records from database")

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Database error fetching CWV data: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _create_cwv_insight(
        self,
        property: str,
        page_path: str,
        metric: str,
        value: float,
        threshold: float,
        device: str,
        unit: str
    ) -> InsightCreate:
        """
        Create a RISK insight for a poor CWV metric.

        Args:
            property: Property URL
            page_path: Page path (entity_id)
            metric: CWV metric name (lcp, fid, inp, cls)
            value: Actual metric value
            threshold: Poor threshold that was exceeded
            device: Device type (mobile, desktop)
            unit: Unit for display (ms, or empty for CLS)

        Returns:
            InsightCreate for the CWV risk insight
        """
        metric_display_name = METRIC_DISPLAY_NAMES.get(metric, metric.upper())

        # Format value display based on metric type
        if metric == 'cls':
            value_display = f"{value:.3f}"
            threshold_display = f"{threshold:.2f}"
            description_value = f"{value:.3f}"
            description_threshold = f"{threshold:.2f}"
        else:
            # LCP, FID, INP are in milliseconds
            value_display = f"{value:.0f}ms"
            threshold_display = f"{threshold:.0f}ms"
            description_value = f"{value:.0f}ms"
            description_threshold = f"{threshold:.0f}ms"

        # Calculate how much the value exceeds the threshold
        excess_percent = ((value - threshold) / threshold) * 100

        # Title format: "Poor {metric_name}: {value}"
        title = f"Poor {metric_display_name}: {value_display}"

        # Create detailed description with context
        if metric == 'lcp':
            description = (
                f"Page '{page_path}' has a poor LCP of {description_value} ({device}), "
                f"which is {excess_percent:.0f}% above the poor threshold of {description_threshold}. "
                f"LCP measures the time until the largest content element is visible. "
                f"Poor LCP indicates slow loading that frustrates users. "
                f"Consider optimizing images, fonts, and critical rendering path. "
                f"Target: <2.5s (Good), Current: {description_value} (Poor)."
            )
        elif metric in ('fid', 'inp'):
            metric_full_name = "First Input Delay" if metric == 'fid' else "Interaction to Next Paint"
            description = (
                f"Page '{page_path}' has a poor {metric.upper()} of {description_value} ({device}), "
                f"which is {excess_percent:.0f}% above the poor threshold of {description_threshold}. "
                f"{metric.upper()} ({metric_full_name}) measures input responsiveness. "
                f"Poor {metric.upper()} makes the page feel unresponsive to user interactions. "
                f"Consider reducing JavaScript execution time and breaking up long tasks. "
                f"Target: <100ms (Good), Current: {description_value} (Poor)."
            )
        else:  # cls
            description = (
                f"Page '{page_path}' has a poor CLS of {description_value} ({device}), "
                f"which is {excess_percent:.0f}% above the poor threshold of {description_threshold}. "
                f"CLS measures visual stability - how much content shifts during loading. "
                f"Poor CLS causes frustrating layout shifts that can make users click wrong elements. "
                f"Consider adding size attributes to images/videos and avoiding dynamic content insertion. "
                f"Target: <0.1 (Good), Current: {description_value} (Poor)."
            )

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title=title,
            description=description,
            severity=InsightSeverity.HIGH,  # All poor CWV metrics are high severity
            confidence=0.95,  # High confidence for objective measurement
            metrics=InsightMetrics(
                metric=metric,
                value=float(value),
                threshold=float(threshold),
                device=device,
                unit=unit,
                cwv_assessment='poor',
                excess_percent=round(excess_percent, 1),
            ),
            window_days=7,  # CWV data is typically recent
            source="CWVQualityDetector",
        )

    def get_cwv_summary(self, property: str) -> Dict[str, Any]:
        """
        Get a summary of CWV quality for a property.

        Convenience method for ad-hoc analysis without creating insights.

        Args:
            property: Property to analyze

        Returns:
            Dictionary with CWV analysis summary
        """
        try:
            cwv_data = self._get_cwv_data(property)

            if not cwv_data:
                return {
                    'available': True,
                    'pages_analyzed': 0,
                    'poor_lcp_count': 0,
                    'poor_fid_count': 0,
                    'poor_cls_count': 0,
                    'issues': []
                }

            poor_lcp = []
            poor_fid = []
            poor_cls = []

            for record in cwv_data:
                page_path = record.get('page_path', '/')
                strategy = record.get('strategy', 'mobile')

                lcp = record.get('lcp')
                if lcp is not None and lcp > LCP_POOR_THRESHOLD:
                    poor_lcp.append({
                        'page_path': page_path,
                        'device': strategy,
                        'value': lcp,
                    })

                fid = record.get('fid') or record.get('inp')
                if fid is not None and fid > FID_POOR_THRESHOLD:
                    poor_fid.append({
                        'page_path': page_path,
                        'device': strategy,
                        'value': fid,
                    })

                cls = record.get('cls')
                if cls is not None and cls > CLS_POOR_THRESHOLD:
                    poor_cls.append({
                        'page_path': page_path,
                        'device': strategy,
                        'value': cls,
                    })

            return {
                'available': True,
                'pages_analyzed': len(cwv_data),
                'poor_lcp_count': len(poor_lcp),
                'poor_fid_count': len(poor_fid),
                'poor_cls_count': len(poor_cls),
                'total_issues': len(poor_lcp) + len(poor_fid) + len(poor_cls),
                'issues': {
                    'poor_lcp': poor_lcp,
                    'poor_fid': poor_fid,
                    'poor_cls': poor_cls,
                }
            }

        except Exception as e:
            logger.error(f"Error in CWV summary: {e}")
            return {
                'available': True,
                'error': str(e)
            }
