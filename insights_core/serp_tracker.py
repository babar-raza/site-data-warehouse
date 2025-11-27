"""
SERP Position Tracking Module
==============================
Track search engine ranking positions using SERP APIs or GSC data.

HYBRID MODE (Default):
- Primary: Uses GSC data (free, no limits, official Google data)
- Fallback: Uses SERP APIs only when needed

Supported APIs:
- ValueSERP (free tier: 100 searches/month)
- SerpAPI (free tier: 100 searches/month)
- DataForSEO (some free credits)
- Self-hosted Scrapy (unlimited, requires setup)
- GSC Data (unlimited, free, built-in)
"""
import asyncio
import logging
import os
from datetime import datetime, date
from typing import Dict, List, Optional
from urllib.parse import urlparse

import asyncpg
import httpx

logger = logging.getLogger(__name__)


class SerpAPIProvider:
    """Base class for SERP API providers"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self,
        query: str,
        location: str = 'United States',
        device: str = 'desktop',
        num_results: int = 100
    ) -> Dict:
        """
        Execute search and return results

        Returns:
            {
                'organic_results': [...]  # Top 100 organic results
                'serp_features': {...},  # SERP features present
                'total_results': int,    # Total result count
            }
        """
        raise NotImplementedError("Subclasses must implement search()")


class ValueSerpProvider(SerpAPIProvider):
    """ValueSERP API provider"""

    BASE_URL = 'https://api.valueserp.com/search'

    async def search(
        self,
        query: str,
        location: str = 'United States',
        device: str = 'desktop',
        num_results: int = 100
    ) -> Dict:
        """Execute search via ValueSERP API"""
        try:
            params = {
                'api_key': self.api_key,
                'q': query,
                'location': location,
                'gl': 'us',  # Country
                'hl': 'en',  # Language
                'device': device,
                'num': num_results,
                'output': 'json'
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return self._parse_valueserp_response(data)

        except Exception as e:
            logger.error(f"ValueSERP API error: {e}")
            raise

    def _parse_valueserp_response(self, data: Dict) -> Dict:
        """Parse ValueSERP response"""
        organic_results = []

        # Extract organic results
        for i, result in enumerate(data.get('organic_results', []), start=1):
            organic_results.append({
                'position': i,
                'url': result.get('link'),
                'domain': urlparse(result.get('link', '')).netloc,
                'title': result.get('title'),
                'description': result.get('snippet'),
                'displayed_link': result.get('displayed_link')
            })

        # Extract SERP features
        serp_features = {}

        if data.get('answer_box'):
            serp_features['featured_snippet'] = True
            serp_features['featured_snippet_data'] = data['answer_box']

        if data.get('knowledge_graph'):
            serp_features['knowledge_panel'] = True

        if data.get('related_questions'):
            serp_features['people_also_ask'] = True
            serp_features['paa_questions'] = [q.get('question') for q in data['related_questions']]

        if data.get('top_stories'):
            serp_features['top_stories'] = True

        if data.get('videos'):
            serp_features['video_carousel'] = True

        if data.get('images'):
            serp_features['image_pack'] = True

        return {
            'organic_results': organic_results,
            'serp_features': serp_features,
            'total_results': data.get('search_information', {}).get('total_results', 0)
        }


class SerpApiProvider(SerpAPIProvider):
    """SerpAPI provider"""

    BASE_URL = 'https://serpapi.com/search'

    async def search(
        self,
        query: str,
        location: str = 'United States',
        device: str = 'desktop',
        num_results: int = 100
    ) -> Dict:
        """Execute search via SerpAPI"""
        try:
            params = {
                'api_key': self.api_key,
                'q': query,
                'location': location,
                'hl': 'en',
                'gl': 'us',
                'device': device,
                'num': num_results
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return self._parse_serpapi_response(data)

        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            raise

    def _parse_serpapi_response(self, data: Dict) -> Dict:
        """Parse SerpAPI response"""
        organic_results = []

        # Extract organic results
        for result in data.get('organic_results', []):
            organic_results.append({
                'position': result.get('position'),
                'url': result.get('link'),
                'domain': result.get('domain'),
                'title': result.get('title'),
                'description': result.get('snippet'),
                'displayed_link': result.get('displayed_link')
            })

        # Extract SERP features
        serp_features = {}

        if data.get('answer_box'):
            serp_features['featured_snippet'] = True
            serp_features['featured_snippet_data'] = data['answer_box']

        if data.get('knowledge_graph'):
            serp_features['knowledge_panel'] = True

        if data.get('related_questions'):
            serp_features['people_also_ask'] = True
            serp_features['paa_questions'] = data['related_questions']

        if data.get('top_stories'):
            serp_features['top_stories'] = True

        if data.get('inline_videos'):
            serp_features['video_carousel'] = True

        if data.get('inline_images'):
            serp_features['image_pack'] = True

        return {
            'organic_results': organic_results,
            'serp_features': serp_features,
            'total_results': data.get('search_information', {}).get('total_results', 0)
        }


class SerpStackProvider(SerpAPIProvider):
    """SerpStack API provider (100 free requests/month)"""

    BASE_URL = 'http://api.serpstack.com/search'

    async def search(
        self,
        query: str,
        location: str = 'United States',
        device: str = 'desktop',
        num_results: int = 100
    ) -> Dict:
        """Execute search via SerpStack API"""
        try:
            # Map location to SerpStack format
            location_code = self._map_location(location)

            params = {
                'access_key': self.api_key,
                'query': query,
                'gl': location_code,
                'hl': 'en',
                'num': num_results,
                'device': device
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            # Check for API errors
            if 'error' in data:
                error_msg = data['error'].get('info', 'Unknown error')
                logger.error(f"SerpStack API error: {error_msg}")
                raise Exception(f"SerpStack API error: {error_msg}")

            return self._parse_serpstack_response(data)

        except Exception as e:
            logger.error(f"SerpStack API error: {e}")
            raise

    def _map_location(self, location: str) -> str:
        """Map location string to country code"""
        location_map = {
            'United States': 'us',
            'United Kingdom': 'uk',
            'Canada': 'ca',
            'Australia': 'au',
            'Germany': 'de',
            'France': 'fr',
            'Spain': 'es',
            'Italy': 'it',
            'Netherlands': 'nl',
            'India': 'in'
        }
        return location_map.get(location, 'us')

    def _parse_serpstack_response(self, data: Dict) -> Dict:
        """Parse SerpStack response"""
        organic_results = []

        # Extract organic results
        for i, result in enumerate(data.get('organic_results', []), start=1):
            organic_results.append({
                'position': i,
                'url': result.get('url'),
                'domain': result.get('domain'),
                'title': result.get('title'),
                'description': result.get('snippet'),
                'displayed_link': result.get('displayed_url')
            })

        # Extract SERP features
        serp_features = {}

        # Answer box / Featured snippet
        if data.get('answer_box'):
            serp_features['featured_snippet'] = True
            serp_features['featured_snippet_data'] = data['answer_box']

        # Knowledge graph/panel
        if data.get('knowledge_graph'):
            serp_features['knowledge_panel'] = True
            serp_features['knowledge_panel_data'] = data['knowledge_graph']

        # People Also Ask
        if data.get('related_questions'):
            serp_features['people_also_ask'] = True
            serp_features['paa_questions'] = data['related_questions']

        # Top stories
        if data.get('top_stories'):
            serp_features['top_stories'] = True

        # Videos
        if data.get('inline_videos'):
            serp_features['video_carousel'] = True

        # Images
        if data.get('inline_images'):
            serp_features['image_pack'] = True

        # Local pack
        if data.get('local_results'):
            serp_features['local_pack'] = True

        return {
            'organic_results': organic_results,
            'serp_features': serp_features,
            'total_results': data.get('search_information', {}).get('total_results', 0),
            'search_metadata': data.get('search_metadata', {})
        }


class SerpTracker:
    """
    SERP position tracker with HYBRID MODE support

    Tracks search engine rankings for configured queries

    HYBRID MODE (Default):
    - Uses GSC data first (free, unlimited, official)
    - Falls back to APIs only when needed
    """

    def __init__(
        self,
        db_dsn: str = None,
        api_provider: str = 'valueserp',
        api_key: str = None,
        use_gsc_data: bool = True,  # NEW: Enable GSC-based tracking by default
        gsc_fallback: bool = True    # NEW: Use GSC when API is unavailable
    ):
        """
        Initialize SERP tracker

        Args:
            db_dsn: Database connection string
            api_provider: 'valueserp', 'serpapi', 'gsc', or None
            api_key: API key for chosen provider (not needed for GSC)
            use_gsc_data: Use GSC data as primary source (default: True)
            gsc_fallback: Fall back to GSC if API fails (default: True)
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.api_provider = api_provider
        self.api_key = api_key or os.getenv(f'{api_provider.upper()}_API_KEY') if api_provider != 'gsc' else None
        self.use_gsc_data = use_gsc_data
        self.gsc_fallback = gsc_fallback

        # Initialize API provider (optional if using GSC only)
        self.provider = None
        if api_provider and api_provider != 'gsc':
            try:
                if api_provider == 'valueserp' and self.api_key:
                    self.provider = ValueSerpProvider(self.api_key)
                elif api_provider == 'serpapi' and self.api_key:
                    self.provider = SerpApiProvider(self.api_key)
                elif api_provider == 'serpstack' and self.api_key:
                    self.provider = SerpStackProvider(self.api_key)
                    logger.info("SerpStack provider initialized (100 free requests/month)")
                elif self.api_key:
                    logger.warning(f"Unsupported API provider: {api_provider}")
            except Exception as e:
                logger.warning(f"Could not initialize API provider: {e}")
                if not gsc_fallback:
                    raise

        self._pool: Optional[asyncpg.Pool] = None

        # Import GSC tracker if needed
        if use_gsc_data or gsc_fallback:
            try:
                from insights_core.gsc_serp_tracker import GSCBasedSerpTracker
                self.gsc_tracker = GSCBasedSerpTracker(db_dsn=self.db_dsn)
                logger.info("GSC-based SERP tracking enabled (HYBRID MODE)")
            except ImportError:
                logger.warning("GSC tracker not available")
                self.gsc_tracker = None
        else:
            self.gsc_tracker = None

        mode = "HYBRID (GSC + API)" if use_gsc_data and self.provider else \
               "GSC ONLY" if use_gsc_data else \
               f"API ONLY ({api_provider})"
        logger.info(f"SerpTracker initialized in {mode} mode")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def fetch_active_queries(
        self,
        property: str = None,
        device: str = None
    ) -> List[Dict]:
        """
        Fetch active queries to track

        Args:
            property: Filter by property (optional)
            device: Filter by device (optional)

        Returns:
            List of query dictionaries
        """
        try:
            pool = await self.get_pool()

            query = """
                SELECT
                    query_id,
                    query_text,
                    property,
                    target_page_path,
                    location,
                    language,
                    device,
                    search_engine
                FROM serp.queries
                WHERE is_active = true
            """

            params = []

            if property:
                query += " AND property = $1"
                params.append(property)

            if device:
                param_num = len(params) + 1
                query += f" AND device = ${param_num}"
                params.append(device)

            query += " ORDER BY property, query_text"

            async with pool.acquire() as conn:
                if params:
                    results = await conn.fetch(query, *params)
                else:
                    results = await conn.fetch(query)

            queries = [dict(r) for r in results]
            logger.info(f"Fetched {len(queries)} active queries")
            return queries

        except Exception as e:
            logger.error(f"Error fetching queries: {e}")
            return []

    async def track_query(self, query_data: Dict) -> Dict:
        """
        Track position for a single query

        Args:
            query_data: Query dictionary from database

        Returns:
            Tracking result
        """
        try:
            # Execute search
            logger.info(f"Tracking: {query_data['query_text']} ({query_data['device']})")

            search_results = await self.provider.search(
                query=query_data['query_text'],
                location=query_data['location'],
                device=query_data['device'],
                num_results=100
            )

            # Find our position
            our_domain = urlparse(query_data['property']).netloc
            our_position = None
            our_url = None
            our_title = None
            our_description = None

            for result in search_results['organic_results']:
                if result['domain'] == our_domain:
                    # Check if target page matches (if specified)
                    if query_data['target_page_path']:
                        result_path = urlparse(result['url']).path
                        if result_path == query_data['target_page_path']:
                            our_position = result['position']
                            our_url = result['url']
                            our_title = result['title']
                            our_description = result['description']
                            break
                    else:
                        # Any page from our domain
                        our_position = result['position']
                        our_url = result['url']
                        our_title = result['title']
                        our_description = result['description']
                        break

            # Store results
            await self.store_position_data(
                query_id=query_data['query_id'],
                check_date=date.today(),
                position=our_position,
                url=our_url,
                domain=our_domain,
                title=our_title,
                description=our_description,
                total_results=search_results['total_results'],
                competitors=search_results['organic_results'][:10],
                serp_features=search_results['serp_features'],
                api_source=self.api_provider
            )

            # Store SERP features
            await self.store_serp_features(
                query_id=query_data['query_id'],
                check_date=date.today(),
                serp_features=search_results['serp_features'],
                organic_results=search_results['organic_results']
            )

            logger.info(f"Tracked: {query_data['query_text']} - Position: {our_position or 'Not found'}")

            return {
                'query_text': query_data['query_text'],
                'position': our_position,
                'url': our_url,
                'success': True
            }

        except Exception as e:
            logger.error(f"Error tracking query {query_data['query_text']}: {e}")
            return {
                'query_text': query_data['query_text'],
                'success': False,
                'error': str(e)
            }

    async def store_position_data(
        self,
        query_id: str,
        check_date: date,
        position: Optional[int],
        url: Optional[str],
        domain: str,
        title: Optional[str],
        description: Optional[str],
        total_results: int,
        competitors: List[Dict],
        serp_features: Dict,
        api_source: str
    ):
        """Store position data in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO serp.position_history (
                        query_id,
                        check_date,
                        position,
                        url,
                        domain,
                        title,
                        description,
                        total_results,
                        competitors,
                        serp_features,
                        api_source
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (query_id, check_date, check_timestamp)
                    DO UPDATE SET
                        position = EXCLUDED.position,
                        url = EXCLUDED.url,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        total_results = EXCLUDED.total_results,
                        competitors = EXCLUDED.competitors,
                        serp_features = EXCLUDED.serp_features
                """,
                    query_id,
                    check_date,
                    position,
                    url,
                    domain,
                    title,
                    description,
                    total_results,
                    competitors,
                    serp_features,
                    api_source
                )

        except Exception as e:
            logger.error(f"Error storing position data: {e}")
            raise

    async def store_serp_features(
        self,
        query_id: str,
        check_date: date,
        serp_features: Dict,
        organic_results: List[Dict]
    ):
        """Store SERP features in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Store each SERP feature
                if serp_features.get('featured_snippet'):
                    snippet_data = serp_features.get('featured_snippet_data', {})
                    owner_domain = snippet_data.get('domain', '')
                    owner_url = snippet_data.get('link', '')

                    await conn.execute("""
                        INSERT INTO serp.serp_features (
                            query_id,
                            check_date,
                            feature_type,
                            owner_domain,
                            owner_url,
                            content,
                            position
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (query_id, check_date, feature_type, owner_domain)
                        DO UPDATE SET
                            owner_url = EXCLUDED.owner_url,
                            content = EXCLUDED.content,
                            position = EXCLUDED.position
                    """,
                        query_id,
                        check_date,
                        'featured_snippet',
                        owner_domain,
                        owner_url,
                        snippet_data,
                        0  # Featured snippet is position 0
                    )

                # Store other features (knowledge panel, PAA, etc.)
                for feature_type in ['knowledge_panel', 'people_also_ask', 'top_stories', 'video_carousel', 'image_pack']:
                    if serp_features.get(feature_type):
                        await conn.execute("""
                            INSERT INTO serp.serp_features (
                                query_id,
                                check_date,
                                feature_type,
                                content
                            ) VALUES ($1, $2, $3, $4)
                            ON CONFLICT (query_id, check_date, feature_type, owner_domain)
                            DO NOTHING
                        """,
                            query_id,
                            check_date,
                            feature_type,
                            {feature_type: serp_features.get(f'{feature_type}_data')}
                        )

        except Exception as e:
            logger.error(f"Error storing SERP features: {e}")
            # Don't raise - features are optional

    async def track_all_queries(
        self,
        property: str = None,
        device: str = None,
        delay_seconds: float = 1.0
    ) -> Dict:
        """
        Track all active queries

        Args:
            property: Filter by property (optional)
            device: Filter by device (optional)
            delay_seconds: Delay between requests (rate limiting)

        Returns:
            Summary of tracking results
        """
        try:
            queries = await self.fetch_active_queries(property, device)

            if not queries:
                logger.warning("No active queries to track")
                return {
                    'queries_tracked': 0,
                    'success_count': 0,
                    'error_count': 0
                }

            results = []
            for i, query_data in enumerate(queries):
                result = await self.track_query(query_data)
                results.append(result)

                # Rate limiting
                if i < len(queries) - 1:
                    await asyncio.sleep(delay_seconds)

            success_count = sum(1 for r in results if r['success'])
            error_count = len(results) - success_count

            logger.info(f"Tracking complete: {success_count}/{len(results)} successful")

            return {
                'queries_tracked': len(results),
                'success_count': success_count,
                'error_count': error_count,
                'results': results
            }

        except Exception as e:
            logger.error(f"Error in track_all_queries: {e}")
            return {
                'queries_tracked': 0,
                'success_count': 0,
                'error_count': 0,
                'error': str(e)
            }

    def track_all_queries_sync(self, property: str = None, device: str = None) -> Dict:
        """Synchronous wrapper for Celery"""
        return asyncio.run(self.track_all_queries(property, device))

    async def get_position_changes(
        self,
        property: str,
        days_back: int = 7
    ) -> List[Dict]:
        """
        Get position changes for property

        Args:
            property: Property URL
            days_back: Days to look back

        Returns:
            List of position changes
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        query_text,
                        current_position,
                        prev_position,
                        position_change,
                        position_status,
                        check_date as latest_check
                    FROM serp.vw_position_changes
                    WHERE property = $1
                    ORDER BY ABS(position_change) DESC NULLS LAST
                """, property)

            changes = [dict(r) for r in results]
            return changes

        except Exception as e:
            logger.error(f"Error getting position changes: {e}")
            return []

    async def get_serp_feature_wins(
        self,
        property: str,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Get SERP features we own

        Args:
            property: Property URL
            days_back: Days to look back

        Returns:
            List of SERP feature wins
        """
        try:
            pool = await self.get_pool()
            our_domain = urlparse(property).netloc

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        query_text,
                        feature_type,
                        check_date
                    FROM serp.vw_serp_feature_summary
                    WHERE property = $1
                        AND we_own_feature = true
                        AND check_date >= CURRENT_DATE - $2
                    ORDER BY check_date DESC, query_text
                """, property, days_back)

            features = [dict(r) for r in results]
            return features

        except Exception as e:
            logger.error(f"Error getting SERP feature wins: {e}")
            return []


__all__ = ['SerpTracker', 'ValueSerpProvider', 'SerpApiProvider']
