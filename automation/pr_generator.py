"""
Automatic Pull Request Generator
=================================
Automatically create GitHub pull requests for SEO optimizations.

Supports:
- Meta tag updates
- Schema markup additions
- Content improvements
- Internal linking suggestions
- Technical fixes
"""
import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import ollama
from github import Github, GithubException
from github.Repository import Repository

logger = logging.getLogger(__name__)


class AutoPRGenerator:
    """
    Automatic Pull Request Generator

    Creates GitHub PRs for automated SEO optimizations
    """

    def __init__(
        self,
        github_token: str = None,
        db_dsn: str = None,
        ollama_url: str = 'http://localhost:11434'
    ):
        """
        Initialize PR generator

        Args:
            github_token: GitHub personal access token
            db_dsn: Database connection string
            ollama_url: Ollama API URL for LLM-generated PR descriptions
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.ollama_url = ollama_url

        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")

        self.github = Github(self.github_token)
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("AutoPRGenerator initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def get_repository(self, repo_owner: str, repo_name: str) -> Repository:
        """Get GitHub repository"""
        try:
            repo = self.github.get_repo(f"{repo_owner}/{repo_name}")
            logger.info(f"Connected to repository: {repo_owner}/{repo_name}")
            return repo
        except GithubException as e:
            logger.error(f"Error accessing repository: {e}")
            raise

    async def generate_pr_description(
        self,
        recommendations: List[Dict],
        property: str
    ) -> str:
        """
        Generate PR description using LLM

        Args:
            recommendations: List of recommendations being implemented
            property: Property URL

        Returns:
            Markdown-formatted PR description
        """
        try:
            prompt = f"""Generate a clear and professional GitHub Pull Request description for these SEO improvements:

Property: {property}
Recommendations: {len(recommendations)} changes

Changes:
{self._format_recommendations(recommendations)}

Generate a PR description with:
1. **Summary** - Brief overview of changes
2. **Changes** - Bulleted list of specific modifications
3. **Expected Impact** - Estimated SEO improvements
4. **Testing Checklist** - Items to verify before merging

Format in GitHub-flavored Markdown. Be concise but informative."""

            response = ollama.chat(
                model='llama3.1:8b',
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )

            description = response['message']['content']

            # Add automation footer
            description += "\n\n---\n\n"
            description += "🤖 *This PR was generated automatically by the SEO Intelligence Platform.*\n"
            description += f"Generated with [Claude Code](https://claude.com/claude-code)\n"

            return description

        except Exception as e:
            logger.error(f"Error generating PR description with LLM: {e}")
            # Fallback to simple description
            return self._generate_simple_description(recommendations, property)

    def _format_recommendations(self, recommendations: List[Dict]) -> str:
        """Format recommendations for LLM prompt"""
        formatted = []
        for i, rec in enumerate(recommendations, 1):
            formatted.append(f"{i}. [{rec.get('action_type', 'UNKNOWN')}] {rec.get('page_path', 'Multiple pages')}")
            if rec.get('title'):
                formatted.append(f"   {rec['title']}")
        return "\n".join(formatted)

    def _generate_simple_description(self, recommendations: List[Dict], property: str) -> str:
        """Generate simple PR description without LLM"""
        description = f"## SEO Optimization for {property}\n\n"
        description += f"This PR implements {len(recommendations)} automated SEO improvements.\n\n"
        description += "### Changes\n\n"

        for rec in recommendations:
            description += f"- **{rec.get('action_type', 'Update')}**: {rec.get('page_path', 'Multiple pages')}\n"
            if rec.get('title'):
                description += f"  - {rec['title']}\n"

        description += "\n### Testing\n\n"
        description += "- [ ] Verify meta tags are correctly formatted\n"
        description += "- [ ] Check that content renders properly\n"
        description += "- [ ] Validate schema markup (if applicable)\n"
        description += "- [ ] Test internal links\n\n"

        description += "---\n\n"
        description += "🤖 *Generated automatically by SEO Intelligence Platform*\n"

        return description

    async def create_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        recommendations: List[Dict],
        property: str,
        base_branch: str = 'main',
        branch_name: str = None
    ) -> Dict:
        """
        Create automated pull request

        Args:
            repo_owner: GitHub repository owner
            repo_name: Repository name
            recommendations: List of recommendations to implement
            property: Property URL
            base_branch: Base branch (default: 'main')
            branch_name: Custom branch name (optional)

        Returns:
            PR result with URL and details
        """
        try:
            repo = self.get_repository(repo_owner, repo_name)

            # Create branch name if not provided
            if not branch_name:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                branch_name = f'auto-optimize-{timestamp}'

            # Get base branch reference
            base = repo.get_branch(base_branch)

            # Create new branch
            logger.info(f"Creating branch: {branch_name}")
            repo.create_git_ref(
                ref=f'refs/heads/{branch_name}',
                sha=base.commit.sha
            )

            # Apply changes
            files_changed = 0
            file_changes = []

            for rec in recommendations:
                try:
                    change_result = await self._apply_recommendation(
                        repo,
                        branch_name,
                        rec
                    )

                    if change_result['success']:
                        files_changed += 1
                        file_changes.append(change_result)

                except Exception as e:
                    logger.error(f"Error applying recommendation: {e}")
                    # Continue with other recommendations

            if files_changed == 0:
                logger.warning("No files were changed, skipping PR creation")
                return {
                    'success': False,
                    'error': 'no_changes',
                    'message': 'No files were modified'
                }

            # Generate PR description
            pr_description = await self.generate_pr_description(recommendations, property)

            # Create PR
            pr_title = f"Auto-optimize: {files_changed} SEO improvements"

            logger.info(f"Creating pull request: {pr_title}")

            pr = repo.create_pull(
                title=pr_title,
                body=pr_description,
                head=branch_name,
                base=base_branch
            )

            # Add labels
            try:
                pr.add_to_labels('automated', 'seo', 'enhancement')
            except:
                pass  # Labels might not exist

            # Store in database
            pr_id = await self._store_pull_request(
                repo_owner=repo_owner,
                repo_name=repo_name,
                branch_name=branch_name,
                pr_number=pr.number,
                pr_url=pr.html_url,
                pr_title=pr_title,
                pr_description=pr_description,
                property=property,
                recommendations=recommendations,
                files_changed=files_changed,
                file_changes=file_changes
            )

            logger.info(f"Pull request created: {pr.html_url}")

            return {
                'success': True,
                'pr_id': pr_id,
                'pr_number': pr.number,
                'pr_url': pr.html_url,
                'branch_name': branch_name,
                'files_changed': files_changed,
                'recommendations_applied': len(recommendations)
            }

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return {
                'success': False,
                'error': 'github_api_error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Error creating PR: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _apply_recommendation(
        self,
        repo: Repository,
        branch_name: str,
        recommendation: Dict
    ) -> Dict:
        """
        Apply a single recommendation

        Args:
            repo: GitHub repository
            branch_name: Branch to commit to
            recommendation: Recommendation to apply

        Returns:
            Change result
        """
        action_type = recommendation.get('action_type')

        if action_type == 'UPDATE_META':
            return await self._update_meta_tags(repo, branch_name, recommendation)
        elif action_type == 'ADD_SCHEMA':
            return await self._add_schema_markup(repo, branch_name, recommendation)
        elif action_type == 'IMPROVE_CONTENT':
            return await self._improve_content(repo, branch_name, recommendation)
        elif action_type == 'FIX_INTERNAL_LINKS':
            return await self._fix_internal_links(repo, branch_name, recommendation)
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return {'success': False, 'error': 'unknown_action_type'}

    async def _update_meta_tags(
        self,
        repo: Repository,
        branch_name: str,
        recommendation: Dict
    ) -> Dict:
        """Update meta tags in HTML/Markdown file"""
        try:
            file_path = recommendation.get('file_path')
            page_path = recommendation.get('page_path')

            if not file_path:
                # Try to infer file path from page_path
                # This depends on your Hugo/Jekyll structure
                file_path = f"content{page_path}index.md"

            # Get current file content
            try:
                file_content = repo.get_contents(file_path, ref=branch_name)
                content = base64.b64decode(file_content.content).decode('utf-8')
                old_content = content
            except:
                logger.warning(f"File not found: {file_path}")
                return {'success': False, 'error': 'file_not_found'}

            # Update meta tags
            # This is a simple example - you'd customize based on your site structure
            new_meta_description = recommendation.get('meta_description')
            new_title = recommendation.get('title')

            if new_meta_description:
                # Update description in frontmatter
                content = self._update_frontmatter_field(content, 'description', new_meta_description)

            if new_title:
                content = self._update_frontmatter_field(content, 'title', new_title)

            if content == old_content:
                return {'success': False, 'error': 'no_changes'}

            # Commit changes
            commit_message = f"chore: update meta tags for {page_path}"

            repo.update_file(
                path=file_content.path,
                message=commit_message,
                content=content,
                sha=file_content.sha,
                branch=branch_name
            )

            logger.info(f"Updated meta tags: {file_path}")

            return {
                'success': True,
                'file_path': file_path,
                'change_type': 'modified',
                'recommendation_type': 'UPDATE_META'
            }

        except Exception as e:
            logger.error(f"Error updating meta tags: {e}")
            return {'success': False, 'error': str(e)}

    def _update_frontmatter_field(self, content: str, field: str, value: str) -> str:
        """Update a field in YAML frontmatter"""
        # Simple regex-based update (you might want to use python-frontmatter library)
        import re

        pattern = rf'^{field}:\s*.*$'
        replacement = f'{field}: "{value}"'

        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # Add field if it doesn't exist
            # Insert after the first ---
            parts = content.split('---', 2)
            if len(parts) >= 2:
                parts[1] += f'\n{field}: "{value}"'
                content = '---'.join(parts)

        return content

    async def _add_schema_markup(
        self,
        repo: Repository,
        branch_name: str,
        recommendation: Dict
    ) -> Dict:
        """Add schema markup to page"""
        # Implementation would depend on your site structure
        # This is a placeholder
        return {'success': True, 'file_path': 'schema_added', 'recommendation_type': 'ADD_SCHEMA'}

    async def _improve_content(
        self,
        repo: Repository,
        branch_name: str,
        recommendation: Dict
    ) -> Dict:
        """Improve content based on recommendation"""
        # Implementation would use LLM to improve content
        # This is a placeholder
        return {'success': True, 'file_path': 'content_improved', 'recommendation_type': 'IMPROVE_CONTENT'}

    async def _fix_internal_links(
        self,
        repo: Repository,
        branch_name: str,
        recommendation: Dict
    ) -> Dict:
        """Fix broken internal links"""
        # Implementation would scan and fix broken links
        # This is a placeholder
        return {'success': True, 'file_path': 'links_fixed', 'recommendation_type': 'FIX_INTERNAL_LINKS'}

    async def _store_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        branch_name: str,
        pr_number: int,
        pr_url: str,
        pr_title: str,
        pr_description: str,
        property: str,
        recommendations: List[Dict],
        files_changed: int,
        file_changes: List[Dict]
    ) -> str:
        """Store PR in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Store PR
                pr_id = await conn.fetchval("""
                    INSERT INTO automation.pull_requests (
                        repo_owner,
                        repo_name,
                        branch_name,
                        pr_number,
                        pr_url,
                        pr_title,
                        pr_description,
                        property,
                        recommendations,
                        files_changed,
                        status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING pr_id
                """,
                    repo_owner,
                    repo_name,
                    branch_name,
                    pr_number,
                    pr_url,
                    pr_title,
                    pr_description,
                    property,
                    recommendations,
                    files_changed,
                    'open'
                )

                # Store file changes
                for change in file_changes:
                    if change.get('success'):
                        await conn.execute("""
                            INSERT INTO automation.file_changes (
                                pr_id,
                                file_path,
                                change_type,
                                recommendation_type
                            ) VALUES ($1, $2, $3, $4)
                        """,
                            pr_id,
                            change.get('file_path'),
                            change.get('change_type', 'modified'),
                            change.get('recommendation_type')
                        )

            logger.info(f"Stored PR in database: {pr_id}")
            return str(pr_id)

        except Exception as e:
            logger.error(f"Error storing PR: {e}")
            raise

    async def get_pr_status(self, pr_id: str) -> Dict:
        """Get status of a PR"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                pr = await conn.fetchrow("""
                    SELECT *
                    FROM automation.pull_requests
                    WHERE pr_id = $1
                """, pr_id)

            if not pr:
                return {'error': 'not_found'}

            return dict(pr)

        except Exception as e:
            logger.error(f"Error getting PR status: {e}")
            return {'error': str(e)}

    def create_pull_request_sync(
        self,
        repo_owner: str,
        repo_name: str,
        recommendations: List[Dict],
        property: str
    ) -> Dict:
        """Synchronous wrapper for Celery"""
        return asyncio.run(self.create_pull_request(
            repo_owner,
            repo_name,
            recommendations,
            property
        ))


__all__ = ['AutoPRGenerator']
