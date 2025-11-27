"""
GSC-Based SERP Position Tracker
Uses existing Google Search Console data for position tracking
No external APIs needed - completely free!

Version: 2.0 - Updated for production schema compatibility
"""

import asyncio
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class GSCBasedSerpTracker:
    """
    Track SERP positions using existing GSC data instead of external APIs

    Advantages:
    - Free - no API costs
    - Official Google data
    - No rate limits
    - Already integrated

    Limitations:
    - 48-hour data delay (GSC limitation)
    - Only tracks queries you already rank for
    - No competitor tracking
    """

    def __init__(self, db_dsn: str = None):
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')

    def sync_positions_from_gsc_sync(self, property_url: str,
                                     min_impressions: int = 10,
                                     days_back: int = 7) -> Dict:
        """
        Synchronous version of sync for scheduler integration

        Args:
            property_url: Property to sync
            min_impressions: Minimum impressions to track (filters out noise)
            days_back: Number of days to analyze

        Returns:
            Summary of synced data
        """
        conn = psycopg2.connect(self.db_dsn)

        try:
            queries_synced = self._sync_queries_sync(conn, property_url, min_impressions, days_back)
            positions_synced = self._sync_position_history_sync(conn, property_url, days_back)

            return {
                'success': True,
                'property': property_url,
                'queries_synced': queries_synced,
                'positions_synced': positions_synced,
                'data_source': 'gsc',
                'synced_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"GSC SERP sync failed: {e}")
            return {
                'success': False,
                'property': property_url,
                'error': str(e),
                'data_source': 'gsc',
                'synced_at': datetime.now().isoformat()
            }

        finally:
            conn.close()

    def _sync_queries_sync(self, conn, property_url: str,
                          min_impressions: int, days_back: int) -> int:
        """
        Create/update SERP queries from GSC data (synchronous)
        Auto-discovers keywords you're ranking for
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if fact_gsc_daily table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'gsc' AND table_name = 'fact_gsc_daily'
                )
            """)
            if not cur.fetchone()['exists']:
                logger.warning("gsc.fact_gsc_daily table not found")
                return 0

            # Get top queries from GSC data
            cur.execute("""
                WITH query_stats AS (
                    SELECT
                        query as query_text,
                        page as page_path,
                        device,
                        country,
                        AVG(position) as avg_position,
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        CASE WHEN SUM(impressions) > 0
                            THEN ROUND(100.0 * SUM(clicks) / SUM(impressions), 2)
                            ELSE 0
                        END as avg_ctr,
                        MAX(date) as latest_date
                    FROM gsc.fact_gsc_daily
                    WHERE property = %s
                        AND date >= CURRENT_DATE - INTERVAL '%s days'
                        AND query IS NOT NULL
                        AND query != ''
                    GROUP BY query, page, device, country
                    HAVING SUM(impressions) >= %s
                )
                SELECT
                    query_text,
                    page_path,
                    device,
                    country as location,
                    avg_position,
                    total_impressions,
                    total_clicks,
                    avg_ctr,
                    latest_date
                FROM query_stats
                ORDER BY total_impressions DESC
                LIMIT 5000
            """, (property_url, days_back, min_impressions))

            queries = cur.fetchall()
            synced_count = 0

            for query in queries:
                try:
                    # Upsert into serp.queries table
                    cur.execute("""
                        INSERT INTO serp.queries
                        (query_text, property, target_page_path, location, device,
                         is_active, data_source, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, true, 'gsc', NOW(), NOW())
                        ON CONFLICT (property, query_text, target_page_path, device, location)
                        DO UPDATE SET
                            is_active = true,
                            data_source = COALESCE(serp.queries.data_source, 'gsc'),
                            updated_at = NOW()
                        RETURNING query_id
                    """, (
                        query['query_text'],
                        property_url,
                        query['page_path'],
                        query['location'] or 'United States',
                        query['device'] or 'desktop'
                    ))

                    synced_count += 1

                except psycopg2.Error as e:
                    # Handle unique constraint violation by trying simpler upsert
                    conn.rollback()
                    try:
                        cur.execute("""
                            INSERT INTO serp.queries
                            (query_text, property, target_page_path, location, device,
                             is_active, data_source)
                            VALUES (%s, %s, %s, %s, %s, true, 'gsc')
                            ON CONFLICT DO NOTHING
                        """, (
                            query['query_text'],
                            property_url,
                            query['page_path'],
                            query['location'] or 'United States',
                            query['device'] or 'desktop'
                        ))
                        conn.commit()
                        synced_count += 1
                    except Exception:
                        conn.rollback()
                        continue

            conn.commit()
            return synced_count

    def _sync_position_history_sync(self, conn, property_url: str,
                                    days_back: int) -> int:
        """
        Sync position history from GSC to SERP tables (synchronous)
        Creates time-series position data
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get daily position data from GSC
            cur.execute("""
                SELECT
                    f.query as query_text,
                    f.page as page_path,
                    f.device,
                    f.country,
                    f.date as data_date,
                    AVG(f.position) as position,
                    SUM(f.impressions) as impressions,
                    SUM(f.clicks) as clicks,
                    CASE WHEN SUM(f.impressions) > 0
                        THEN ROUND(100.0 * SUM(f.clicks) / SUM(f.impressions), 2)
                        ELSE 0
                    END as ctr
                FROM gsc.fact_gsc_daily f
                WHERE f.property = %s
                    AND f.date >= CURRENT_DATE - INTERVAL '%s days'
                    AND f.query IS NOT NULL
                    AND f.query != ''
                GROUP BY f.query, f.page, f.device, f.country, f.date
                ORDER BY f.date DESC
            """, (property_url, days_back))

            daily_positions = cur.fetchall()
            synced_count = 0

            for record in daily_positions:
                # Get query_id
                cur.execute("""
                    SELECT query_id FROM serp.queries
                    WHERE query_text = %s
                        AND property = %s
                        AND target_page_path = %s
                        AND device = %s
                    LIMIT 1
                """, (
                    record['query_text'],
                    property_url,
                    record['page_path'],
                    record['device']
                ))

                result = cur.fetchone()
                if not result:
                    continue

                query_id = result['query_id']

                try:
                    # Insert position history
                    cur.execute("""
                        INSERT INTO serp.position_history
                        (query_id, check_date, check_timestamp, position, url,
                         api_source, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'gsc', NOW())
                        ON CONFLICT (query_id, check_date, check_timestamp) DO UPDATE SET
                            position = EXCLUDED.position,
                            url = EXCLUDED.url
                    """, (
                        query_id,
                        record['data_date'],
                        datetime.combine(record['data_date'], datetime.min.time()),
                        int(record['position']) if record['position'] else None,
                        property_url.rstrip('/') + (record['page_path'] or '')
                    ))

                    synced_count += 1

                except psycopg2.Error:
                    conn.rollback()
                    continue

            conn.commit()
            return synced_count

    async def sync_positions_from_gsc(self, property_url: str,
                                     min_impressions: int = 10,
                                     days_back: int = 7) -> Dict:
        """
        Async version: Sync position data from GSC to SERP tracking tables

        Args:
            property_url: Property to sync
            min_impressions: Minimum impressions to track (filters out noise)
            days_back: Number of days to analyze

        Returns:
            Summary of synced data
        """
        conn = await asyncpg.connect(self.db_dsn)

        try:
            queries_synced = await self._sync_queries(conn, property_url, min_impressions, days_back)
            positions_synced = await self._sync_position_history(conn, property_url, days_back)

            return {
                'success': True,
                'property': property_url,
                'queries_synced': queries_synced,
                'positions_synced': positions_synced,
                'data_source': 'gsc',
                'synced_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"GSC SERP sync failed: {e}")
            return {
                'success': False,
                'property': property_url,
                'error': str(e),
                'data_source': 'gsc',
                'synced_at': datetime.now().isoformat()
            }

        finally:
            await conn.close()

    async def _sync_queries(self, conn, property_url: str,
                           min_impressions: int, days_back: int) -> int:
        """
        Create/update SERP queries from GSC data
        Auto-discovers keywords you're ranking for
        """
        # Check if table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'gsc' AND table_name = 'fact_gsc_daily'
            )
        """)

        if not exists:
            logger.warning("gsc.fact_gsc_daily table not found")
            return 0

        # Get top queries from GSC data
        queries = await conn.fetch(f"""
            WITH query_stats AS (
                SELECT
                    query as query_text,
                    page as page_path,
                    device,
                    country,
                    AVG(position) as avg_position,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    CASE WHEN SUM(impressions) > 0
                        THEN ROUND(100.0 * SUM(clicks) / SUM(impressions), 2)
                        ELSE 0
                    END as avg_ctr,
                    MAX(date) as latest_date
                FROM gsc.fact_gsc_daily
                WHERE property = $1
                    AND date >= CURRENT_DATE - INTERVAL '{days_back} days'
                    AND query IS NOT NULL
                    AND query != ''
                GROUP BY query, page, device, country
                HAVING SUM(impressions) >= $2
            )
            SELECT
                query_text,
                page_path,
                device,
                country as location,
                avg_position,
                total_impressions,
                total_clicks,
                avg_ctr,
                latest_date
            FROM query_stats
            ORDER BY total_impressions DESC
            LIMIT 5000
        """, property_url, min_impressions)

        synced_count = 0

        for query in queries:
            try:
                await conn.execute("""
                    INSERT INTO serp.queries
                    (query_text, property, target_page_path, location, device,
                     is_active, data_source, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, true, 'gsc', NOW(), NOW())
                    ON CONFLICT (property, query_text, target_page_path, device, location)
                    DO UPDATE SET
                        is_active = true,
                        data_source = COALESCE(serp.queries.data_source, 'gsc'),
                        updated_at = NOW()
                """,
                    query['query_text'],
                    property_url,
                    query['page_path'],
                    query['location'] or 'United States',
                    query['device'] or 'desktop'
                )

                synced_count += 1
            except Exception:
                continue

        return synced_count

    async def _sync_position_history(self, conn, property_url: str,
                                     days_back: int) -> int:
        """
        Sync position history from GSC to SERP tables
        Creates time-series position data
        """
        # Get daily position data from GSC
        daily_positions = await conn.fetch(f"""
            SELECT
                f.query as query_text,
                f.page as page_path,
                f.device,
                f.country,
                f.date as data_date,
                AVG(f.position) as position,
                SUM(f.impressions) as impressions,
                SUM(f.clicks) as clicks,
                CASE WHEN SUM(f.impressions) > 0
                    THEN ROUND(100.0 * SUM(f.clicks) / SUM(f.impressions), 2)
                    ELSE 0
                END as ctr
            FROM gsc.fact_gsc_daily f
            WHERE f.property = $1
                AND f.date >= CURRENT_DATE - INTERVAL '{days_back} days'
                AND f.query IS NOT NULL
                AND f.query != ''
            GROUP BY f.query, f.page, f.device, f.country, f.date
            ORDER BY f.date DESC
        """, property_url)

        synced_count = 0

        for record in daily_positions:
            # Get query_id
            query_id = await conn.fetchval("""
                SELECT query_id FROM serp.queries
                WHERE query_text = $1
                    AND property = $2
                    AND target_page_path = $3
                    AND device = $4
                LIMIT 1
            """,
                record['query_text'],
                property_url,
                record['page_path'],
                record['device']
            )

            if not query_id:
                continue

            try:
                await conn.execute("""
                    INSERT INTO serp.position_history
                    (query_id, check_date, check_timestamp, position, url,
                     api_source, created_at)
                    VALUES ($1, $2, $3, $4, $5, 'gsc', NOW())
                    ON CONFLICT (query_id, check_date, check_timestamp) DO UPDATE SET
                        position = EXCLUDED.position,
                        url = EXCLUDED.url
                """,
                    query_id,
                    record['data_date'],
                    datetime.combine(record['data_date'], datetime.min.time()),
                    int(record['position']) if record['position'] else None,
                    property_url.rstrip('/') + (record['page_path'] or '')
                )

                synced_count += 1
            except Exception:
                continue

        return synced_count

    async def get_position_changes(self, property_url: str,
                                  days: int = 7) -> List[Dict]:
        """
        Detect position changes from GSC data
        Useful for alerts and analysis
        """
        conn = await asyncpg.connect(self.db_dsn)

        try:
            changes = await conn.fetch(f"""
                WITH current_positions AS (
                    SELECT
                        query as query_text,
                        page as page_path,
                        AVG(position) as current_position,
                        SUM(impressions) as current_impressions
                    FROM gsc.fact_gsc_daily
                    WHERE property = $1
                        AND date >= CURRENT_DATE - INTERVAL '3 days'
                        AND query IS NOT NULL
                    GROUP BY query, page
                ),
                previous_positions AS (
                    SELECT
                        query as query_text,
                        page as page_path,
                        AVG(position) as previous_position,
                        SUM(impressions) as previous_impressions
                    FROM gsc.fact_gsc_daily
                    WHERE property = $1
                        AND date >= CURRENT_DATE - INTERVAL '{days + 3} days'
                        AND date < CURRENT_DATE - INTERVAL '3 days'
                        AND query IS NOT NULL
                    GROUP BY query, page
                )
                SELECT
                    c.query_text,
                    c.page_path,
                    c.current_position,
                    p.previous_position,
                    (p.previous_position - c.current_position) as position_change,
                    c.current_impressions,
                    p.previous_impressions
                FROM current_positions c
                INNER JOIN previous_positions p
                    ON c.query_text = p.query_text
                    AND c.page_path = p.page_path
                WHERE ABS(p.previous_position - c.current_position) >= 2
                    AND c.current_impressions > 10
                ORDER BY ABS(p.previous_position - c.current_position) DESC
                LIMIT 50
            """, property_url)

            return [dict(row) for row in changes]

        finally:
            await conn.close()

    async def get_top_ranking_keywords(self, property_url: str,
                                      position_max: int = 10,
                                      days: int = 7) -> List[Dict]:
        """
        Get keywords ranking in top positions from GSC
        """
        conn = await asyncpg.connect(self.db_dsn)

        try:
            keywords = await conn.fetch(f"""
                SELECT
                    query as query_text,
                    page as page_path,
                    AVG(position) as avg_position,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    CASE WHEN SUM(impressions) > 0
                        THEN ROUND(100.0 * SUM(clicks) / SUM(impressions), 2)
                        ELSE 0
                    END as avg_ctr
                FROM gsc.fact_gsc_daily
                WHERE property = $1
                    AND date >= CURRENT_DATE - INTERVAL '{days} days'
                    AND position <= $2
                    AND query IS NOT NULL
                GROUP BY query, page
                HAVING SUM(impressions) > 10
                ORDER BY AVG(position) ASC, SUM(impressions) DESC
                LIMIT 100
            """, property_url, position_max)

            return [dict(row) for row in keywords]

        finally:
            await conn.close()

    async def get_opportunity_keywords(self, property_url: str,
                                      position_min: int = 11,
                                      position_max: int = 20,
                                      days: int = 30) -> List[Dict]:
        """
        Get keywords ranking 11-20 (easy wins)
        """
        conn = await asyncpg.connect(self.db_dsn)

        try:
            opportunities = await conn.fetch(f"""
                SELECT
                    query as query_text,
                    page as page_path,
                    AVG(position) as avg_position,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    CASE WHEN SUM(impressions) > 0
                        THEN ROUND(100.0 * SUM(clicks) / SUM(impressions), 2)
                        ELSE 0
                    END as avg_ctr,
                    -- Estimate potential clicks if moved to position 5
                    ROUND(SUM(impressions) * 0.07) as potential_clicks,
                    ROUND(SUM(impressions) * 0.07 - SUM(clicks)) as potential_gain
                FROM gsc.fact_gsc_daily
                WHERE property = $1
                    AND date >= CURRENT_DATE - INTERVAL '{days} days'
                    AND position BETWEEN $2 AND $3
                    AND query IS NOT NULL
                GROUP BY query, page
                HAVING SUM(impressions) > 50
                ORDER BY (SUM(impressions) * 0.07 - SUM(clicks)) DESC
                LIMIT 50
            """, property_url, position_min, position_max)

            return [dict(row) for row in opportunities]

        finally:
            await conn.close()

    def get_sync_stats(self) -> Dict:
        """Get statistics about synced data"""
        conn = psycopg2.connect(self.db_dsn)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        data_source,
                        COUNT(*) as total_queries,
                        COUNT(*) FILTER (WHERE is_active) as active_queries
                    FROM serp.queries
                    GROUP BY data_source
                """)
                query_stats = cur.fetchall()

                cur.execute("""
                    SELECT
                        api_source,
                        COUNT(*) as total_records,
                        MIN(check_date) as earliest_date,
                        MAX(check_date) as latest_date
                    FROM serp.position_history
                    GROUP BY api_source
                """)
                position_stats = cur.fetchall()

                return {
                    'queries_by_source': {r['data_source']: r for r in query_stats},
                    'positions_by_source': {r['api_source']: r for r in position_stats}
                }

        finally:
            conn.close()


def sync_all_properties(min_impressions: int = 10, days_back: int = 7) -> List[Dict]:
    """
    Sync GSC data to SERP tables for all configured properties

    Returns:
        List of sync results per property
    """
    db_dsn = os.getenv('WAREHOUSE_DSN')
    properties_str = os.getenv('GSC_PROPERTIES', '')

    if not properties_str:
        logger.warning("GSC_PROPERTIES not configured")
        return []

    properties = [p.strip() for p in properties_str.split(',') if p.strip()]
    tracker = GSCBasedSerpTracker(db_dsn)
    results = []

    for prop in properties:
        logger.info(f"Syncing GSC SERP data for: {prop}")
        result = tracker.sync_positions_from_gsc_sync(
            property_url=prop,
            min_impressions=min_impressions,
            days_back=days_back
        )
        results.append(result)

        if result['success']:
            logger.info(f"  Synced {result['queries_synced']} queries, "
                       f"{result['positions_synced']} positions")
        else:
            logger.error(f"  Failed: {result.get('error', 'Unknown error')}")

    return results


async def example_usage():
    """Example of how to use GSC-based SERP tracker"""

    tracker = GSCBasedSerpTracker()

    property_url = os.getenv('GSC_PROPERTIES', '').split(',')[0]
    if not property_url:
        print("GSC_PROPERTIES not configured")
        return

    # 1. Sync positions from GSC
    print("Syncing positions from GSC data...")
    result = await tracker.sync_positions_from_gsc(
        property_url=property_url,
        min_impressions=10,
        days_back=30
    )

    print(f"Synced {result['queries_synced']} queries")
    print(f"Synced {result['positions_synced']} position records")

    # 2. Get position changes
    print("\nDetecting position changes...")
    changes = await tracker.get_position_changes(property_url, days=7)

    print(f"\nTop Position Changes (last 7 days):")
    for change in changes[:10]:
        direction = "UP" if change['position_change'] > 0 else "DOWN"
        print(f"  {direction} {change['query_text']}")
        print(f"    Position: {change['previous_position']:.1f} -> {change['current_position']:.1f} "
              f"({change['position_change']:+.1f})")

    # 3. Get top ranking keywords
    print("\nTop 10 Ranking Keywords:")
    top_keywords = await tracker.get_top_ranking_keywords(property_url, position_max=10)

    for kw in top_keywords[:10]:
        print(f"  #{kw['avg_position']:.1f} - {kw['query_text']} "
              f"({kw['total_clicks']} clicks, {kw['total_impressions']} impressions)")

    # 4. Get opportunity keywords
    print("\nTop Opportunities (Ranking 11-20):")
    opportunities = await tracker.get_opportunity_keywords(property_url)

    for opp in opportunities[:10]:
        print(f"  #{opp['avg_position']:.1f} - {opp['query_text']}")
        print(f"    Potential gain: +{opp['potential_gain']} clicks/month")


if __name__ == '__main__':
    asyncio.run(example_usage())
