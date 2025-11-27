"""
Core Web Vitals Monitoring Module
==================================
Monitor Core Web Vitals using Google PageSpeed Insights API.

Tracks:
- LCP (Largest Contentful Paint)
- FID (First Input Delay) / INP (Interaction to Next Paint)
- CLS (Cumulative Layout Shift)
- Lighthouse scores (Performance, Accessibility, SEO, Best Practices)
"""
import asyncio
import logging
import os
from datetime import date
from typing import Dict, List, Optional
from urllib.parse import urljoin

import asyncpg
import httpx

logger = logging.getLogger(__name__)


class CoreWebVitalsMonitor:
    """
    Monitor Core Web Vitals using PageSpeed Insights API

    Free tier: 25,000 requests/day
    Rate limit: 1 request per second per URL
    """

    PAGESPEED_API_URL = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'

    def __init__(
        self,
        db_dsn: str = None,
        api_key: str = None
    ):
        """
        Initialize CWV monitor

        Args:
            db_dsn: Database connection string
            api_key: PageSpeed Insights API key (optional but recommended)
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.api_key = api_key or os.getenv('PAGESPEED_API_KEY')
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("CoreWebVitalsMonitor initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def fetch_page_metrics(
        self,
        url: str,
        strategy: str = 'mobile',
        categories: List[str] = None
    ) -> Dict:
        """
        Fetch metrics for a single URL

        Args:
            url: Full URL to test
            strategy: 'mobile' or 'desktop'
            categories: List of categories to audit
                       ['performance', 'accessibility', 'best-practices', 'seo', 'pwa']

        Returns:
            Metrics dictionary
        """
        try:
            if categories is None:
                categories = ['performance', 'accessibility', 'best-practices', 'seo']

            params = {
                'url': url,
                'strategy': strategy,
            }

            # Add categories
            for category in categories:
                params[f'category'] = category

            # Add API key if available
            if self.api_key:
                params['key'] = self.api_key

            logger.info(f"Fetching CWV for {url} ({strategy})")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(self.PAGESPEED_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return self._parse_pagespeed_response(data, url, strategy)

        except httpx.HTTPStatusError as e:
            logger.error(f"PageSpeed API error for {url}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching metrics for {url}: {e}")
            raise

    def _parse_pagespeed_response(self, data: Dict, url: str, strategy: str) -> Dict:
        """Parse PageSpeed Insights response"""
        try:
            lighthouse = data.get('lighthouseResult', {})
            audits = lighthouse.get('audits', {})
            categories = lighthouse.get('categories', {})

            # Extract Core Web Vitals
            # Try to get field data (real user data) first, fall back to lab data
            loading_experience = data.get('loadingExperience', {})
            metrics = loading_experience.get('metrics', {})

            # LCP - Largest Contentful Paint
            lcp = None
            if 'LARGEST_CONTENTFUL_PAINT_MS' in metrics:
                lcp = metrics['LARGEST_CONTENTFUL_PAINT_MS'].get('percentile')
            elif 'largest-contentful-paint' in audits:
                lcp = audits['largest-contentful-paint'].get('numericValue')

            # FID - First Input Delay (or INP - Interaction to Next Paint)
            fid = None
            if 'FIRST_INPUT_DELAY_MS' in metrics:
                fid = metrics['FIRST_INPUT_DELAY_MS'].get('percentile')
            elif 'INTERACTION_TO_NEXT_PAINT' in metrics:
                fid = metrics['INTERACTION_TO_NEXT_PAINT'].get('percentile')
            elif 'max-potential-fid' in audits:
                fid = audits['max-potential-fid'].get('numericValue')

            # CLS - Cumulative Layout Shift
            cls = None
            if 'CUMULATIVE_LAYOUT_SHIFT_SCORE' in metrics:
                cls = metrics['CUMULATIVE_LAYOUT_SHIFT_SCORE'].get('percentile') / 100  # Convert to decimal
            elif 'cumulative-layout-shift' in audits:
                cls = audits['cumulative-layout-shift'].get('numericValue')

            # FCP - First Contentful Paint
            fcp = audits.get('first-contentful-paint', {}).get('numericValue')

            # INP - Interaction to Next Paint
            inp = None
            if 'INTERACTION_TO_NEXT_PAINT' in metrics:
                inp = metrics['INTERACTION_TO_NEXT_PAINT'].get('percentile')

            # TTFB - Time to First Byte
            ttfb = audits.get('server-response-time', {}).get('numericValue')

            # Lab-only metrics
            tti = audits.get('interactive', {}).get('numericValue')
            tbt = audits.get('total-blocking-time', {}).get('numericValue')
            speed_index = audits.get('speed-index', {}).get('numericValue')

            # Lighthouse category scores (0-100)
            performance_score = int(categories.get('performance', {}).get('score', 0) * 100)
            accessibility_score = int(categories.get('accessibility', {}).get('score', 0) * 100)
            best_practices_score = int(categories.get('best-practices', {}).get('score', 0) * 100)
            seo_score = int(categories.get('seo', {}).get('score', 0) * 100)
            pwa_score = int(categories.get('pwa', {}).get('score', 0) * 100) if 'pwa' in categories else None

            # Calculate CWV assessment
            cwv_assessment = self._calculate_cwv_assessment(lcp, fid, cls)

            # Extract opportunities (optimization suggestions)
            opportunities = []
            for audit_id, audit in audits.items():
                if audit.get('details', {}).get('type') == 'opportunity':
                    opportunities.append({
                        'audit_id': audit_id,
                        'title': audit.get('title'),
                        'description': audit.get('description'),
                        'score': audit.get('score'),
                        'overallSavingsMs': audit.get('details', {}).get('overallSavingsMs', 0),
                        'items': audit.get('details', {}).get('items', [])
                    })

            # Sort opportunities by potential savings
            opportunities.sort(key=lambda x: x.get('overallSavingsMs', 0), reverse=True)

            # Extract diagnostics
            diagnostics = {}
            for audit_id in ['uses-optimized-images', 'uses-text-compression', 'uses-responsive-images',
                            'efficient-animated-content', 'offscreen-images', 'render-blocking-resources']:
                if audit_id in audits:
                    diagnostics[audit_id] = {
                        'title': audits[audit_id].get('title'),
                        'score': audits[audit_id].get('score'),
                        'description': audits[audit_id].get('description')
                    }

            return {
                'url': url,
                'strategy': strategy,
                # Core Web Vitals
                'lcp': lcp,
                'fid': fid,
                'cls': cls,
                'fcp': fcp,
                'inp': inp,
                'ttfb': ttfb,
                # Lab metrics
                'tti': tti,
                'tbt': tbt,
                'speed_index': speed_index,
                # Lighthouse scores
                'performance_score': performance_score,
                'accessibility_score': accessibility_score,
                'best_practices_score': best_practices_score,
                'seo_score': seo_score,
                'pwa_score': pwa_score,
                # Assessment
                'cwv_assessment': cwv_assessment,
                # Optimizations
                'opportunities': opportunities,
                'diagnostics': diagnostics,
                # Metadata
                'lighthouse_version': lighthouse.get('lighthouseVersion'),
                'user_agent': lighthouse.get('userAgent'),
                'fetch_time': lighthouse.get('fetchTime'),
                # Raw data
                'raw_response': data
            }

        except Exception as e:
            logger.error(f"Error parsing PageSpeed response: {e}")
            raise

    def _calculate_cwv_assessment(
        self,
        lcp: Optional[float],
        fid: Optional[float],
        cls: Optional[float]
    ) -> Optional[str]:
        """
        Calculate overall CWV assessment

        Returns: 'pass', 'needs_improvement', 'fail', or None
        """
        if lcp is None or fid is None or cls is None:
            return None

        # All three must be "good" for pass
        if lcp <= 2500 and fid <= 100 and cls <= 0.1:
            return 'pass'

        # If any metric is "poor", overall is fail
        if lcp > 4000 or fid > 300 or cls > 0.25:
            return 'fail'

        # Otherwise needs improvement
        return 'needs_improvement'

    async def store_metrics(
        self,
        property: str,
        page_path: str,
        metrics: Dict
    ):
        """Store CWV metrics in database"""
        try:
            # Normalize property URL (remove trailing slash)
            property = property.rstrip('/')

            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO performance.core_web_vitals (
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
                        tti,
                        tbt,
                        speed_index,
                        performance_score,
                        accessibility_score,
                        best_practices_score,
                        seo_score,
                        pwa_score,
                        cwv_assessment,
                        opportunities,
                        diagnostics,
                        audits,
                        lighthouse_version,
                        user_agent,
                        fetch_time,
                        raw_response
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24, $25, $26
                    )
                    ON CONFLICT (property, page_path, check_date, strategy)
                    DO UPDATE SET
                        lcp = EXCLUDED.lcp,
                        fid = EXCLUDED.fid,
                        cls = EXCLUDED.cls,
                        fcp = EXCLUDED.fcp,
                        inp = EXCLUDED.inp,
                        ttfb = EXCLUDED.ttfb,
                        tti = EXCLUDED.tti,
                        tbt = EXCLUDED.tbt,
                        speed_index = EXCLUDED.speed_index,
                        performance_score = EXCLUDED.performance_score,
                        accessibility_score = EXCLUDED.accessibility_score,
                        best_practices_score = EXCLUDED.best_practices_score,
                        seo_score = EXCLUDED.seo_score,
                        pwa_score = EXCLUDED.pwa_score,
                        cwv_assessment = EXCLUDED.cwv_assessment,
                        opportunities = EXCLUDED.opportunities,
                        diagnostics = EXCLUDED.diagnostics,
                        audits = EXCLUDED.audits,
                        lighthouse_version = EXCLUDED.lighthouse_version,
                        user_agent = EXCLUDED.user_agent,
                        fetch_time = EXCLUDED.fetch_time
                """,
                    property,
                    page_path,
                    date.today(),
                    metrics['strategy'],
                    metrics.get('lcp'),
                    metrics.get('fid'),
                    metrics.get('cls'),
                    metrics.get('fcp'),
                    metrics.get('inp'),
                    metrics.get('ttfb'),
                    metrics.get('tti'),
                    metrics.get('tbt'),
                    metrics.get('speed_index'),
                    metrics.get('performance_score'),
                    metrics.get('accessibility_score'),
                    metrics.get('best_practices_score'),
                    metrics.get('seo_score'),
                    metrics.get('pwa_score'),
                    metrics.get('cwv_assessment'),
                    metrics.get('opportunities'),
                    metrics.get('diagnostics'),
                    {},  # audits (full audit data, can be large)
                    metrics.get('lighthouse_version'),
                    metrics.get('user_agent'),
                    metrics.get('fetch_time'),
                    {}  # raw_response (stored but not queried often)
                )

            logger.info(f"Stored CWV metrics: {property}{page_path} ({metrics['strategy']})")

        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            raise

    async def monitor_page(
        self,
        property: str,
        page_path: str,
        strategies: List[str] = None,
        delay_seconds: float = 1.0
    ) -> Dict:
        """
        Monitor a single page

        Args:
            property: Property URL
            page_path: Page path
            strategies: List of strategies to test ['mobile', 'desktop']
            delay_seconds: Delay between strategy checks

        Returns:
            Results for all strategies
        """
        if strategies is None:
            strategies = ['mobile', 'desktop']

        results = {}

        for strategy in strategies:
            try:
                # Build full URL
                url = urljoin(property, page_path)

                # Fetch metrics
                metrics = await self.fetch_page_metrics(url, strategy)

                # Store in database
                await self.store_metrics(property, page_path, metrics)

                results[strategy] = {
                    'success': True,
                    'performance_score': metrics['performance_score'],
                    'lcp': metrics.get('lcp'),
                    'cls': metrics.get('cls'),
                    'cwv_assessment': metrics.get('cwv_assessment')
                }

                # Rate limiting
                if strategy != strategies[-1]:
                    await asyncio.sleep(delay_seconds)

            except Exception as e:
                logger.error(f"Error monitoring {url} ({strategy}): {e}")
                results[strategy] = {
                    'success': False,
                    'error': str(e)
                }

        return {
            'property': property,
            'page_path': page_path,
            'results': results
        }

    async def monitor_pages(
        self,
        property: str,
        page_paths: List[str],
        strategies: List[str] = None,
        delay_seconds: float = 1.0
    ) -> Dict:
        """
        Monitor multiple pages

        Args:
            property: Property URL
            page_paths: List of page paths
            strategies: List of strategies ['mobile', 'desktop']
            delay_seconds: Delay between requests (rate limiting)

        Returns:
            Summary of results
        """
        if strategies is None:
            strategies = ['mobile']  # Default to mobile only to save API quota

        results = []
        success_count = 0
        error_count = 0

        logger.info(f"Monitoring {len(page_paths)} pages for {property}")

        for i, page_path in enumerate(page_paths):
            try:
                result = await self.monitor_page(property, page_path, strategies, delay_seconds=0)
                results.append(result)

                # Count successes
                for strategy_result in result['results'].values():
                    if strategy_result['success']:
                        success_count += 1
                    else:
                        error_count += 1

                # Rate limiting between pages
                if i < len(page_paths) - 1:
                    await asyncio.sleep(delay_seconds)

            except Exception as e:
                logger.error(f"Error monitoring {page_path}: {e}")
                error_count += len(strategies)

        logger.info(f"Monitoring complete: {success_count} successful, {error_count} errors")

        return {
            'property': property,
            'pages_monitored': len(page_paths),
            'strategies': strategies,
            'success_count': success_count,
            'error_count': error_count,
            'results': results
        }

    def monitor_pages_sync(
        self,
        property: str,
        page_paths: List[str],
        strategies: List[str] = None
    ) -> Dict:
        """Synchronous wrapper for Celery"""
        return asyncio.run(self.monitor_pages(property, page_paths, strategies))

    async def get_poor_performing_pages(
        self,
        property: str,
        strategy: str = 'mobile',
        min_performance_score: int = 90
    ) -> List[Dict]:
        """
        Get pages with poor performance

        Args:
            property: Property URL
            strategy: 'mobile' or 'desktop'
            min_performance_score: Minimum acceptable score

        Returns:
            List of pages needing attention
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT
                        page_path,
                        performance_score,
                        lcp,
                        fid,
                        cls,
                        cwv_assessment,
                        check_date,
                        opportunities
                    FROM performance.vw_poor_cwv
                    WHERE property = $1
                        AND strategy = $2
                        AND performance_score < $3
                    ORDER BY performance_score ASC
                    LIMIT 100
                """, property, strategy, min_performance_score)

            pages = [dict(r) for r in results]
            return pages

        except Exception as e:
            logger.error(f"Error getting poor performing pages: {e}")
            return []

    async def get_performance_summary(self, property: str) -> Dict:
        """
        Get performance summary for property

        Args:
            property: Property URL

        Returns:
            Performance summary
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT *
                    FROM performance.vw_performance_summary
                    WHERE property = $1
                """, property)

            summary = {}
            for row in results:
                summary[row['strategy']] = dict(row)

            return summary

        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}

    async def check_budgets(self, property: str) -> List[Dict]:
        """
        Check performance budgets and create alerts

        Args:
            property: Property URL

        Returns:
            List of budget violations
        """
        try:
            pool = await self.get_pool()

            violations = []

            async with pool.acquire() as conn:
                # Get active budgets
                budgets = await conn.fetch("""
                    SELECT *
                    FROM performance.budgets
                    WHERE property = $1
                        AND is_active = true
                """, property)

                # Check each budget
                for budget in budgets:
                    # Get latest CWV data
                    pages = await conn.fetch("""
                        SELECT *
                        FROM performance.vw_cwv_current
                        WHERE property = $1
                            AND (
                                $2 IS NULL
                                OR page_path ~ $2
                            )
                            AND (
                                $3 = 'both'
                                OR strategy = $3
                            )
                    """, property, budget['page_path_pattern'], budget['strategy'])

                    for page in pages:
                        # Check violations
                        if budget['max_lcp'] and page['lcp'] and page['lcp'] > budget['max_lcp']:
                            violations.append({
                                'budget_id': budget['budget_id'],
                                'page_path': page['page_path'],
                                'strategy': page['strategy'],
                                'violation_type': 'lcp',
                                'threshold': budget['max_lcp'],
                                'actual': page['lcp'],
                                'severity': 'high' if page['lcp'] > budget['max_lcp'] * 1.5 else 'medium'
                            })

                        if budget['max_cls'] and page['cls'] and page['cls'] > budget['max_cls']:
                            violations.append({
                                'budget_id': budget['budget_id'],
                                'page_path': page['page_path'],
                                'strategy': page['strategy'],
                                'violation_type': 'cls',
                                'threshold': budget['max_cls'],
                                'actual': page['cls'],
                                'severity': 'high' if page['cls'] > budget['max_cls'] * 2 else 'medium'
                            })

                        if budget['min_performance_score'] and page['performance_score'] < budget['min_performance_score']:
                            violations.append({
                                'budget_id': budget['budget_id'],
                                'page_path': page['page_path'],
                                'strategy': page['strategy'],
                                'violation_type': 'performance_score',
                                'threshold': budget['min_performance_score'],
                                'actual': page['performance_score'],
                                'severity': 'high' if page['performance_score'] < budget['min_performance_score'] - 20 else 'medium'
                            })

                # Store alerts
                for violation in violations:
                    await conn.execute("""
                        INSERT INTO performance.alerts (
                            budget_id,
                            property,
                            page_path,
                            check_date,
                            strategy,
                            violation_type,
                            threshold_value,
                            actual_value,
                            severity,
                            status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT DO NOTHING
                    """,
                        violation['budget_id'],
                        property,
                        violation['page_path'],
                        date.today(),
                        violation['strategy'],
                        violation['violation_type'],
                        violation['threshold'],
                        violation['actual'],
                        violation['severity'],
                        'open'
                    )

            logger.info(f"Found {len(violations)} budget violations for {property}")
            return violations

        except Exception as e:
            logger.error(f"Error checking budgets: {e}")
            return []


__all__ = ['CoreWebVitalsMonitor']
