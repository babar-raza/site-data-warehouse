"""
Trends Accumulator - Daily collection of Google Trends data

Collects trends data for tracked keywords and stores in database
for correlation with GSC performance data.

Example:
    accumulator = TrendsAccumulator()
    stats = accumulator.collect_for_property('sc-domain:example.com')
    print(f"Collected {stats['keywords_collected']} keywords")
"""
import logging
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import pandas as pd

from ingestors.trends.trends_client import GoogleTrendsClient

logger = logging.getLogger(__name__)


class TrendsAccumulator:
    """
    Accumulates Google Trends data for tracked keywords

    Collects daily trends data for top keywords from GSC
    and stores for historical analysis.

    Example:
        accumulator = TrendsAccumulator()
        stats = accumulator.collect_for_property('sc-domain:example.com')
    """

    MAX_KEYWORDS_PER_PROPERTY = 50
    MIN_CLICKS_THRESHOLD = 10  # Minimum clicks to consider a keyword
    DAYS_LOOKBACK = 30  # Look at last 30 days of GSC data

    def __init__(self, db_dsn: str = None, client: GoogleTrendsClient = None):
        """
        Initialize Trends Accumulator

        Args:
            db_dsn: Database connection string
            client: Optional GoogleTrendsClient instance
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.client = client or GoogleTrendsClient()
        logger.info("TrendsAccumulator initialized")

    def collect_for_property(self, property: str) -> Dict:
        """
        Collect trends for property's top keywords

        Args:
            property: GSC property to collect for

        Returns:
            Dict with collection statistics
        """
        run_id = None
        stats = {
            'property': property,
            'keywords_collected': 0,
            'keywords_failed': 0,
            'related_queries_collected': 0,
            'started_at': datetime.utcnow().isoformat()
        }

        try:
            # Start collection run
            run_id = self._start_collection_run(property)

            # Get tracked keywords
            keywords = self._get_tracked_keywords(property)

            if not keywords:
                logger.warning(f"No keywords found for property {property}")
                self._complete_collection_run(run_id, 'completed', stats)
                return stats

            logger.info(f"Collecting trends for {len(keywords)} keywords from property {property}")

            # Collect data for each keyword
            for keyword in keywords:
                try:
                    # Get interest over time (last 90 days)
                    interest_data = self.client.get_interest_over_time(
                        [keyword],
                        timeframe='today 3-m'
                    )

                    if not interest_data.empty:
                        rows_stored = self._store_interest_data(property, keyword, interest_data)
                        if rows_stored > 0:
                            stats['keywords_collected'] += 1
                            logger.info(f"Stored {rows_stored} data points for '{keyword}'")

                    # Get related queries
                    related = self.client.get_related_queries(keyword)
                    if related.get('top') is not None or related.get('rising') is not None:
                        queries_stored = self._store_related_queries(property, keyword, related)
                        if queries_stored > 0:
                            stats['related_queries_collected'] += 1
                            logger.info(f"Stored {queries_stored} related queries for '{keyword}'")

                except Exception as e:
                    logger.warning(f"Failed to collect for keyword '{keyword}': {e}")
                    stats['keywords_failed'] += 1

            # Complete collection run
            stats['completed_at'] = datetime.utcnow().isoformat()
            self._complete_collection_run(run_id, 'completed', stats)

            logger.info(f"Trends collection complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Trends collection failed: {e}", exc_info=True)
            stats['error'] = str(e)
            if run_id:
                self._complete_collection_run(run_id, 'failed', stats, error=str(e))
            return stats

    def collect_all_properties(self) -> List[Dict]:
        """
        Collect trends for all configured properties

        Returns:
            List of stats dictionaries, one per property
        """
        try:
            properties = self._get_all_properties()

            if not properties:
                logger.warning("No properties configured for trends collection")
                return []

            logger.info(f"Collecting trends for {len(properties)} properties")

            results = []
            for property_url in properties:
                try:
                    stats = self.collect_for_property(property_url)
                    results.append(stats)
                except Exception as e:
                    logger.error(f"Failed to collect for property {property_url}: {e}")
                    results.append({
                        'property': property_url,
                        'error': str(e),
                        'keywords_collected': 0,
                        'keywords_failed': 0
                    })

            return results

        except Exception as e:
            logger.error(f"Failed to collect all properties: {e}")
            return []

    def _get_all_properties(self) -> List[str]:
        """
        Get all configured properties from database

        Returns:
            List of property URLs
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT property_url
                    FROM gsc.dim_property
                    WHERE property_url IS NOT NULL
                    ORDER BY property_url
                """)
                properties = [row[0] for row in cur.fetchall()]
            conn.close()
            return properties
        except Exception as e:
            logger.error(f"Failed to get properties: {e}")
            return []

    def _get_tracked_keywords(self, property: str) -> List[str]:
        """
        Get top keywords from GSC data

        Returns top N keywords by clicks for the property from recent data.

        Args:
            property: GSC property URL

        Returns:
            List of keyword strings
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor() as cur:
                # Get top keywords from last 30 days of GSC data
                cur.execute("""
                    SELECT
                        query,
                        SUM(clicks) as total_clicks,
                        SUM(impressions) as total_impressions
                    FROM gsc.fact_gsc_daily
                    WHERE property = %s
                        AND date >= CURRENT_DATE - INTERVAL '%s days'
                        AND query IS NOT NULL
                        AND query != ''
                    GROUP BY query
                    HAVING SUM(clicks) >= %s
                    ORDER BY SUM(clicks) DESC
                    LIMIT %s
                """, (property, self.DAYS_LOOKBACK, self.MIN_CLICKS_THRESHOLD, self.MAX_KEYWORDS_PER_PROPERTY))

                keywords = [row[0] for row in cur.fetchall()]
            conn.close()

            logger.info(f"Found {len(keywords)} keywords for property {property}")
            return keywords

        except Exception as e:
            logger.error(f"Failed to get tracked keywords: {e}")
            return []

    def _store_interest_data(self, property: str, keyword: str, data: pd.DataFrame) -> int:
        """
        Store interest over time data in database

        Args:
            property: GSC property URL
            keyword: Keyword text
            data: DataFrame from GoogleTrendsClient.get_interest_over_time()

        Returns:
            Number of rows stored
        """
        if data.empty:
            return 0

        try:
            conn = psycopg2.connect(self.db_dsn)

            # Prepare data for insertion
            rows = []
            for idx, row in data.iterrows():
                # Get the interest score for this keyword
                interest_score = row.get(keyword, None)

                # Skip if no valid score
                if pd.isna(interest_score):
                    continue

                # Determine if this is partial data (current week)
                data_date = idx.date() if hasattr(idx, 'date') else idx
                is_partial = (datetime.now().date() - data_date).days < 7

                rows.append((
                    property,
                    keyword,
                    data_date,
                    int(interest_score),
                    is_partial
                ))

            if not rows:
                conn.close()
                return 0

            # Insert with ON CONFLICT handling
            with conn.cursor() as cur:
                execute_values(cur, """
                    INSERT INTO trends.keyword_interest
                        (property, keyword, date, interest_score, is_partial)
                    VALUES %s
                    ON CONFLICT (property, keyword, date)
                    DO UPDATE SET
                        interest_score = EXCLUDED.interest_score,
                        is_partial = EXCLUDED.is_partial,
                        collected_at = CURRENT_TIMESTAMP
                """, rows)

            conn.commit()
            conn.close()

            return len(rows)

        except Exception as e:
            logger.error(f"Failed to store interest data: {e}")
            return 0

    def _store_related_queries(self, property: str, keyword: str, related: Dict) -> int:
        """
        Store related queries in database

        Args:
            property: GSC property URL
            keyword: Keyword text
            related: Dict with 'top' and 'rising' DataFrames

        Returns:
            Number of queries stored
        """
        try:
            conn = psycopg2.connect(self.db_dsn)

            rows = []

            # Process top queries
            top_df = related.get('top')
            if top_df is not None and not top_df.empty:
                for _, row in top_df.iterrows():
                    query = row.get('query', None)
                    value = row.get('value', None)

                    if query and pd.notna(query):
                        rows.append((
                            property,
                            keyword,
                            str(query),
                            'top',
                            int(value) if pd.notna(value) else None
                        ))

            # Process rising queries
            rising_df = related.get('rising')
            if rising_df is not None and not rising_df.empty:
                for _, row in rising_df.iterrows():
                    query = row.get('query', None)
                    value = row.get('value', None)

                    if query and pd.notna(query):
                        rows.append((
                            property,
                            keyword,
                            str(query),
                            'rising',
                            int(value) if pd.notna(value) and str(value) != 'Breakout' else None
                        ))

            if not rows:
                conn.close()
                return 0

            # Insert related queries
            with conn.cursor() as cur:
                execute_values(cur, """
                    INSERT INTO trends.related_queries
                        (property, keyword, related_query, query_type, score)
                    VALUES %s
                    ON CONFLICT (property, keyword, related_query, query_type, collected_at)
                    DO NOTHING
                """, rows)

            conn.commit()
            conn.close()

            return len(rows)

        except Exception as e:
            logger.error(f"Failed to store related queries: {e}")
            return 0

    def _start_collection_run(self, property: str) -> Optional[int]:
        """
        Start a collection run and return its ID

        Args:
            property: GSC property URL

        Returns:
            Collection run ID
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trends.collection_runs
                        (property, status)
                    VALUES (%s, 'running')
                    RETURNING id
                """, (property,))
                run_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            return run_id
        except Exception as e:
            logger.error(f"Failed to start collection run: {e}")
            return None

    def _complete_collection_run(
        self,
        run_id: int,
        status: str,
        stats: Dict,
        error: str = None
    ) -> None:
        """
        Mark collection run as complete

        Args:
            run_id: Collection run ID
            status: Final status ('completed' or 'failed')
            stats: Statistics dictionary
            error: Optional error message
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE trends.collection_runs
                    SET
                        keywords_collected = %s,
                        keywords_failed = %s,
                        related_queries_collected = %s,
                        completed_at = CURRENT_TIMESTAMP,
                        status = %s,
                        error_message = %s
                    WHERE id = %s
                """, (
                    stats.get('keywords_collected', 0),
                    stats.get('keywords_failed', 0),
                    stats.get('related_queries_collected', 0),
                    status,
                    error,
                    run_id
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to complete collection run: {e}")

    def get_keyword_trend(self, property: str, keyword: str, days: int = 30) -> List[Dict]:
        """
        Get stored trend data for a keyword

        Args:
            property: GSC property URL
            keyword: Keyword text
            days: Number of days to retrieve (default 30)

        Returns:
            List of dictionaries with date, interest_score, is_partial
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        date,
                        interest_score,
                        is_partial,
                        collected_at
                    FROM trends.keyword_interest
                    WHERE property = %s
                        AND keyword = %s
                        AND date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY date DESC
                """, (property, keyword, days))

                results = cur.fetchall()
            conn.close()

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get keyword trend: {e}")
            return []

    def get_collection_health(self, property: str = None) -> List[Dict]:
        """
        Get collection health statistics

        Args:
            property: Optional property to filter by

        Returns:
            List of health statistics
        """
        try:
            conn = psycopg2.connect(self.db_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if property:
                    cur.execute("""
                        SELECT * FROM trends.vw_collection_health
                        WHERE property = %s
                    """, (property,))
                else:
                    cur.execute("SELECT * FROM trends.vw_collection_health")

                results = cur.fetchall()
            conn.close()

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get collection health: {e}")
            return []


def main():
    """CLI entry point for manual execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Google Trends Accumulator')
    parser.add_argument('--property', type=str, help='Specific property to collect')
    parser.add_argument('--all', action='store_true', help='Collect for all properties')
    parser.add_argument('--health', action='store_true', help='Show collection health')
    args = parser.parse_args()

    accumulator = TrendsAccumulator()

    if args.health:
        health = accumulator.get_collection_health()
        print("Collection Health:")
        for h in health:
            print(f"  {h['property']}: {h['total_keywords_collected']} keywords, "
                  f"{h['total_runs']} runs, avg {h['avg_duration_seconds']:.1f}s")
    elif args.all:
        results = accumulator.collect_all_properties()
        print(f"Collected trends for {len(results)} properties")
        for result in results:
            print(f"  {result['property']}: {result['keywords_collected']} keywords")
    elif args.property:
        stats = accumulator.collect_for_property(args.property)
        print(f"Collection complete: {stats}")
    else:
        print("Use --property, --all, or --health")


if __name__ == '__main__':
    main()
