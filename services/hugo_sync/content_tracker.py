"""
Hugo Content Tracker - Tracks content changes and correlates with performance

Monitors Hugo CMS content directory for changes and maintains a database
of content versions to correlate with GSC performance data.

Example:
    tracker = HugoContentTracker('/path/to/hugo/content')
    tracker.sync()
    history = tracker.get_content_history('/blog/article.md')
    correlation = tracker.correlate_with_performance('/blog/article')
"""
import hashlib
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class HugoContentTracker:
    """
    Tracks Hugo CMS content changes and correlates with SEO performance

    Features:
    - Scans Hugo content directory for markdown files
    - Calculates content hashes for change detection
    - Tracks content history (created, updated, deleted)
    - Correlates content changes with GSC performance metrics
    - Uses git history when available for accurate timestamps

    Example:
        tracker = HugoContentTracker('/path/to/hugo')

        # Sync all content to database
        stats = tracker.sync()
        print(f"Synced {stats['updated']} pages")

        # Get change history for a page
        history = tracker.get_content_history('/blog/my-article')

        # Correlate with performance
        correlation = tracker.correlate_with_performance('/blog/my-article')
    """

    # File extensions to track
    CONTENT_EXTENSIONS = {'.md', '.markdown', '.html'}

    # Front matter patterns
    FRONT_MATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    TOML_FRONT_MATTER_PATTERN = re.compile(r'^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n', re.DOTALL)

    def __init__(self, hugo_path: str, db_dsn: str = None, property_name: str = None):
        """
        Initialize Hugo Content Tracker

        Args:
            hugo_path: Path to Hugo site root (contains 'content' directory)
            db_dsn: Database connection string
            property_name: Property identifier for GSC data correlation
        """
        self.hugo_path = Path(hugo_path)
        self.content_path = self.hugo_path / 'content'
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.property_name = property_name or os.getenv('GSC_PROPERTY')

        # Check if git is available
        self.has_git = self._check_git()

        logger.info(f"HugoContentTracker initialized for {hugo_path}")
        if self.has_git:
            logger.info("Git history available for accurate timestamps")

    def _check_git(self) -> bool:
        """Check if the Hugo directory is a git repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=str(self.hugo_path),
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def sync(self) -> Dict:
        """
        Sync all content to database

        Scans the content directory and updates the database with
        current content state, tracking any changes.

        Returns:
            Dict with sync statistics

        Example:
            >>> tracker = HugoContentTracker('/path/to/hugo')
            >>> stats = tracker.sync()
            >>> print(f"Created: {stats['created']}, Updated: {stats['updated']}")
        """
        if not self.content_path.exists():
            logger.error(f"Content path does not exist: {self.content_path}")
            return {'error': 'Content path not found', 'created': 0, 'updated': 0, 'deleted': 0}

        stats = {
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'deleted': 0,
            'errors': 0,
            'synced_at': datetime.now().isoformat()
        }

        # Get current content files
        current_files = self._scan_content_directory()
        logger.info(f"Found {len(current_files)} content files")

        # Get existing pages from database
        existing_pages = self._get_existing_pages()
        existing_paths = {p['page_path'] for p in existing_pages}

        # Process each file
        for file_path, file_info in current_files.items():
            try:
                page_path = self._file_to_page_path(file_path)

                if page_path in existing_paths:
                    # Check for updates
                    existing = next(p for p in existing_pages if p['page_path'] == page_path)
                    if existing['content_hash'] != file_info['content_hash']:
                        self._update_page(page_path, file_info, existing['content_hash'])
                        stats['updated'] += 1
                    else:
                        stats['unchanged'] += 1
                else:
                    # New page
                    self._create_page(page_path, file_info)
                    stats['created'] += 1

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats['errors'] += 1

        # Mark deleted pages
        current_paths = {self._file_to_page_path(f) for f in current_files}
        for existing_path in existing_paths:
            if existing_path not in current_paths:
                self._mark_deleted(existing_path)
                stats['deleted'] += 1

        logger.info(f"Sync complete: {stats}")
        return stats

    def track_change(self, file_path: str, change_type: str) -> None:
        """
        Track a specific content change

        Args:
            file_path: Path to the changed file
            change_type: Type of change ('created', 'updated', 'deleted')

        Example:
            >>> tracker.track_change('/blog/new-post.md', 'created')
        """
        page_path = self._file_to_page_path(file_path)

        if change_type == 'deleted':
            self._mark_deleted(page_path)
        else:
            full_path = self.content_path / file_path
            if full_path.exists():
                file_info = self._get_file_info(full_path)

                if change_type == 'created':
                    self._create_page(page_path, file_info)
                else:
                    existing = self._get_page(page_path)
                    old_hash = existing['content_hash'] if existing else None
                    self._update_page(page_path, file_info, old_hash)

        logger.info(f"Tracked {change_type} change for {page_path}")

    def get_content_history(self, page_path: str) -> List[Dict]:
        """
        Get change history for a page

        Args:
            page_path: URL path of the page

        Returns:
            List of changes with timestamps and types

        Example:
            >>> history = tracker.get_content_history('/blog/my-article')
            >>> for change in history:
            ...     print(f"{change['changed_at']}: {change['change_type']}")
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    c.change_type,
                    c.old_hash,
                    c.new_hash,
                    c.changed_at,
                    c.word_count_change,
                    p.title
                FROM content.hugo_changes c
                JOIN content.hugo_pages p ON c.page_id = p.id
                WHERE p.page_path = %s
                  AND p.property = %s
                ORDER BY c.changed_at DESC
            """, (page_path, self.property_name))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting content history: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def correlate_with_performance(self, page_path: str, days_before: int = 7,
                                    days_after: int = 30) -> Dict:
        """
        Correlate content changes with GSC performance

        Analyzes how content changes affected search performance
        by comparing metrics before and after changes.

        Args:
            page_path: URL path of the page
            days_before: Days before change to analyze
            days_after: Days after change to analyze

        Returns:
            Dict with correlation analysis

        Example:
            >>> correlation = tracker.correlate_with_performance('/blog/article')
            >>> if correlation['changes']:
            ...     for c in correlation['changes']:
            ...         print(f"Change on {c['date']}: {c['clicks_change']}% click change")
        """
        conn = None
        cursor = None
        result = {
            'page_path': page_path,
            'changes': [],
            'overall_trend': 'insufficient_data'
        }

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get content changes
            cursor.execute("""
                SELECT
                    c.change_type,
                    c.changed_at::date as change_date,
                    c.word_count_change
                FROM content.hugo_changes c
                JOIN content.hugo_pages p ON c.page_id = p.id
                WHERE p.page_path = %s
                  AND p.property = %s
                  AND c.changed_at >= CURRENT_DATE - INTERVAL '90 days'
                ORDER BY c.changed_at DESC
            """, (page_path, self.property_name))

            changes = cursor.fetchall()

            if not changes:
                result['overall_trend'] = 'no_changes'
                return result

            # For each change, get performance before and after
            for change in changes:
                change_date = change['change_date']

                # Get performance before change
                cursor.execute("""
                    SELECT
                        AVG(clicks) as avg_clicks,
                        AVG(impressions) as avg_impressions,
                        AVG(ctr) as avg_ctr,
                        AVG(position) as avg_position
                    FROM gsc.search_performance
                    WHERE property = %s
                      AND page LIKE %s
                      AND date BETWEEN %s - INTERVAL '%s days' AND %s - INTERVAL '1 day'
                """, (
                    self.property_name,
                    f'%{page_path}%',
                    change_date,
                    days_before,
                    change_date
                ))
                before = cursor.fetchone()

                # Get performance after change
                cursor.execute("""
                    SELECT
                        AVG(clicks) as avg_clicks,
                        AVG(impressions) as avg_impressions,
                        AVG(ctr) as avg_ctr,
                        AVG(position) as avg_position
                    FROM gsc.search_performance
                    WHERE property = %s
                      AND page LIKE %s
                      AND date BETWEEN %s + INTERVAL '1 day' AND %s + INTERVAL '%s days'
                """, (
                    self.property_name,
                    f'%{page_path}%',
                    change_date,
                    change_date,
                    days_after
                ))
                after = cursor.fetchone()

                # Calculate change percentages
                change_analysis = {
                    'date': change_date.isoformat() if hasattr(change_date, 'isoformat') else str(change_date),
                    'change_type': change['change_type'],
                    'word_count_change': change['word_count_change'],
                    'performance_before': dict(before) if before else None,
                    'performance_after': dict(after) if after else None,
                }

                # Calculate percentage changes
                if before and after and before.get('avg_clicks') and after.get('avg_clicks'):
                    before_clicks = before['avg_clicks'] or 0.001
                    change_analysis['clicks_change_pct'] = round(
                        ((after['avg_clicks'] - before_clicks) / before_clicks) * 100, 2
                    )

                if before and after and before.get('avg_position') and after.get('avg_position'):
                    change_analysis['position_change'] = round(
                        before['avg_position'] - after['avg_position'], 2
                    )

                result['changes'].append(change_analysis)

            # Determine overall trend
            if result['changes']:
                positive_changes = sum(
                    1 for c in result['changes']
                    if c.get('clicks_change_pct', 0) > 0
                )
                if positive_changes > len(result['changes']) / 2:
                    result['overall_trend'] = 'improving'
                elif positive_changes < len(result['changes']) / 2:
                    result['overall_trend'] = 'declining'
                else:
                    result['overall_trend'] = 'stable'

            return result

        except Exception as e:
            logger.error(f"Error correlating with performance: {e}")
            result['error'] = str(e)
            return result

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_recent_changes(self, days: int = 7, limit: int = 50) -> List[Dict]:
        """
        Get recent content changes

        Args:
            days: Number of days to look back
            limit: Maximum number of changes to return

        Returns:
            List of recent changes
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    p.page_path,
                    p.title,
                    c.change_type,
                    c.changed_at,
                    c.word_count_change
                FROM content.hugo_changes c
                JOIN content.hugo_pages p ON c.page_id = p.id
                WHERE p.property = %s
                  AND c.changed_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY c.changed_at DESC
                LIMIT %s
            """, (self.property_name, days, limit))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting recent changes: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _scan_content_directory(self) -> Dict[str, Dict]:
        """Scan content directory for all files"""
        files = {}

        for ext in self.CONTENT_EXTENSIONS:
            for file_path in self.content_path.rglob(f'*{ext}'):
                rel_path = file_path.relative_to(self.content_path)
                files[str(rel_path)] = self._get_file_info(file_path)

        return files

    def _get_file_info(self, file_path: Path) -> Dict:
        """Get information about a content file"""
        try:
            content = file_path.read_text(encoding='utf-8')

            # Calculate hash
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

            # Extract front matter
            title = self._extract_title(content)

            # Count words (excluding front matter)
            body = self._strip_front_matter(content)
            word_count = len(body.split())

            # Get modification time
            if self.has_git:
                last_modified = self._get_git_modified_time(file_path)
            else:
                stat = file_path.stat()
                last_modified = datetime.fromtimestamp(stat.st_mtime)

            return {
                'content_hash': content_hash,
                'title': title,
                'word_count': word_count,
                'last_modified': last_modified
            }

        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {
                'content_hash': '',
                'title': '',
                'word_count': 0,
                'last_modified': datetime.utcnow()
            }

    def _extract_title(self, content: str) -> str:
        """Extract title from front matter"""
        # Try YAML front matter
        match = self.FRONT_MATTER_PATTERN.match(content)
        if match:
            front_matter = match.group(1)
            for line in front_matter.split('\n'):
                if line.startswith('title:'):
                    return line[6:].strip().strip('"\'')

        # Try TOML front matter
        match = self.TOML_FRONT_MATTER_PATTERN.match(content)
        if match:
            front_matter = match.group(1)
            for line in front_matter.split('\n'):
                if line.startswith('title'):
                    parts = line.split('=', 1)
                    if len(parts) > 1:
                        return parts[1].strip().strip('"\'')

        # Try first heading
        for line in content.split('\n'):
            if line.startswith('# '):
                return line[2:].strip()

        return ''

    def _strip_front_matter(self, content: str) -> str:
        """Remove front matter from content"""
        # Remove YAML front matter
        content = self.FRONT_MATTER_PATTERN.sub('', content)
        # Remove TOML front matter
        content = self.TOML_FRONT_MATTER_PATTERN.sub('', content)
        return content

    def _get_git_modified_time(self, file_path: Path) -> datetime:
        """Get last modified time from git"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cI', '--', str(file_path)],
                cwd=str(self.hugo_path),
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return datetime.fromisoformat(result.stdout.strip().replace('Z', '+00:00'))
        except Exception:
            pass

        # Fallback to file stat
        stat = file_path.stat()
        return datetime.fromtimestamp(stat.st_mtime)

    def _file_to_page_path(self, file_path: str) -> str:
        """Convert file path to URL page path"""
        # Remove extension
        path = re.sub(r'\.(md|markdown|html)$', '', file_path)
        # Handle index files
        path = re.sub(r'/_?index$', '', path)
        # Ensure leading slash
        if not path.startswith('/'):
            path = '/' + path
        # Convert backslashes to forward slashes (Windows compatibility)
        path = path.replace('\\', '/')
        return path

    def _get_existing_pages(self) -> List[Dict]:
        """Get all existing pages from database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT id, page_path, content_hash, word_count
                FROM content.hugo_pages
                WHERE property = %s
                  AND deleted_at IS NULL
            """, (self.property_name,))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting existing pages: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_page(self, page_path: str) -> Optional[Dict]:
        """Get a single page from database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT id, page_path, content_hash, word_count
                FROM content.hugo_pages
                WHERE property = %s
                  AND page_path = %s
            """, (self.property_name, page_path))

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting page: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _create_page(self, page_path: str, file_info: Dict) -> None:
        """Create new page in database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            # Insert page
            cursor.execute("""
                INSERT INTO content.hugo_pages (
                    property, page_path, title, content_hash, word_count, last_modified
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                self.property_name,
                page_path,
                file_info['title'],
                file_info['content_hash'],
                file_info['word_count'],
                file_info['last_modified']
            ))

            page_id = cursor.fetchone()[0]

            # Record change
            cursor.execute("""
                INSERT INTO content.hugo_changes (
                    page_id, change_type, new_hash, word_count_change
                ) VALUES (%s, 'created', %s, %s)
            """, (page_id, file_info['content_hash'], file_info['word_count']))

            conn.commit()

        except Exception as e:
            logger.error(f"Error creating page: {e}")
            if conn:
                conn.rollback()

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _update_page(self, page_path: str, file_info: Dict, old_hash: str) -> None:
        """Update existing page in database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            # Get current word count for delta calculation
            cursor.execute("""
                SELECT id, word_count
                FROM content.hugo_pages
                WHERE property = %s AND page_path = %s
            """, (self.property_name, page_path))

            row = cursor.fetchone()
            if not row:
                return

            page_id, old_word_count = row
            word_count_change = file_info['word_count'] - (old_word_count or 0)

            # Update page
            cursor.execute("""
                UPDATE content.hugo_pages
                SET title = %s,
                    content_hash = %s,
                    word_count = %s,
                    last_modified = %s,
                    synced_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                file_info['title'],
                file_info['content_hash'],
                file_info['word_count'],
                file_info['last_modified'],
                page_id
            ))

            # Record change
            cursor.execute("""
                INSERT INTO content.hugo_changes (
                    page_id, change_type, old_hash, new_hash, word_count_change
                ) VALUES (%s, 'updated', %s, %s, %s)
            """, (page_id, old_hash, file_info['content_hash'], word_count_change))

            conn.commit()

        except Exception as e:
            logger.error(f"Error updating page: {e}")
            if conn:
                conn.rollback()

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _mark_deleted(self, page_path: str) -> None:
        """Mark page as deleted in database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            # Get page ID
            cursor.execute("""
                SELECT id, content_hash
                FROM content.hugo_pages
                WHERE property = %s AND page_path = %s
            """, (self.property_name, page_path))

            row = cursor.fetchone()
            if not row:
                return

            page_id, old_hash = row

            # Mark as deleted
            cursor.execute("""
                UPDATE content.hugo_pages
                SET deleted_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (page_id,))

            # Record change
            cursor.execute("""
                INSERT INTO content.hugo_changes (
                    page_id, change_type, old_hash
                ) VALUES (%s, 'deleted', %s)
            """, (page_id, old_hash))

            conn.commit()

        except Exception as e:
            logger.error(f"Error marking page deleted: {e}")
            if conn:
                conn.rollback()

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
