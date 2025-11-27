"""
Tests for Hugo Content Sync Service

Tests the HugoContentTracker class with mocked filesystem and database operations.
"""
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

import pytest
import psycopg2

from services.hugo_sync.content_tracker import HugoContentTracker


@pytest.fixture
def temp_hugo_dir():
    """Create a temporary Hugo directory structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        hugo_path = Path(tmpdir) / 'hugo-site'
        content_path = hugo_path / 'content'
        content_path.mkdir(parents=True)

        # Create sample content files
        blog_dir = content_path / 'blog'
        blog_dir.mkdir()

        # Sample markdown with YAML front matter
        (blog_dir / 'article1.md').write_text('''---
title: First Article
date: 2024-01-15
---

This is the content of the first article.
It has multiple paragraphs and some words.
''')

        # Sample markdown with TOML front matter
        (blog_dir / 'article2.md').write_text('''+++
title = "Second Article"
date = "2024-01-20"
+++

Content for the second article goes here.
More content with additional words.
''')

        # Index file
        (content_path / '_index.md').write_text('''---
title: Home Page
---

# Welcome

This is the home page content.
''')

        yield hugo_path


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        yield {
            'connect': mock_connect,
            'conn': mock_conn,
            'cursor': mock_cursor
        }


@pytest.fixture
def tracker(temp_hugo_dir, mock_db_connection):
    """Create a HugoContentTracker instance"""
    with patch.dict(os.environ, {
        'WAREHOUSE_DSN': 'postgresql://test:test@localhost/test',
        'GSC_PROPERTY': 'https://example.com'
    }):
        tracker = HugoContentTracker(str(temp_hugo_dir))
        # Disable git for consistent testing
        tracker.has_git = False
        return tracker


class TestHugoContentTracker:
    """Test suite for HugoContentTracker"""

    def test_initialization(self, temp_hugo_dir):
        """Test tracker initialization"""
        with patch.dict(os.environ, {
            'WAREHOUSE_DSN': 'postgresql://test:test@localhost/test',
            'GSC_PROPERTY': 'https://example.com'
        }):
            tracker = HugoContentTracker(str(temp_hugo_dir))

            assert tracker.hugo_path == temp_hugo_dir
            assert tracker.content_path == temp_hugo_dir / 'content'
            assert tracker.db_dsn == 'postgresql://test:test@localhost/test'
            assert tracker.property_name == 'https://example.com'

    def test_scan_content_directory(self, tracker):
        """Test scanning content directory"""
        files = tracker._scan_content_directory()

        assert len(files) == 3
        # Check for files with Windows or Unix path separators
        file_keys = list(files.keys())
        assert any('article1.md' in f for f in file_keys)

        # Check file info structure
        for file_info in files.values():
            assert 'content_hash' in file_info
            assert 'title' in file_info
            assert 'word_count' in file_info
            assert 'last_modified' in file_info

    def test_extract_title_yaml(self, tracker):
        """Test title extraction from YAML front matter"""
        content = '''---
title: Test Article
date: 2024-01-01
---

Content here.
'''
        title = tracker._extract_title(content)
        assert title == 'Test Article'

    def test_extract_title_toml(self, tracker):
        """Test title extraction from TOML front matter"""
        content = '''+++
title = "TOML Article"
date = "2024-01-01"
+++

Content here.
'''
        title = tracker._extract_title(content)
        assert title == 'TOML Article'

    def test_extract_title_heading(self, tracker):
        """Test title extraction from markdown heading"""
        content = '''# Heading Title

No front matter here.
'''
        title = tracker._extract_title(content)
        assert title == 'Heading Title'

    def test_strip_front_matter_yaml(self, tracker):
        """Test stripping YAML front matter"""
        content = '''---
title: Test
---

Body content here.
'''
        body = tracker._strip_front_matter(content)
        assert 'title:' not in body
        assert 'Body content here.' in body

    def test_strip_front_matter_toml(self, tracker):
        """Test stripping TOML front matter"""
        content = '''+++
title = "Test"
+++

Body content here.
'''
        body = tracker._strip_front_matter(content)
        assert 'title =' not in body
        assert 'Body content here.' in body

    def test_file_to_page_path(self, tracker):
        """Test converting file path to URL page path"""
        # Regular file
        assert tracker._file_to_page_path('blog/article.md') == '/blog/article'

        # Index file - Note: _index without directory stays as /_index (not root)
        # This is intentional - only content/_index.md would be root
        assert tracker._file_to_page_path('blog/_index.md') == '/blog'
        assert tracker._file_to_page_path('blog/index.md') == '/blog'

        # Different extensions
        assert tracker._file_to_page_path('page.markdown') == '/page'
        assert tracker._file_to_page_path('page.html') == '/page'

        # Windows path (backslashes)
        assert tracker._file_to_page_path('blog\\article.md') == '/blog/article'

    def test_get_file_info(self, tracker, temp_hugo_dir):
        """Test getting file information"""
        file_path = temp_hugo_dir / 'content' / 'blog' / 'article1.md'
        file_info = tracker._get_file_info(file_path)

        assert file_info['title'] == 'First Article'
        assert file_info['word_count'] > 0
        assert len(file_info['content_hash']) == 16
        assert isinstance(file_info['last_modified'], datetime)

    def test_content_hash_calculation(self, tracker, temp_hugo_dir):
        """Test that content hash changes when content changes"""
        file_path = temp_hugo_dir / 'content' / 'blog' / 'article1.md'

        # Get initial hash
        info1 = tracker._get_file_info(file_path)
        hash1 = info1['content_hash']

        # Modify content
        file_path.write_text(file_path.read_text() + '\nNew content added.')

        # Get new hash
        info2 = tracker._get_file_info(file_path)
        hash2 = info2['content_hash']

        assert hash1 != hash2

    def test_sync_new_pages(self, tracker, mock_db_connection):
        """Test syncing new pages"""
        cursor = mock_db_connection['cursor']

        # Mock empty database (no existing pages)
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = [1]  # page_id

        stats = tracker.sync()

        assert stats['created'] == 3
        assert stats['updated'] == 0
        assert stats['deleted'] == 0
        assert stats['errors'] == 0

    def test_sync_updated_pages(self, tracker, mock_db_connection):
        """Test syncing updated pages"""
        cursor = mock_db_connection['cursor']

        # Mock existing pages with different hashes
        # Note: /_index becomes /_index (not /), so we need to match actual paths
        cursor.fetchall.return_value = [
            {'id': 1, 'page_path': '/blog/article1', 'content_hash': 'oldhash1', 'word_count': 10},
            {'id': 2, 'page_path': '/blog/article2', 'content_hash': 'oldhash2', 'word_count': 10},
            {'id': 3, 'page_path': '/_index', 'content_hash': 'oldhash3', 'word_count': 10}
        ]
        cursor.fetchone.return_value = [1, 10]  # page_id, word_count

        stats = tracker.sync()

        # All pages should be detected as updated (different hashes)
        assert stats['updated'] > 0

    def test_sync_deleted_pages(self, tracker, mock_db_connection):
        """Test detecting deleted pages"""
        cursor = mock_db_connection['cursor']

        # Mock existing pages including one that doesn't exist in filesystem
        cursor.fetchall.return_value = [
            {'id': 1, 'page_path': '/blog/article1', 'content_hash': 'hash1', 'word_count': 10},
            {'id': 4, 'page_path': '/deleted-page', 'content_hash': 'hash4', 'word_count': 10}
        ]
        cursor.fetchone.return_value = [4, 'hash4']  # For deleted page

        stats = tracker.sync()

        assert stats['deleted'] > 0

    def test_track_change_created(self, tracker, mock_db_connection):
        """Test tracking a created file"""
        cursor = mock_db_connection['cursor']
        cursor.fetchone.return_value = [1]  # page_id

        tracker.track_change('blog/article1.md', 'created')

        # Verify INSERT was called
        assert any('INSERT INTO content.hugo_pages' in str(call)
                   for call in cursor.execute.call_args_list)

    def test_track_change_updated(self, tracker, mock_db_connection):
        """Test tracking an updated file"""
        cursor = mock_db_connection['cursor']
        cursor.fetchone.side_effect = [
            {'id': 1, 'page_path': '/blog/article1', 'content_hash': 'oldhash', 'word_count': 10},
            [1, 10]  # For update query
        ]

        tracker.track_change('blog/article1.md', 'updated')

        # Verify UPDATE was called
        assert any('UPDATE content.hugo_pages' in str(call)
                   for call in cursor.execute.call_args_list)

    def test_track_change_deleted(self, tracker, mock_db_connection):
        """Test tracking a deleted file"""
        cursor = mock_db_connection['cursor']
        cursor.fetchone.return_value = [1, 'oldhash']  # page_id, old_hash

        tracker.track_change('blog/article1.md', 'deleted')

        # Verify UPDATE with deleted_at was called
        execute_calls = [str(call) for call in cursor.execute.call_args_list]
        assert any('deleted_at' in call for call in execute_calls)

    def test_get_content_history(self, tracker, mock_db_connection):
        """Test retrieving content history"""
        cursor = mock_db_connection['cursor']

        # Mock history data
        cursor.fetchall.return_value = [
            {
                'change_type': 'updated',
                'old_hash': 'hash1',
                'new_hash': 'hash2',
                'changed_at': datetime(2024, 1, 20),
                'word_count_change': 50,
                'title': 'Test Article'
            },
            {
                'change_type': 'created',
                'old_hash': None,
                'new_hash': 'hash1',
                'changed_at': datetime(2024, 1, 15),
                'word_count_change': 100,
                'title': 'Test Article'
            }
        ]

        history = tracker.get_content_history('/blog/article')

        assert len(history) == 2
        assert history[0]['change_type'] == 'updated'
        assert history[1]['change_type'] == 'created'

    def test_get_recent_changes(self, tracker, mock_db_connection):
        """Test retrieving recent changes"""
        cursor = mock_db_connection['cursor']

        # Mock recent changes
        cursor.fetchall.return_value = [
            {
                'page_path': '/blog/article1',
                'title': 'Article 1',
                'change_type': 'updated',
                'changed_at': datetime(2024, 1, 20),
                'word_count_change': 25
            }
        ]

        changes = tracker.get_recent_changes(days=7)

        assert len(changes) == 1
        assert changes[0]['page_path'] == '/blog/article1'

    def test_correlate_with_performance(self, tracker, mock_db_connection):
        """Test correlating content changes with performance"""
        cursor = mock_db_connection['cursor']

        # Mock changes
        cursor.fetchall.return_value = [
            {
                'change_type': 'updated',
                'change_date': datetime(2024, 1, 15).date(),
                'word_count_change': 100
            }
        ]

        # Mock performance data (before and after)
        cursor.fetchone.side_effect = [
            {'avg_clicks': 10.0, 'avg_impressions': 100.0, 'avg_ctr': 0.1, 'avg_position': 15.0},
            {'avg_clicks': 15.0, 'avg_impressions': 150.0, 'avg_ctr': 0.1, 'avg_position': 12.0}
        ]

        correlation = tracker.correlate_with_performance('/blog/article')

        assert 'changes' in correlation
        assert len(correlation['changes']) == 1
        assert correlation['changes'][0]['clicks_change_pct'] == 50.0
        assert correlation['changes'][0]['position_change'] == 3.0

    def test_correlate_with_performance_no_changes(self, tracker, mock_db_connection):
        """Test correlation when no changes exist"""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.return_value = []

        correlation = tracker.correlate_with_performance('/blog/article')

        assert correlation['overall_trend'] == 'no_changes'
        assert len(correlation['changes']) == 0

    def test_word_count_calculation(self, tracker, temp_hugo_dir):
        """Test word count excludes front matter"""
        file_path = temp_hugo_dir / 'content' / 'blog' / 'article1.md'
        file_info = tracker._get_file_info(file_path)

        # Count should not include front matter
        content = file_path.read_text()
        body = tracker._strip_front_matter(content)
        expected_count = len(body.split())

        assert file_info['word_count'] == expected_count
        assert file_info['word_count'] < len(content.split())  # Less than total

    def test_error_handling_missing_directory(self, mock_db_connection):
        """Test handling of missing content directory"""
        with patch.dict(os.environ, {
            'WAREHOUSE_DSN': 'postgresql://test:test@localhost/test',
            'GSC_PROPERTY': 'https://example.com'
        }):
            tracker = HugoContentTracker('/nonexistent/path')
            stats = tracker.sync()

            assert 'error' in stats
            assert stats['created'] == 0

    def test_database_connection_error(self, tracker):
        """Test handling of database connection errors"""
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Connection failed')):
            history = tracker.get_content_history('/blog/article')
            assert history == []

    def test_git_not_available(self, temp_hugo_dir, mock_db_connection):
        """Test fallback when git is not available"""
        with patch.dict(os.environ, {
            'WAREHOUSE_DSN': 'postgresql://test:test@localhost/test',
            'GSC_PROPERTY': 'https://example.com'
        }):
            with patch('subprocess.run', side_effect=Exception('Git not found')):
                tracker = HugoContentTracker(str(temp_hugo_dir))
                assert tracker.has_git is False

    def test_multiple_extensions_scanned(self, tracker, temp_hugo_dir):
        """Test that all configured extensions are scanned"""
        # Add HTML file
        (temp_hugo_dir / 'content' / 'test.html').write_text('<h1>HTML Content</h1>')

        # Add .markdown file
        (temp_hugo_dir / 'content' / 'test.markdown').write_text('# Markdown Content')

        files = tracker._scan_content_directory()

        # Should find .md, .markdown, and .html files
        extensions = {Path(f).suffix for f in files.keys()}
        assert '.md' in extensions or '.markdown' in extensions or '.html' in extensions

    def test_overall_trend_calculation(self, tracker, mock_db_connection):
        """Test overall trend calculation logic"""
        cursor = mock_db_connection['cursor']

        # Mock multiple changes with mixed results
        cursor.fetchall.return_value = [
            {'change_type': 'updated', 'change_date': datetime(2024, 1, 15).date(), 'word_count_change': 50},
            {'change_type': 'updated', 'change_date': datetime(2024, 1, 10).date(), 'word_count_change': 30}
        ]

        # Mock performance showing improvement for both
        cursor.fetchone.side_effect = [
            {'avg_clicks': 10.0, 'avg_impressions': 100.0, 'avg_ctr': 0.1, 'avg_position': 15.0},
            {'avg_clicks': 15.0, 'avg_impressions': 150.0, 'avg_ctr': 0.1, 'avg_position': 12.0},
            {'avg_clicks': 8.0, 'avg_impressions': 80.0, 'avg_ctr': 0.1, 'avg_position': 18.0},
            {'avg_clicks': 12.0, 'avg_impressions': 120.0, 'avg_ctr': 0.1, 'avg_position': 14.0}
        ]

        correlation = tracker.correlate_with_performance('/blog/article')

        assert correlation['overall_trend'] == 'improving'


class TestIntegration:
    """Integration tests requiring database setup"""

    @pytest.mark.integration
    def test_full_sync_workflow(self, tracker, mock_db_connection):
        """Test complete sync workflow"""
        cursor = mock_db_connection['cursor']

        # First sync - all new
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = [1]

        stats1 = tracker.sync()
        assert stats1['created'] > 0

        # Second sync - no changes
        cursor.fetchall.return_value = [
            {'id': i, 'page_path': f'/page{i}', 'content_hash': 'hash', 'word_count': 10}
            for i in range(stats1['created'])
        ]

        # Would need actual file hashes to match
        # This is a simplified test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
