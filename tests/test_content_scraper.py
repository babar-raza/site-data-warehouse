"""
Tests for Content Scraper Module
=================================
Tests Playwright-based content scraping and change detection.
"""
import os
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from services.content_scraper import ContentScraper, ChangeDetector, ScreenshotComparer


@pytest.fixture
async def scraper():
    """Create ContentScraper instance"""
    scraper = ContentScraper(
        db_dsn=os.getenv('TEST_WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db')
    )
    yield scraper
    await scraper.close()


@pytest.fixture
def change_detector():
    """Create ChangeDetector instance"""
    return ChangeDetector()


@pytest.fixture
def screenshot_comparer():
    """Create ScreenshotComparer instance"""
    return ScreenshotComparer()


@pytest.fixture
def sample_html():
    """Sample HTML content"""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Main Heading</h1>
        <p>This is the first paragraph with some content.</p>
        <p>This is the second paragraph with more content.</p>
        <div class="section">
            <h2>Section Heading</h2>
            <p>Section content goes here.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_modified_html():
    """Modified HTML content"""
    return """
    <html>
    <head><title>Test Page - Updated</title></head>
    <body>
        <h1>Main Heading Updated</h1>
        <p>This is the first paragraph with some CHANGED content.</p>
        <p>This is the second paragraph with more content.</p>
        <div class="section">
            <h2>New Section Heading</h2>
            <p>Section content has been modified.</p>
            <p>Added new paragraph.</p>
        </div>
    </body>
    </html>
    """


# =============================================
# CONTENT SCRAPING TESTS
# =============================================

@pytest.mark.asyncio
async def test_scrape_page_success(scraper):
    """Test successful page scraping"""
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        # Mock Playwright browser
        mock_page = AsyncMock()
        mock_page.goto.return_value = None
        mock_page.content.return_value = "<html><body>Test</body></html>"
        mock_page.title.return_value = "Test Page"
        mock_page.screenshot.return_value = b'fake_screenshot_data'

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance

        result = await scraper.scrape_page('https://example.com/test/')

    assert result['success'] is True
    assert result['html'] == "<html><body>Test</body></html>"
    assert result['title'] == "Test Page"
    assert 'screenshot' in result
    assert result['url'] == 'https://example.com/test/'


@pytest.mark.asyncio
async def test_scrape_page_timeout(scraper):
    """Test page scraping timeout"""
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_page = AsyncMock()
        mock_page.goto.side_effect = TimeoutError("Page load timeout")

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance

        result = await scraper.scrape_page('https://example.com/slow/')

    assert result['success'] is False
    assert 'error' in result


@pytest.mark.asyncio
async def test_scrape_page_404(scraper):
    """Test scraping non-existent page"""
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_page = AsyncMock()
        mock_response = Mock()
        mock_response.status = 404
        mock_page.goto.return_value = mock_response

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance

        result = await scraper.scrape_page('https://example.com/404/')

    assert result['success'] is False


@pytest.mark.asyncio
async def test_extract_text_from_html(scraper, sample_html):
    """Test text extraction from HTML"""
    text = await scraper.extract_text(sample_html)

    assert 'Main Heading' in text
    assert 'first paragraph' in text
    assert 'Section content' in text
    # Should not contain HTML tags
    assert '<html>' not in text
    assert '<p>' not in text


@pytest.mark.asyncio
async def test_extract_text_removes_scripts(scraper):
    """Test that scripts are removed during extraction"""
    html_with_script = """
    <html>
    <body>
        <p>Visible content</p>
        <script>alert('This should not appear');</script>
        <style>.hidden { display: none; }</style>
    </body>
    </html>
    """

    text = await scraper.extract_text(html_with_script)

    assert 'Visible content' in text
    assert 'alert' not in text
    assert '.hidden' not in text


# =============================================
# CHANGE DETECTION TESTS
# =============================================

def test_detect_changes_no_change(change_detector):
    """Test no changes detected when content is identical"""
    old_content = {
        'html': '<html><body>Test</body></html>',
        'text': 'Test',
        'title': 'Test Page'
    }

    new_content = old_content.copy()

    result = change_detector.detect_changes(old_content, new_content)

    assert result['changed'] is False
    assert result['change_score'] == 0.0


def test_detect_changes_title_change(change_detector):
    """Test title change detection"""
    old_content = {
        'html': '<html><body>Test</body></html>',
        'text': 'Test',
        'title': 'Old Title'
    }

    new_content = {
        'html': '<html><body>Test</body></html>',
        'text': 'Test',
        'title': 'New Title'
    }

    result = change_detector.detect_changes(old_content, new_content)

    assert result['changed'] is True
    assert 'title' in result['changes']


def test_detect_changes_text_modification(change_detector):
    """Test text content modification detection"""
    old_content = {
        'html': '<html><body><p>Original content here</p></body></html>',
        'text': 'Original content here',
        'title': 'Test'
    }

    new_content = {
        'html': '<html><body><p>Modified content here</p></body></html>',
        'text': 'Modified content here',
        'title': 'Test'
    }

    result = change_detector.detect_changes(old_content, new_content)

    assert result['changed'] is True
    assert result['change_score'] > 0


def test_detect_changes_major_update(change_detector, sample_html, sample_modified_html):
    """Test major content update detection"""
    old_content = {
        'html': sample_html,
        'text': 'Original text with lots of content here',
        'title': 'Test Page'
    }

    new_content = {
        'html': sample_modified_html,
        'text': 'Completely different text content',
        'title': 'Test Page - Updated'
    }

    result = change_detector.detect_changes(old_content, new_content)

    assert result['changed'] is True
    assert result['change_type'] in ['major', 'moderate']
    assert result['change_score'] > 30


def test_calculate_text_similarity(change_detector):
    """Test Levenshtein distance calculation"""
    text1 = "The quick brown fox"
    text2 = "The quick brown dog"

    similarity = change_detector.calculate_text_similarity(text1, text2)

    # Should be very similar (only one word different)
    assert 0.7 < similarity < 1.0


def test_calculate_text_similarity_identical(change_detector):
    """Test similarity of identical texts"""
    text = "The quick brown fox jumps over the lazy dog"

    similarity = change_detector.calculate_text_similarity(text, text)

    assert similarity == 1.0


def test_calculate_text_similarity_completely_different(change_detector):
    """Test similarity of completely different texts"""
    text1 = "The quick brown fox"
    text2 = "xyz abc def ghi"

    similarity = change_detector.calculate_text_similarity(text1, text2)

    assert similarity < 0.3


def test_classify_change_type(change_detector):
    """Test change type classification"""
    # Minor change
    assert change_detector.classify_change_type(5.0) == 'minor'

    # Moderate change
    assert change_detector.classify_change_type(25.0) == 'moderate'

    # Major change
    assert change_detector.classify_change_type(60.0) == 'major'


# =============================================
# SCREENSHOT COMPARISON TESTS
# =============================================

def test_compare_screenshots_identical(screenshot_comparer):
    """Test comparison of identical screenshots"""
    from PIL import Image

    # Create identical images
    img1 = Image.new('RGB', (100, 100), color='red')
    img2 = Image.new('RGB', (100, 100), color='red')

    similarity = screenshot_comparer.compare(img1, img2)

    assert similarity == 1.0


def test_compare_screenshots_different(screenshot_comparer):
    """Test comparison of different screenshots"""
    from PIL import Image

    # Create different images
    img1 = Image.new('RGB', (100, 100), color='red')
    img2 = Image.new('RGB', (100, 100), color='blue')

    similarity = screenshot_comparer.compare(img1, img2)

    assert similarity < 0.5


def test_compare_screenshots_size_mismatch(screenshot_comparer):
    """Test comparison of different sized images"""
    from PIL import Image

    img1 = Image.new('RGB', (100, 100), color='red')
    img2 = Image.new('RGB', (200, 200), color='red')

    # Should resize and compare
    similarity = screenshot_comparer.compare(img1, img2)

    # Should still be similar after resize
    assert similarity > 0.8


# =============================================
# DATABASE OPERATIONS TESTS
# =============================================

@pytest.mark.asyncio
async def test_get_previous_snapshot(scraper):
    """Test fetching previous snapshot from database"""
    with patch.object(scraper, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            'snapshot_id': 'snap-123',
            'html_content': '<html><body>Old</body></html>',
            'plain_text': 'Old',
            'title': 'Old Title',
            'word_count': 100,
            'screenshot': b'old_screenshot'
        }

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        snapshot = await scraper._get_previous_snapshot(
            'https://example.com',
            '/page/'
        )

    assert snapshot['title'] == 'Old Title'
    assert snapshot['word_count'] == 100


@pytest.mark.asyncio
async def test_get_previous_snapshot_not_found(scraper):
    """Test when no previous snapshot exists"""
    with patch.object(scraper, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        snapshot = await scraper._get_previous_snapshot(
            'https://example.com',
            '/new-page/'
        )

    assert snapshot is None


@pytest.mark.asyncio
async def test_store_snapshot(scraper):
    """Test storing new snapshot"""
    content = {
        'html': '<html><body>Test</body></html>',
        'text': 'Test content here',
        'title': 'Test Page',
        'screenshot': b'screenshot_data'
    }

    with patch.object(scraper, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 'snap-456'

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        snapshot_id = await scraper._store_snapshot(
            'https://example.com',
            '/page/',
            content
        )

    assert snapshot_id == 'snap-456'


@pytest.mark.asyncio
async def test_store_change_record(scraper):
    """Test storing change record"""
    change_result = {
        'changed': True,
        'change_type': 'moderate',
        'change_score': 35.5,
        'changes': ['title', 'content'],
        'similarity': 0.75
    }

    with patch.object(scraper, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        await scraper._store_change(
            'https://example.com',
            '/page/',
            'snap-old',
            'snap-new',
            change_result
        )

    # Verify insert was called
    assert mock_conn.execute.called


# =============================================
# END-TO-END WORKFLOW TESTS
# =============================================

@pytest.mark.asyncio
async def test_scrape_and_compare_first_scrape(scraper):
    """Test first scrape (no previous snapshot)"""
    with patch.object(scraper, 'scrape_page') as mock_scrape:
        mock_scrape.return_value = {
            'success': True,
            'html': '<html><body>New</body></html>',
            'title': 'New Page',
            'screenshot': b'screenshot'
        }

        with patch.object(scraper, 'extract_text') as mock_extract:
            mock_extract.return_value = 'New page content'

            with patch.object(scraper, '_get_previous_snapshot') as mock_prev:
                mock_prev.return_value = None

                with patch.object(scraper, '_store_snapshot') as mock_store:
                    mock_store.return_value = 'snap-1'

                    result = await scraper.scrape_and_compare(
                        'https://example.com',
                        '/new-page/'
                    )

    assert result['success'] is True
    assert result['first_scrape'] is True
    assert 'changed' not in result


@pytest.mark.asyncio
async def test_scrape_and_compare_with_changes(scraper):
    """Test scraping with detected changes"""
    with patch.object(scraper, 'scrape_page') as mock_scrape:
        mock_scrape.return_value = {
            'success': True,
            'html': '<html><body>New content</body></html>',
            'title': 'Updated Page',
            'screenshot': b'new_screenshot'
        }

        with patch.object(scraper, 'extract_text') as mock_extract:
            mock_extract.return_value = 'New content here'

            with patch.object(scraper, '_get_previous_snapshot') as mock_prev:
                mock_prev.return_value = {
                    'snapshot_id': 'snap-old',
                    'html_content': '<html><body>Old content</body></html>',
                    'plain_text': 'Old content here',
                    'title': 'Old Page',
                    'screenshot': b'old_screenshot'
                }

                with patch.object(scraper, 'change_detector') as mock_detector:
                    mock_detector.detect_changes.return_value = {
                        'changed': True,
                        'change_type': 'moderate',
                        'change_score': 40.0,
                        'changes': ['title', 'content']
                    }

                    with patch.object(scraper, '_store_snapshot') as mock_store_snap:
                        mock_store_snap.return_value = 'snap-new'

                        with patch.object(scraper, '_store_change') as mock_store_change:
                            mock_store_change.return_value = None

                            result = await scraper.scrape_and_compare(
                                'https://example.com',
                                '/page/'
                            )

    assert result['success'] is True
    assert result['changed'] is True
    assert result['change_type'] == 'moderate'


@pytest.mark.asyncio
async def test_scrape_and_compare_no_changes(scraper):
    """Test scraping with no changes"""
    same_content = {
        'html': '<html><body>Same</body></html>',
        'text': 'Same content',
        'title': 'Same Title',
        'screenshot': b'same_screenshot'
    }

    with patch.object(scraper, 'scrape_page') as mock_scrape:
        mock_scrape.return_value = {
            'success': True,
            **same_content
        }

        with patch.object(scraper, 'extract_text') as mock_extract:
            mock_extract.return_value = same_content['text']

            with patch.object(scraper, '_get_previous_snapshot') as mock_prev:
                mock_prev.return_value = {
                    'snapshot_id': 'snap-old',
                    'html_content': same_content['html'],
                    'plain_text': same_content['text'],
                    'title': same_content['title'],
                    'screenshot': same_content['screenshot']
                }

                with patch.object(scraper, 'change_detector') as mock_detector:
                    mock_detector.detect_changes.return_value = {
                        'changed': False,
                        'change_score': 0.0
                    }

                    result = await scraper.scrape_and_compare(
                        'https://example.com',
                        '/page/'
                    )

    assert result['success'] is True
    assert result['changed'] is False


# =============================================
# MONITORING WORKFLOW TESTS
# =============================================

@pytest.mark.asyncio
async def test_monitor_property(scraper):
    """Test monitoring multiple pages"""
    pages = ['/page1/', '/page2/', '/page3/']

    with patch.object(scraper, 'scrape_and_compare') as mock_scrape:
        mock_scrape.side_effect = [
            {'success': True, 'changed': True, 'change_type': 'moderate'},
            {'success': True, 'changed': False},
            {'success': False, 'error': 'Page not found'}
        ]

        result = await scraper.monitor_property(
            'https://example.com',
            page_paths=pages
        )

    assert result['pages_monitored'] == 3
    assert result['changes_detected'] == 1
    assert result['errors'] == 1


@pytest.mark.asyncio
async def test_monitor_property_sync_wrapper(scraper):
    """Test synchronous wrapper for monitoring"""
    with patch.object(scraper, 'monitor_property') as mock_monitor:
        mock_monitor.return_value = {
            'pages_monitored': 5,
            'changes_detected': 2,
            'errors': 0
        }

        result = scraper.monitor_property_sync(
            'https://example.com',
            page_paths=['/page1/', '/page2/']
        )

    assert result['pages_monitored'] == 5
    assert result['changes_detected'] == 2


# =============================================
# ERROR HANDLING TESTS
# =============================================

@pytest.mark.asyncio
async def test_scrape_page_browser_crash(scraper):
    """Test handling browser crash"""
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright.side_effect = Exception("Browser crashed")

        result = await scraper.scrape_page('https://example.com/page/')

    assert result['success'] is False
    assert 'error' in result


@pytest.mark.asyncio
async def test_scrape_and_compare_db_error(scraper):
    """Test handling database error"""
    with patch.object(scraper, 'scrape_page') as mock_scrape:
        mock_scrape.return_value = {
            'success': True,
            'html': '<html></html>',
            'title': 'Test',
            'screenshot': b'data'
        }

        with patch.object(scraper, '_get_previous_snapshot') as mock_prev:
            mock_prev.side_effect = Exception("Database connection failed")

            result = await scraper.scrape_and_compare(
                'https://example.com',
                '/page/'
            )

    assert result['success'] is False


# =============================================
# INTEGRATION TESTS
# =============================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_page_scraping():
    """Integration test with real browser"""
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    scraper = ContentScraper()

    try:
        result = await scraper.scrape_page('https://example.com/')

        assert result['success'] is True
        assert len(result['html']) > 0
        assert len(result['title']) > 0

    finally:
        await scraper.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
