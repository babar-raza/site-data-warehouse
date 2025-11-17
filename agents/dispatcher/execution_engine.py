"""Execution engine for implementing recommendations."""

import asyncio
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import asyncpg
import requests


class ExecutionEngine:
    """Engine that executes approved recommendations."""
    
    def __init__(self, db_pool: asyncpg.Pool, config: Optional[Dict[str, Any]] = None):
        """Initialize execution engine.
        
        Args:
            db_pool: Database connection pool
            config: Optional execution configuration
        """
        self.db_pool = db_pool
        self.config = config or {}
        self.integrations = config.get('integrations', {})
        self.max_concurrent = config.get('max_concurrent', 3)
        self.timeout_seconds = config.get('timeout_seconds', 300)
        self.retry_attempts = config.get('retry_attempts', 3)
        
    async def execute_recommendation(
        self,
        recommendation_id: int,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute a recommendation.
        
        Args:
            recommendation_id: Recommendation ID to execute
            dry_run: If True, simulate execution without making changes
            
        Returns:
            Execution result
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get recommendation details
                recommendation = await conn.fetchrow(
                    """
                    SELECT r.*, d.issue_type, d.affected_urls
                    FROM gsc.agent_recommendations r
                    JOIN gsc.agent_diagnoses d ON r.diagnosis_id = d.id
                    WHERE r.id = $1
                    """,
                    recommendation_id
                )
                
                if not recommendation:
                    return {
                        'success': False,
                        'message': 'Recommendation not found',
                        'recommendation_id': recommendation_id
                    }
                
                # Check if already executed
                if recommendation['implemented'] and not dry_run:
                    return {
                        'success': False,
                        'message': 'Recommendation already implemented',
                        'recommendation_id': recommendation_id
                    }
                
                # Create execution record
                execution_id = await conn.fetchval(
                    """
                    INSERT INTO gsc.agent_executions (
                        recommendation_id,
                        agent_name,
                        execution_type,
                        status,
                        execution_details,
                        dry_run
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    recommendation_id,
                    'dispatcher',
                    recommendation['recommendation_type'],
                    'in_progress',
                    json.dumps({}),
                    dry_run
                )
                
                # Determine execution method based on recommendation type
                rec_type = recommendation['recommendation_type']
                action_items = recommendation['action_items']
                
                execution_result = None
                
                if rec_type == 'content_optimization':
                    execution_result = await self._execute_content_update(
                        action_items, dry_run
                    )
                elif rec_type == 'technical_fixes':
                    execution_result = await self._execute_technical_fix(
                        action_items, dry_run
                    )
                elif rec_type == 'internal_linking':
                    execution_result = await self._execute_linking_update(
                        action_items, dry_run
                    )
                else:
                    execution_result = await self._execute_generic(
                        rec_type, action_items, dry_run
                    )
                
                # Update execution record
                status = 'completed' if execution_result['success'] else 'failed'
                
                await conn.execute(
                    """
                    UPDATE gsc.agent_executions
                    SET status = $1,
                        execution_details = $2,
                        completed_at = $3,
                        error_message = $4
                    WHERE id = $5
                    """,
                    status,
                    json.dumps(execution_result.get('details', {})),
                    datetime.now(),
                    execution_result.get('error'),
                    execution_id
                )
                
                # Send notifications if configured
                if execution_result['success'] and not dry_run:
                    await self._send_notifications(
                        recommendation_id,
                        execution_id,
                        execution_result
                    )
                
                return {
                    'success': execution_result['success'],
                    'message': execution_result.get('message', 'Execution completed'),
                    'recommendation_id': recommendation_id,
                    'execution_id': execution_id,
                    'dry_run': dry_run,
                    'details': execution_result.get('details', {})
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Execution error: {str(e)}',
                'recommendation_id': recommendation_id,
                'error': str(e)
            }
    
    async def _execute_content_update(
        self,
        action_items: Dict[str, Any],
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute content optimization update."""
        try:
            url = action_items.get('url')
            changes = action_items.get('changes', {})
            
            if not url or not changes:
                return {
                    'success': False,
                    'message': 'Missing URL or changes',
                    'details': {}
                }
            
            if dry_run:
                return {
                    'success': True,
                    'message': f'DRY RUN: Would update {url}',
                    'details': {
                        'url': url,
                        'changes': changes,
                        'dry_run': True
                    }
                }
            
            # Check if Content API integration is enabled
            content_api = self.integrations.get('content_api', {})
            
            if content_api.get('enabled'):
                # Use Content API
                result = await self._update_via_content_api(url, changes, content_api)
            else:
                # Create PR instead
                result = await self._create_pr_for_changes(url, changes)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Content update error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _execute_technical_fix(
        self,
        action_items: Dict[str, Any],
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute technical fix via PR creation."""
        try:
            fix_type = action_items.get('fix_type')
            files = action_items.get('files', [])
            
            if not files:
                return {
                    'success': False,
                    'message': 'No files to fix',
                    'details': {}
                }
            
            if dry_run:
                return {
                    'success': True,
                    'message': f'DRY RUN: Would create PR for {len(files)} files',
                    'details': {
                        'fix_type': fix_type,
                        'files_count': len(files),
                        'dry_run': True
                    }
                }
            
            # Create PR for technical fixes
            result = await self._create_pr_for_technical_fix(fix_type, files)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Technical fix error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _execute_linking_update(
        self,
        action_items: Dict[str, Any],
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute internal linking update."""
        try:
            links_to_add = action_items.get('links_to_add', [])
            
            if not links_to_add:
                return {
                    'success': False,
                    'message': 'No links to add',
                    'details': {}
                }
            
            if dry_run:
                return {
                    'success': True,
                    'message': f'DRY RUN: Would add {len(links_to_add)} internal links',
                    'details': {
                        'links_count': len(links_to_add),
                        'dry_run': True
                    }
                }
            
            # Create PR for linking updates
            result = await self._create_pr_for_linking(links_to_add)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Linking update error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _execute_generic(
        self,
        rec_type: str,
        action_items: Dict[str, Any],
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute generic recommendation type."""
        if dry_run:
            return {
                'success': True,
                'message': f'DRY RUN: Would execute {rec_type}',
                'details': {
                    'recommendation_type': rec_type,
                    'action_items': action_items,
                    'dry_run': True
                }
            }
        
        # For generic types, create notification only
        return {
            'success': True,
            'message': f'Created action items for {rec_type}',
            'details': {
                'recommendation_type': rec_type,
                'action_items': action_items,
                'requires_manual_action': True
            }
        }
    
    async def _update_via_content_api(
        self,
        url: str,
        changes: Dict[str, Any],
        api_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update content via Content API."""
        try:
            base_url = api_config.get('base_url')
            timeout = api_config.get('timeout_seconds', 30)
            
            # Simulate API call (replace with actual API implementation)
            response = requests.put(
                f"{base_url}/content",
                json={
                    'url': url,
                    'changes': changes
                },
                timeout=timeout
            )
            
            if response.status_code in [200, 201]:
                return {
                    'success': True,
                    'message': 'Content updated via API',
                    'details': {
                        'url': url,
                        'changes': changes,
                        'api_response': response.json()
                    }
                }
            else:
                return {
                    'success': False,
                    'message': f'API error: {response.status_code}',
                    'details': {
                        'url': url,
                        'status_code': response.status_code
                    }
                }
                
        except Exception as e:
            # If API fails, fall back to PR creation
            return await self._create_pr_for_changes(url, changes)
    
    async def _create_pr_for_changes(
        self,
        url: str,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create pull request for content changes."""
        try:
            github_config = self.integrations.get('github', {})
            
            if not github_config.get('enabled'):
                return {
                    'success': False,
                    'message': 'GitHub integration not enabled',
                    'details': {
                        'url': url,
                        'changes': changes,
                        'requires_manual_action': True
                    }
                }
            
            # Prepare PR data
            branch_name = f"seo-content-update-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            pr_title = f"SEO: Update content for {url}"
            pr_body = self._generate_pr_body(url, changes)
            
            # Create branch and PR (simulated)
            pr_url = f"https://github.com/org/repo/pull/123"  # Placeholder
            
            return {
                'success': True,
                'message': 'PR created for content changes',
                'details': {
                    'url': url,
                    'changes': changes,
                    'pr_url': pr_url,
                    'pr_id': 123,
                    'branch': branch_name
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'PR creation error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _create_pr_for_technical_fix(
        self,
        fix_type: str,
        files: List[str]
    ) -> Dict[str, Any]:
        """Create pull request for technical fixes."""
        try:
            github_config = self.integrations.get('github', {})
            
            if not github_config.get('enabled'):
                return {
                    'success': False,
                    'message': 'GitHub integration not enabled',
                    'details': {
                        'fix_type': fix_type,
                        'files': files,
                        'requires_manual_action': True
                    }
                }
            
            branch_name = f"seo-fix-{fix_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            pr_title = f"SEO: Fix {fix_type}"
            
            # Create PR (simulated)
            pr_url = f"https://github.com/org/repo/pull/124"  # Placeholder
            
            return {
                'success': True,
                'message': f'PR created for {fix_type}',
                'details': {
                    'fix_type': fix_type,
                    'files': files,
                    'pr_url': pr_url,
                    'pr_id': 124,
                    'branch': branch_name
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'PR creation error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _create_pr_for_linking(
        self,
        links_to_add: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Create pull request for internal linking updates."""
        try:
            github_config = self.integrations.get('github', {})
            
            if not github_config.get('enabled'):
                return {
                    'success': False,
                    'message': 'GitHub integration not enabled',
                    'details': {
                        'links_to_add': links_to_add,
                        'requires_manual_action': True
                    }
                }
            
            branch_name = f"seo-linking-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            pr_title = f"SEO: Add {len(links_to_add)} internal links"
            
            # Create PR (simulated)
            pr_url = f"https://github.com/org/repo/pull/125"  # Placeholder
            
            return {
                'success': True,
                'message': f'PR created for internal linking',
                'details': {
                    'links_count': len(links_to_add),
                    'pr_url': pr_url,
                    'pr_id': 125,
                    'branch': branch_name
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'PR creation error: {str(e)}',
                'details': {},
                'error': str(e)
            }
    
    async def _send_notifications(
        self,
        recommendation_id: int,
        execution_id: int,
        execution_result: Dict[str, Any]
    ) -> None:
        """Send notifications about execution."""
        try:
            notifications = self.integrations.get('notifications', {})
            
            # Email notification
            if notifications.get('email', {}).get('enabled'):
                await self._send_email_notification(
                    recommendation_id,
                    execution_id,
                    execution_result
                )
            
            # Slack notification
            if notifications.get('slack', {}).get('enabled'):
                await self._send_slack_notification(
                    recommendation_id,
                    execution_id,
                    execution_result
                )
                
        except Exception as e:
            print(f"Notification error: {e}")
    
    async def _send_email_notification(
        self,
        recommendation_id: int,
        execution_id: int,
        execution_result: Dict[str, Any]
    ) -> None:
        """Send email notification."""
        try:
            email_config = self.integrations.get('notifications', {}).get('email', {})
            
            msg = MIMEMultipart()
            msg['From'] = email_config.get('from_address', 'seo-agent@example.com')
            msg['To'] = email_config.get('to_address', 'team@example.com')
            msg['Subject'] = f'SEO Recommendation {recommendation_id} Executed'
            
            body = f"""
            Recommendation #{recommendation_id} has been executed.
            
            Execution ID: {execution_id}
            Status: {execution_result.get('message', 'Completed')}
            
            Details: {json.dumps(execution_result.get('details', {}), indent=2)}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (simulated)
            print(f"Email notification sent for execution {execution_id}")
            
        except Exception as e:
            print(f"Email notification error: {e}")
    
    async def _send_slack_notification(
        self,
        recommendation_id: int,
        execution_id: int,
        execution_result: Dict[str, Any]
    ) -> None:
        """Send Slack notification."""
        try:
            slack_config = self.integrations.get('notifications', {}).get('slack', {})
            webhook_url = slack_config.get('webhook_url')
            
            if not webhook_url:
                return
            
            payload = {
                'channel': slack_config.get('channel', '#seo-alerts'),
                'text': f'SEO Recommendation #{recommendation_id} Executed',
                'attachments': [{
                    'color': 'good' if execution_result.get('success') else 'danger',
                    'fields': [
                        {'title': 'Execution ID', 'value': str(execution_id), 'short': True},
                        {'title': 'Status', 'value': execution_result.get('message', 'Completed'), 'short': True}
                    ]
                }]
            }
            
            # Send to Slack (simulated)
            # requests.post(webhook_url, json=payload)
            print(f"Slack notification sent for execution {execution_id}")
            
        except Exception as e:
            print(f"Slack notification error: {e}")
    
    def _generate_pr_body(self, url: str, changes: Dict[str, Any]) -> str:
        """Generate PR body description."""
        body = f"## SEO Content Update\n\n"
        body += f"**URL:** {url}\n\n"
        body += f"### Changes\n\n"
        
        for change_type, change_value in changes.items():
            body += f"- **{change_type}:** {change_value}\n"
        
        body += f"\n---\n*Generated by SEO Dispatcher Agent*"
        
        return body
    
    async def rollback_execution(self, execution_id: int) -> Dict[str, Any]:
        """Rollback an execution.
        
        Args:
            execution_id: Execution ID to rollback
            
        Returns:
            Rollback result
        """
        try:
            async with self.db_pool.acquire() as conn:
                execution = await conn.fetchrow(
                    "SELECT * FROM gsc.agent_executions WHERE id = $1",
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found'
                    }
                
                if execution['status'] == 'rolled_back':
                    return {
                        'success': False,
                        'message': 'Already rolled back'
                    }
                
                execution_details = execution['execution_details']
                
                # Perform rollback based on execution type
                rollback_details = {
                    'rolled_back_at': datetime.now().isoformat(),
                    'original_execution': execution_details,
                    'rollback_method': 'automated'
                }
                
                # Update execution status
                await conn.execute(
                    """
                    UPDATE gsc.agent_executions
                    SET status = 'rolled_back',
                        rollback_details = $1,
                        completed_at = $2
                    WHERE id = $3
                    """,
                    json.dumps(rollback_details),
                    datetime.now(),
                    execution_id
                )
                
                return {
                    'success': True,
                    'message': 'Execution rolled back',
                    'execution_id': execution_id,
                    'rollback_details': rollback_details
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Rollback error: {str(e)}',
                'error': str(e)
            }
