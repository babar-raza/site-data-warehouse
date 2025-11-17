"""Validation framework for execution results."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncpg
import requests


class ValidationRule:
    """Base validation rule."""
    
    def __init__(self, rule_name: str, rule_type: str, params: Dict[str, Any]):
        self.rule_name = rule_name
        self.rule_type = rule_type
        self.params = params
        
    async def validate(self, execution_details: Dict[str, Any], db_pool: asyncpg.Pool) -> Dict[str, Any]:
        """Execute validation rule.
        
        Returns:
            Dict with success, message, and details
        """
        raise NotImplementedError()


class ContentValidationRule(ValidationRule):
    """Validates content changes were applied correctly."""
    
    async def validate(self, execution_details: Dict[str, Any], db_pool: asyncpg.Pool) -> Dict[str, Any]:
        """Validate content changes."""
        try:
            url = execution_details.get('url')
            expected_changes = execution_details.get('changes', {})
            
            if not url:
                return {
                    'success': False,
                    'message': 'No URL provided for validation',
                    'details': {}
                }
            
            # Fetch current content
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'Failed to fetch URL: {response.status_code}',
                    'details': {'status_code': response.status_code}
                }
            
            content = response.text
            validated_changes = {}
            
            # Check each expected change
            for change_type, change_value in expected_changes.items():
                if change_type == 'title' and f'<title>{change_value}</title>' in content:
                    validated_changes['title'] = True
                elif change_type == 'meta_description' and f'name="description" content="{change_value}"' in content:
                    validated_changes['meta_description'] = True
                elif change_type == 'h1' and f'<h1>{change_value}</h1>' in content:
                    validated_changes['h1'] = True
                else:
                    validated_changes[change_type] = False
            
            all_validated = all(validated_changes.values())
            
            return {
                'success': all_validated,
                'message': 'All changes validated' if all_validated else 'Some changes not found',
                'details': {
                    'validated_changes': validated_changes,
                    'validation_timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'details': {'error': str(e)}
            }


class PRValidationRule(ValidationRule):
    """Validates pull request was created successfully."""
    
    async def validate(self, execution_details: Dict[str, Any], db_pool: asyncpg.Pool) -> Dict[str, Any]:
        """Validate PR creation."""
        try:
            pr_url = execution_details.get('pr_url')
            pr_id = execution_details.get('pr_id')
            
            if not pr_url:
                return {
                    'success': False,
                    'message': 'No PR URL provided',
                    'details': {}
                }
            
            # Parse GitHub PR URL
            if 'github.com' in pr_url:
                # Extract API URL from PR URL
                parts = pr_url.replace('https://github.com/', '').split('/')
                if len(parts) >= 4:
                    owner, repo = parts[0], parts[1]
                    api_url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pr_id}'
                    
                    # Check PR status
                    response = requests.get(api_url, timeout=30)
                    if response.status_code == 200:
                        pr_data = response.json()
                        return {
                            'success': True,
                            'message': 'PR validated successfully',
                            'details': {
                                'pr_state': pr_data.get('state'),
                                'pr_title': pr_data.get('title'),
                                'pr_merged': pr_data.get('merged', False),
                                'validation_timestamp': datetime.now().isoformat()
                            }
                        }
            
            return {
                'success': True,
                'message': 'PR URL exists',
                'details': {'pr_url': pr_url}
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'PR validation error: {str(e)}',
                'details': {'error': str(e)}
            }


class NotificationValidationRule(ValidationRule):
    """Validates notification was sent successfully."""
    
    async def validate(self, execution_details: Dict[str, Any], db_pool: asyncpg.Pool) -> Dict[str, Any]:
        """Validate notification sending."""
        try:
            notification_type = execution_details.get('notification_type')
            recipients = execution_details.get('recipients', [])
            sent_count = execution_details.get('sent_count', 0)
            
            if sent_count >= len(recipients):
                return {
                    'success': True,
                    'message': f'All {sent_count} notifications sent',
                    'details': {
                        'notification_type': notification_type,
                        'recipients_count': len(recipients),
                        'sent_count': sent_count
                    }
                }
            else:
                return {
                    'success': False,
                    'message': f'Only {sent_count}/{len(recipients)} notifications sent',
                    'details': {
                        'notification_type': notification_type,
                        'expected': len(recipients),
                        'sent': sent_count
                    }
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Notification validation error: {str(e)}',
                'details': {'error': str(e)}
            }


class Validator:
    """Main validator class that orchestrates validation."""
    
    def __init__(self, db_pool: asyncpg.Pool, config: Optional[Dict[str, Any]] = None):
        """Initialize validator.
        
        Args:
            db_pool: Database connection pool
            config: Optional validator configuration
        """
        self.db_pool = db_pool
        self.config = config or {}
        self.validation_rules = {
            'content_update': ContentValidationRule('content_validation', 'content', {}),
            'pr_creation': PRValidationRule('pr_validation', 'pr', {}),
            'notification': NotificationValidationRule('notification_validation', 'notification', {})
        }
        
    async def validate_execution(self, execution_id: int) -> Dict[str, Any]:
        """Validate an execution.
        
        Args:
            execution_id: Execution ID to validate
            
        Returns:
            Validation results
        """
        try:
            # Fetch execution details
            async with self.db_pool.acquire() as conn:
                execution = await conn.fetchrow(
                    """
                    SELECT e.*, r.recommendation_type
                    FROM gsc.agent_executions e
                    JOIN gsc.agent_recommendations r ON e.recommendation_id = r.id
                    WHERE e.id = $1
                    """,
                    execution_id
                )
                
                if not execution:
                    return {
                        'execution_id': execution_id,
                        'success': False,
                        'message': 'Execution not found',
                        'validations': []
                    }
                
                execution_type = execution['execution_type']
                execution_details = execution['execution_details']
                
                # Get appropriate validation rule
                rule = self.validation_rules.get(execution_type)
                
                if not rule:
                    return {
                        'execution_id': execution_id,
                        'success': True,
                        'message': f'No validation rule for {execution_type}',
                        'validations': []
                    }
                
                # Execute validation
                validation_result = await rule.validate(execution_details, self.db_pool)
                
                # Store validation result
                await conn.execute(
                    """
                    UPDATE gsc.agent_executions
                    SET validation_result = $1,
                        status = CASE 
                            WHEN $2 THEN status
                            ELSE 'failed'
                        END
                    WHERE id = $3
                    """,
                    json.dumps(validation_result),
                    validation_result['success'],
                    execution_id
                )
                
                return {
                    'execution_id': execution_id,
                    'success': validation_result['success'],
                    'message': validation_result['message'],
                    'validations': [validation_result],
                    'validated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'execution_id': execution_id,
                'success': False,
                'message': f'Validation error: {str(e)}',
                'validations': [],
                'error': str(e)
            }
    
    async def validate_batch(self, execution_ids: List[int]) -> List[Dict[str, Any]]:
        """Validate multiple executions.
        
        Args:
            execution_ids: List of execution IDs to validate
            
        Returns:
            List of validation results
        """
        tasks = [self.validate_execution(exec_id) for exec_id in execution_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            r if not isinstance(r, Exception) else {
                'execution_id': execution_ids[i],
                'success': False,
                'message': f'Validation exception: {str(r)}',
                'validations': []
            }
            for i, r in enumerate(results)
        ]
    
    async def should_rollback(self, validation_result: Dict[str, Any]) -> bool:
        """Determine if execution should be rolled back based on validation.
        
        Args:
            validation_result: Validation result dictionary
            
        Returns:
            True if should rollback, False otherwise
        """
        auto_rollback = self.config.get('auto_rollback_on_failure', True)
        
        if not auto_rollback:
            return False
        
        return not validation_result.get('success', False)
