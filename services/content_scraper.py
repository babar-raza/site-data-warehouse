"""
Content Scraper - Automated Content Monitoring
===============================================
Monitors content changes using Playwright:
- Scrapes pages automatically
- Detects content changes (text + visual)
- Screenshots comparison
- Change impact analysis
- Integrates with content.content_changes table

Features:
- Headless browser (Playwright)
- Change detection (text diff)
- Screenshot comparison
- Automated scheduling
- Integration with analysis pipeline
"""
import hashlib
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import asyncpg
import Levenshtein
from playwright.async_api import async_playwright, Browser, Page
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ContentScraper:
    """
    Automated content scraping and change detection
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize content scraper

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None
        self._browser: Optional[Browser] = None

        logger.info("ContentScraper initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close connections"""
        if self._pool:
            await self._pool.close()
        if self._browser:
            await self._browser.close()

    async def scrape_page(
        self,
        url: str,
        wait_for: str = 'networkidle',
        timeout: int = 30000
    ) -> Dict:
        """
        Scrape a page with Playwright

        Args:
            url: URL to scrape
            wait_for: Wait condition ('load', 'domcontentloaded', 'networkidle')
            timeout: Timeout in milliseconds

        Returns:
            Dict with HTML, text, screenshot
        """
        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navigate
                await page.goto(url, wait_until=wait_for, timeout=timeout)

                # Wait a bit for dynamic content
                await page.wait_for_timeout(2000)

                # Get content
                html = await page.content()
                text = await page.evaluate("document.body.innerText")

                # Take screenshot
                screenshot_bytes = await page.screenshot(full_page=True)

                # Get metadata
                title = await page.title()
                meta_desc = await page.evaluate(
                    "document.querySelector('meta[name=\"description\"]')?.content"
                )

                await browser.close()

                return {
                    'url': url,
                    'html': html,
                    'text': text,
                    'screenshot': screenshot_bytes,
                    'title': title,
                    'meta_description': meta_desc,
                    'scraped_at': datetime.utcnow(),
                    'success': True
                }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {'url': url, 'error': str(e), 'success': False}

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using Levenshtein distance

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1, 1 = identical)
        """
        try:
            if not text1 or not text2:
                return 0.0

            # Normalize
            text1 = text1.lower().strip()
            text2 = text2.lower().strip()

            # Calculate Levenshtein ratio
            ratio = Levenshtein.ratio(text1, text2)
            return ratio

        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def compare_screenshots(
        self,
        screenshot1: bytes,
        screenshot2: bytes,
        threshold: float = 0.95
    ) -> Dict:
        """
        Compare two screenshots

        Args:
            screenshot1: First screenshot
            screenshot2: Second screenshot
            threshold: Similarity threshold

        Returns:
            Dict with similarity score and changed status
        """
        try:
            # Load images
            img1 = Image.open(io.BytesIO(screenshot1))
            img2 = Image.open(io.BytesIO(screenshot2))

            # Resize to same size for comparison
            size = (800, 600)  # Standard size
            img1 = img1.resize(size)
            img2 = img2.resize(size)

            # Convert to RGB
            img1 = img1.convert('RGB')
            img2 = img2.convert('RGB')

            # Calculate pixel differences
            pixels1 = list(img1.getdata())
            pixels2 = list(img2.getdata())

            # Calculate similarity
            total_pixels = len(pixels1)
            different_pixels = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 != p2)

            similarity = 1 - (different_pixels / total_pixels)
            changed = similarity < threshold

            return {
                'similarity': similarity,
                'changed': changed,
                'different_pixels': different_pixels,
                'total_pixels': total_pixels
            }

        except Exception as e:
            logger.error(f"Error comparing screenshots: {e}")
            return {'similarity': 0.0, 'changed': True, 'error': str(e)}

    def detect_changes(
        self,
        old_content: Dict,
        new_content: Dict
    ) -> Dict:
        """
        Detect changes between old and new content

        Args:
            old_content: Previous content
            new_content: Current content

        Returns:
            Dict with change details
        """
        changes = {
            'changed': False,
            'changes': [],
            'similarity': 1.0
        }

        # Compare title
        if old_content.get('title') != new_content.get('title'):
            changes['changed'] = True
            changes['changes'].append('title_changed')

        # Compare meta description
        if old_content.get('meta_description') != new_content.get('meta_description'):
            changes['changed'] = True
            changes['changes'].append('meta_description_changed')

        # Compare text content
        text_similarity = self.calculate_text_similarity(
            old_content.get('text', ''),
            new_content.get('text', '')
        )

        changes['similarity'] = text_similarity

        if text_similarity < 0.95:  # 95% similarity threshold
            changes['changed'] = True
            changes['changes'].append(f'content_updated ({(1-text_similarity)*100:.1f}% modified)')

        # Compare screenshots if available
        if old_content.get('screenshot') and new_content.get('screenshot'):
            screenshot_comp = self.compare_screenshots(
                old_content['screenshot'],
                new_content['screenshot']
            )

            if screenshot_comp['changed']:
                changes['changed'] = True
                changes['changes'].append('visual_changes_detected')
                changes['visual_similarity'] = screenshot_comp['similarity']

        return changes

    async def scrape_and_compare(
        self,
        property: str,
        page_path: str
    ) -> Dict:
        """
        Scrape page and compare with previous version

        Args:
            property: Property URL
            page_path: Page path

        Returns:
            Scraping and comparison results
        """
        try:
            url = f"{property}{page_path}"

            logger.info(f"Scraping and comparing: {url}")

            # Scrape current content
            new_content = await self.scrape_page(url)

            if not new_content.get('success'):
                return new_content

            # Get previous content from database
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                previous = await conn.fetchrow("""
                    SELECT
                        text_content,
                        html_content,
                        title,
                        meta_description,
                        content_hash
                    FROM content.page_snapshots
                    WHERE property = $1
                        AND page_path = $2
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, property, page_path)

            if previous:
                old_content = {
                    'text': previous['text_content'],
                    'html': previous['html_content'],
                    'title': previous['title'],
                    'meta_description': previous['meta_description']
                }

                # Detect changes
                change_result = self.detect_changes(old_content, new_content)

                if change_result['changed']:
                    # Store change record
                    await self._store_change(
                        property,
                        page_path,
                        change_result
                    )

                    logger.info(f"Changes detected for {url}: {change_result['changes']}")

                return {
                    'url': url,
                    'changed': change_result['changed'],
                    'changes': change_result['changes'],
                    'similarity': change_result['similarity'],
                    'new_content': new_content,
                    'success': True
                }

            else:
                # First scrape, no comparison possible
                logger.info(f"First scrape for {url}, storing baseline")

                return {
                    'url': url,
                    'changed': False,
                    'message': 'First scrape, no previous version',
                    'new_content': new_content,
                    'success': True
                }

        except Exception as e:
            logger.error(f"Error in scrape_and_compare: {e}")
            return {'error': str(e), 'success': False}

    async def _store_change(
        self,
        property: str,
        page_path: str,
        change_result: Dict
    ) -> None:
        """Store change record in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO content.content_changes (
                        property,
                        page_path,
                        change_date,
                        change_type,
                        changes_summary,
                        content_similarity,
                        changed_sections
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    property,
                    page_path,
                    datetime.utcnow(),
                    'updated',
                    ', '.join(change_result['changes']),
                    change_result['similarity'],
                    change_result['changes']
                )

            logger.info(f"Stored change record for {property}{page_path}")

        except Exception as e:
            logger.error(f"Error storing change: {e}")

    async def monitor_property(
        self,
        property: str,
        page_paths: List[str] = None,
        max_pages: int = 100
    ) -> Dict:
        """
        Monitor all pages for a property

        Args:
            property: Property URL
            page_paths: Optional specific pages (None = all pages)
            max_pages: Maximum pages to monitor

        Returns:
            Monitoring results
        """
        try:
            pool = await self.get_pool()

            # Get pages to monitor
            if not page_paths:
                async with pool.acquire() as conn:
                    results = await conn.fetch("""
                        SELECT DISTINCT page_path
                        FROM content.page_snapshots
                        WHERE property = $1
                        ORDER BY snapshot_date DESC
                        LIMIT $2
                    """, property, max_pages)

                    page_paths = [r['page_path'] for r in results]

            logger.info(f"Monitoring {len(page_paths)} pages for {property}")

            results = {
                'property': property,
                'pages_monitored': 0,
                'changes_detected': 0,
                'errors': 0,
                'changes': []
            }

            for page_path in page_paths:
                result = await self.scrape_and_compare(property, page_path)

                results['pages_monitored'] += 1

                if result.get('success'):
                    if result.get('changed'):
                        results['changes_detected'] += 1
                        results['changes'].append({
                            'page_path': page_path,
                            'changes': result['changes']
                        })
                else:
                    results['errors'] += 1

            logger.info(
                f"Monitoring complete: {results['pages_monitored']} pages, "
                f"{results['changes_detected']} changes detected"
            )

            return results

        except Exception as e:
            logger.error(f"Error monitoring property: {e}")
            return {'error': str(e), 'success': False}

    def monitor_property_sync(
        self,
        property: str,
        page_paths: List[str] = None
    ) -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.monitor_property(property, page_paths))
