"""Diagnostician Agent - Analyzes findings and performs root cause analysis."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.diagnostician.correlation_engine import CorrelationEngine
from agents.diagnostician.issue_classifier import IssueClassifier
from agents.diagnostician.root_cause_analyzer import RootCauseAnalyzer


class DiagnosticianAgent(AgentContract):
    """Agent that diagnoses issues and performs root cause analysis."""

    def __init__(
        self,
        agent_id: str,
        db_config: Dict[str, str],
        config: Optional[Dict[str, any]] = None
    ):
        """Initialize diagnostician agent.
        
        Args:
            agent_id: Unique agent identifier
            db_config: Database configuration
            config: Optional agent configuration
        """
        super().__init__(agent_id, "diagnostician", config)
        
        self.db_config = db_config
        self._pool: Optional[asyncpg.Pool] = None
        
        # Initialize components
        self.root_cause_analyzer = RootCauseAnalyzer(
            min_confidence=config.get('min_confidence', 0.6)
        )
        
        self.correlation_engine = CorrelationEngine(
            min_correlation=config.get('min_correlation', 0.5)
        )
        
        self.issue_classifier = IssueClassifier()
        
        self._diagnoses: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the diagnostician agent."""
        try:
            self._start_time = datetime.now()
            
            # Connect to database
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                user=self.db_config.get('user', 'gsc_user'),
                password=self.db_config.get('password', ''),
                database=self.db_config.get('database', 'gsc_warehouse'),
                min_size=2,
                max_size=10
            )
            
            self._set_status(AgentStatus.RUNNING)
            
            return True
        
        except Exception as e:
            print(f"Error initializing diagnostician agent: {e}")
            self._set_status(AgentStatus.ERROR)
            self._increment_error_count()
            return False

    async def process(self, input_data: Dict[str, any]) -> Dict[str, any]:
        """Process diagnosis request.
        
        Args:
            input_data: Input containing diagnosis parameters
            
        Returns:
            Processing results
        """
        try:
            finding_id = input_data.get('finding_id')
            page_path = input_data.get('page_path')
            
            if finding_id:
                diagnosis = await self.analyze_finding(finding_id)
                self._increment_processed_count()
                
                return {
                    'status': 'success',
                    'finding_id': finding_id,
                    'diagnosis': diagnosis,
                    'agent_id': self.agent_id
                }
            elif page_path:
                report = await self.generate_report(page_path)
                self._increment_processed_count()
                
                return {
                    'status': 'success',
                    'page_path': page_path,
                    'report': report,
                    'agent_id': self.agent_id
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Missing finding_id or page_path',
                    'agent_id': self.agent_id
                }
        
        except Exception as e:
            self._increment_error_count()
            return {
                'status': 'error',
                'error': str(e),
                'agent_id': self.agent_id
            }

    async def analyze_finding(self, finding_id: int) -> Dict[str, any]:
        """Analyze a finding and generate diagnosis.
        
        Args:
            finding_id: Finding ID to analyze
            
        Returns:
            Diagnosis dictionary
        """
        # Get finding details
        finding = await self._get_finding(finding_id)
        
        if not finding:
            return {'error': 'Finding not found'}
        
        # Get page metrics
        affected_pages = json.loads(finding['affected_pages']) if finding['affected_pages'] else []
        
        if not affected_pages:
            return {'error': 'No affected pages in finding'}
        
        page_path = affected_pages[0]
        
        # Get current and historical metrics
        current_metrics = await self._get_page_current_metrics(page_path)
        historical_metrics = await self._get_page_historical_metrics(page_path, days=30)
        
        # Perform root cause analysis based on finding type
        finding_type = finding['finding_type']
        finding_metrics = json.loads(finding['metrics']) if finding['metrics'] else {}
        
        root_cause = None
        
        if finding_type == 'anomaly':
            metric_name = finding_metrics.get('metric_name', '')
            
            if 'click' in metric_name.lower() or 'traffic' in metric_name.lower():
                root_cause = self.root_cause_analyzer.analyze_traffic_drop(
                    current_metrics,
                    historical_metrics,
                    finding_metrics.get('context', {})
                )
            elif 'engagement' in metric_name.lower() or 'bounce' in metric_name.lower():
                root_cause = self.root_cause_analyzer.analyze_engagement_issue(
                    current_metrics,
                    historical_metrics
                )
            elif 'conversion' in metric_name.lower():
                root_cause = self.root_cause_analyzer.analyze_conversion_issue(
                    current_metrics,
                    historical_metrics
                )
            elif 'zero' in metric_name.lower():
                root_cause = self.root_cause_analyzer.analyze_technical_issue(
                    current_metrics
                )
        
        # If no root cause found, try general analysis
        if not root_cause:
            root_cause = self.root_cause_analyzer.analyze_traffic_drop(
                current_metrics,
                historical_metrics,
                finding_metrics.get('context', {})
            )
        
        if not root_cause:
            return {
                'finding_id': finding_id,
                'diagnosis': 'Unable to determine root cause',
                'confidence': 0.0
            }
        
        # Classify issue
        classification = self.issue_classifier.classify_issue(
            root_cause.cause_type,
            current_metrics,
            root_cause.evidence
        )
        
        # Perform correlation analysis
        metric_data = {}
        for metric in ['clicks', 'impressions', 'ctr', 'avg_position', 'engagement_rate']:
            metric_data[metric] = [m.get(metric, 0) for m in historical_metrics]
        
        correlations = self.correlation_engine.find_correlations(metric_data)
        
        # Store diagnosis
        diagnosis_id = await self._store_diagnosis(
            finding_id,
            root_cause,
            classification,
            correlations
        )
        
        self._diagnoses.append({
            'id': diagnosis_id,
            'finding_id': finding_id,
            'root_cause': root_cause.cause_type,
            'confidence': root_cause.confidence
        })
        
        return {
            'diagnosis_id': diagnosis_id,
            'finding_id': finding_id,
            'root_cause': root_cause.cause_type,
            'confidence': root_cause.confidence,
            'severity': root_cause.severity,
            'classification': {
                'category': classification.category,
                'subcategory': classification.subcategory,
                'priority': classification.priority,
                'impact_score': classification.impact_score
            },
            'evidence': root_cause.evidence,
            'recommendations': root_cause.recommendations,
            'correlations': [
                {
                    'metric1': c.metric1,
                    'metric2': c.metric2,
                    'correlation': c.correlation_coefficient,
                    'strength': c.strength
                }
                for c in correlations[:5]
            ]
        }

    async def generate_report(self, page_path: str) -> Dict[str, any]:
        """Generate comprehensive diagnosis report for a page.
        
        Args:
            page_path: Page path to analyze
            
        Returns:
            Diagnosis report
        """
        # Get all findings for this page
        findings = await self._get_page_findings(page_path)
        
        if not findings:
            return {
                'page_path': page_path,
                'status': 'no_findings',
                'message': 'No findings for this page'
            }
        
        # Analyze each finding
        diagnoses = []
        for finding in findings:
            diagnosis = await self.analyze_finding(finding['id'])
            if 'error' not in diagnosis:
                diagnoses.append(diagnosis)
        
        # Get current and historical metrics
        current_metrics = await self._get_page_current_metrics(page_path)
        historical_metrics = await self._get_page_historical_metrics(page_path, days=30)
        
        # Comprehensive correlation analysis
        metric_data = {}
        for metric in ['clicks', 'impressions', 'ctr', 'avg_position', 
                      'engagement_rate', 'conversion_rate', 'bounce_rate']:
            metric_data[metric] = [m.get(metric, 0) for m in historical_metrics if m.get(metric) is not None]
        
        all_correlations = self.correlation_engine.find_correlations(metric_data)
        
        # Classify all issues
        classifications = []
        for diagnosis in diagnoses:
            if 'classification' in diagnosis:
                classifications.append(diagnosis['classification'])
        
        # Prioritize issues
        # (We'd need the full IssueClassification objects for this)
        
        return {
            'page_path': page_path,
            'findings_analyzed': len(findings),
            'diagnoses_generated': len(diagnoses),
            'diagnoses': diagnoses,
            'current_metrics': current_metrics,
            'correlations': [
                {
                    'metric1': c.metric1,
                    'metric2': c.metric2,
                    'correlation': c.correlation_coefficient,
                    'strength': c.strength,
                    'p_value': c.p_value
                }
                for c in all_correlations[:10]
            ],
            'summary': self._generate_summary(diagnoses)
        }

    def _generate_summary(self, diagnoses: List[Dict]) -> Dict[str, any]:
        """Generate summary of diagnoses.
        
        Args:
            diagnoses: List of diagnosis dicts
            
        Returns:
            Summary dictionary
        """
        if not diagnoses:
            return {'status': 'no_diagnoses'}
        
        # Count by root cause
        root_causes = {}
        priorities = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for diagnosis in diagnoses:
            root_cause = diagnosis.get('root_cause', 'unknown')
            root_causes[root_cause] = root_causes.get(root_cause, 0) + 1
            
            if 'classification' in diagnosis:
                priority = diagnosis['classification'].get('priority', 'low')
                priorities[priority] = priorities.get(priority, 0) + 1
        
        # Get highest priority issue
        top_priority_diagnosis = max(
            diagnoses,
            key=lambda d: d.get('confidence', 0)
        )
        
        return {
            'total_issues': len(diagnoses),
            'root_causes': root_causes,
            'priority_breakdown': priorities,
            'top_issue': {
                'root_cause': top_priority_diagnosis.get('root_cause'),
                'confidence': top_priority_diagnosis.get('confidence'),
                'priority': top_priority_diagnosis.get('classification', {}).get('priority')
            },
            'avg_confidence': sum(d.get('confidence', 0) for d in diagnoses) / len(diagnoses)
        }

    async def _get_finding(self, finding_id: int) -> Optional[Dict]:
        """Get finding by ID."""
        query = """
            SELECT id, finding_type, severity, affected_pages, metrics, detected_at
            FROM gsc.agent_findings
            WHERE id = $1
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, finding_id)
        
        return dict(row) if row else None

    async def _get_page_findings(self, page_path: str) -> List[Dict]:
        """Get all findings for a page."""
        query = """
            SELECT id, finding_type, severity, affected_pages, metrics, detected_at
            FROM gsc.agent_findings
            WHERE affected_pages::text LIKE $1
            ORDER BY detected_at DESC
            LIMIT 20
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, f'%{page_path}%')
        
        return [dict(row) for row in rows]

    async def _get_page_current_metrics(self, page_path: str) -> Dict[str, float]:
        """Get current metrics for a page."""
        query = """
            SELECT clicks, impressions, ctr, avg_position,
                   engagement_rate, conversion_rate, bounce_rate,
                   sessions, avg_session_duration
            FROM gsc.mv_unified_page_performance
            WHERE page_path = $1
            ORDER BY date DESC
            LIMIT 1
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, page_path)
        
        return dict(row) if row else {}

    async def _get_page_historical_metrics(
        self,
        page_path: str,
        days: int = 30
    ) -> List[Dict[str, float]]:
        """Get historical metrics for a page."""
        query = """
            SELECT date, clicks, impressions, ctr, avg_position,
                   engagement_rate, conversion_rate, bounce_rate,
                   sessions, avg_session_duration
            FROM gsc.mv_unified_page_performance
            WHERE page_path = $1
              AND date >= CURRENT_DATE - $2
            ORDER BY date ASC
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, page_path, days)
        
        return [dict(row) for row in rows]

    async def _store_diagnosis(
        self,
        finding_id: int,
        root_cause,
        classification,
        correlations
    ) -> int:
        """Store diagnosis in database."""
        query = """
            INSERT INTO gsc.agent_diagnoses (
                finding_id, agent_name, root_cause, confidence_score,
                supporting_evidence, related_pages, notes, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """
        
        supporting_evidence = {
            'evidence': root_cause.evidence,
            'classification': {
                'category': classification.category,
                'subcategory': classification.subcategory,
                'priority': classification.priority,
                'impact_score': classification.impact_score,
                'urgency_score': classification.urgency_score,
                'tags': classification.tags
            },
            'correlations': [
                {
                    'metric1': c.metric1,
                    'metric2': c.metric2,
                    'correlation': c.correlation_coefficient
                }
                for c in correlations[:5]
            ]
        }
        
        recommendations_text = '\n'.join(f"- {rec}" for rec in root_cause.recommendations)
        
        async with self._pool.acquire() as conn:
            diagnosis_id = await conn.fetchval(
                query,
                finding_id,
                self.agent_id,
                root_cause.cause_type,
                root_cause.confidence,
                json.dumps(supporting_evidence),
                json.dumps([]),  # related_pages
                recommendations_text,
                json.dumps({'severity': root_cause.severity})
            )
        
        return diagnosis_id

    async def health_check(self) -> AgentHealth:
        """Check agent health."""
        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return AgentHealth(
            agent_id=self.agent_id,
            status=self.status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={
                'diagnoses_generated': len(self._diagnoses)
            }
        )

    async def shutdown(self) -> bool:
        """Shutdown the agent."""
        try:
            if self._pool:
                await self._pool.close()
            
            self._set_status(AgentStatus.SHUTDOWN)
            
            return True
        
        except Exception as e:
            print(f"Error shutting down: {e}")
            return False


async def main():
    """CLI for diagnostician agent."""
    parser = argparse.ArgumentParser(description='Diagnostician Agent')
    parser.add_argument('--initialize', action='store_true', help='Initialize agent')
    parser.add_argument('--analyze', action='store_true', help='Analyze finding')
    parser.add_argument('--finding-id', type=int, help='Finding ID to analyze')
    parser.add_argument('--report', action='store_true', help='Generate diagnosis report')
    parser.add_argument('--page-path', help='Page path for report')
    parser.add_argument('--config', default='agents/diagnostician/config.yaml', help='Config file')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'user': 'gsc_user',
                'password': 'changeme',
                'database': 'gsc_warehouse'
            },
            'min_confidence': 0.6,
            'min_correlation': 0.5
        }
    
    # Create agent
    agent = DiagnosticianAgent(
        agent_id='diagnostician_001',
        db_config=config.get('database', {}),
        config=config
    )
    
    if args.initialize:
        print("Initializing diagnostician agent...")
        success = await agent.initialize()
        if success:
            print("✓ Diagnostician agent initialized")
        else:
            print("✗ Failed to initialize")
            return
    
    if args.analyze and args.finding_id:
        print(f"Analyzing finding {args.finding_id}...")
        
        if not agent._pool:
            await agent.initialize()
        
        diagnosis = await agent.analyze_finding(args.finding_id)
        
        if 'error' in diagnosis:
            print(f"✗ Error: {diagnosis['error']}")
        else:
            print(f"✓ Diagnosis generated")
            print(f"\nRoot Cause: {diagnosis['root_cause']}")
            print(f"Confidence: {diagnosis['confidence']:.2%}")
            print(f"Severity: {diagnosis['severity']}")
            print(f"\nClassification:")
            print(f"  Category: {diagnosis['classification']['category']}")
            print(f"  Priority: {diagnosis['classification']['priority']}")
            print(f"  Impact: {diagnosis['classification']['impact_score']:.1f}/10")
            print(f"\nRecommendations:")
            for i, rec in enumerate(diagnosis['recommendations'], 1):
                print(f"  {i}. {rec}")
    
    if args.report and args.page_path:
        print(f"Generating report for {args.page_path}...")
        
        if not agent._pool:
            await agent.initialize()
        
        report = await agent.generate_report(args.page_path)
        
        print(f"✓ Report generated")
        print(f"\nFindings Analyzed: {report['findings_analyzed']}")
        print(f"Diagnoses Generated: {report['diagnoses_generated']}")
        
        if 'summary' in report:
            summary = report['summary']
            print(f"\nSummary:")
            print(f"  Total Issues: {summary.get('total_issues', 0)}")
            if 'top_issue' in summary:
                top = summary['top_issue']
                print(f"  Top Issue: {top.get('root_cause')} ({top.get('confidence', 0):.1%} confidence)")
    
    # Shutdown
    await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
