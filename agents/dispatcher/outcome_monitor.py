"""Outcome monitoring system for tracking execution results over time."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import asyncpg


class OutcomeMonitor:
    """Monitors execution outcomes and tracks performance metrics."""
    
    def __init__(self, db_pool: asyncpg.Pool, config: Optional[Dict[str, Any]] = None):
        """Initialize outcome monitor.
        
        Args:
            db_pool: Database connection pool
            config: Optional monitor configuration
        """
        self.db_pool = db_pool
        self.config = config or {}
        self.monitoring_days = config.get('outcome_monitoring_days', 30)
        self.metrics_interval_hours = config.get('metrics_collection_interval_hours', 24)
        self.performance_threshold = config.get('performance_threshold', {})
        
    async def start_monitoring(self, execution_id: int) -> Dict[str, Any]:
        """Start monitoring an execution.
        
        Args:
            execution_id: Execution ID to monitor
            
        Returns:
            Monitoring setup result
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get execution details
                execution = await conn.fetchrow(
                    """
                    SELECT e.*, r.recommendation_type, r.diagnosis_id
                    FROM gsc.agent_executions e
                    JOIN gsc.agent_recommendations r ON e.recommendation_id = r.id
                    WHERE e.id = $1
                    """,
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found',
                        'execution_id': execution_id
                    }
                
                # Get affected URLs from execution details
                execution_details = execution['execution_details']
                urls = execution_details.get('urls', [])
                if isinstance(execution_details.get('url'), str):
                    urls.append(execution_details['url'])
                
                if not urls:
                    return {
                        'success': False,
                        'message': 'No URLs found to monitor',
                        'execution_id': execution_id
                    }
                
                # Collect baseline metrics
                baseline_metrics = await self._collect_baseline_metrics(urls, conn)
                
                # Initialize outcome metrics
                outcome_metrics = {
                    'monitoring_started_at': datetime.now().isoformat(),
                    'monitoring_end_date': (datetime.now() + timedelta(days=self.monitoring_days)).isoformat(),
                    'baseline_metrics': baseline_metrics,
                    'daily_metrics': [],
                    'urls_monitored': urls
                }
                
                # Update execution with initial outcome metrics
                await conn.execute(
                    """
                    UPDATE gsc.agent_executions
                    SET outcome_metrics = $1
                    WHERE id = $2
                    """,
                    json.dumps(outcome_metrics),
                    execution_id
                )
                
                return {
                    'success': True,
                    'message': f'Monitoring started for {len(urls)} URLs',
                    'execution_id': execution_id,
                    'monitoring_period_days': self.monitoring_days,
                    'urls_monitored': len(urls)
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error starting monitoring: {str(e)}',
                'execution_id': execution_id,
                'error': str(e)
            }
    
    async def collect_metrics(self, execution_id: int) -> Dict[str, Any]:
        """Collect current metrics for monitored execution.
        
        Args:
            execution_id: Execution ID to collect metrics for
            
        Returns:
            Collected metrics
        """
        try:
            async with self.db_pool.acquire() as conn:
                execution = await conn.fetchrow(
                    """
                    SELECT outcome_metrics, execution_details
                    FROM gsc.agent_executions
                    WHERE id = $1
                    """,
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found'
                    }
                
                outcome_metrics = execution['outcome_metrics']
                urls = outcome_metrics.get('urls_monitored', [])
                
                if not urls:
                    return {
                        'success': False,
                        'message': 'No URLs being monitored'
                    }
                
                # Collect current metrics
                current_metrics = await self._collect_current_metrics(urls, conn)
                baseline_metrics = outcome_metrics.get('baseline_metrics', {})
                
                # Calculate improvements
                improvements = self._calculate_improvements(baseline_metrics, current_metrics)
                
                # Append to daily metrics
                daily_metrics = outcome_metrics.get('daily_metrics', [])
                daily_metrics.append({
                    'collected_at': datetime.now().isoformat(),
                    'metrics': current_metrics,
                    'improvements': improvements
                })
                
                # Update outcome metrics
                outcome_metrics['daily_metrics'] = daily_metrics
                outcome_metrics['latest_metrics'] = current_metrics
                outcome_metrics['latest_improvements'] = improvements
                outcome_metrics['last_collected_at'] = datetime.now().isoformat()
                
                await conn.execute(
                    """
                    UPDATE gsc.agent_executions
                    SET outcome_metrics = $1
                    WHERE id = $2
                    """,
                    json.dumps(outcome_metrics),
                    execution_id
                )
                
                return {
                    'success': True,
                    'message': 'Metrics collected',
                    'execution_id': execution_id,
                    'metrics': current_metrics,
                    'improvements': improvements
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error collecting metrics: {str(e)}',
                'error': str(e)
            }
    
    async def evaluate_outcome(self, execution_id: int) -> Dict[str, Any]:
        """Evaluate overall outcome of execution.
        
        Args:
            execution_id: Execution ID to evaluate
            
        Returns:
            Outcome evaluation
        """
        try:
            async with self.db_pool.acquire() as conn:
                execution = await conn.fetchrow(
                    """
                    SELECT e.*, r.expected_impact, r.expected_traffic_lift_pct
                    FROM gsc.agent_executions e
                    JOIN gsc.agent_recommendations r ON e.recommendation_id = r.id
                    WHERE e.id = $1
                    """,
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found'
                    }
                
                outcome_metrics = execution['outcome_metrics']
                latest_improvements = outcome_metrics.get('latest_improvements', {})
                
                # Evaluate against thresholds
                min_traffic_lift = self.performance_threshold.get('min_traffic_lift_pct', 5.0)
                min_ctr_improvement = self.performance_threshold.get('min_ctr_improvement_pct', 2.0)
                
                traffic_lift = latest_improvements.get('clicks_improvement_pct', 0)
                ctr_improvement = latest_improvements.get('ctr_improvement_pct', 0)
                
                meets_expectations = (
                    traffic_lift >= min_traffic_lift or
                    ctr_improvement >= min_ctr_improvement
                )
                
                # Compare with expected impact
                expected_lift = execution['expected_traffic_lift_pct'] or 0
                achieved_ratio = (traffic_lift / expected_lift * 100) if expected_lift > 0 else 0
                
                evaluation = {
                    'execution_id': execution_id,
                    'meets_expectations': meets_expectations,
                    'traffic_lift_pct': traffic_lift,
                    'ctr_improvement_pct': ctr_improvement,
                    'expected_lift_pct': expected_lift,
                    'achievement_ratio_pct': achieved_ratio,
                    'evaluation_date': datetime.now().isoformat(),
                    'monitoring_complete': self._is_monitoring_complete(outcome_metrics)
                }
                
                # Update recommendation with actual impact
                if meets_expectations:
                    await conn.execute(
                        """
                        UPDATE gsc.agent_recommendations
                        SET actual_impact = $1,
                            implemented = TRUE,
                            implemented_at = $2
                        WHERE id = $3
                        """,
                        json.dumps(evaluation),
                        execution['completed_at'],
                        execution['recommendation_id']
                    )
                
                return {
                    'success': True,
                    'message': 'Outcome evaluated',
                    'evaluation': evaluation
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error evaluating outcome: {str(e)}',
                'error': str(e)
            }
    
    async def get_monitoring_status(self, execution_id: int) -> Dict[str, Any]:
        """Get current monitoring status.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Monitoring status
        """
        try:
            async with self.db_pool.acquire() as conn:
                execution = await conn.fetchrow(
                    "SELECT outcome_metrics, started_at FROM gsc.agent_executions WHERE id = $1",
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found'
                    }
                
                outcome_metrics = execution['outcome_metrics']
                
                if not outcome_metrics or 'monitoring_started_at' not in outcome_metrics:
                    return {
                        'success': False,
                        'message': 'Monitoring not started'
                    }
                
                monitoring_start = datetime.fromisoformat(outcome_metrics['monitoring_started_at'])
                monitoring_end = datetime.fromisoformat(outcome_metrics['monitoring_end_date'])
                days_elapsed = (datetime.now() - monitoring_start).days
                days_remaining = (monitoring_end - datetime.now()).days
                
                return {
                    'success': True,
                    'execution_id': execution_id,
                    'monitoring_active': days_remaining > 0,
                    'days_elapsed': days_elapsed,
                    'days_remaining': max(0, days_remaining),
                    'total_monitoring_days': self.monitoring_days,
                    'metrics_collected': len(outcome_metrics.get('daily_metrics', [])),
                    'urls_monitored': len(outcome_metrics.get('urls_monitored', [])),
                    'latest_improvements': outcome_metrics.get('latest_improvements', {})
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting status: {str(e)}',
                'error': str(e)
            }
    
    async def _collect_baseline_metrics(self, urls: List[str], conn) -> Dict[str, Any]:
        """Collect baseline metrics for URLs."""
        try:
            # Get last 7 days of data as baseline
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            metrics = {}
            for url in urls:
                url_metrics = await conn.fetchrow(
                    """
                    SELECT 
                        SUM(clicks) as total_clicks,
                        SUM(impressions) as total_impressions,
                        AVG(ctr) as avg_ctr,
                        AVG(position) as avg_position
                    FROM gsc.fact_gsc_daily
                    WHERE url = $1 
                    AND date BETWEEN $2 AND $3
                    """,
                    url, start_date, end_date
                )
                
                if url_metrics:
                    metrics[url] = {
                        'clicks': float(url_metrics['total_clicks'] or 0),
                        'impressions': float(url_metrics['total_impressions'] or 0),
                        'ctr': float(url_metrics['avg_ctr'] or 0),
                        'position': float(url_metrics['avg_position'] or 0)
                    }
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting baseline metrics: {e}")
            return {}
    
    async def _collect_current_metrics(self, urls: List[str], conn) -> Dict[str, Any]:
        """Collect current metrics for URLs."""
        try:
            # Get last 7 days of data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            metrics = {}
            for url in urls:
                url_metrics = await conn.fetchrow(
                    """
                    SELECT 
                        SUM(clicks) as total_clicks,
                        SUM(impressions) as total_impressions,
                        AVG(ctr) as avg_ctr,
                        AVG(position) as avg_position
                    FROM gsc.fact_gsc_daily
                    WHERE url = $1 
                    AND date BETWEEN $2 AND $3
                    """,
                    url, start_date, end_date
                )
                
                if url_metrics:
                    metrics[url] = {
                        'clicks': float(url_metrics['total_clicks'] or 0),
                        'impressions': float(url_metrics['total_impressions'] or 0),
                        'ctr': float(url_metrics['avg_ctr'] or 0),
                        'position': float(url_metrics['avg_position'] or 0)
                    }
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting current metrics: {e}")
            return {}
    
    def _calculate_improvements(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate improvements from baseline to current."""
        improvements = {}
        
        for url in baseline.keys():
            if url not in current:
                continue
            
            base = baseline[url]
            curr = current[url]
            
            # Calculate percentage improvements
            clicks_improvement = ((curr['clicks'] - base['clicks']) / base['clicks'] * 100) if base['clicks'] > 0 else 0
            impressions_improvement = ((curr['impressions'] - base['impressions']) / base['impressions'] * 100) if base['impressions'] > 0 else 0
            ctr_improvement = ((curr['ctr'] - base['ctr']) / base['ctr'] * 100) if base['ctr'] > 0 else 0
            position_improvement = base['position'] - curr['position']  # Lower is better
            
            improvements[url] = {
                'clicks_improvement_pct': round(clicks_improvement, 2),
                'impressions_improvement_pct': round(impressions_improvement, 2),
                'ctr_improvement_pct': round(ctr_improvement, 2),
                'position_improvement': round(position_improvement, 2)
            }
        
        # Calculate aggregate improvements
        if improvements:
            improvements['aggregate'] = {
                'clicks_improvement_pct': round(sum(i['clicks_improvement_pct'] for i in improvements.values() if isinstance(i, dict)) / len(improvements), 2),
                'ctr_improvement_pct': round(sum(i['ctr_improvement_pct'] for i in improvements.values() if isinstance(i, dict)) / len(improvements), 2)
            }
        
        return improvements
    
    def _is_monitoring_complete(self, outcome_metrics: Dict[str, Any]) -> bool:
        """Check if monitoring period is complete."""
        if 'monitoring_end_date' not in outcome_metrics:
            return False
        
        end_date = datetime.fromisoformat(outcome_metrics['monitoring_end_date'])
        return datetime.now() >= end_date
