"""
Event Correlation Engine
=========================
Links SERP ranking changes to potential trigger events such as content changes,
Google algorithm updates, and technical issues.

The engine analyzes a 7-day window before a ranking change to identify
correlated events and calculates confidence scores for each correlation.

Example:
    >>> from insights_core.event_correlation_engine import EventCorrelationEngine
    >>> engine = EventCorrelationEngine()
    >>> events = engine.find_trigger_events(
    ...     page_path='/blog/post/',
    ...     ranking_change_date='2025-01-20'
    ... )
    >>> for event in events:
    ...     print(f"{event['event_type']}: {event['confidence']:.2f}")
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Event types
EVENT_TYPE_CONTENT_CHANGE = 'content_change'
EVENT_TYPE_ALGORITHM_UPDATE = 'algorithm_update'
EVENT_TYPE_TECHNICAL_ISSUE = 'technical_issue'

# Default correlation window (days before ranking change to check)
DEFAULT_LOOKBACK_DAYS = 7


@dataclass
class CorrelatedEvent:
    """
    Represents a potential trigger event correlated with a ranking change.

    Attributes:
        event_type: Type of event (content_change, algorithm_update, technical_issue)
        event_date: Date the event occurred
        details: Event-specific details (commit info, update name, issue description)
        confidence: Correlation confidence score (0.0 to 1.0)
        days_before_change: Number of days between event and ranking change
    """
    event_type: str
    event_date: date
    details: Dict[str, Any]
    confidence: float
    days_before_change: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_type': self.event_type,
            'event_date': self.event_date.isoformat() if isinstance(self.event_date, date) else self.event_date,
            'details': self.details,
            'confidence': self.confidence,
            'days_before_change': self.days_before_change
        }


@dataclass
class RankingChange:
    """
    Represents a SERP ranking change event.

    Attributes:
        property: Property URL (e.g., 'sc-domain:example.com')
        page_path: Page path that experienced the ranking change
        query: Search query (optional)
        change_date: Date the ranking change was detected
        previous_position: Previous SERP position
        new_position: New SERP position
        change_magnitude: Position change (positive = improvement, negative = decline)
    """
    property: str
    page_path: str
    query: Optional[str]
    change_date: date
    previous_position: Optional[int]
    new_position: Optional[int]
    change_magnitude: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'property': self.property,
            'page_path': self.page_path,
            'query': self.query,
            'change_date': self.change_date.isoformat() if isinstance(self.change_date, date) else self.change_date,
            'previous_position': self.previous_position,
            'new_position': self.new_position,
            'change_magnitude': self.change_magnitude
        }


class EventCorrelationEngine:
    """
    Engine for correlating SERP ranking changes with potential trigger events.

    This engine identifies potential causes for ranking changes by analyzing:
    1. Content changes (git commits modifying the page)
    2. Google algorithm updates
    3. Technical issues (CWV problems, crawl errors, etc.)

    The engine uses a 7-day lookback window and calculates confidence scores
    based on event proximity and type.

    Example:
        >>> engine = EventCorrelationEngine()
        >>> events = engine.find_trigger_events('/blog/seo-tips/', '2025-01-20')
        >>> print(f"Found {len(events)} correlated events")

    Attributes:
        db_dsn: PostgreSQL connection string
        lookback_days: Number of days to look back for trigger events
        git_repo_path: Path to git repository for commit analysis
    """

    # Confidence weights based on event proximity (days before change)
    PROXIMITY_WEIGHTS = {
        0: 0.95,   # Same day
        1: 0.90,   # 1 day before
        2: 0.80,   # 2 days before
        3: 0.70,   # 3 days before
        4: 0.60,   # 4 days before
        5: 0.50,   # 5 days before
        6: 0.40,   # 6 days before
        7: 0.30,   # 7 days before
    }

    # Base confidence by event type
    EVENT_TYPE_BASE_CONFIDENCE = {
        EVENT_TYPE_CONTENT_CHANGE: 0.85,
        EVENT_TYPE_ALGORITHM_UPDATE: 0.75,
        EVENT_TYPE_TECHNICAL_ISSUE: 0.80,
    }

    def __init__(
        self,
        db_dsn: str = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        git_repo_path: str = None
    ):
        """
        Initialize the EventCorrelationEngine.

        Args:
            db_dsn: PostgreSQL connection string. Defaults to WAREHOUSE_DSN env var.
            lookback_days: Number of days to look back for trigger events. Default 7.
            git_repo_path: Path to git repository for commit analysis.
                          Defaults to current working directory.
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.lookback_days = lookback_days
        self.git_repo_path = git_repo_path or os.getcwd()

        logger.info(
            f"EventCorrelationEngine initialized "
            f"(lookback_days={lookback_days}, git_repo={self.git_repo_path})"
        )

    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_dsn, cursor_factory=RealDictCursor)

    def _parse_date(self, date_input: Union[str, date, datetime]) -> date:
        """
        Parse date input to date object.

        Args:
            date_input: Date as string (YYYY-MM-DD), date, or datetime

        Returns:
            date object

        Raises:
            ValueError: If date cannot be parsed
        """
        if isinstance(date_input, datetime):
            return date_input.date()
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, str):
            try:
                return datetime.strptime(date_input, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Invalid date format: {date_input}. Expected YYYY-MM-DD")
        raise ValueError(f"Unsupported date type: {type(date_input)}")

    def _calculate_confidence(
        self,
        event_type: str,
        days_before_change: int,
        additional_factors: Dict[str, float] = None
    ) -> float:
        """
        Calculate correlation confidence score.

        The confidence is calculated as:
        base_confidence * proximity_weight * additional_factors

        Args:
            event_type: Type of trigger event
            days_before_change: Days between event and ranking change
            additional_factors: Additional multipliers for confidence

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = self.EVENT_TYPE_BASE_CONFIDENCE.get(event_type, 0.5)

        # Get proximity weight, default to lowest for events beyond lookback
        proximity_weight = self.PROXIMITY_WEIGHTS.get(
            min(days_before_change, self.lookback_days),
            0.30
        )

        confidence = base_confidence * proximity_weight

        # Apply additional factors
        if additional_factors:
            for factor_name, factor_value in additional_factors.items():
                confidence *= factor_value
                logger.debug(f"Applied factor {factor_name}: {factor_value:.2f}")

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))

    def find_trigger_events(
        self,
        page_path: str,
        ranking_change_date: Union[str, date, datetime],
        property: str = None,
        include_content_changes: bool = True,
        include_algorithm_updates: bool = True,
        include_technical_issues: bool = True
    ) -> List[CorrelatedEvent]:
        """
        Find potential trigger events for a ranking change.

        Searches within the lookback window (default 7 days) for:
        - Git commits modifying content for the page
        - Google algorithm updates
        - Technical issues (CWV degradation, crawl errors)

        Args:
            page_path: Page path that experienced ranking change (e.g., '/blog/post/')
            ranking_change_date: Date the ranking change was detected
            property: Property URL (optional, for database queries)
            include_content_changes: Include git commit analysis
            include_algorithm_updates: Include algorithm update checks
            include_technical_issues: Include technical issue checks

        Returns:
            List of CorrelatedEvent objects sorted by confidence (highest first)

        Example:
            >>> events = engine.find_trigger_events(
            ...     page_path='/blog/seo-tips/',
            ...     ranking_change_date='2025-01-20',
            ...     property='sc-domain:example.com'
            ... )
            >>> for event in events:
            ...     print(f"{event.event_type}: confidence={event.confidence:.2f}")
        """
        ranking_date = self._parse_date(ranking_change_date)
        start_date = ranking_date - timedelta(days=self.lookback_days)

        logger.info(
            f"Finding trigger events for {page_path} "
            f"(change date: {ranking_date}, window: {start_date} to {ranking_date})"
        )

        events: List[CorrelatedEvent] = []

        # Get git commits for content changes
        if include_content_changes:
            try:
                content_events = self._get_git_commits(
                    file_path=page_path,
                    date_range=(start_date, ranking_date)
                )
                events.extend(content_events)
                logger.debug(f"Found {len(content_events)} content change events")
            except Exception as e:
                logger.warning(f"Error getting git commits: {e}")

        # Get algorithm updates
        if include_algorithm_updates:
            try:
                algo_events = self._get_algorithm_updates(
                    date_range=(start_date, ranking_date)
                )
                events.extend(algo_events)
                logger.debug(f"Found {len(algo_events)} algorithm update events")
            except Exception as e:
                logger.warning(f"Error getting algorithm updates: {e}")

        # Get technical issues
        if include_technical_issues:
            try:
                tech_events = self._get_technical_changes(
                    page_path=page_path,
                    date_range=(start_date, ranking_date),
                    property=property
                )
                events.extend(tech_events)
                logger.debug(f"Found {len(tech_events)} technical issue events")
            except Exception as e:
                logger.warning(f"Error getting technical changes: {e}")

        # Sort by confidence (highest first)
        events.sort(key=lambda e: e.confidence, reverse=True)

        logger.info(f"Found {len(events)} total trigger events for {page_path}")
        return events

    def _get_git_commits(
        self,
        file_path: str,
        date_range: Tuple[date, date]
    ) -> List[CorrelatedEvent]:
        """
        Find git commits that modified content for the specified page.

        Searches the git history for commits that modified files matching
        the page path pattern within the date range.

        Args:
            file_path: Page path to search for (e.g., '/blog/post/')
            date_range: Tuple of (start_date, end_date) to search within

        Returns:
            List of CorrelatedEvent for content changes

        Example:
            >>> events = engine._get_git_commits(
            ...     file_path='/blog/seo-tips/',
            ...     date_range=(date(2025, 1, 13), date(2025, 1, 20))
            ... )
        """
        events: List[CorrelatedEvent] = []
        start_date, end_date = date_range

        # Convert page path to potential file patterns
        # Remove leading slash and try common content locations
        clean_path = file_path.lstrip('/')
        search_patterns = [
            clean_path,
            f"content/{clean_path}",
            f"pages/{clean_path}",
            f"src/{clean_path}",
            f"*{clean_path}*",
        ]

        try:
            # Build git log command
            since_date = start_date.strftime('%Y-%m-%d')
            until_date = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')

            for pattern in search_patterns:
                try:
                    # Run git log with JSON-like format
                    cmd = [
                        'git', 'log',
                        f'--since={since_date}',
                        f'--until={until_date}',
                        '--pretty=format:%H|%ad|%an|%s',
                        '--date=short',
                        '--name-only',
                        '--',
                        pattern
                    ]

                    result = subprocess.run(
                        cmd,
                        cwd=self.git_repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if result.returncode != 0:
                        continue

                    output = result.stdout.strip()
                    if not output:
                        continue

                    # Parse git log output
                    commits = self._parse_git_log_output(output, end_date)
                    events.extend(commits)

                except subprocess.TimeoutExpired:
                    logger.warning(f"Git log timeout for pattern: {pattern}")
                except FileNotFoundError:
                    logger.debug("Git not available in PATH")
                    break

        except Exception as e:
            logger.warning(f"Error running git log: {e}")

        # Deduplicate by commit hash
        seen_commits = set()
        unique_events = []
        for event in events:
            commit_hash = event.details.get('commit_hash')
            if commit_hash and commit_hash not in seen_commits:
                seen_commits.add(commit_hash)
                unique_events.append(event)

        return unique_events

    def _parse_git_log_output(
        self,
        output: str,
        ranking_change_date: date
    ) -> List[CorrelatedEvent]:
        """
        Parse git log output into CorrelatedEvent objects.

        Args:
            output: Raw git log output
            ranking_change_date: Date of the ranking change for confidence calculation

        Returns:
            List of CorrelatedEvent objects
        """
        events: List[CorrelatedEvent] = []
        lines = output.strip().split('\n')

        current_commit = None
        current_files = []

        for line in lines:
            if not line.strip():
                # Empty line = end of commit file list
                if current_commit and current_files:
                    current_commit['files'] = current_files
                    events.append(self._create_content_change_event(
                        current_commit,
                        ranking_change_date
                    ))
                current_commit = None
                current_files = []
            elif '|' in line and len(line.split('|')) == 4:
                # Commit header line: hash|date|author|message
                if current_commit and current_files:
                    current_commit['files'] = current_files
                    events.append(self._create_content_change_event(
                        current_commit,
                        ranking_change_date
                    ))

                parts = line.split('|')
                try:
                    commit_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
                    current_commit = {
                        'commit_hash': parts[0],
                        'date': commit_date,
                        'author': parts[2],
                        'message': parts[3]
                    }
                    current_files = []
                except (ValueError, IndexError):
                    current_commit = None
                    current_files = []
            elif current_commit and line.strip():
                # File path line
                current_files.append(line.strip())

        # Handle last commit
        if current_commit and current_files:
            current_commit['files'] = current_files
            events.append(self._create_content_change_event(
                current_commit,
                ranking_change_date
            ))

        return events

    def _create_content_change_event(
        self,
        commit_info: Dict[str, Any],
        ranking_change_date: date
    ) -> CorrelatedEvent:
        """
        Create a CorrelatedEvent for a content change.

        Args:
            commit_info: Dictionary with commit details
            ranking_change_date: Date of the ranking change

        Returns:
            CorrelatedEvent object
        """
        commit_date = commit_info['date']
        days_before = (ranking_change_date - commit_date).days

        # Additional confidence factors based on commit content
        additional_factors = {}

        # Boost confidence for commits with SEO-related keywords
        message = commit_info.get('message', '').lower()
        seo_keywords = ['seo', 'title', 'meta', 'description', 'heading', 'content', 'update']
        if any(kw in message for kw in seo_keywords):
            additional_factors['seo_relevance'] = 1.1

        # Boost for larger changes (more files)
        file_count = len(commit_info.get('files', []))
        if file_count >= 5:
            additional_factors['change_scope'] = 1.05
        elif file_count == 1:
            additional_factors['change_scope'] = 1.1  # Targeted change

        confidence = self._calculate_confidence(
            EVENT_TYPE_CONTENT_CHANGE,
            days_before,
            additional_factors
        )

        return CorrelatedEvent(
            event_type=EVENT_TYPE_CONTENT_CHANGE,
            event_date=commit_date,
            details={
                'commit_hash': commit_info['commit_hash'],
                'author': commit_info['author'],
                'message': commit_info['message'],
                'files_changed': commit_info.get('files', []),
                'file_count': file_count
            },
            confidence=confidence,
            days_before_change=days_before
        )

    def _get_algorithm_updates(
        self,
        date_range: Tuple[date, date]
    ) -> List[CorrelatedEvent]:
        """
        Find Google algorithm updates within the date range.

        Queries the serp.algorithm_updates table for known updates.

        Args:
            date_range: Tuple of (start_date, end_date) to search within

        Returns:
            List of CorrelatedEvent for algorithm updates

        Example:
            >>> events = engine._get_algorithm_updates(
            ...     date_range=(date(2025, 1, 13), date(2025, 1, 20))
            ... )
        """
        events: List[CorrelatedEvent] = []
        start_date, end_date = date_range

        if not self.db_dsn:
            logger.debug("No database connection, skipping algorithm updates lookup")
            return events

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT
                            update_name,
                            update_date,
                            update_type,
                            description,
                            impact_level
                        FROM serp.algorithm_updates
                        WHERE update_date >= %s AND update_date <= %s
                        ORDER BY update_date DESC
                    """, (start_date, end_date))

                    rows = cursor.fetchall()

                    for row in rows:
                        update_date = row['update_date']
                        days_before = (end_date - update_date).days

                        # Additional confidence factors based on update type
                        additional_factors = {}

                        impact_level = row.get('impact_level', 'moderate')
                        if impact_level == 'major':
                            additional_factors['impact'] = 1.2
                        elif impact_level == 'minor':
                            additional_factors['impact'] = 0.8

                        confidence = self._calculate_confidence(
                            EVENT_TYPE_ALGORITHM_UPDATE,
                            days_before,
                            additional_factors
                        )

                        events.append(CorrelatedEvent(
                            event_type=EVENT_TYPE_ALGORITHM_UPDATE,
                            event_date=update_date,
                            details={
                                'update_name': row['update_name'],
                                'update_type': row.get('update_type'),
                                'description': row.get('description'),
                                'impact_level': impact_level
                            },
                            confidence=confidence,
                            days_before_change=days_before
                        ))

        except psycopg2.Error as e:
            logger.warning(f"Database error getting algorithm updates: {e}")
        except Exception as e:
            logger.warning(f"Error getting algorithm updates: {e}")

        return events

    def _get_technical_changes(
        self,
        page_path: str,
        date_range: Tuple[date, date],
        property: str = None
    ) -> List[CorrelatedEvent]:
        """
        Find technical issues that may have affected the page.

        Checks for:
        - Core Web Vitals degradation
        - Crawl errors
        - Server errors
        - Page speed issues

        Args:
            page_path: Page path to check
            date_range: Tuple of (start_date, end_date) to search within
            property: Property URL for database queries

        Returns:
            List of CorrelatedEvent for technical issues

        Example:
            >>> events = engine._get_technical_changes(
            ...     page_path='/blog/seo-tips/',
            ...     date_range=(date(2025, 1, 13), date(2025, 1, 20)),
            ...     property='sc-domain:example.com'
            ... )
        """
        events: List[CorrelatedEvent] = []
        start_date, end_date = date_range

        if not self.db_dsn:
            logger.debug("No database connection, skipping technical changes lookup")
            return events

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check for CWV degradation from performance schema
                    events.extend(
                        self._check_cwv_issues(cursor, page_path, start_date, end_date, property)
                    )

                    # Check for page errors from gsc data
                    events.extend(
                        self._check_page_errors(cursor, page_path, start_date, end_date, property)
                    )

        except psycopg2.Error as e:
            logger.warning(f"Database error getting technical changes: {e}")
        except Exception as e:
            logger.warning(f"Error getting technical changes: {e}")

        return events

    def _check_cwv_issues(
        self,
        cursor,
        page_path: str,
        start_date: date,
        end_date: date,
        property: str = None
    ) -> List[CorrelatedEvent]:
        """
        Check for Core Web Vitals degradation.

        Args:
            cursor: Database cursor
            page_path: Page path to check
            start_date: Start of date range
            end_date: End of date range
            property: Property URL

        Returns:
            List of CorrelatedEvent for CWV issues
        """
        events: List[CorrelatedEvent] = []

        try:
            # Check if performance.cwv_metrics table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'performance'
                    AND table_name = 'cwv_metrics'
                )
            """)
            table_exists = cursor.fetchone()['exists']

            if not table_exists:
                logger.debug("CWV metrics table not found, skipping CWV check")
                return events

            # Query for CWV degradation
            query = """
                WITH cwv_changes AS (
                    SELECT
                        date,
                        lcp_p75,
                        fid_p75,
                        cls_p75,
                        LAG(lcp_p75) OVER (ORDER BY date) as prev_lcp,
                        LAG(fid_p75) OVER (ORDER BY date) as prev_fid,
                        LAG(cls_p75) OVER (ORDER BY date) as prev_cls
                    FROM performance.cwv_metrics
                    WHERE page_path = %s
                        AND date >= %s
                        AND date <= %s
            """
            params = [page_path, start_date, end_date]

            if property:
                query += " AND property = %s"
                params.append(property)

            query += """
                    ORDER BY date
                )
                SELECT
                    date,
                    lcp_p75,
                    fid_p75,
                    cls_p75,
                    prev_lcp,
                    prev_fid,
                    prev_cls,
                    CASE WHEN prev_lcp > 0 THEN ((lcp_p75 - prev_lcp) / prev_lcp) * 100 ELSE 0 END as lcp_change_pct,
                    CASE WHEN prev_fid > 0 THEN ((fid_p75 - prev_fid) / prev_fid) * 100 ELSE 0 END as fid_change_pct,
                    CASE WHEN prev_cls > 0 THEN ((cls_p75 - prev_cls) / prev_cls) * 100 ELSE 0 END as cls_change_pct
                FROM cwv_changes
                WHERE prev_lcp IS NOT NULL
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                # Check for significant degradation (>20% worse)
                degradation_found = False
                issues = []

                if row.get('lcp_change_pct', 0) > 20:
                    issues.append(f"LCP degraded {row['lcp_change_pct']:.1f}%")
                    degradation_found = True

                if row.get('fid_change_pct', 0) > 20:
                    issues.append(f"FID degraded {row['fid_change_pct']:.1f}%")
                    degradation_found = True

                if row.get('cls_change_pct', 0) > 20:
                    issues.append(f"CLS degraded {row['cls_change_pct']:.1f}%")
                    degradation_found = True

                if degradation_found:
                    issue_date = row['date']
                    days_before = (end_date - issue_date).days

                    confidence = self._calculate_confidence(
                        EVENT_TYPE_TECHNICAL_ISSUE,
                        days_before,
                        {'severity': 1.1}  # CWV issues are significant
                    )

                    events.append(CorrelatedEvent(
                        event_type=EVENT_TYPE_TECHNICAL_ISSUE,
                        event_date=issue_date,
                        details={
                            'issue_type': 'cwv_degradation',
                            'issues': issues,
                            'lcp_p75': row.get('lcp_p75'),
                            'fid_p75': row.get('fid_p75'),
                            'cls_p75': row.get('cls_p75'),
                            'lcp_change_pct': row.get('lcp_change_pct'),
                            'fid_change_pct': row.get('fid_change_pct'),
                            'cls_change_pct': row.get('cls_change_pct')
                        },
                        confidence=confidence,
                        days_before_change=days_before
                    ))

        except psycopg2.Error as e:
            logger.debug(f"Error checking CWV issues: {e}")

        return events

    def _check_page_errors(
        self,
        cursor,
        page_path: str,
        start_date: date,
        end_date: date,
        property: str = None
    ) -> List[CorrelatedEvent]:
        """
        Check for page errors and crawl issues.

        Args:
            cursor: Database cursor
            page_path: Page path to check
            start_date: Start of date range
            end_date: End of date range
            property: Property URL

        Returns:
            List of CorrelatedEvent for page errors
        """
        events: List[CorrelatedEvent] = []

        try:
            # Check for sudden drops in impressions which might indicate crawl issues
            query = """
                WITH daily_data AS (
                    SELECT
                        date,
                        SUM(impressions) as impressions,
                        LAG(SUM(impressions)) OVER (ORDER BY date) as prev_impressions
                    FROM gsc.search_data
                    WHERE page_path = %s
                        AND date >= %s
                        AND date <= %s
            """
            params = [page_path, start_date, end_date]

            if property:
                query += " AND property = %s"
                params.append(property)

            query += """
                    GROUP BY date
                    ORDER BY date
                )
                SELECT
                    date,
                    impressions,
                    prev_impressions,
                    CASE
                        WHEN prev_impressions > 0
                        THEN ((impressions - prev_impressions)::float / prev_impressions) * 100
                        ELSE 0
                    END as change_pct
                FROM daily_data
                WHERE prev_impressions IS NOT NULL
                    AND prev_impressions > 10  -- Minimum threshold
                    AND ((impressions - prev_impressions)::float / prev_impressions) * 100 < -50
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                issue_date = row['date']
                days_before = (end_date - issue_date).days

                confidence = self._calculate_confidence(
                    EVENT_TYPE_TECHNICAL_ISSUE,
                    days_before,
                    {'severity': 0.9}  # Lower confidence since could be normal fluctuation
                )

                events.append(CorrelatedEvent(
                    event_type=EVENT_TYPE_TECHNICAL_ISSUE,
                    event_date=issue_date,
                    details={
                        'issue_type': 'impression_drop',
                        'impressions': row['impressions'],
                        'prev_impressions': row['prev_impressions'],
                        'change_pct': row['change_pct'],
                        'possible_causes': ['crawl_error', 'server_error', 'noindex_added']
                    },
                    confidence=confidence,
                    days_before_change=days_before
                ))

        except psycopg2.Error as e:
            logger.debug(f"Error checking page errors: {e}")

        return events

    def store_correlation(
        self,
        ranking_change: RankingChange,
        event: CorrelatedEvent
    ) -> Optional[int]:
        """
        Store a ranking change correlation in the database.

        Args:
            ranking_change: The ranking change event
            event: The correlated trigger event

        Returns:
            ID of the stored record, or None if storage failed
        """
        if not self.db_dsn:
            logger.warning("No database connection, cannot store correlation")
            return None

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO serp.ranking_change_events (
                            property,
                            page_path,
                            query,
                            ranking_change_date,
                            previous_position,
                            new_position,
                            change_magnitude,
                            trigger_event_type,
                            trigger_event_date,
                            trigger_event_details,
                            correlation_confidence
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (property, page_path, ranking_change_date, trigger_event_type, trigger_event_date)
                        DO UPDATE SET
                            correlation_confidence = EXCLUDED.correlation_confidence,
                            trigger_event_details = EXCLUDED.trigger_event_details,
                            updated_at = NOW()
                        RETURNING id
                    """, (
                        ranking_change.property,
                        ranking_change.page_path,
                        ranking_change.query,
                        ranking_change.change_date,
                        ranking_change.previous_position,
                        ranking_change.new_position,
                        ranking_change.change_magnitude,
                        event.event_type,
                        event.event_date,
                        psycopg2.extras.Json(event.details),
                        event.confidence
                    ))

                    result = cursor.fetchone()
                    conn.commit()

                    record_id = result['id'] if result else None
                    logger.info(f"Stored correlation {record_id} for {ranking_change.page_path}")
                    return record_id

        except psycopg2.Error as e:
            logger.error(f"Database error storing correlation: {e}")
            return None
        except Exception as e:
            logger.error(f"Error storing correlation: {e}")
            return None

    def find_and_store_correlations(
        self,
        ranking_change: RankingChange
    ) -> List[int]:
        """
        Find trigger events for a ranking change and store all correlations.

        Args:
            ranking_change: The ranking change to analyze

        Returns:
            List of stored record IDs
        """
        events = self.find_trigger_events(
            page_path=ranking_change.page_path,
            ranking_change_date=ranking_change.change_date,
            property=ranking_change.property
        )

        stored_ids = []
        for event in events:
            record_id = self.store_correlation(ranking_change, event)
            if record_id:
                stored_ids.append(record_id)

        logger.info(
            f"Stored {len(stored_ids)} correlations for ranking change on {ranking_change.page_path}"
        )
        return stored_ids

    def get_high_confidence_correlations(
        self,
        property: str = None,
        min_confidence: float = 0.7,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get high-confidence correlations from the database.

        Args:
            property: Filter by property (optional)
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results

        Returns:
            List of correlation records
        """
        if not self.db_dsn:
            logger.warning("No database connection")
            return []

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                        SELECT *
                        FROM serp.ranking_change_events
                        WHERE correlation_confidence >= %s
                    """
                    params = [min_confidence]

                    if property:
                        query += " AND property = %s"
                        params.append(property)

                    query += " ORDER BY correlation_confidence DESC, ranking_change_date DESC LIMIT %s"
                    params.append(limit)

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    return [dict(row) for row in rows]

        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            return []


__all__ = [
    'EventCorrelationEngine',
    'CorrelatedEvent',
    'RankingChange',
    'EVENT_TYPE_CONTENT_CHANGE',
    'EVENT_TYPE_ALGORITHM_UPDATE',
    'EVENT_TYPE_TECHNICAL_ISSUE',
    'DEFAULT_LOOKBACK_DAYS',
]
