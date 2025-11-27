"""
Celery Tasks for Async Processing
==================================
Phase 1 Tasks:
- Content embedding generation
- Content quality analysis
- Prophet forecasting
- Hugo content sync

Phase 2 Tasks:
- Topic clustering
- Natural language query
- Intelligent agent analysis
- Content scraping and monitoring

Phase 3 Tasks:
- SERP position tracking
- Core Web Vitals monitoring
- Causal impact analysis
- Auto-PR generation

Phase 4 Tasks:
- Notification queue processing
- Anomaly detection (SERP, traffic, CWV)
- Multi-agent workflow execution
- Alert rule evaluation
"""
import logging
import os
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from celery import Celery
from celery.schedules import crontab

# Initialize Celery
celery_app = Celery(
    'gsc_tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

logger = logging.getLogger(__name__)

# =============================================
# EMBEDDING TASKS
# =============================================

@celery_app.task(name='generate_embeddings', bind=True, max_retries=3)
def generate_embeddings_task(self, property: str, page_paths: List[str] = None):
    """
    Generate embeddings for pages

    Args:
        property: Property URL
        page_paths: Optional list of specific pages (None = all pages)
    """
    try:
        from insights_core.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator()
        result = generator.generate_for_property(property, page_paths)

        logger.info(f"Generated {result['embeddings_created']} embeddings for {property}")
        return result

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name='update_page_embedding', bind=True, max_retries=3)
def update_page_embedding_task(self, property: str, page_path: str, content: str):
    """
    Update embedding for a single page

    Args:
        property: Property URL
        page_path: Page path
        content: Page text content
    """
    try:
        from insights_core.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator()
        embedding = generator.generate_single(content)
        generator.store_embedding(property, page_path, embedding)

        logger.info(f"Updated embedding for {property}{page_path}")
        return {'property': property, 'page_path': page_path, 'success': True}

    except Exception as e:
        logger.error(f"Error updating embedding: {e}")
        raise self.retry(exc=e, countdown=30)


# =============================================
# CONTENT ANALYSIS TASKS
# =============================================

@celery_app.task(name='analyze_content', bind=True, max_retries=3)
def analyze_content_task(self, property: str, page_path: str, html_content: str):
    """
    Analyze content quality using Ollama

    Args:
        property: Property URL
        page_path: Page path
        html_content: Raw HTML content
    """
    try:
        from insights_core.content_analyzer import ContentAnalyzer

        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(property, page_path, html_content)

        logger.info(f"Analyzed content for {property}{page_path}")
        return analysis

    except Exception as e:
        logger.error(f"Error analyzing content: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name='batch_analyze_content', bind=True)
def batch_analyze_content_task(self, property: str, pages: List[Dict]):
    """
    Batch analyze multiple pages

    Args:
        property: Property URL
        pages: List of {page_path, html_content} dicts
    """
    try:
        from insights_core.content_analyzer import ContentAnalyzer

        analyzer = ContentAnalyzer()
        results = []

        for page in pages:
            analysis = analyzer.analyze(
                property,
                page['page_path'],
                page['html_content']
            )
            results.append(analysis)

        logger.info(f"Batch analyzed {len(results)} pages for {property}")
        return {'analyzed': len(results), 'results': results}

    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise


# =============================================
# FORECASTING TASKS
# =============================================

@celery_app.task(name='generate_forecasts', bind=True, max_retries=2)
def generate_forecasts_task(self, property: str, page_path: str = None, days_ahead: int = 30):
    """
    Generate Prophet forecasts

    Args:
        property: Property URL
        page_path: Optional specific page (None = all pages)
        days_ahead: Days to forecast
    """
    try:
        from insights_core.forecasting import ProphetForecaster

        forecaster = ProphetForecaster()

        if page_path:
            result = forecaster.forecast_page(property, page_path, days_ahead)
        else:
            result = forecaster.forecast_property(property, days_ahead)

        logger.info(f"Generated {days_ahead}-day forecast for {property}")
        return result

    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='detect_anomalies_prophet', bind=True)
def detect_anomalies_task(self, property: str, lookback_days: int = 7):
    """
    Detect anomalies using Prophet forecasts

    Args:
        property: Property URL
        lookback_days: Days to look back
    """
    try:
        from insights_core.forecasting import ProphetForecaster

        forecaster = ProphetForecaster()
        anomalies = forecaster.detect_anomalies(property, lookback_days)

        logger.info(f"Detected {len(anomalies)} anomalies for {property}")
        return {'anomaly_count': len(anomalies), 'anomalies': anomalies}

    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise


# =============================================
# CANNIBALIZATION DETECTION
# =============================================

@celery_app.task(name='detect_cannibalization', bind=True, max_retries=2)
def detect_cannibalization_task(self, property: str, similarity_threshold: float = 0.8):
    """
    Detect content cannibalization using embeddings

    Args:
        property: Property URL
        similarity_threshold: Minimum similarity to flag (0-1)
    """
    try:
        from insights_core.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator()
        cannibalization = generator.find_cannibalization(property, similarity_threshold)

        logger.info(f"Found {len(cannibalization)} cannibalization pairs for {property}")
        return {'pairs_found': len(cannibalization), 'pairs': cannibalization}

    except Exception as e:
        logger.error(f"Error detecting cannibalization: {e}")
        raise self.retry(exc=e, countdown=90)


# =============================================
# HUGO SYNC TASKS
# =============================================

@celery_app.task(name='sync_hugo_content', bind=True, max_retries=2)
def sync_hugo_content_task(self, hugo_path: str = None):
    """
    Sync Hugo content to database

    Args:
        hugo_path: Path to Hugo site (or use HUGO_CONTENT_PATH env var)

    Returns:
        Dict with sync statistics
    """
    import os
    from services.hugo_sync import HugoContentTracker

    path = hugo_path or os.getenv('HUGO_CONTENT_PATH')

    if not path:
        return {
            'status': 'skipped',
            'reason': 'Hugo path not configured'
        }

    try:
        tracker = HugoContentTracker(path)
        stats = tracker.sync()
        return {
            'status': 'success',
            **stats
        }
    except Exception as e:
        logger.error(f"Error syncing Hugo content: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


# =============================================
# PHASE 2 TASKS
# =============================================

@celery_app.task(name='auto_cluster_topics', bind=True, max_retries=2)
def auto_cluster_topics_task(self, property: str, n_clusters: int = None):
    """
    Auto-cluster content into topics

    Args:
        property: Property URL
        n_clusters: Number of clusters (None = auto-detect)
    """
    try:
        from insights_core.topic_clustering import TopicClusterer

        clusterer = TopicClusterer()
        result = clusterer.auto_cluster_sync(property, n_clusters)

        logger.info(f"Created {result.get('topics_created', 0)} topics for {property}")
        return result

    except Exception as e:
        logger.error(f"Error clustering topics: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='natural_language_query', bind=True, max_retries=2)
def natural_language_query_task(self, question: str, context: Dict = None):
    """
    Execute natural language query

    Args:
        question: Natural language question
        context: Optional context dict
    """
    try:
        from insights_core.nl_query import NaturalLanguageQuery

        nlq = NaturalLanguageQuery()
        result = nlq.query_sync(question, context, execute=True)

        logger.info(f"NL Query completed: {result.get('row_count', 0)} rows")
        return result

    except Exception as e:
        logger.error(f"Error in NL query: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(name='run_intelligent_watcher', bind=True, max_retries=2)
def run_intelligent_watcher_task(self, property: str):
    """
    Run intelligent watcher agent

    Args:
        property: Property URL to analyze
    """
    try:
        from agents.watcher.intelligent_watcher import IntelligentWatcherAgent

        watcher = IntelligentWatcherAgent()
        result = watcher.analyze_property_sync(property)

        logger.info(f"Intelligent Watcher completed for {property}")
        return result

    except Exception as e:
        logger.error(f"Error in intelligent watcher: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name='monitor_content_changes', bind=True, max_retries=2)
def monitor_content_changes_task(self, property: str, page_paths: List[str] = None):
    """
    Monitor content changes

    Args:
        property: Property URL
        page_paths: Optional specific pages
    """
    try:
        from services.content_scraper import ContentScraper

        scraper = ContentScraper()
        result = scraper.monitor_property_sync(property, page_paths)

        logger.info(f"Monitored {result.get('pages_monitored', 0)} pages, {result.get('changes_detected', 0)} changes")
        return result

    except Exception as e:
        logger.error(f"Error monitoring content: {e}")
        raise self.retry(exc=e, countdown=90)


# =============================================
# PHASE 3 TASKS
# =============================================

@celery_app.task(name='track_serp_positions', bind=True, max_retries=2)
def track_serp_positions_task(self, property: str = None, device: str = None):
    """
    Track SERP positions for active queries

    Args:
        property: Property URL (None = all properties)
        device: Device type ('mobile' or 'desktop', None = both)
    """
    try:
        from insights_core.serp_tracker import SerpTracker

        tracker = SerpTracker()
        result = tracker.track_all_queries_sync(property, device)

        logger.info(f"Tracked {result.get('queries_tracked', 0)} SERP queries")
        return result

    except Exception as e:
        logger.error(f"Error tracking SERP positions: {e}")
        raise self.retry(exc=e, countdown=300)  # 5 min delay (API rate limiting)


@celery_app.task(name='monitor_core_web_vitals', bind=True, max_retries=2)
def monitor_core_web_vitals_task(self, property: str, page_paths: List[str] = None, strategies: List[str] = None):
    """
    Monitor Core Web Vitals for pages

    Args:
        property: Property URL
        page_paths: Optional list of specific pages
        strategies: Optional strategies list ['mobile', 'desktop']
    """
    try:
        from insights_core.cwv_monitor import CoreWebVitalsMonitor

        monitor = CoreWebVitalsMonitor()

        if not page_paths:
            # Get top pages to monitor by traffic (limit to save API quota)
            conn = None
            try:
                conn = psycopg2.connect(os.getenv('WAREHOUSE_DSN'))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT page_path
                    FROM gsc.vw_unified_page_performance
                    WHERE property = %s
                      AND date >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY gsc_clicks DESC NULLS LAST
                    LIMIT 20
                """, (property,))
                page_paths = [row[0] for row in cursor.fetchall()]
                cursor.close()
                logger.info(f"Fetched {len(page_paths)} top pages for CWV monitoring")
            except Exception as e:
                logger.warning(f"Error fetching top pages: {e}")
                page_paths = []
            finally:
                if conn:
                    conn.close()

            # Fallback to homepage if no data
            if not page_paths:
                page_paths = ['/']
                logger.info("No top pages found, falling back to homepage")

        result = monitor.monitor_pages_sync(property, page_paths, strategies)

        logger.info(f"Monitored {result.get('pages_monitored', 0)} pages for CWV")
        return result

    except Exception as e:
        logger.error(f"Error monitoring CWV: {e}")
        raise self.retry(exc=e, countdown=120)  # 2 min delay (API rate limiting)


@celery_app.task(name='analyze_causal_impact', bind=True, max_retries=2)
def analyze_causal_impact_task(self, intervention_id: str, metric: str = 'clicks'):
    """
    Analyze causal impact of an intervention

    Args:
        intervention_id: Intervention UUID
        metric: Metric to analyze (clicks, impressions, etc.)
    """
    try:
        from insights_core.causal_analyzer import CausalAnalyzer

        analyzer = CausalAnalyzer()
        result = analyzer.analyze_intervention_sync(intervention_id, metric)

        logger.info(f"Causal analysis complete for intervention {intervention_id}")
        return result

    except Exception as e:
        logger.error(f"Error in causal analysis: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name='analyze_all_interventions', bind=True, max_retries=2)
def analyze_all_interventions_task(self, property: str = None, days_back: int = 90):
    """
    Analyze all recent interventions

    Args:
        property: Property URL (None = all properties)
        days_back: Days to look back
    """
    try:
        from insights_core.causal_analyzer import CausalAnalyzer

        analyzer = CausalAnalyzer()
        # Note: This is currently synchronous, would need async version
        result = analyzer.analyze_all_interventions(property, days_back=days_back)

        logger.info(f"Analyzed {result.get('interventions_analyzed', 0)} interventions")
        return result

    except Exception as e:
        logger.error(f"Error analyzing interventions: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='create_auto_pr', bind=True, max_retries=1)
def create_auto_pr_task(
    self,
    repo_owner: str,
    repo_name: str,
    property: str,
    recommendation_ids: List[str] = None,
    max_recommendations: int = 10
):
    """
    Create automated pull request

    Args:
        repo_owner: GitHub repository owner
        repo_name: Repository name
        property: Property URL
        recommendation_ids: Optional specific recommendation IDs
        max_recommendations: Maximum recommendations to include
    """
    try:
        from automation.pr_generator import AutoPRGenerator

        # Fetch recommendations from database if not provided
        if not recommendation_ids:
            conn = None
            try:
                conn = psycopg2.connect(os.getenv('WAREHOUSE_DSN'))
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                cursor.execute("""
                    SELECT id, recommendation_id, title, description, priority,
                           impact_score, page_path, recommendation_type
                    FROM gsc.agent_recommendations
                    WHERE property = %s
                      AND status = 'approved'
                      AND priority IN ('high', 'critical')
                      AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            ELSE 3
                        END,
                        impact_score DESC,
                        created_at DESC
                    LIMIT %s
                """, (property, max_recommendations))

                recommendations = cursor.fetchall()
                cursor.close()

                if not recommendations:
                    logger.info("No approved high-priority recommendations found")
                    return {'success': False, 'error': 'no_recommendations'}

                recommendation_ids = [r['recommendation_id'] for r in recommendations]
                logger.info(f"Fetched {len(recommendation_ids)} recommendations for auto-PR")

            except Exception as e:
                logger.warning(f"Error fetching recommendations: {e}")
                return {'success': False, 'error': f'db_error: {str(e)}'}
            finally:
                if conn:
                    conn.close()
        else:
            # Fetch complete recommendation data with diagnoses, findings, and insights
            conn = None
            try:
                conn = psycopg2.connect(os.getenv('WAREHOUSE_DSN'))
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Complex JOIN query to fetch full context for PR generation
                cursor.execute("""
                    SELECT
                        -- Recommendation data
                        r.id,
                        r.recommendation_id,
                        r.title,
                        r.description,
                        r.priority,
                        r.impact_score,
                        r.page_path,
                        r.recommendation_type,
                        r.action_type,
                        r.action_details,
                        r.confidence,
                        r.estimated_effort,
                        r.status,

                        -- Linked diagnosis data
                        d.id as diagnosis_id,
                        d.root_cause,
                        d.confidence_score as diagnosis_confidence,
                        d.supporting_evidence,
                        d.related_pages,

                        -- Originating finding data
                        f.id as finding_id,
                        f.finding_type,
                        f.severity as finding_severity,
                        f.affected_pages,
                        f.metrics as finding_metrics,

                        -- Related insight (first matching by entity_id/page_path)
                        i.id as insight_id,
                        i.category as insight_category,
                        i.severity as insight_severity,
                        i.title as insight_title,
                        i.metrics as insight_metrics

                    FROM gsc.agent_recommendations r
                    LEFT JOIN gsc.agent_diagnoses d ON r.diagnosis_id = d.id
                    LEFT JOIN gsc.agent_findings f ON d.finding_id = f.id
                    LEFT JOIN gsc.insights i ON r.page_path = i.entity_id
                        AND i.property = r.property

                    WHERE r.recommendation_id = ANY(%s)
                      AND r.property = %s
                    ORDER BY
                        CASE r.priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            ELSE 3
                        END,
                        r.impact_score DESC
                """, (recommendation_ids, property))

                recommendations = cursor.fetchall()
                cursor.close()
                logger.info(f"Fetched {len(recommendations)} complete recommendations with context for auto-PR")

            except Exception as e:
                logger.warning(f"Error fetching recommendations by ID: {e}")
                recommendations = []
            finally:
                if conn:
                    conn.close()

        generator = AutoPRGenerator()
        result = generator.create_pull_request_sync(
            repo_owner,
            repo_name,
            recommendations,
            property
        )

        if result.get('success'):
            logger.info(f"Created PR #{result.get('pr_number')}: {result.get('pr_url')}")
        else:
            logger.error(f"Failed to create PR: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Error creating auto-PR: {e}")
        raise self.retry(exc=e, countdown=300)


# =============================================
# PHASE 4 TASKS (NOTIFICATIONS & AUTOMATION)
# =============================================

@celery_app.task(name='process_notification_queue', bind=True)
def process_notification_queue_task(self):
    """
    Process pending notifications in the queue

    Sends notifications via Slack, email, webhooks with retry logic
    """
    try:
        from notifications.alert_manager import AlertManager
        from notifications.channels.slack_notifier import SlackNotifier
        from notifications.channels.email_notifier import EmailNotifier
        from notifications.channels.webhook_notifier import WebhookNotifier

        manager = AlertManager()

        # Register notification channels
        manager.register_notifier('slack', SlackNotifier())
        manager.register_notifier('email', EmailNotifier())
        manager.register_notifier('webhook', WebhookNotifier())

        # Process queue
        import asyncio
        result = asyncio.run(manager.process_notification_queue())

        logger.info("Processed notification queue")
        return {'success': True}

    except Exception as e:
        logger.error(f"Error processing notification queue: {e}")
        return {'success': False, 'error': str(e)}


@celery_app.task(name='detect_serp_anomalies', bind=True, max_retries=2)
def detect_serp_anomalies_task(self, property: str, lookback_days: int = 30):
    """
    Detect SERP position anomalies using ML and statistical methods

    Args:
        property: Property URL
        lookback_days: Days to analyze
    """
    try:
        from insights_core.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector()
        import asyncio
        anomalies = asyncio.run(detector.detect_serp_anomalies(property, lookback_days))

        logger.info(f"Detected {len(anomalies)} SERP anomalies for {property}")
        return {'anomalies_detected': len(anomalies), 'anomalies': anomalies[:10]}  # Top 10

    except Exception as e:
        logger.error(f"Error detecting SERP anomalies: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='detect_traffic_anomalies', bind=True, max_retries=2)
def detect_traffic_anomalies_task(self, property: str, lookback_days: int = 30):
    """
    Detect traffic anomalies (clicks, impressions) using ML

    Args:
        property: Property URL
        lookback_days: Days to analyze
    """
    try:
        from insights_core.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector()
        import asyncio
        anomalies = asyncio.run(detector.detect_traffic_anomalies(property, lookback_days))

        logger.info(f"Detected {len(anomalies)} traffic anomalies for {property}")
        return {'anomalies_detected': len(anomalies), 'anomalies': anomalies[:10]}

    except Exception as e:
        logger.error(f"Error detecting traffic anomalies: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='run_multi_agent_workflow', bind=True, max_retries=1)
def run_multi_agent_workflow_task(
    self,
    workflow_type: str,
    property: str,
    trigger_event: Dict,
    page_path: str = None
):
    """
    Run multi-agent orchestration workflow

    Args:
        workflow_type: daily_analysis, emergency_response, optimization, validation
        property: Property URL
        trigger_event: Event that triggered the workflow
        page_path: Optional page path
    """
    try:
        from agents.orchestration.supervisor_agent import SupervisorAgent
        from agents.orchestration.serp_analyst_agent import SerpAnalystAgent
        from agents.orchestration.performance_agent import PerformanceAgent

        # Initialize supervisor
        supervisor = SupervisorAgent()

        # Register specialist agents
        supervisor.register_agent('serp_analyst', SerpAnalystAgent())
        supervisor.register_agent('performance_agent', PerformanceAgent())

        # Run workflow
        import asyncio
        result = asyncio.run(supervisor.run_workflow(
            workflow_type=workflow_type,
            trigger_event=trigger_event,
            property=property,
            page_path=page_path
        ))

        logger.info(f"Workflow {workflow_type} completed: {result.get('workflow_id')}")
        return result

    except Exception as e:
        logger.error(f"Error running multi-agent workflow: {e}")
        raise self.retry(exc=e, countdown=300)


@celery_app.task(name='evaluate_alert_rules', bind=True)
def evaluate_alert_rules_task(self, property: str = None):
    """
    Evaluate all active alert rules and trigger alerts if conditions met

    Args:
        property: Property URL (None = all properties)
    """
    try:
        from notifications.alert_manager import AlertManager
        from services.alert_engine import AlertRuleEvaluator

        manager = AlertManager()
        evaluator = AlertRuleEvaluator()
        import asyncio

        # Get active rules
        rules = asyncio.run(manager.get_alert_rules(is_active=True))

        alerts_triggered = 0
        rules_evaluated = 0

        for rule in rules:
            rule_property = rule.get('property')

            # Skip if property filter doesn't match
            if property and rule_property and rule_property != property:
                continue

            # Evaluate rule based on type
            rule_type = rule['rule_type']
            rules_evaluated += 1

            eval_property = rule_property or property
            triggered = False
            current_metrics = {}

            if rule_type == 'threshold':
                # Fetch current metrics for evaluation
                current_metrics = evaluator.fetch_current_metrics(
                    property=eval_property,
                    page_path=rule.get('page_path')
                )

                # Evaluate the threshold rule
                triggered = evaluator.evaluate_threshold_rule(rule, current_metrics)

            elif rule_type == 'anomaly':
                # Phase 2: Anomaly-based rules
                # Fetch historical metrics for anomaly detection
                metrics_history = evaluator.fetch_metrics_history(
                    property=eval_property,
                    page_path=rule.get('page_path'),
                    lookback_days=30
                )

                # Evaluate the anomaly rule
                triggered = evaluator.evaluate_anomaly_rule(rule, metrics_history)

                # Get current metrics for alert data
                if triggered and metrics_history:
                    current_metrics = metrics_history[-1] if metrics_history else {}

            elif rule_type == 'pattern':
                # Phase 3: Pattern-based rules
                # Fetch historical metrics for pattern detection
                duration = rule.get('condition', {}).get('duration', 3)
                metrics_history = evaluator.fetch_metrics_history(
                    property=eval_property,
                    page_path=rule.get('page_path'),
                    lookback_days=max(duration + 7, 14)  # Enough history for pattern detection
                )

                # Evaluate the pattern rule
                triggered = evaluator.evaluate_pattern_rule(rule, metrics_history)

                # Get current metrics for alert data
                if triggered and metrics_history:
                    current_metrics = metrics_history[-1] if metrics_history else {}

            if triggered:
                alert_data = {
                    'property': eval_property,
                    'page_path': rule.get('page_path'),
                    'title': f"{rule_type.capitalize()} Alert: {rule.get('rule_name')}",
                    'message': f"Metric '{rule.get('metric')}' triggered {rule_type} alert",
                    'metrics': current_metrics
                }
                alert_id = evaluator.trigger_alert(rule, alert_data)
                if alert_id:
                    alerts_triggered += 1

        logger.info(f"Evaluated {rules_evaluated} alert rules, triggered {alerts_triggered} alerts")
        return {'rules_evaluated': rules_evaluated, 'alerts_triggered': alerts_triggered}

    except Exception as e:
        logger.error(f"Error evaluating alert rules: {e}")
        return {'success': False, 'error': str(e)}


@celery_app.task(name='daily_analysis_workflow', bind=True)
def daily_analysis_workflow_task(self, property: str):
    """
    Run daily automated analysis workflow

    Combines SERP tracking, anomaly detection, and multi-agent analysis

    Args:
        property: Property URL
    """
    try:
        results = {}

        # 1. Track SERP positions
        serp_result = track_serp_positions_task.apply_async(args=[property])
        results['serp_tracking'] = serp_result.get(timeout=300)

        # 2. Detect anomalies
        anomaly_result = detect_serp_anomalies_task.apply_async(args=[property])
        results['anomaly_detection'] = anomaly_result.get(timeout=300)

        # 3. Run multi-agent workflow
        workflow_result = run_multi_agent_workflow_task.apply_async(
            args=[
                'daily_analysis',
                property,
                {'type': 'scheduled', 'schedule': 'daily'}
            ]
        )
        results['multi_agent_workflow'] = workflow_result.get(timeout=600)

        # 4. Process notifications
        notify_result = process_notification_queue_task.apply_async()
        results['notifications'] = notify_result.get(timeout=60)

        logger.info(f"Daily analysis complete for {property}")
        return results

    except Exception as e:
        logger.error(f"Error in daily analysis workflow: {e}")
        return {'success': False, 'error': str(e)}


# =============================================
# PERIODIC TASKS (SCHEDULED)
# =============================================

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks"""

    # Daily: Generate forecasts for all properties
    sender.add_periodic_task(
        crontab(hour=2, minute=0),  # 2 AM daily
        generate_forecasts_task.s(property='all'),
        name='daily_forecast_generation'
    )

    # Daily: Detect anomalies
    sender.add_periodic_task(
        crontab(hour=3, minute=0),  # 3 AM daily
        detect_anomalies_task.s(property='all'),
        name='daily_anomaly_detection'
    )

    # Weekly: Update embeddings for all pages
    sender.add_periodic_task(
        crontab(hour=1, minute=0, day_of_week=0),  # Sunday 1 AM
        generate_embeddings_task.s(property='all'),
        name='weekly_embedding_update'
    )

    # Weekly: Detect cannibalization
    sender.add_periodic_task(
        crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
        detect_cannibalization_task.s(property='all'),
        name='weekly_cannibalization_check'
    )

    # Daily: Hugo content sync
    sender.add_periodic_task(
        crontab(hour=5, minute=0),  # 5 AM daily
        sync_hugo_content_task.s(),
        name='daily_hugo_sync'
    )

    # PHASE 2 PERIODIC TASKS

    # Daily: Run intelligent watcher
    sender.add_periodic_task(
        crontab(hour=5, minute=0),  # 5 AM daily
        run_intelligent_watcher_task.s(property='all'),
        name='daily_intelligent_watcher'
    )

    # Weekly: Auto-cluster topics
    sender.add_periodic_task(
        crontab(hour=6, minute=0, day_of_week=1),  # Monday 6 AM
        auto_cluster_topics_task.s(property='all'),
        name='weekly_topic_clustering'
    )

    # Daily: Monitor content changes
    sender.add_periodic_task(
        crontab(hour=7, minute=0),  # 7 AM daily
        monitor_content_changes_task.s(property='all'),
        name='daily_content_monitoring'
    )

    # PHASE 3 PERIODIC TASKS

    # Daily: Track SERP positions
    sender.add_periodic_task(
        crontab(hour=8, minute=0),  # 8 AM daily
        track_serp_positions_task.s(property='all'),
        name='daily_serp_tracking'
    )

    # Weekly: Monitor Core Web Vitals (mobile)
    sender.add_periodic_task(
        crontab(hour=9, minute=0, day_of_week=2),  # Tuesday 9 AM
        monitor_core_web_vitals_task.s(
            property='all',
            strategies=['mobile']
        ),
        name='weekly_cwv_mobile_monitoring'
    )

    # Monthly: Analyze all interventions
    sender.add_periodic_task(
        crontab(hour=10, minute=0, day_of_month=1),  # 1st of month, 10 AM
        analyze_all_interventions_task.s(property='all'),
        name='monthly_intervention_analysis'
    )

    # PHASE 4 PERIODIC TASKS

    # Every 5 minutes: Process notification queue
    sender.add_periodic_task(
        300.0,  # 5 minutes
        process_notification_queue_task.s(),
        name='notification_queue_processing'
    )

    # Daily: Detect SERP anomalies
    sender.add_periodic_task(
        crontab(hour=11, minute=0),  # 11 AM daily
        detect_serp_anomalies_task.s(property='all'),
        name='daily_serp_anomaly_detection'
    )

    # Daily: Detect traffic anomalies
    sender.add_periodic_task(
        crontab(hour=12, minute=0),  # 12 PM daily
        detect_traffic_anomalies_task.s(property='all'),
        name='daily_traffic_anomaly_detection'
    )

    # Daily: Run multi-agent daily analysis
    sender.add_periodic_task(
        crontab(hour=13, minute=0),  # 1 PM daily
        daily_analysis_workflow_task.s(property='all'),
        name='daily_multi_agent_analysis'
    )

    # Every hour: Evaluate alert rules
    sender.add_periodic_task(
        crontab(minute=0),  # Every hour
        evaluate_alert_rules_task.s(),
        name='hourly_alert_evaluation'
    )


# =============================================
# ACTION GENERATION TASKS
# =============================================

@celery_app.task(name='generate_actions_task', bind=True, max_retries=2)
def generate_actions_task(self, property: str, limit: int = 100) -> dict:
    """
    Generate actions for a property asynchronously

    Args:
        property: Property to generate actions for
        limit: Maximum actions to generate

    Returns:
        Dict with generation statistics
    """
    try:
        from services.action_generator import ActionGenerator

        generator = ActionGenerator()
        actions = generator.generate_batch(property, limit=limit)

        logger.info(f"Generated {len(actions)} actions for {property}")
        return {
            'property': property,
            'actions_generated': len(actions),
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Action generation task failed: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name='refresh_insights_task', bind=True, max_retries=2)
def refresh_insights_task(self, property: str, generate_actions: bool = True) -> dict:
    """
    Refresh insights and optionally generate actions

    Args:
        property: Property to refresh
        generate_actions: Whether to generate actions

    Returns:
        Dict with refresh statistics
    """
    try:
        from insights_core.engine import InsightEngine

        engine = InsightEngine()
        stats = engine.refresh(property=property, generate_actions=generate_actions)

        logger.info(f"Insight refresh completed for {property}: {stats.get('total_insights_created', 0)} insights, {stats.get('actions_generated', 0)} actions")
        return stats

    except Exception as e:
        logger.error(f"Insight refresh task failed: {e}")
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))


# =============================================
# UTILITY TASKS
# =============================================

@celery_app.task(name='health_check')
def health_check_task():
    """Health check task"""
    return {'status': 'healthy', 'tasks_available': True}


# Export app
__all__ = ['celery_app']
