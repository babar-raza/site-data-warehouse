"""
Hugo Content Sync - Static Site Integration
===========================================
Syncs Hugo markdown content with the data warehouse:
- Parses frontmatter metadata
- Tracks content versions via Git
- Maps content to GSC performance
- Detects content changes
- Links Hugo posts to analytics

Perfect for Aspose Hugo sites!
"""
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import frontmatter
import git
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HugoContentSync:
    """
    Syncs Hugo content with data warehouse
    """

    def __init__(
        self,
        hugo_repo_path: str,
        property: str,
        db_dsn: str = None
    ):
        """
        Initialize Hugo sync

        Args:
            hugo_repo_path: Path to Hugo repository
            property: Property URL to map content to
            db_dsn: Database connection string
        """
        self.hugo_path = Path(hugo_repo_path)
        self.property = property
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None

        # Initialize Git repo
        try:
            self.repo = git.Repo(hugo_repo_path)
            logger.info(f"Git repo initialized: {hugo_repo_path}")
        except git.exc.InvalidGitRepositoryError:
            logger.warning(f"Not a git repository: {hugo_repo_path}")
            self.repo = None

        logger.info(f"HugoContentSync initialized for {property}")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def find_content_files(self, content_dir: str = 'content') -> List[Path]:
        """
        Find all markdown files in content directory

        Args:
            content_dir: Content directory name

        Returns:
            List of markdown file paths
        """
        content_path = self.hugo_path / content_dir

        if not content_path.exists():
            logger.error(f"Content directory not found: {content_path}")
            return []

        # Find all .md files recursively
        md_files = list(content_path.rglob('*.md'))
        logger.info(f"Found {len(md_files)} markdown files")

        return md_files

    def parse_hugo_file(self, file_path: Path) -> Dict:
        """
        Parse Hugo markdown file

        Args:
            file_path: Path to .md file

        Returns:
            Dict with frontmatter and content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            # Extract frontmatter
            metadata = dict(post.metadata)

            # Get content
            content = post.content

            # Get relative path (for URL mapping)
            relative_path = file_path.relative_to(self.hugo_path / 'content')

            # Construct URL path (Hugo convention)
            # e.g., content/blog/my-post.md -> /blog/my-post/
            url_path_parts = list(relative_path.parts[:-1])  # Remove filename
            filename = relative_path.stem

            if filename != '_index':
                url_path_parts.append(filename)

            url_path = '/' + '/'.join(url_path_parts) + '/'

            # Get git info
            git_info = self.get_git_info(file_path) if self.repo else {}

            return {
                'file_path': str(file_path),
                'relative_path': str(relative_path),
                'url_path': url_path,
                'title': metadata.get('title', ''),
                'description': metadata.get('description', ''),
                'date': metadata.get('date'),
                'draft': metadata.get('draft', False),
                'tags': metadata.get('tags', []),
                'categories': metadata.get('categories', []),
                'author': metadata.get('author', ''),
                'content': content,
                'word_count': len(content.split()),
                'content_hash': hashlib.sha256(content.encode()).hexdigest(),
                'metadata': metadata,
                'git_info': git_info
            }

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def get_git_info(self, file_path: Path) -> Dict:
        """
        Get Git history for file

        Args:
            file_path: Path to file

        Returns:
            Dict with git information
        """
        try:
            if not self.repo:
                return {}

            # Get relative path for Git
            rel_path = str(file_path.relative_to(self.hugo_path))

            # Get commits for this file
            commits = list(self.repo.iter_commits(paths=rel_path, max_count=10))

            if not commits:
                return {}

            latest_commit = commits[0]
            first_commit = commits[-1]

            return {
                'latest_commit_sha': latest_commit.hexsha[:8],
                'latest_commit_date': datetime.fromtimestamp(latest_commit.committed_date),
                'latest_commit_message': latest_commit.message.strip(),
                'latest_commit_author': latest_commit.author.name,
                'first_commit_date': datetime.fromtimestamp(first_commit.committed_date),
                'total_commits': len(commits)
            }

        except Exception as e:
            logger.error(f"Error getting git info: {e}")
            return {}

    async def store_hugo_content(self, parsed: Dict) -> bool:
        """
        Store Hugo content in database

        Args:
            parsed: Parsed Hugo content

        Returns:
            True if successful
        """
        try:
            if not parsed or parsed.get('draft'):
                return False

            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Store in content snapshots
                await conn.execute("""
                    INSERT INTO content.page_snapshots (
                        property,
                        page_path,
                        url,
                        text_content,
                        title,
                        meta_description,
                        word_count,
                        content_hash,
                        snapshot_date,
                        analyzed_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (property, page_path, snapshot_date)
                    DO UPDATE SET
                        text_content = EXCLUDED.text_content,
                        title = EXCLUDED.title,
                        word_count = EXCLUDED.word_count,
                        content_hash = EXCLUDED.content_hash,
                        analyzed_at = EXCLUDED.analyzed_at
                """,
                    self.property,
                    parsed['url_path'],
                    f"{self.property}{parsed['url_path']}",
                    parsed['content'],
                    parsed['title'],
                    parsed['description'],
                    parsed['word_count'],
                    parsed['content_hash'],
                    datetime.utcnow().date(),
                    datetime.utcnow()
                )

                # Track change if hash changed
                prev_hash = await conn.fetchval("""
                    SELECT content_hash
                    FROM content.page_snapshots
                    WHERE property = $1
                        AND page_path = $2
                        AND snapshot_date < $3
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, self.property, parsed['url_path'], datetime.utcnow().date())

                if prev_hash and prev_hash != parsed['content_hash']:
                    # Content changed
                    await conn.execute("""
                        INSERT INTO content.content_changes (
                            property,
                            page_path,
                            change_date,
                            change_type,
                            changes_summary,
                            changed_by
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        self.property,
                        parsed['url_path'],
                        datetime.utcnow(),
                        'updated',
                        parsed['git_info'].get('latest_commit_message', 'Content updated'),
                        parsed['git_info'].get('latest_commit_author', 'unknown')
                    )

            logger.info(f"Stored Hugo content: {parsed['url_path']}")
            return True

        except Exception as e:
            logger.error(f"Error storing Hugo content: {e}")
            return False

    async def sync_all(self, content_dir: str = 'content') -> Dict:
        """
        Sync all Hugo content

        Args:
            content_dir: Content directory name

        Returns:
            Sync results
        """
        try:
            # Find all markdown files
            md_files = self.find_content_files(content_dir)

            synced = 0
            skipped = 0
            errors = 0

            for file_path in md_files:
                parsed = self.parse_hugo_file(file_path)

                if parsed:
                    success = await self.store_hugo_content(parsed)
                    if success:
                        synced += 1
                    else:
                        skipped += 1
                else:
                    errors += 1

            logger.info(f"Hugo sync complete: {synced} synced, {skipped} skipped, {errors} errors")

            return {
                'total_files': len(md_files),
                'synced_count': synced,
                'skipped_count': skipped,
                'error_count': errors,
                'property': self.property
            }

        except Exception as e:
            logger.error(f"Error in sync_all: {e}")
            return {'error': str(e)}

    async def link_to_gsc(self) -> Dict:
        """
        Link synced Hugo content to GSC performance data

        Returns:
            Linking results
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Find Hugo pages that have GSC data
                results = await conn.fetch("""
                    SELECT
                        c.page_path,
                        c.title,
                        COUNT(DISTINCT g.date) AS days_tracked,
                        SUM(g.clicks) AS total_clicks,
                        AVG(g.avg_position) AS avg_position
                    FROM content.vw_latest_snapshots c
                    LEFT JOIN gsc.fact_gsc_daily g
                        ON c.property = g.property
                        AND c.page_path = REGEXP_REPLACE(g.url, '^https?://[^/]+', '')
                    WHERE c.property = $1
                    GROUP BY c.page_path, c.title
                    HAVING COUNT(DISTINCT g.date) > 0
                    ORDER BY total_clicks DESC
                """, self.property)

            linked = []
            for row in results:
                linked.append({
                    'page_path': row['page_path'],
                    'title': row['title'],
                    'days_tracked': row['days_tracked'],
                    'total_clicks': int(row['total_clicks']),
                    'avg_position': round(float(row['avg_position']), 2)
                })

            logger.info(f"Linked {len(linked)} Hugo pages to GSC data")

            return {
                'linked_pages': len(linked),
                'pages': linked
            }

        except Exception as e:
            logger.error(f"Error linking to GSC: {e}")
            return {'error': str(e)}

    def sync_sync(self, content_dir: str = 'content') -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.sync_all(content_dir))
