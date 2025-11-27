"""
Seed test data for dashboard testing
Loads sample data from samples/ directory and generates synthetic data

Usage:
    # As a script
    python -m tests.dashboards.fixtures.seed_dashboard_data

    # With custom DSN
    WAREHOUSE_DSN=postgresql://user:pass@host:5432/db python -m tests.dashboards.fixtures.seed_dashboard_data
"""

import asyncio
import csv
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# Try to import asyncpg
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None


# Path to samples directory
SAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "samples"


async def seed_gsc_data(conn) -> int:
    """
    Seed GSC sample data for dashboard tests.

    Args:
        conn: asyncpg connection

    Returns:
        Number of rows inserted
    """
    csv_path = SAMPLES_DIR / "gsc_sample_data.csv"

    if not csv_path.exists():
        print(f"Warning: {csv_path} not found, generating synthetic GSC data")
        return await seed_synthetic_gsc_data(conn)

    rows_inserted = 0
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                await conn.execute("""
                    INSERT INTO gsc.fact_gsc_daily (
                        property, url, query, date, clicks, impressions, ctr, position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (property, url, query, date) DO UPDATE SET
                        clicks = EXCLUDED.clicks,
                        impressions = EXCLUDED.impressions,
                        ctr = EXCLUDED.ctr,
                        position = EXCLUDED.position
                """,
                    row.get("property", "https://test-domain.com"),
                    row.get("url", row.get("page_path", "/")),
                    row.get("query", ""),
                    datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    int(row["clicks"]),
                    int(row["impressions"]),
                    float(row["ctr"]),
                    float(row["position"])
                )
                rows_inserted += 1
            except Exception as e:
                print(f"Warning: Failed to insert GSC row: {e}")

    return rows_inserted


async def seed_synthetic_gsc_data(conn) -> int:
    """Generate synthetic GSC data."""
    property_url = "https://test-domain.com"
    pages = ["/", "/product/shoes", "/blog/seo-guide", "/about", "/contact"]
    queries = ["running shoes", "seo guide", "test query", "brand name"]

    rows_inserted = 0
    for page in pages:
        for query in queries:
            for i in range(30):
                check_date = datetime.now().date() - timedelta(days=i)
                clicks = 50 + (hash(f"{page}{query}{i}") % 200)
                impressions = clicks * 10 + (hash(f"{page}{i}") % 1000)

                try:
                    await conn.execute("""
                        INSERT INTO gsc.fact_gsc_daily (
                            property, url, query, date, clicks, impressions, ctr, position
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (property, url, query, date) DO NOTHING
                    """,
                        property_url,
                        f"{property_url}{page}",
                        query,
                        check_date,
                        clicks,
                        impressions,
                        round(clicks / impressions, 4),
                        5.0 + (hash(f"{page}{i}pos") % 15)
                    )
                    rows_inserted += 1
                except Exception as e:
                    print(f"Warning: Failed to insert synthetic GSC row: {e}")

    return rows_inserted


async def seed_ga4_data(conn) -> int:
    """
    Seed GA4 sample data for dashboard tests.

    Args:
        conn: asyncpg connection

    Returns:
        Number of rows inserted
    """
    csv_path = SAMPLES_DIR / "ga4_sample_data.csv"

    if not csv_path.exists():
        print(f"Warning: {csv_path} not found, generating synthetic GA4 data")
        return await seed_synthetic_ga4_data(conn)

    rows_inserted = 0
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                await conn.execute("""
                    INSERT INTO gsc.fact_ga4_daily (
                        property, page_path, date, sessions, engaged_sessions,
                        conversions, engagement_rate, bounce_rate, conversion_rate
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (property, page_path, date) DO UPDATE SET
                        sessions = EXCLUDED.sessions,
                        conversions = EXCLUDED.conversions
                """,
                    row.get("property", "https://test-domain.com"),
                    row["page_path"],
                    datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    int(row["sessions"]),
                    int(row.get("engaged_sessions", int(row["sessions"]) * 0.6)),
                    int(row.get("conversions", 0)),
                    float(row.get("engagement_rate", 0.5)),
                    float(row.get("bounce_rate", 0.3)),
                    float(row.get("conversion_rate", 0.02))
                )
                rows_inserted += 1
            except Exception as e:
                print(f"Warning: Failed to insert GA4 row: {e}")

    return rows_inserted


async def seed_synthetic_ga4_data(conn) -> int:
    """Generate synthetic GA4 data."""
    property_url = "https://test-domain.com"
    pages = ["/", "/product/shoes", "/blog/seo-guide", "/about", "/contact", "/checkout"]

    rows_inserted = 0
    for page in pages:
        for i in range(30):
            check_date = datetime.now().date() - timedelta(days=i)
            sessions = 100 + (hash(f"{page}{i}") % 500)
            engaged = int(sessions * 0.6)
            conversions = int(sessions * 0.02)

            try:
                await conn.execute("""
                    INSERT INTO gsc.fact_ga4_daily (
                        property, page_path, date, sessions, engaged_sessions,
                        conversions, engagement_rate, bounce_rate, conversion_rate
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (property, page_path, date) DO NOTHING
                """,
                    property_url,
                    page,
                    check_date,
                    sessions,
                    engaged,
                    conversions,
                    round(0.5 + (hash(f"{page}{i}eng") % 30) / 100, 4),
                    round(0.3 + (hash(f"{page}{i}bnc") % 20) / 100, 4),
                    round(conversions / sessions if sessions > 0 else 0, 4)
                )
                rows_inserted += 1
            except Exception as e:
                print(f"Warning: Failed to insert synthetic GA4 row: {e}")

    return rows_inserted


async def seed_cwv_data(conn) -> int:
    """
    Seed CWV sample data for dashboard tests.

    Args:
        conn: asyncpg connection

    Returns:
        Number of rows inserted
    """
    property_url = "https://test-domain.com"
    pages = ["/", "/product/shoes", "/blog/seo-guide", "/about", "/contact"]
    strategies = ["mobile", "desktop"]

    rows_inserted = 0
    for page in pages:
        for i in range(30):
            check_date = datetime.now().date() - timedelta(days=i)
            for strategy in strategies:
                perf_score = 70 + (hash(f"{page}{i}{strategy}") % 30)

                try:
                    await conn.execute("""
                        INSERT INTO performance.core_web_vitals (
                            property, page_path, strategy, check_date,
                            performance_score, lcp, fid, cls, ttfb, fcp
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (property, page_path, strategy, check_date) DO NOTHING
                    """,
                        property_url,
                        page,
                        strategy,
                        check_date,
                        perf_score,
                        1800 + (hash(f"{page}{i}lcp") % 1500),  # LCP: 1800-3300ms
                        30 + (hash(f"{page}{i}fid") % 150),     # FID: 30-180ms
                        round(0.05 + (hash(f"{page}{i}cls") % 20) / 100, 3),  # CLS: 0.05-0.25
                        200 + (hash(f"{page}{i}ttfb") % 400),   # TTFB: 200-600ms
                        800 + (hash(f"{page}{i}fcp") % 800)     # FCP: 800-1600ms
                    )
                    rows_inserted += 1
                except Exception as e:
                    print(f"Warning: Failed to insert CWV row: {e}")

    return rows_inserted


async def seed_serp_data(conn) -> int:
    """
    Seed SERP tracking data for dashboard tests.

    Args:
        conn: asyncpg connection

    Returns:
        Number of rows inserted
    """
    property_url = "https://test-domain.com"
    queries = [
        ("best running shoes", "/product/shoes"),
        ("seo guide 2024", "/blog/seo-guide"),
        ("marathon training tips", "/blog/marathon"),
        ("shoe size guide", "/product/size-guide"),
        ("running gear reviews", "/blog/reviews")
    ]

    rows_inserted = 0
    for query_text, target_page in queries:
        try:
            # Insert query
            query_id = await conn.fetchval("""
                INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
                VALUES ($1, $2, $3, true)
                ON CONFLICT (property, query_text) DO UPDATE SET is_active = true
                RETURNING query_id
            """, query_text, property_url, target_page)

            # Insert position history
            for i in range(30):
                check_date = datetime.now().date() - timedelta(days=i)
                position = 5 + (hash(f"{query_text}{i}") % 15)

                await conn.execute("""
                    INSERT INTO serp.position_history (
                        query_id, property, position, url, domain, check_date
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                """,
                    query_id,
                    property_url,
                    position,
                    f"{property_url}{target_page}",
                    "test-domain.com",
                    check_date
                )
                rows_inserted += 1

        except Exception as e:
            print(f"Warning: Failed to insert SERP data for '{query_text}': {e}")

    return rows_inserted


async def seed_insights_data(conn) -> int:
    """
    Seed insights data for dashboard tests.

    Args:
        conn: asyncpg connection

    Returns:
        Number of rows inserted
    """
    insights = [
        {
            "category": "risk",
            "severity": "high",
            "title": "Traffic Drop Detected",
            "description": "Significant traffic decrease on /product/shoes",
            "metric_affected": "clicks",
            "percent_change": -25.0
        },
        {
            "category": "opportunity",
            "severity": "medium",
            "title": "Ranking Improvement Potential",
            "description": "Page /blog/seo-guide could rank higher with optimization",
            "metric_affected": "position",
            "percent_change": None
        },
        {
            "category": "observation",
            "severity": "low",
            "title": "New Keywords Detected",
            "description": "5 new keywords driving traffic",
            "metric_affected": "impressions",
            "percent_change": 15.0
        }
    ]

    rows_inserted = 0
    for insight in insights:
        try:
            await conn.execute("""
                INSERT INTO gsc.insights (
                    property, category, severity, title, description,
                    metric_affected, percent_change, created_at, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), 'active')
                ON CONFLICT DO NOTHING
            """,
                "https://test-domain.com",
                insight["category"],
                insight["severity"],
                insight["title"],
                insight["description"],
                insight["metric_affected"],
                insight["percent_change"]
            )
            rows_inserted += 1
        except Exception as e:
            print(f"Warning: Failed to insert insight: {e}")

    return rows_inserted


async def seed_all_dashboard_data(dsn: str):
    """
    Seed all dashboard test data.

    Args:
        dsn: PostgreSQL connection string
    """
    if not HAS_ASYNCPG:
        print("Error: asyncpg is not installed. Install with: pip install asyncpg")
        return

    print(f"Connecting to database...")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        return

    try:
        print("Seeding GSC data...")
        gsc_rows = await seed_gsc_data(conn)
        print(f"  Inserted {gsc_rows} GSC rows")

        print("Seeding GA4 data...")
        ga4_rows = await seed_ga4_data(conn)
        print(f"  Inserted {ga4_rows} GA4 rows")

        print("Seeding CWV data...")
        cwv_rows = await seed_cwv_data(conn)
        print(f"  Inserted {cwv_rows} CWV rows")

        print("Seeding SERP data...")
        serp_rows = await seed_serp_data(conn)
        print(f"  Inserted {serp_rows} SERP rows")

        print("Seeding Insights data...")
        insights_rows = await seed_insights_data(conn)
        print(f"  Inserted {insights_rows} insight rows")

        total = gsc_rows + ga4_rows + cwv_rows + serp_rows + insights_rows
        print(f"\nDashboard test data seeded successfully! Total rows: {total}")

    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        await conn.close()


async def clear_test_data(dsn: str):
    """
    Clear test data from database.

    Args:
        dsn: PostgreSQL connection string
    """
    if not HAS_ASYNCPG:
        print("Error: asyncpg is not installed")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        return

    try:
        property_url = "https://test-domain.com"

        print("Clearing test data...")
        await conn.execute(
            "DELETE FROM gsc.fact_gsc_daily WHERE property = $1", property_url
        )
        await conn.execute(
            "DELETE FROM gsc.fact_ga4_daily WHERE property = $1", property_url
        )
        await conn.execute(
            "DELETE FROM performance.core_web_vitals WHERE property = $1", property_url
        )
        await conn.execute(
            "DELETE FROM serp.position_history WHERE property = $1", property_url
        )
        await conn.execute(
            "DELETE FROM serp.queries WHERE property = $1", property_url
        )
        await conn.execute(
            "DELETE FROM gsc.insights WHERE property = $1", property_url
        )

        print("Test data cleared successfully!")

    except Exception as e:
        print(f"Error clearing data: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = os.getenv(
        "WAREHOUSE_DSN",
        "postgresql://gsc_user:gsc_password@localhost:5432/gsc_db"
    )

    if len(sys.argv) > 1:
        if sys.argv[1] == "--clear":
            asyncio.run(clear_test_data(dsn))
        elif sys.argv[1] == "--dsn" and len(sys.argv) > 2:
            asyncio.run(seed_all_dashboard_data(sys.argv[2]))
        else:
            print("Usage:")
            print("  python -m tests.dashboards.fixtures.seed_dashboard_data")
            print("  python -m tests.dashboards.fixtures.seed_dashboard_data --clear")
            print("  python -m tests.dashboards.fixtures.seed_dashboard_data --dsn <connection_string>")
    else:
        asyncio.run(seed_all_dashboard_data(dsn))
