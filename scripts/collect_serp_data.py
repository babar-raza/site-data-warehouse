#!/usr/bin/env python3
"""
SERP Position Tracking - Multi-Provider Support
Collects search position data for tracked keywords using external APIs.

Supported providers:
- SerpStack (default)
- ValueSERP
- SerpAPI

Version: 2.0 - Added data_source tracking for dual-source support
"""
import os
import sys
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
from typing import List, Dict, Optional
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection using WAREHOUSE_DSN or individual params"""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if dsn:
        return psycopg2.connect(dsn)

    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        database=os.environ.get('DB_NAME', 'gsc_db'),
        user=os.environ.get('DB_USER', 'gsc_user'),
        password=os.environ.get('DB_PASSWORD', 'gsc_pass_secure_2024')
    )


def get_api_provider() -> str:
    """Determine which SERP API provider to use"""
    # Check for configured provider
    provider = os.environ.get('SERP_API_PROVIDER', 'serpstack').lower()

    # Validate API key exists for the provider
    if provider == 'serpstack' and os.environ.get('SERPSTACK_API_KEY'):
        return 'serpstack'
    elif provider == 'valueserp' and os.environ.get('VALUESERP_API_KEY'):
        return 'valueserp'
    elif provider == 'serpapi' and os.environ.get('SERPAPI_KEY'):
        return 'serpapi'

    # Fallback: check which API key is available
    if os.environ.get('SERPSTACK_API_KEY'):
        return 'serpstack'
    elif os.environ.get('VALUESERP_API_KEY'):
        return 'valueserp'
    elif os.environ.get('SERPAPI_KEY'):
        return 'serpapi'

    return None


def get_tracked_queries(data_source: str = None) -> List[Dict]:
    """
    Get active queries to track

    Args:
        data_source: Filter by data source (e.g., 'serpstack', 'manual')
                    If None, returns all non-GSC queries
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if data_source column exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'serp'
                    AND table_name = 'queries'
                    AND column_name = 'data_source'
                )
            """)
            has_data_source = cur.fetchone()['exists']

            if has_data_source and data_source:
                cur.execute("""
                    SELECT query_id, query_text, property, target_page_path,
                           location, device, data_source
                    FROM serp.queries
                    WHERE is_active = true
                    AND data_source = %s
                """, (data_source,))
            elif has_data_source:
                # Get queries that are NOT from GSC (for API collection)
                cur.execute("""
                    SELECT query_id, query_text, property, target_page_path,
                           location, device, data_source
                    FROM serp.queries
                    WHERE is_active = true
                    AND (data_source IS NULL OR data_source != 'gsc')
                """)
            else:
                cur.execute("""
                    SELECT query_id, query_text, property, target_page_path,
                           location, device
                    FROM serp.queries
                    WHERE is_active = true
                """)

            return cur.fetchall()
    finally:
        conn.close()


def search_serpstack(query: str, location: str = 'United States',
                    device: str = 'desktop') -> Dict:
    """Query SerpStack API"""
    api_key = os.environ.get('SERPSTACK_API_KEY')
    if not api_key:
        raise ValueError("SERPSTACK_API_KEY not set")

    url = "http://api.serpstack.com/search"
    params = {
        'access_key': api_key,
        'query': query,
        'location': location,
        'device': device,
        'num': 100
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_valueserp(query: str, location: str = 'United States',
                    device: str = 'desktop') -> Dict:
    """Query ValueSERP API"""
    api_key = os.environ.get('VALUESERP_API_KEY')
    if not api_key:
        raise ValueError("VALUESERP_API_KEY not set")

    url = "https://api.valueserp.com/search"
    params = {
        'api_key': api_key,
        'q': query,
        'location': location,
        'device': device,
        'num': 100
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_serpapi(query: str, location: str = 'United States',
                  device: str = 'desktop') -> Dict:
    """Query SerpAPI"""
    api_key = os.environ.get('SERPAPI_KEY')
    if not api_key:
        raise ValueError("SERPAPI_KEY not set")

    url = "https://serpapi.com/search"
    params = {
        'api_key': api_key,
        'q': query,
        'location': location,
        'device': device,
        'num': 100,
        'engine': 'google'
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_serp(query: str, location: str = 'United States',
               device: str = 'desktop', provider: str = 'serpstack') -> Dict:
    """
    Unified SERP search function

    Args:
        query: Search query
        location: Search location
        device: Device type (desktop/mobile)
        provider: API provider to use

    Returns:
        Normalized search results
    """
    if provider == 'serpstack':
        return search_serpstack(query, location, device)
    elif provider == 'valueserp':
        return search_valueserp(query, location, device)
    elif provider == 'serpapi':
        return search_serpapi(query, location, device)
    else:
        raise ValueError(f"Unknown SERP provider: {provider}")


def normalize_results(results: Dict, provider: str) -> List[Dict]:
    """
    Normalize results from different providers to common format

    Returns list of: {position, url, domain, title, snippet}
    """
    normalized = []

    if provider == 'serpstack':
        for item in results.get('organic_results', []):
            normalized.append({
                'position': item.get('position'),
                'url': item.get('url', ''),
                'domain': item.get('domain', ''),
                'title': item.get('title', ''),
                'snippet': item.get('snippet', '')
            })
    elif provider == 'valueserp':
        for item in results.get('organic_results', []):
            normalized.append({
                'position': item.get('position'),
                'url': item.get('link', ''),
                'domain': item.get('domain', ''),
                'title': item.get('title', ''),
                'snippet': item.get('snippet', '')
            })
    elif provider == 'serpapi':
        for item in results.get('organic_results', []):
            normalized.append({
                'position': item.get('position'),
                'url': item.get('link', ''),
                'domain': item.get('displayed_link', '').split('/')[0] if item.get('displayed_link') else '',
                'title': item.get('title', ''),
                'snippet': item.get('snippet', '')
            })

    return normalized


def find_our_position(results: List[Dict], property_url: str,
                     target_path: str = None) -> Dict:
    """
    Find our property's position in search results

    Returns:
        {position, url, title, snippet} or None if not found
    """
    # Normalize property URL for comparison
    property_domain = property_url.replace('https://', '').replace('http://', '').rstrip('/')

    for result in results:
        result_domain = result.get('domain', '').replace('www.', '')
        result_url = result.get('url', '')

        # Check if domain matches
        if property_domain.replace('www.', '') in result_domain:
            # If target_path specified, check URL contains it
            if target_path:
                if target_path in result_url:
                    return result
            else:
                return result

    return None


def save_position_data(query_id: str, property_url: str, target_path: str,
                      results: Dict, provider: str):
    """Save SERP positions to database with data_source tracking"""
    conn = get_db_connection()
    try:
        # Normalize results
        normalized = normalize_results(results, provider)
        check_date = date.today()
        check_timestamp = datetime.now()

        # Find our position
        our_result = find_our_position(normalized, property_url, target_path)
        our_position = our_result['position'] if our_result else None
        our_url = our_result['url'] if our_result else None

        # Get top 10 competitors
        competitors = [
            {
                'position': r['position'],
                'domain': r['domain'],
                'url': r['url'],
                'title': r['title']
            }
            for r in normalized[:10]
        ]

        # Construct full target URL
        target_url = property_url.rstrip('/') + (target_path if target_path else '')

        # Insert position record
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO serp.position_history
                (query_id, check_date, check_timestamp, position, url, domain,
                 title, description, competitors, api_source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (query_id, check_date, check_timestamp) DO UPDATE SET
                    position = EXCLUDED.position,
                    url = EXCLUDED.url,
                    domain = EXCLUDED.domain,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    competitors = EXCLUDED.competitors,
                    api_source = EXCLUDED.api_source
            """, (
                query_id,
                check_date,
                check_timestamp,
                our_position,
                our_url or target_url,
                our_result['domain'] if our_result else None,
                our_result['title'] if our_result else None,
                our_result['snippet'] if our_result else None,
                json.dumps(competitors) if competitors else None,
                provider
            ))

            # Update the query's data_source if needed
            cur.execute("""
                UPDATE serp.queries
                SET data_source = COALESCE(data_source, %s),
                    updated_at = NOW()
                WHERE query_id = %s
                AND (data_source IS NULL OR data_source = 'manual')
            """, (provider, query_id))

            conn.commit()

        if our_position:
            logger.info(f"Tracked: {query_id} - Position: {our_position}")
        else:
            logger.info(f"Tracked: {query_id} - Position: Not in top 100")

    except Exception as e:
        logger.error(f"Error saving position data: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def collect_serp_data(provider: str = None, limit: int = None) -> Dict:
    """
    Main collection function

    Args:
        provider: SERP API provider to use (auto-detect if None)
        limit: Maximum number of queries to process

    Returns:
        Collection statistics
    """
    # Determine provider
    if not provider:
        provider = get_api_provider()

    if not provider:
        logger.error("No SERP API provider configured. Set one of: "
                    "SERPSTACK_API_KEY, VALUESERP_API_KEY, SERPAPI_KEY")
        return {
            'success': False,
            'error': 'No API provider configured',
            'queries_processed': 0
        }

    logger.info(f"Using SERP provider: {provider}")

    # Get queries to track (exclude GSC-sourced queries)
    queries = get_tracked_queries()

    if limit:
        queries = queries[:limit]

    logger.info(f"Found {len(queries)} queries to track")

    stats = {
        'success': True,
        'provider': provider,
        'queries_processed': 0,
        'queries_found': 0,
        'queries_not_found': 0,
        'errors': 0
    }

    for query in queries:
        query_id = str(query['query_id'])
        query_text = query['query_text']
        property_url = query['property']
        target_path = query.get('target_page_path', '')
        location = query.get('location', 'United States')
        device = query.get('device', 'desktop')

        logger.info(f"Tracking: {query_text}")

        try:
            # Search SERP
            results = search_serp(query_text, location, device, provider)

            # Save results
            save_position_data(query_id, property_url, target_path, results, provider)

            stats['queries_processed'] += 1

            # Check if we found position
            normalized = normalize_results(results, provider)
            our_result = find_our_position(normalized, property_url, target_path)
            if our_result:
                stats['queries_found'] += 1
            else:
                stats['queries_not_found'] += 1

        except Exception as e:
            logger.error(f"Error tracking {query_text}: {e}")
            stats['errors'] += 1
            continue

    return stats


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='SERP Position Tracking')
    parser.add_argument('--provider', choices=['serpstack', 'valueserp', 'serpapi'],
                       help='SERP API provider to use')
    parser.add_argument('--limit', type=int, help='Maximum queries to process')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making API calls')
    args = parser.parse_args()

    print("=== SERP Position Tracking ===")
    print(f"Date: {date.today()}")
    print()

    if args.dry_run:
        provider = args.provider or get_api_provider()
        print(f"Provider: {provider or 'NOT CONFIGURED'}")
        queries = get_tracked_queries()
        print(f"Queries to track: {len(queries)}")
        for q in queries[:10]:
            print(f"  - {q['query_text']} ({q['property']})")
        if len(queries) > 10:
            print(f"  ... and {len(queries) - 10} more")
        return

    # Run collection
    stats = collect_serp_data(provider=args.provider, limit=args.limit)

    # Print summary
    print()
    print("=== Collection Summary ===")
    print(f"Provider: {stats.get('provider', 'N/A')}")
    print(f"Queries processed: {stats['queries_processed']}")
    print(f"Positions found: {stats['queries_found']}")
    print(f"Not in top 100: {stats['queries_not_found']}")
    print(f"Errors: {stats['errors']}")

    if stats['success']:
        print()
        print("SERP tracking complete!")
    else:
        print()
        print(f"SERP tracking failed: {stats.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
