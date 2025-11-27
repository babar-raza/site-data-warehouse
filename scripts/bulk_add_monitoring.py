#!/usr/bin/env python3
"""
Bulk Add Monitoring Pages from GSC Data
Automatically finds high-traffic pages and adds them to SERP and CWV monitoring
"""
import os
import sys
import psycopg2
import psycopg2.extras
from typing import List, Dict, Tuple
from datetime import date, timedelta

# Subdomain configuration
SUBDOMAINS_WITH_FAMILIES = [
    'products.aspose.net',
    'docs.aspose.net',
    'reference.aspose.net',
    'blog.aspose.net',
    'kb.aspose.net'
]

SUBDOMAINS_WITHOUT_FAMILIES = [
    'about.aspose.net',
    'websites.aspose.net',
    'metrics.aspose.net'
]

# Product families to monitor (14 total - slides excluded as it doesn't exist)
PRODUCT_FAMILIES = [
    '/pdf/', '/words/', '/cells/', '/email/',
    '/imaging/', '/barcode/', '/tasks/', '/ocr/',
    '/cad/', '/html/', '/zip/', '/page/',
    '/psd/', '/svg/', '/tex/'
]

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        database=os.environ.get('DB_NAME', 'gsc_db'),
        user=os.environ.get('DB_USER', 'gsc_user'),
        password=os.environ.get('DB_PASSWORD', 'gsc_pass_secure_2024')
    )

def find_top_pages_with_families(conn, min_impressions: int = 100, limit: int = 100) -> List[Dict]:
    """Find top-performing pages from subdomains that have product families"""

    # Build property URLs for query
    property_urls = [f'sc-domain:{subdomain}' for subdomain in SUBDOMAINS_WITH_FAMILIES]
    property_placeholders = ','.join(['%s'] * len(property_urls))

    # Build family pattern for LIKE clause
    family_conditions = ' OR '.join(['url LIKE %s'] * len(PRODUCT_FAMILIES))

    query = f"""
        WITH recent_data AS (
            SELECT
                property,
                url as page,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                AVG(position) as avg_position,
                AVG(ctr) as avg_ctr
            FROM gsc.fact_gsc_daily
            WHERE date >= %s
              AND property IN ({property_placeholders})
              AND ({family_conditions})
            GROUP BY property, url
            HAVING SUM(impressions) >= %s
        )
        SELECT
            property,
            page,
            total_impressions,
            total_clicks,
            avg_position,
            avg_ctr
        FROM recent_data
        ORDER BY total_clicks DESC, total_impressions DESC
        LIMIT %s
    """

    # Build parameters
    params = [date.today() - timedelta(days=30)]  # Last 30 days
    params.extend(property_urls)  # Property list
    params.extend([f'%{family}%' for family in PRODUCT_FAMILIES])  # Family patterns
    params.append(min_impressions)  # Min impressions threshold
    params.append(limit)  # Result limit

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

def find_top_pages_without_families(conn, min_impressions: int = 100, limit: int = 50) -> List[Dict]:
    """Find top-performing pages from subdomains without product families"""

    # Build property URLs for query
    property_urls = [f'sc-domain:{subdomain}' for subdomain in SUBDOMAINS_WITHOUT_FAMILIES]
    property_placeholders = ','.join(['%s'] * len(property_urls))

    query = f"""
        WITH recent_data AS (
            SELECT
                property,
                url as page,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                AVG(position) as avg_position,
                AVG(ctr) as avg_ctr
            FROM gsc.fact_gsc_daily
            WHERE date >= %s
              AND property IN ({property_placeholders})
            GROUP BY property, url
            HAVING SUM(impressions) >= %s
        )
        SELECT
            property,
            page,
            total_impressions,
            total_clicks,
            avg_position,
            avg_ctr
        FROM recent_data
        ORDER BY total_clicks DESC, total_impressions DESC
        LIMIT %s
    """

    params = [date.today() - timedelta(days=30)]
    params.extend(property_urls)
    params.append(min_impressions)
    params.append(limit)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

def extract_page_info(page_url: str) -> Tuple[str, str]:
    """Extract property and path from full page URL"""
    # Page format: https://products.aspose.net/pdf/net/
    # Extract: property=https://products.aspose.net/, path=/pdf/net/

    if '://' not in page_url:
        return None, None

    parts = page_url.split('://', 1)
    protocol = parts[0]
    rest = parts[1]

    # Find first slash after domain
    slash_idx = rest.find('/')
    if slash_idx == -1:
        # No path, entire URL is the property
        return f"{protocol}://{rest}/", '/'

    domain = rest[:slash_idx]
    path = rest[slash_idx:]

    return f"{protocol}://{domain}/", path

def get_top_keywords_for_page(conn, property: str, page: str, limit: int = 5) -> List[str]:
    """Get top keywords driving traffic to a page"""

    query = """
        SELECT
            query,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions
        FROM gsc.fact_gsc_daily
        WHERE date >= %s
          AND property = %s
          AND url = %s
          AND query != ''
        GROUP BY query
        ORDER BY total_clicks DESC, total_impressions DESC
        LIMIT %s
    """

    with conn.cursor() as cur:
        cur.execute(query, (date.today() - timedelta(days=30), property, page, limit))
        return [row[0] for row in cur.fetchall()]

def add_serp_query(conn, query_text: str, property: str, target_path: str) -> bool:
    """Add a SERP query (returns True if added, False if already exists)"""

    # Check if already exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT query_id FROM serp.queries
            WHERE query_text = %s AND property = %s AND target_page_path = %s
        """, (query_text, property, target_path))

        if cur.fetchone():
            return False

    # Insert new query
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO serp.queries
                (query_text, property, target_page_path, location, device, is_active)
                VALUES (%s, %s, %s, 'United States', 'desktop', true)
            """, (query_text, property, target_path))
            conn.commit()
            return True
    except Exception as e:
        print(f"  ✗ Error adding SERP query: {e}")
        conn.rollback()
        return False

def add_cwv_page(conn, property: str, page_path: str, page_name: str, check_mobile: bool = True, check_desktop: bool = True) -> bool:
    """Add a CWV monitored page (returns True if added, False if already exists)"""

    # Check if already exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT page_id FROM performance.monitored_pages
            WHERE property = %s AND page_path = %s
        """, (property, page_path))

        if cur.fetchone():
            return False

    # Insert new page
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO performance.monitored_pages
                (property, page_path, page_name, check_mobile, check_desktop, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
            """, (property, page_path, page_name, check_mobile, check_desktop))
            conn.commit()
            return True
    except Exception as e:
        print(f"  ✗ Error adding CWV page: {e}")
        conn.rollback()
        return False

def main():
    print("=== Bulk Add Monitoring Pages ===")
    print(f"Date: {date.today()}\n")

    conn = get_db_connection()

    try:
        # Statistics
        serp_added = 0
        cwv_added = 0
        serp_skipped = 0
        cwv_skipped = 0

        # 1. Process subdomains WITH product families
        print("=" * 60)
        print("SUBDOMAINS WITH PRODUCT FAMILIES")
        print("=" * 60)
        print(f"Searching: {', '.join(SUBDOMAINS_WITH_FAMILIES)}\n")

        pages_with_families = find_top_pages_with_families(conn, min_impressions=100, limit=100)
        print(f"Found {len(pages_with_families)} high-traffic pages with product families\n")

        for page_data in pages_with_families:
            page_url = page_data['page']
            property_gsc = page_data['property']
            impressions = page_data['total_impressions']
            clicks = page_data['total_clicks']
            avg_pos = page_data['avg_position']

            # Extract property URL and path
            property_url, page_path = extract_page_info(page_url)

            if not property_url or not page_path:
                continue

            print(f"\n📄 {page_url}")
            print(f"   Clicks: {clicks:,} | Impressions: {impressions:,} | Avg Pos: {avg_pos:.1f}")

            # Add to CWV monitoring
            page_name = page_path.strip('/').replace('/', ' - ').title()
            cwv_result = add_cwv_page(conn, property_url, page_path, page_name, check_mobile=True, check_desktop=False)

            if cwv_result:
                print(f"   ✓ Added to CWV monitoring")
                cwv_added += 1
            else:
                print(f"   ⊗ Already in CWV monitoring")
                cwv_skipped += 1

            # Get top keywords for this page
            keywords = get_top_keywords_for_page(conn, property_gsc, page_url, limit=3)

            if keywords:
                print(f"   Keywords: {', '.join(keywords[:3])}")

                # Add top keyword to SERP tracking
                top_keyword = keywords[0]
                serp_result = add_serp_query(conn, top_keyword, property_url, page_path)

                if serp_result:
                    print(f"   ✓ Added to SERP tracking: '{top_keyword}'")
                    serp_added += 1
                else:
                    print(f"   ⊗ Already tracking: '{top_keyword}'")
                    serp_skipped += 1

        # 2. Process subdomains WITHOUT product families
        print("\n" + "=" * 60)
        print("SUBDOMAINS WITHOUT PRODUCT FAMILIES")
        print("=" * 60)
        print(f"Searching: {', '.join(SUBDOMAINS_WITHOUT_FAMILIES)}\n")

        pages_without_families = find_top_pages_without_families(conn, min_impressions=100, limit=50)
        print(f"Found {len(pages_without_families)} high-traffic pages\n")

        for page_data in pages_without_families:
            page_url = page_data['page']
            property_gsc = page_data['property']
            impressions = page_data['total_impressions']
            clicks = page_data['total_clicks']
            avg_pos = page_data['avg_position']

            # Extract property URL and path
            property_url, page_path = extract_page_info(page_url)

            if not property_url or not page_path:
                continue

            print(f"\n📄 {page_url}")
            print(f"   Clicks: {clicks:,} | Impressions: {impressions:,} | Avg Pos: {avg_pos:.1f}")

            # Add to CWV monitoring
            page_name = page_path.strip('/').replace('/', ' - ').title()
            cwv_result = add_cwv_page(conn, property_url, page_path, page_name, check_mobile=True, check_desktop=False)

            if cwv_result:
                print(f"   ✓ Added to CWV monitoring")
                cwv_added += 1
            else:
                print(f"   ⊗ Already in CWV monitoring")
                cwv_skipped += 1

            # Get top keywords for this page
            keywords = get_top_keywords_for_page(conn, property_gsc, page_url, limit=3)

            if keywords:
                print(f"   Keywords: {', '.join(keywords[:3])}")

                # Add top keyword to SERP tracking
                top_keyword = keywords[0]
                serp_result = add_serp_query(conn, top_keyword, property_url, page_path)

                if serp_result:
                    print(f"   ✓ Added to SERP tracking: '{top_keyword}'")
                    serp_added += 1
                else:
                    print(f"   ⊗ Already tracking: '{top_keyword}'")
                    serp_skipped += 1

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"SERP Queries Added:    {serp_added}")
        print(f"SERP Queries Skipped:  {serp_skipped} (already exist)")
        print(f"CWV Pages Added:       {cwv_added}")
        print(f"CWV Pages Skipped:     {cwv_skipped} (already exist)")
        print(f"\n✓ Bulk add complete!")

    finally:
        conn.close()

if __name__ == '__main__':
    main()
