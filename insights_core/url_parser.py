"""
URL Parser for normalizing and tracking URL variations

Handles:
- Query parameter normalization (removes tracking params)
- Fragment handling
- Trailing slash normalization
- Case normalization
- Protocol normalization

Example:
    >>> parser = URLParser()
    >>> canonical = parser.normalize('/page?utm_source=google&id=123')
    >>> print(canonical)  # '/page?id=123'

    >>> variations = parser.extract_variations('/page#section?sort=desc')
    >>> print(variations['has_fragment'])  # True
"""
import logging
import os
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


class URLParser:
    """
    URL Parser for normalizing URLs and detecting variations

    This class provides functionality to:
    - Normalize URLs by removing tracking parameters
    - Detect different types of URL variations
    - Group URLs by their canonical form
    - Store and track variations in the database
    - Identify consolidation opportunities

    Example usage:
        parser = URLParser()
        canonical = parser.normalize('/page?utm_source=google&id=123')
        # Returns: '/page?id=123'

        variations = parser.extract_variations('/page#section?sort=desc')
        # Returns: {'has_fragment': True, 'fragment': 'section', ...}
    """

    # Tracking parameters to remove during normalization
    TRACKING_PARAMS = {
        # UTM parameters (Google Analytics standard)
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',

        # Facebook tracking
        'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
        'fbadid', 'fbadsetid', 'fbcampaignid',

        # Google tracking
        'gclid', 'gclsrc', 'dclid', 'gbraid', 'wbraid',

        # Microsoft/Bing
        'msclkid', 'mstoken',

        # Twitter
        'twclid', 'twsrc',

        # LinkedIn
        'li_fat_id', 'lipi',

        # TikTok
        'ttclid',

        # Other advertising platforms
        'mc_cid', 'mc_eid',  # Mailchimp
        '_ga', '_gl', '_gac',  # Google Analytics client-side
        'klaviyo',  # Klaviyo
        'yclid',  # Yandex

        # Common tracking parameters
        'ref', 'source', 'referrer', 'referer',
        'affiliate', 'partner', 'affiliate_id', 'partner_id',
        'campaign', 'adgroup', 'creative', 'keyword',

        # Session/state params (often not meaningful for SEO)
        'sessionid', 'sid', 'token', 'auth',
        '_hsenc', '_hsmi',  # HubSpot
        'vero_conv', 'vero_id',  # Vero

        # Social media share tracking
        'share', 'shared', 'sharesource',

        # Email tracking
        'email_id', 'message_id', 'recipient_id',
    }

    # Parameters to preserve (semantic meaning for content)
    PRESERVE_PARAMS = {
        # Pagination and navigation
        'id', 'page', 'p', 'offset', 'limit', 'start',

        # Search and filtering
        'q', 'query', 'search', 's', 'keywords', 'term',
        'sort', 'order', 'orderby', 'sortby', 'dir', 'direction',
        'filter', 'filters', 'facets', 'category', 'categories',

        # Content selection
        'type', 'format', 'view', 'display', 'mode',

        # Localization
        'lang', 'language', 'locale', 'region', 'country',

        # Versioning
        'v', 'version', 'rev', 'revision',

        # Product/commerce
        'sku', 'product', 'variant', 'color', 'size',

        # Media
        'width', 'height', 'quality', 'format',

        # Date/time
        'date', 'year', 'month', 'day', 'from', 'to',
    }

    def __init__(self, db_dsn: str = None):
        """
        Initialize URL Parser

        Args:
            db_dsn: Database connection string for storing variations.
                   If not provided, will attempt to read from WAREHOUSE_DSN env var.
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        logger.debug(f"URLParser initialized with DSN: {'configured' if self.db_dsn else 'not configured'}")

    def normalize(self, url: str, remove_fragment: bool = True) -> str:
        """
        Normalize URL by removing tracking parameters and standardizing format

        Process:
        1. Parse URL into components
        2. Lowercase the path
        3. Remove trailing slashes (except root)
        4. Filter out tracking parameters
        5. Sort remaining parameters alphabetically
        6. Remove or preserve fragment based on parameter
        7. Reconstruct normalized URL

        Args:
            url: URL to normalize (can be absolute or relative)
            remove_fragment: Whether to remove URL fragments (default True)

        Returns:
            Normalized URL string

        Example:
            >>> parser = URLParser()
            >>> parser.normalize('/page?utm_source=google&id=123')
            '/page?id=123'

            >>> parser.normalize('/Page/?utm_campaign=test')
            '/page'

            >>> parser.normalize('/page#section', remove_fragment=False)
            '/page#section'
        """
        if not url:
            return ''

        try:
            parsed = urlparse(url)

            # Normalize path
            path = parsed.path.lower() if parsed.path else '/'
            # Remove trailing slash (except for root)
            if path != '/' and path.endswith('/'):
                path = path.rstrip('/')

            # Parse and filter query parameters
            query_params = parse_qs(parsed.query, keep_blank_values=False)
            filtered_params = {}

            for key, values in query_params.items():
                key_lower = key.lower()
                # Remove tracking parameters, keep everything else
                if key_lower not in self.TRACKING_PARAMS:
                    # Keep parameter, use lowercase key for consistency
                    filtered_params[key_lower] = values

            # Sort parameters for consistent output
            sorted_query = urlencode(
                sorted(filtered_params.items()),
                doseq=True
            ) if filtered_params else ''

            # Handle fragment
            fragment = '' if remove_fragment else parsed.fragment

            # Reconstruct URL (relative format)
            normalized = urlunparse((
                '',  # scheme - remove for relative URLs
                '',  # netloc - remove for relative URLs
                path,
                '',  # params (deprecated, not used)
                sorted_query,
                fragment
            ))

            return normalized if normalized else '/'

        except Exception as e:
            logger.warning(f"Error normalizing URL '{url}': {e}")
            return url

    def extract_variations(self, url: str) -> Dict:
        """
        Extract variation information from URL

        Analyzes a URL to identify what types of variations it contains,
        such as tracking parameters, fragments, trailing slashes, etc.

        Args:
            url: URL to analyze

        Returns:
            Dict with variation details including:
            - original_url: The input URL
            - path: URL path component
            - has_query: Whether URL has query parameters
            - query_param_count: Number of query parameters
            - has_fragment: Whether URL has a fragment
            - fragment: The fragment value (if present)
            - has_trailing_slash: Whether path has trailing slash
            - tracking_params: List of tracking parameters found
            - semantic_params: List of semantic parameters found
            - tracking_param_count: Count of tracking parameters
            - is_mixed_case: Whether path has mixed case

        Example:
            >>> parser = URLParser()
            >>> parser.extract_variations('/page#section?sort=desc')
            {'has_fragment': True, 'fragment': 'section', ...}

            >>> parser.extract_variations('/Page/?utm_source=google&id=123')
            {'has_trailing_slash': True, 'tracking_param_count': 1, ...}
        """
        if not url:
            return {'error': 'Empty URL'}

        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query, keep_blank_values=True)

            # Identify tracking parameters present
            tracking_present = [
                key for key in query_params.keys()
                if key.lower() in self.TRACKING_PARAMS
            ]

            # Identify semantic parameters
            semantic_present = [
                key for key in query_params.keys()
                if key.lower() in self.PRESERVE_PARAMS
            ]

            # Check for mixed case in path
            is_mixed_case = False
            if parsed.path:
                is_mixed_case = parsed.path != parsed.path.lower()

            # Check for trailing slash
            has_trailing_slash = False
            if parsed.path and len(parsed.path) > 1:
                has_trailing_slash = parsed.path.endswith('/')

            return {
                'original_url': url,
                'path': parsed.path or '/',
                'has_query': bool(parsed.query),
                'query_param_count': len(query_params),
                'has_fragment': bool(parsed.fragment),
                'fragment': parsed.fragment or None,
                'has_trailing_slash': has_trailing_slash,
                'tracking_params': tracking_present,
                'semantic_params': semantic_present,
                'tracking_param_count': len(tracking_present),
                'semantic_param_count': len(semantic_present),
                'is_mixed_case': is_mixed_case,
                'scheme': parsed.scheme or None,
                'netloc': parsed.netloc or None,
            }

        except Exception as e:
            logger.warning(f"Error extracting variations from '{url}': {e}")
            return {'error': str(e), 'original_url': url}

    def group_by_canonical(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        Group URLs by their canonical form

        Takes a list of URLs and groups them by their normalized canonical URL.
        This helps identify which URLs are variations of the same content.

        Args:
            urls: List of URLs to group

        Returns:
            Dict mapping canonical URL to list of variations

        Example:
            >>> parser = URLParser()
            >>> parser.group_by_canonical([
            ...     '/page?utm_source=google',
            ...     '/page?utm_source=facebook',
            ...     '/page',
            ...     '/other'
            ... ])
            {'/page': ['/page?utm_source=google', '/page?utm_source=facebook', '/page'],
             '/other': ['/other']}
        """
        groups: Dict[str, List[str]] = {}

        for url in urls:
            if not url:
                continue

            canonical = self.normalize(url)
            if canonical not in groups:
                groups[canonical] = []
            # Avoid duplicates in the variation list
            if url not in groups[canonical]:
                groups[canonical].append(url)

        return groups

    def detect_variation_type(self, canonical: str, variation: str) -> str:
        """
        Detect the type of variation between canonical and variation URL

        Determines what type of difference exists between a canonical URL
        and one of its variations.

        Args:
            canonical: Canonical URL
            variation: Variation URL

        Returns:
            Variation type string: 'identical', 'query_param', 'fragment',
            'trailing_slash', 'case', 'protocol', or 'other'

        Example:
            >>> parser = URLParser()
            >>> parser.detect_variation_type('/page', '/page?utm_source=google')
            'query_param'

            >>> parser.detect_variation_type('/page', '/page#section')
            'fragment'
        """
        if canonical == variation:
            return 'identical'

        var_info = self.extract_variations(variation)

        # Check for errors in parsing
        if 'error' in var_info:
            return 'other'

        # Priority order: tracking params > fragment > trailing slash > case
        if var_info.get('tracking_param_count', 0) > 0:
            return 'query_param'
        if var_info.get('has_fragment'):
            return 'fragment'
        if var_info.get('has_trailing_slash'):
            return 'trailing_slash'
        if var_info.get('is_mixed_case'):
            return 'case'

        # Check for protocol differences
        if var_info.get('scheme'):
            return 'protocol'

        return 'other'

    def detect_consolidation_opportunities(self, property: str) -> List[Dict]:
        """
        Find pages that might need URL consolidation

        Queries the database to find URLs with multiple variations,
        which may indicate opportunities for canonical tags, redirects,
        or other consolidation strategies.

        Args:
            property: Property to analyze (e.g., 'sc-domain:example.com')

        Returns:
            List of consolidation opportunities, each containing:
            - canonical_url: The canonical URL
            - variation_count: Number of variations
            - variation_types: Types of variations present
            - total_occurrences: Total times variations have been seen
            - recommendation: Suggested action

        Example:
            >>> parser = URLParser(db_dsn='postgresql://...')
            >>> opportunities = parser.detect_consolidation_opportunities('sc-domain:example.com')
            >>> print(opportunities[0]['recommendation'])
            'Set up canonical tags and consider 301 redirects for 5 URL variations...'
        """
        conn = None
        cursor = None
        opportunities = []

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            if not self.db_dsn:
                logger.warning("No database connection configured")
                return opportunities

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Find URLs with multiple variations
            cursor.execute("""
                SELECT
                    canonical_url,
                    variation_count,
                    variation_types,
                    total_occurrences,
                    first_seen,
                    last_seen
                FROM analytics.vw_url_consolidation_candidates
                WHERE property = %s
                ORDER BY variation_count DESC, total_occurrences DESC
                LIMIT 100
            """, (property,))

            rows = cursor.fetchall()

            for row in rows:
                opportunity = {
                    'canonical_url': row['canonical_url'],
                    'variation_count': row['variation_count'],
                    'variation_types': row['variation_types'],
                    'total_occurrences': row['total_occurrences'],
                    'first_seen': row['first_seen'],
                    'last_seen': row['last_seen'],
                    'recommendation': self._generate_recommendation(row)
                }
                opportunities.append(opportunity)

            logger.info(f"Found {len(opportunities)} consolidation opportunities for {property}")
            return opportunities

        except Exception as e:
            logger.error(f"Error detecting consolidation opportunities: {e}")
            return opportunities

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _generate_recommendation(self, opportunity: Dict) -> str:
        """
        Generate consolidation recommendation based on variation types

        Args:
            opportunity: Dict with variation information

        Returns:
            Recommendation string
        """
        types = opportunity.get('variation_types', [])
        count = opportunity.get('variation_count', 0)
        occurrences = opportunity.get('total_occurrences', 0)

        if 'query_param' in types:
            return (f"Set up canonical tags and consider 301 redirects for {count} URL variations "
                   f"with tracking parameters ({occurrences} total occurrences)")
        elif 'trailing_slash' in types:
            return (f"Standardize trailing slash usage and add redirects for {count} variations "
                   f"({occurrences} total occurrences)")
        elif 'case' in types:
            return (f"Normalize URL casing and add case-insensitive redirects for {count} variations "
                   f"({occurrences} total occurrences)")
        elif 'fragment' in types:
            return (f"Review {count} URL variations with fragments - consider if fragments should be "
                   f"separate pages ({occurrences} total occurrences)")
        elif 'protocol' in types:
            return (f"Ensure consistent HTTPS usage and redirects for {count} protocol variations "
                   f"({occurrences} total occurrences)")
        else:
            return (f"Review {count} URL variations for potential consolidation "
                   f"({occurrences} total occurrences)")

    def store_variation(self, property: str, canonical: str, variation: str) -> bool:
        """
        Store a URL variation in the database

        Records a URL variation for tracking and analysis. If the variation
        already exists, increments its occurrence count and updates last_seen.

        Args:
            property: Property identifier (e.g., 'sc-domain:example.com')
            canonical: Canonical URL (normalized)
            variation: Variation URL (original)

        Returns:
            True if stored successfully, False otherwise

        Example:
            >>> parser = URLParser(db_dsn='postgresql://...')
            >>> parser.store_variation(
            ...     'sc-domain:example.com',
            ...     '/page',
            ...     '/page?utm_source=google'
            ... )
            True
        """
        conn = None
        cursor = None

        try:
            import psycopg2

            if not self.db_dsn:
                logger.warning("No database connection configured")
                return False

            # Don't store if canonical and variation are identical
            if canonical == variation:
                logger.debug(f"Skipping identical URL: {canonical}")
                return True

            variation_type = self.detect_variation_type(canonical, variation)

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            # Insert or update variation record
            cursor.execute("""
                INSERT INTO analytics.url_variations
                    (property, canonical_url, variation_url, variation_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (property, canonical_url, variation_url)
                DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    occurrences = analytics.url_variations.occurrences + 1
            """, (property, canonical, variation, variation_type))

            conn.commit()
            logger.debug(f"Stored URL variation: {variation} -> {canonical} (type: {variation_type})")
            return True

        except Exception as e:
            logger.error(f"Error storing URL variation: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def batch_store_variations(self, property: str, url_pairs: List[Tuple[str, str]]) -> int:
        """
        Store multiple URL variations in a single transaction

        More efficient than calling store_variation() multiple times.

        Args:
            property: Property identifier
            url_pairs: List of (canonical, variation) tuples

        Returns:
            Number of variations successfully stored
        """
        conn = None
        cursor = None
        stored_count = 0

        try:
            import psycopg2

            if not self.db_dsn:
                logger.warning("No database connection configured")
                return 0

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            for canonical, variation in url_pairs:
                # Skip identical URLs
                if canonical == variation:
                    continue

                variation_type = self.detect_variation_type(canonical, variation)

                cursor.execute("""
                    INSERT INTO analytics.url_variations
                        (property, canonical_url, variation_url, variation_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (property, canonical_url, variation_url)
                    DO UPDATE SET
                        last_seen = CURRENT_TIMESTAMP,
                        occurrences = analytics.url_variations.occurrences + 1
                """, (property, canonical, variation, variation_type))

                stored_count += 1

            conn.commit()
            logger.info(f"Stored {stored_count} URL variations for {property}")
            return stored_count

        except Exception as e:
            logger.error(f"Error batch storing URL variations: {e}")
            if conn:
                conn.rollback()
            return stored_count

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
