"""
URL Discovery Sync Module
=========================
Discovers URLs from GSC and GA4 fact tables and syncs them to CWV monitoring.

This ensures that every URL receiving clicks (GSC) or sessions (GA4) is
automatically considered for Core Web Vitals data collection.

Discovery criteria:
- GSC: URLs with clicks >= min_clicks in last N days
- GA4: Page paths with sessions >= min_sessions in last N days

Priority scoring formula:
    priority_score = (
        0.40 * normalized_clicks +
        0.25 * normalized_sessions +
        0.20 * position_score +
        0.15 * recency_score
    )
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Configuration for URL discovery sync"""
    min_gsc_clicks: int = 10
    min_ga4_sessions: int = 5
    lookback_days: int = 30
    stale_threshold_days: int = 90
    check_mobile: bool = True
    check_desktop: bool = False
    max_new_urls_per_run: int = 100

    @classmethod
    def from_dict(cls, config: Dict) -> 'SyncConfig':
        """Create config from dictionary"""
        return cls(
            min_gsc_clicks=config.get('min_gsc_clicks', 10),
            min_ga4_sessions=config.get('min_ga4_sessions', 5),
            lookback_days=config.get('lookback_days', 30),
            stale_threshold_days=config.get('stale_threshold_days', 90),
            check_mobile=config.get('check_mobile', True),
            check_desktop=config.get('check_desktop', False),
            max_new_urls_per_run=config.get('max_new_urls_per_run', 100),
        )


@dataclass
class DiscoveredURL:
    """Represents a discovered URL from GSC or GA4"""
    property: str
    page_path: str
    source: str  # 'gsc', 'ga4', 'gsc+ga4'
    clicks: int = 0
    sessions: int = 0
    avg_position: Optional[float] = None
    last_seen_at: Optional[datetime] = None


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    property: str
    urls_discovered: int = 0
    urls_new: int = 0
    urls_updated: int = 0
    urls_deactivated: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)


class URLDiscoverySync:
    """
    Discovers URLs from GSC and GA4 fact tables and syncs to CWV monitoring.

    Usage:
        sync = URLDiscoverySync(db_dsn)
        result = sync.sync_all()
        print(f"Discovered {result.urls_discovered} URLs")
    """

    def __init__(
        self,
        db_dsn: str = None,
        config: SyncConfig = None
    ):
        """
        Initialize URL Discovery Sync.

        Args:
            db_dsn: Database connection string
            config: Sync configuration
        """
        self.db_dsn = db_dsn or os.environ.get('WAREHOUSE_DSN')
        self.config = config or SyncConfig()
        self._conn = None

    def get_connection(self):
        """Get or create database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.db_dsn)
        return self._conn

    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def normalize_page_path(self, url_or_path: str, property_url: str = None) -> str:
        """
        Normalize a URL or page path to a consistent format.

        - Extracts path from full URLs
        - Removes trailing slashes (except for root)
        - Lowercases the path
        - Strips query parameters (optional, configurable)

        Args:
            url_or_path: Full URL or page path
            property_url: Property URL for context

        Returns:
            Normalized page path (e.g., '/blog/post-title')
        """
        if not url_or_path:
            return '/'

        # If it's a full URL, extract the path
        if url_or_path.startswith('http://') or url_or_path.startswith('https://'):
            parsed = urlparse(url_or_path)
            path = parsed.path
        else:
            path = url_or_path

        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path

        # Remove trailing slash (except for root path)
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Lowercase for consistency
        path = path.lower()

        return path

    def normalize_property(self, property_url: str) -> str:
        """
        Normalize a property URL.

        - Ensures trailing slash
        - Lowercases

        Args:
            property_url: Property URL

        Returns:
            Normalized property URL
        """
        if not property_url:
            return ''

        # Ensure trailing slash for property URLs
        property_url = property_url.rstrip('/') + '/'

        return property_url

    def discover_gsc_urls(
        self,
        property: str = None,
        min_clicks: int = None,
        lookback_days: int = None
    ) -> List[DiscoveredURL]:
        """
        Discover URLs from GSC fact table.

        Args:
            property: Filter by property (optional)
            min_clicks: Minimum clicks threshold
            lookback_days: Days to look back

        Returns:
            List of discovered URLs
        """
        min_clicks = min_clicks or self.config.min_gsc_clicks
        lookback_days = lookback_days or self.config.lookback_days

        conn = self.get_connection()

        query = """
            SELECT
                property,
                url,
                SUM(clicks) as total_clicks,
                SUM(impressions) as total_impressions,
                AVG(position) as avg_position,
                MAX(date) as last_seen_date
            FROM gsc.fact_gsc_daily
            WHERE date >= CURRENT_DATE - %s * INTERVAL '1 day'
        """
        params = [lookback_days]

        if property:
            query += " AND property = %s"
            params.append(property)

        query += """
            GROUP BY property, url
            HAVING SUM(clicks) >= %s
            ORDER BY SUM(clicks) DESC
        """
        params.append(min_clicks)

        discovered = []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

                for row in rows:
                    prop = self.normalize_property(row['property'])
                    page_path = self.normalize_page_path(row['url'], prop)

                    discovered.append(DiscoveredURL(
                        property=prop,
                        page_path=page_path,
                        source='gsc',
                        clicks=int(row['total_clicks']),
                        avg_position=float(row['avg_position']) if row['avg_position'] else None,
                        last_seen_at=row['last_seen_date']
                    ))

            logger.info(f"Discovered {len(discovered)} URLs from GSC (min_clicks={min_clicks})")

        except Exception as e:
            logger.error(f"Error discovering GSC URLs: {e}")
            raise

        return discovered

    def discover_ga4_urls(
        self,
        property: str = None,
        min_sessions: int = None,
        lookback_days: int = None
    ) -> List[DiscoveredURL]:
        """
        Discover URLs from GA4 fact table.

        Args:
            property: Filter by property (optional)
            min_sessions: Minimum sessions threshold
            lookback_days: Days to look back

        Returns:
            List of discovered URLs
        """
        min_sessions = min_sessions or self.config.min_ga4_sessions
        lookback_days = lookback_days or self.config.lookback_days

        conn = self.get_connection()

        query = """
            SELECT
                property,
                page_path,
                SUM(sessions) as total_sessions,
                SUM(page_views) as total_page_views,
                MAX(date) as last_seen_date
            FROM gsc.fact_ga4_daily
            WHERE date >= CURRENT_DATE - %s * INTERVAL '1 day'
        """
        params = [lookback_days]

        if property:
            query += " AND property = %s"
            params.append(property)

        query += """
            GROUP BY property, page_path
            HAVING SUM(sessions) >= %s
            ORDER BY SUM(sessions) DESC
        """
        params.append(min_sessions)

        discovered = []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

                for row in rows:
                    prop = self.normalize_property(row['property'])
                    page_path = self.normalize_page_path(row['page_path'], prop)

                    discovered.append(DiscoveredURL(
                        property=prop,
                        page_path=page_path,
                        source='ga4',
                        sessions=int(row['total_sessions']),
                        last_seen_at=row['last_seen_date']
                    ))

            logger.info(f"Discovered {len(discovered)} URLs from GA4 (min_sessions={min_sessions})")

        except Exception as e:
            logger.error(f"Error discovering GA4 URLs: {e}")
            raise

        return discovered

    def merge_discovered_urls(
        self,
        gsc_urls: List[DiscoveredURL],
        ga4_urls: List[DiscoveredURL]
    ) -> List[DiscoveredURL]:
        """
        Merge URLs discovered from GSC and GA4.

        URLs found in both sources get combined metrics and source='gsc+ga4'.

        Args:
            gsc_urls: URLs from GSC
            ga4_urls: URLs from GA4

        Returns:
            Merged list of unique URLs
        """
        # Create lookup by (property, page_path)
        url_map: Dict[Tuple[str, str], DiscoveredURL] = {}

        # Add GSC URLs
        for url in gsc_urls:
            key = (url.property, url.page_path)
            url_map[key] = url

        # Merge GA4 URLs
        for url in ga4_urls:
            key = (url.property, url.page_path)
            if key in url_map:
                # Merge with existing GSC URL
                existing = url_map[key]
                existing.sessions = url.sessions
                existing.source = 'gsc+ga4'
                # Keep the most recent last_seen_at
                if url.last_seen_at and (not existing.last_seen_at or url.last_seen_at > existing.last_seen_at):
                    existing.last_seen_at = url.last_seen_at
            else:
                # New GA4-only URL
                url_map[key] = url

        merged = list(url_map.values())

        # Count by source
        gsc_only = sum(1 for u in merged if u.source == 'gsc')
        ga4_only = sum(1 for u in merged if u.source == 'ga4')
        both = sum(1 for u in merged if u.source == 'gsc+ga4')

        logger.info(
            f"Merged URLs: {len(merged)} total "
            f"(GSC only: {gsc_only}, GA4 only: {ga4_only}, both: {both})"
        )

        return merged

    def calculate_priority_score(self, url: DiscoveredURL) -> float:
        """
        Calculate priority score for a discovered URL.

        Higher scores get checked first for CWV.

        Formula:
            0.40 * normalized_clicks +
            0.25 * normalized_sessions +
            0.20 * position_score +
            0.15 * recency_score

        Args:
            url: Discovered URL

        Returns:
            Priority score (0.0 to 1.0)
        """
        import math

        # Normalize clicks (log scale, max at 10000)
        click_score = min(1.0, math.log(max(url.clicks, 1) + 1) / math.log(10001))

        # Normalize sessions (log scale, max at 5000)
        session_score = min(1.0, math.log(max(url.sessions, 1) + 1) / math.log(5001))

        # Position score (better position = higher score)
        if url.avg_position and url.avg_position > 0:
            position_score = max(0, 1.0 - (url.avg_position - 1) / 100)
        else:
            position_score = 0.5  # Default for unknown position

        # Recency score
        if url.last_seen_at:
            if isinstance(url.last_seen_at, datetime):
                days_since = (datetime.now() - url.last_seen_at).days
            else:
                # It's a date object
                days_since = (datetime.now().date() - url.last_seen_at).days
            recency_score = max(0, 1.0 - (days_since / 90))
        else:
            recency_score = 0.5

        # Weighted combination
        score = (
            0.40 * click_score +
            0.25 * session_score +
            0.20 * position_score +
            0.15 * recency_score
        )

        return round(score, 4)

    def sync_to_monitored_pages(
        self,
        urls: List[DiscoveredURL],
        dry_run: bool = False
    ) -> Dict:
        """
        Sync discovered URLs to performance.monitored_pages table.

        Args:
            urls: List of discovered URLs
            dry_run: If True, don't commit changes

        Returns:
            Dict with sync statistics
        """
        stats = {
            'urls_processed': len(urls),
            'urls_new': 0,
            'urls_updated': 0,
            'urls_skipped': 0,
        }

        if not urls:
            logger.info("No URLs to sync")
            return stats

        conn = self.get_connection()

        # Calculate priority scores
        for url in urls:
            url.priority_score = self.calculate_priority_score(url)

        # Sort by priority for consistent processing
        urls.sort(key=lambda u: u.priority_score, reverse=True)

        # Limit new URLs per run
        new_url_count = 0

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for url in urls:
                    # Check if URL already exists
                    cur.execute("""
                        SELECT page_id, discovery_source, total_clicks, total_sessions
                        FROM performance.monitored_pages
                        WHERE property = %s AND page_path = %s
                    """, (url.property, url.page_path))

                    existing = cur.fetchone()

                    if existing:
                        # Update existing URL
                        # Merge discovery source
                        old_source = existing['discovery_source'] or 'manual'
                        if url.source == 'gsc+ga4':
                            new_source = 'gsc+ga4'
                        elif old_source == 'manual':
                            new_source = url.source
                        elif old_source == 'gsc' and url.source == 'ga4':
                            new_source = 'gsc+ga4'
                        elif old_source == 'ga4' and url.source == 'gsc':
                            new_source = 'gsc+ga4'
                        else:
                            new_source = old_source

                        if not dry_run:
                            cur.execute("""
                                UPDATE performance.monitored_pages
                                SET
                                    discovery_source = %s,
                                    last_seen_at = CURRENT_TIMESTAMP,
                                    total_clicks = GREATEST(total_clicks, %s),
                                    total_sessions = GREATEST(total_sessions, %s),
                                    avg_position = COALESCE(%s, avg_position),
                                    priority_score = %s,
                                    is_active = true
                                WHERE property = %s AND page_path = %s
                            """, (
                                new_source,
                                url.clicks,
                                url.sessions,
                                url.avg_position,
                                url.priority_score,
                                url.property,
                                url.page_path
                            ))

                        stats['urls_updated'] += 1
                    else:
                        # New URL - check limit
                        if new_url_count >= self.config.max_new_urls_per_run:
                            stats['urls_skipped'] += 1
                            continue

                        if not dry_run:
                            cur.execute("""
                                INSERT INTO performance.monitored_pages (
                                    property, page_path, check_mobile, check_desktop,
                                    is_active, discovery_source, first_discovered_at,
                                    last_seen_at, total_clicks, total_sessions,
                                    avg_position, priority_score
                                ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP,
                                          CURRENT_TIMESTAMP, %s, %s, %s, %s)
                            """, (
                                url.property,
                                url.page_path,
                                self.config.check_mobile,
                                self.config.check_desktop,
                                True,
                                url.source,
                                url.clicks,
                                url.sessions,
                                url.avg_position,
                                url.priority_score
                            ))

                        stats['urls_new'] += 1
                        new_url_count += 1

                if not dry_run:
                    conn.commit()
                else:
                    conn.rollback()

            logger.info(
                f"Sync complete: {stats['urls_new']} new, "
                f"{stats['urls_updated']} updated, "
                f"{stats['urls_skipped']} skipped"
            )

        except Exception as e:
            conn.rollback()
            logger.error(f"Error syncing URLs: {e}")
            raise

        return stats

    def deactivate_stale_urls(
        self,
        property: str = None,
        stale_days: int = None,
        dry_run: bool = False
    ) -> int:
        """
        Deactivate URLs not seen in GSC/GA4 data for a long time.

        Args:
            property: Filter by property (optional)
            stale_days: Days threshold for staleness
            dry_run: If True, don't commit changes

        Returns:
            Number of URLs deactivated
        """
        stale_days = stale_days or self.config.stale_threshold_days
        conn = self.get_connection()

        query = """
            UPDATE performance.monitored_pages
            SET is_active = false
            WHERE is_active = true
              AND discovery_source != 'manual'
              AND last_seen_at < CURRENT_TIMESTAMP - %s * INTERVAL '1 day'
        """
        params = [stale_days]

        if property:
            query += " AND property = %s"
            params.append(property)

        try:
            with conn.cursor() as cur:
                if dry_run:
                    # Count only
                    count_query = query.replace(
                        "UPDATE performance.monitored_pages\n            SET is_active = false",
                        "SELECT COUNT(*) FROM performance.monitored_pages"
                    )
                    cur.execute(count_query, params)
                    count = cur.fetchone()[0]
                else:
                    cur.execute(query, params)
                    count = cur.rowcount
                    conn.commit()

            logger.info(f"Deactivated {count} stale URLs (>{stale_days} days)")
            return count

        except Exception as e:
            conn.rollback()
            logger.error(f"Error deactivating stale URLs: {e}")
            raise

    def get_properties(self) -> List[str]:
        """Get list of unique properties from GSC and GA4 data."""
        conn = self.get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT property FROM (
                        SELECT DISTINCT property FROM gsc.fact_gsc_daily
                        WHERE date >= CURRENT_DATE - 30
                        UNION
                        SELECT DISTINCT property FROM gsc.fact_ga4_daily
                        WHERE date >= CURRENT_DATE - 30
                    ) combined
                    ORDER BY property
                """)
                properties = [row[0] for row in cur.fetchall()]

            return properties

        except Exception as e:
            logger.error(f"Error getting properties: {e}")
            return []

    def sync(
        self,
        property: str = None,
        dry_run: bool = False
    ) -> SyncResult:
        """
        Run full URL discovery and sync.

        Args:
            property: Filter by property (optional)
            dry_run: If True, don't commit changes

        Returns:
            SyncResult with statistics
        """
        import time
        start_time = time.time()

        result = SyncResult(
            success=False,
            property=property or 'all'
        )

        try:
            # Discover URLs from GSC
            logger.info(f"Discovering URLs from GSC (lookback={self.config.lookback_days} days)...")
            gsc_urls = self.discover_gsc_urls(property=property)

            # Discover URLs from GA4
            logger.info(f"Discovering URLs from GA4 (lookback={self.config.lookback_days} days)...")
            ga4_urls = self.discover_ga4_urls(property=property)

            # Merge URLs
            logger.info("Merging discovered URLs...")
            merged_urls = self.merge_discovered_urls(gsc_urls, ga4_urls)
            result.urls_discovered = len(merged_urls)

            # Sync to monitored_pages
            logger.info("Syncing to monitored_pages...")
            sync_stats = self.sync_to_monitored_pages(merged_urls, dry_run=dry_run)
            result.urls_new = sync_stats['urls_new']
            result.urls_updated = sync_stats['urls_updated']

            # Deactivate stale URLs
            logger.info("Checking for stale URLs...")
            result.urls_deactivated = self.deactivate_stale_urls(
                property=property,
                dry_run=dry_run
            )

            # Store details
            result.details = {
                'gsc_urls_found': len(gsc_urls),
                'ga4_urls_found': len(ga4_urls),
                'urls_from_gsc_only': sum(1 for u in merged_urls if u.source == 'gsc'),
                'urls_from_ga4_only': sum(1 for u in merged_urls if u.source == 'ga4'),
                'urls_from_both': sum(1 for u in merged_urls if u.source == 'gsc+ga4'),
                'urls_skipped': sync_stats.get('urls_skipped', 0),
            }

            result.success = True
            result.duration_seconds = time.time() - start_time

            logger.info(
                f"Sync complete in {result.duration_seconds:.2f}s: "
                f"{result.urls_discovered} discovered, "
                f"{result.urls_new} new, "
                f"{result.urls_updated} updated, "
                f"{result.urls_deactivated} deactivated"
            )

        except Exception as e:
            result.error = str(e)
            result.duration_seconds = time.time() - start_time
            logger.error(f"Sync failed: {e}")

        return result

    def sync_all_properties(self, dry_run: bool = False) -> List[SyncResult]:
        """
        Sync all properties.

        Args:
            dry_run: If True, don't commit changes

        Returns:
            List of SyncResult for each property
        """
        properties = self.get_properties()
        results = []

        logger.info(f"Syncing {len(properties)} properties...")

        for prop in properties:
            logger.info(f"Processing property: {prop}")
            result = self.sync(property=prop, dry_run=dry_run)
            results.append(result)

        return results

    def update_watermark(
        self,
        property: str,
        source_type: str,
        result: SyncResult
    ):
        """Update discovery watermark after sync."""
        conn = self.get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO performance.discovery_watermarks (
                        property, source_type, last_sync_at,
                        urls_discovered, urls_updated, urls_deactivated,
                        last_run_status, error_message
                    ) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s)
                    ON CONFLICT (property, source_type) DO UPDATE SET
                        last_sync_at = CURRENT_TIMESTAMP,
                        urls_discovered = EXCLUDED.urls_discovered,
                        urls_updated = EXCLUDED.urls_updated,
                        urls_deactivated = EXCLUDED.urls_deactivated,
                        last_run_status = EXCLUDED.last_run_status,
                        error_message = EXCLUDED.error_message
                """, (
                    property,
                    source_type,
                    result.urls_discovered,
                    result.urls_updated,
                    result.urls_deactivated,
                    'success' if result.success else 'failed',
                    result.error
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating watermark: {e}")
            conn.rollback()


def sync_all_properties(
    db_dsn: str = None,
    config: Dict = None,
    dry_run: bool = False
) -> List[SyncResult]:
    """
    Convenience function to sync all properties.

    Args:
        db_dsn: Database connection string
        config: Configuration dictionary
        dry_run: If True, don't commit changes

    Returns:
        List of SyncResult
    """
    sync_config = SyncConfig.from_dict(config or {})
    sync = URLDiscoverySync(db_dsn=db_dsn, config=sync_config)

    try:
        return sync.sync_all_properties(dry_run=dry_run)
    finally:
        sync.close()


__all__ = [
    'URLDiscoverySync',
    'SyncConfig',
    'SyncResult',
    'DiscoveredURL',
    'sync_all_properties',
]
