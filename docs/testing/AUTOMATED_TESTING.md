# Automated Testing Strategy - Zero Human Review

> **Goal**: Achieve fully automated testing and validation to eliminate the need for human review before deployments.

## Executive Summary

This plan establishes a comprehensive automated testing framework that validates all system components without human intervention. By implementing quality gates at every stage, the system can self-validate and deploy with confidence.

---

## Current State Analysis

### Existing Coverage

| Category | Test Files | Test Functions | Coverage |
|----------|-----------|----------------|----------|
| Agent Tests | 15+ | 400+ | 22-96% |
| Insights Core | 20+ | 500+ | 88-99% |
| Dashboard Tests | 10+ | 200+ | Schema only |
| Integration Tests | 8+ | 150+ | Partial |
| E2E Tests | 6+ | 100+ | Basic |
| **Total** | **85** | **1,942** | **Variable** |

### Identified Gaps Requiring Automation

1. **Agent Orchestration** - Multi-agent workflows untested
2. **Data Pipeline Validation** - Ingestion quality checks missing
3. **API Contract Testing** - No OpenAPI/schema validation
4. **Performance Regression** - No automated benchmarks
5. **Dashboard Functionality** - UI tests not in CI
6. **Database Migrations** - Schema drift detection missing
7. **Configuration Validation** - Environment parity not verified
8. **Security Scanning** - Limited automated security tests

---

## Automated Testing Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CI/CD PIPELINE STAGES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  STAGE 1 │──▶│  STAGE 2 │──▶│  STAGE 3 │──▶│  STAGE 4 │──▶│  STAGE 5 │  │
│  │  Static  │   │   Unit   │   │ Integra- │   │   E2E    │   │  Deploy  │  │
│  │ Analysis │   │  Tests   │   │   tion   │   │  Tests   │   │  Gates   │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│       │              │              │              │              │         │
│       ▼              ▼              ▼              ▼              ▼         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Linting  │   │ Coverage │   │ Contract │   │ UI/API   │   │ Canary   │  │
│  │ Security │   │ >90%     │   │ Database │   │ Perf     │   │ Smoke    │  │
│  │ Types    │   │ All Pass │   │ Services │   │ Load     │   │ Rollback │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                                             │
│                    QUALITY GATES (Auto-Block on Failure)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Static Analysis (< 2 minutes)

### 1.1 Code Quality

```yaml
# .github/workflows/static-analysis.yml
name: Static Analysis
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Python Linting
        run: |
          pip install flake8 black isort mypy
          flake8 . --max-line-length=120 --ignore=E501,W503
          black --check .
          isort --check-only .

      - name: Type Checking
        run: mypy --config-file mypy.ini .

      - name: SQL Linting
        run: |
          pip install sqlfluff
          sqlfluff lint sql/ --dialect postgres
```

### 1.2 Security Scanning

```yaml
  security:
    runs-on: ubuntu-latest
    steps:
      - name: Dependency Audit
        run: |
          pip install safety pip-audit
          safety check -r requirements.txt
          pip-audit -r requirements.txt

      - name: Secret Scanning
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./

      - name: SAST Scanning
        uses: PyCQA/bandit-action@v1
        with:
          path: "."
          level: medium
```

### 1.3 Configuration Validation

```python
# tests/static/test_configuration.py
"""Automated configuration validation tests."""

import pytest
import yaml
import json
from pathlib import Path

class TestConfigurationFiles:
    """Validate all configuration files."""

    def test_env_example_completeness(self):
        """Ensure .env.example contains all required variables."""
        required_vars = {
            'WAREHOUSE_DSN', 'GOOGLE_APPLICATION_CREDENTIALS',
            'GA4_PROPERTY_ID', 'OLLAMA_HOST', 'REDIS_URL'
        }
        with open('.env.example') as f:
            content = f.read()
        for var in required_vars:
            assert var in content, f"Missing required var: {var}"

    def test_docker_compose_valid(self):
        """Validate docker-compose.yml syntax."""
        with open('docker-compose.yml') as f:
            config = yaml.safe_load(f)
        assert 'services' in config
        assert 'version' in config or 'name' in config

    def test_prometheus_config_valid(self):
        """Validate Prometheus configuration."""
        with open('prometheus/prometheus.yml') as f:
            config = yaml.safe_load(f)
        assert 'scrape_configs' in config

    def test_grafana_dashboards_valid_json(self):
        """Validate all Grafana dashboard JSON files."""
        dashboard_dir = Path('grafana/provisioning/dashboards')
        for dashboard in dashboard_dir.glob('*.json'):
            with open(dashboard) as f:
                data = json.load(f)
            assert 'panels' in data or 'rows' in data
            assert 'title' in data
```

---

## Stage 2: Unit Tests (< 5 minutes)

### 2.1 Core Coverage Requirements

```ini
# pytest.ini additions
[pytest]
minversion = 7.0
addopts =
    --cov=insights_core
    --cov=agents
    --cov=ingestors
    --cov=insights_api
    --cov=scheduler
    --cov-fail-under=90
    --cov-report=xml
    --cov-report=html
    -x --tb=short
```

### 2.2 Missing Unit Tests to Add

#### Detector Tests (100% Coverage Target)

```python
# tests/insights_core/test_all_detectors.py
"""Comprehensive detector testing with edge cases."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from insights_core.detectors.anomaly import AnomalyDetector
from insights_core.detectors.cannibalization import CannibalizationDetector
from insights_core.detectors.content_quality import ContentQualityDetector
from insights_core.detectors.cwv_quality import CWVQualityDetector
from insights_core.detectors.diagnosis import DiagnosisDetector
from insights_core.detectors.opportunity import OpportunityDetector
from insights_core.detectors.topic_strategy import TopicStrategyDetector
from insights_core.detectors.trend import TrendDetector


class TestAnomalyDetector:
    """Test anomaly detection with various data patterns."""

    @pytest.fixture
    def detector(self, mock_db_pool):
        return AnomalyDetector(mock_db_pool)

    @pytest.mark.parametrize("scenario,expected_count", [
        ("normal_traffic", 0),
        ("sudden_spike", 1),
        ("sudden_drop", 1),
        ("gradual_decline", 0),
        ("weekend_pattern", 0),
        ("holiday_anomaly", 1),
    ])
    async def test_detection_scenarios(self, detector, scenario, expected_count, sample_data):
        """Test various traffic patterns."""
        data = sample_data[scenario]
        insights = await detector.detect(data)
        assert len(insights) == expected_count

    async def test_empty_data_handling(self, detector):
        """Detector handles empty data gracefully."""
        insights = await detector.detect([])
        assert insights == []

    async def test_null_values_handling(self, detector):
        """Detector handles null/None values."""
        data_with_nulls = [
            {"date": "2024-01-01", "clicks": None, "impressions": 100},
            {"date": "2024-01-02", "clicks": 50, "impressions": None},
        ]
        insights = await detector.detect(data_with_nulls)
        # Should not raise, should skip nulls


class TestCannibalizationDetector:
    """Test keyword cannibalization detection."""

    @pytest.fixture
    def detector(self, mock_db_pool):
        return CannibalizationDetector(mock_db_pool)

    async def test_detects_same_keyword_multiple_pages(self, detector):
        """Detect when multiple pages target same keyword."""
        data = [
            {"page": "/page-a", "query": "best widgets", "clicks": 100},
            {"page": "/page-b", "query": "best widgets", "clicks": 80},
        ]
        insights = await detector.detect(data)
        assert len(insights) >= 1
        assert insights[0].category == "CANNIBALIZATION"

    async def test_ignores_different_intent(self, detector):
        """Don't flag pages with different search intent."""
        data = [
            {"page": "/buy-widgets", "query": "buy widgets", "clicks": 100},
            {"page": "/widget-reviews", "query": "widget reviews", "clicks": 80},
        ]
        insights = await detector.detect(data)
        assert len(insights) == 0


# Similar comprehensive tests for all 8 detectors...
```

#### Agent Tests (95% Coverage Target)

```python
# tests/agents/test_agent_contracts.py
"""Test all agents implement contract correctly."""

import pytest
from abc import ABC
from agents.base.agent_contract import AgentContract
from agents.watcher.watcher_agent import WatcherAgent
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.strategist.strategist_agent import StrategistAgent
from agents.dispatcher.dispatcher_agent import DispatcherAgent


class TestAgentContractCompliance:
    """Verify all agents implement the base contract."""

    AGENT_CLASSES = [
        WatcherAgent,
        DiagnosticianAgent,
        StrategistAgent,
        DispatcherAgent,
    ]

    @pytest.mark.parametrize("agent_class", AGENT_CLASSES)
    def test_inherits_contract(self, agent_class):
        """Agent inherits from AgentContract."""
        assert issubclass(agent_class, AgentContract)

    @pytest.mark.parametrize("agent_class", AGENT_CLASSES)
    def test_has_required_methods(self, agent_class):
        """Agent implements all required methods."""
        required_methods = ['initialize', 'process', 'health_check', 'shutdown']
        for method in required_methods:
            assert hasattr(agent_class, method)
            assert callable(getattr(agent_class, method))

    @pytest.mark.parametrize("agent_class", AGENT_CLASSES)
    async def test_health_check_returns_dict(self, agent_class, mock_dependencies):
        """Health check returns proper status dict."""
        agent = agent_class(**mock_dependencies)
        await agent.initialize()
        health = await agent.health_check()
        assert isinstance(health, dict)
        assert 'status' in health
        assert health['status'] in ['healthy', 'unhealthy', 'degraded']
```

### 2.3 Ingestor Tests

```python
# tests/ingestors/test_all_ingestors.py
"""Test data ingestion with mocked external APIs."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date, timedelta

from ingestors.api.api_ingestor import SearchAnalyticsAPIIngestor
from ingestors.ga4.ga4_extractor import GA4Extractor
from ingestors.trends.trends_accumulator import TrendsAccumulator


class TestGSCIngestor:
    """Test GSC API ingestion."""

    @pytest.fixture
    def mock_gsc_response(self):
        """Mock GSC API response."""
        return {
            'rows': [
                {
                    'keys': ['https://example.com/page1', 'widget'],
                    'clicks': 100,
                    'impressions': 1000,
                    'ctr': 0.1,
                    'position': 5.5
                }
            ]
        }

    @patch('ingestors.api.api_ingestor.build')
    async def test_fetch_and_transform(self, mock_build, mock_gsc_response, mock_db):
        """Test data fetch and transformation."""
        mock_service = MagicMock()
        mock_service.searchanalytics().query().execute.return_value = mock_gsc_response
        mock_build.return_value = mock_service

        ingestor = SearchAnalyticsAPIIngestor(mock_db)
        data = await ingestor.fetch_api_data('sc-domain:example.com', date.today())

        assert len(data) == 1
        assert data[0]['clicks'] == 100

    async def test_watermark_tracking(self, mock_db):
        """Test watermark is updated after ingestion."""
        ingestor = SearchAnalyticsAPIIngestor(mock_db)

        initial = await ingestor.get_watermark('sc-domain:example.com')
        await ingestor.update_watermark('sc-domain:example.com', date.today())
        updated = await ingestor.get_watermark('sc-domain:example.com')

        assert updated > initial

    async def test_rate_limiting(self, mock_db):
        """Test rate limiter prevents API abuse."""
        ingestor = SearchAnalyticsAPIIngestor(mock_db)

        # Rapid requests should be throttled
        for _ in range(10):
            await ingestor.fetch_api_data('sc-domain:example.com', date.today())

        # Verify rate limiter engaged
        assert ingestor.rate_limiter.request_count <= ingestor.rate_limiter.max_requests


class TestGA4Ingestor:
    """Test GA4 data extraction."""

    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    async def test_extracts_page_metrics(self, mock_client, mock_db):
        """Test GA4 page-level metric extraction."""
        mock_response = MagicMock()
        mock_response.rows = [
            MagicMock(
                dimension_values=[MagicMock(value='/page1')],
                metric_values=[
                    MagicMock(value='100'),  # sessions
                    MagicMock(value='50'),   # conversions
                ]
            )
        ]
        mock_client.return_value.run_report.return_value = mock_response

        extractor = GA4Extractor(mock_db, property_id='123456')
        data = await extractor.extract_page_metrics(date.today())

        assert len(data) == 1
        assert data[0]['page_path'] == '/page1'
        assert data[0]['sessions'] == 100


class TestTrendsIngestor:
    """Test Google Trends data collection."""

    @patch('ingestors.trends.trends_client.TrendReq')
    async def test_collects_interest_over_time(self, mock_pytrends, mock_db):
        """Test interest over time data collection."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = MagicMock(
            to_dict=lambda orient: {'widget': [50, 60, 70, 80, 90]}
        )
        mock_pytrends.return_value = mock_instance

        accumulator = TrendsAccumulator(mock_db)
        data = await accumulator.collect_keyword_trends(['widget'])

        assert 'widget' in data
        assert len(data['widget']) > 0
```

---

## Stage 3: Integration Tests (< 10 minutes)

### 3.1 Database Integration

```python
# tests/integration/test_database_operations.py
"""Test database operations with real PostgreSQL."""

import pytest
from datetime import date

@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseIntegration:
    """Test database layer with actual PostgreSQL."""

    async def test_schema_migrations_apply_cleanly(self, test_db):
        """All SQL migrations apply without errors."""
        from pathlib import Path

        sql_files = sorted(Path('sql').glob('*.sql'))
        for sql_file in sql_files:
            with open(sql_file) as f:
                sql = f.read()
            await test_db.execute(sql)

        # Verify key tables exist
        tables = await test_db.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema IN ('gsc', 'public', 'insights')
        """)
        table_names = {t['table_name'] for t in tables}

        assert 'fact_gsc_daily' in table_names or 'gsc.fact_gsc_daily' in table_names
        assert 'insights' in table_names

    async def test_upsert_operations(self, test_db, sample_gsc_data):
        """Test upsert correctly handles duplicates."""
        # Insert initial data
        await test_db.executemany(
            "INSERT INTO gsc.fact_gsc_daily VALUES ($1, $2, $3, $4, $5, $6)",
            sample_gsc_data
        )

        # Upsert with updated values
        updated_data = [(d[0], d[1], d[2], d[3] * 2, d[4], d[5]) for d in sample_gsc_data]
        await test_db.executemany(
            """INSERT INTO gsc.fact_gsc_daily VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (property_id, page_id, query_id, date)
               DO UPDATE SET clicks = EXCLUDED.clicks""",
            updated_data
        )

        # Verify update
        result = await test_db.fetchrow(
            "SELECT clicks FROM gsc.fact_gsc_daily LIMIT 1"
        )
        assert result['clicks'] == sample_gsc_data[0][3] * 2

    async def test_materialized_view_refresh(self, test_db):
        """Test materialized views refresh correctly."""
        await test_db.execute("REFRESH MATERIALIZED VIEW gsc.mv_daily_summary")

        # Should not raise
        count = await test_db.fetchval("SELECT COUNT(*) FROM gsc.mv_daily_summary")
        assert count >= 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestTransactionIsolation:
    """Test database transactions are properly isolated."""

    async def test_rollback_on_error(self, test_db):
        """Transaction rolls back on error."""
        initial_count = await test_db.fetchval("SELECT COUNT(*) FROM insights.insights")

        try:
            async with test_db.transaction():
                await test_db.execute(
                    "INSERT INTO insights.insights (id, category) VALUES ($1, $2)",
                    'test-id', 'ANOMALY'
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass

        final_count = await test_db.fetchval("SELECT COUNT(*) FROM insights.insights")
        assert final_count == initial_count  # Rolled back
```

### 3.2 Service Integration

```python
# tests/integration/test_service_integration.py
"""Test service-to-service communication."""

import pytest
import httpx
from unittest.mock import patch

@pytest.mark.integration
class TestAPIIntegration:
    """Test Insights API with real database."""

    @pytest.fixture
    async def api_client(self, test_db):
        """Create test client with real database."""
        from insights_api.insights_api import create_app
        app = create_app(db_pool=test_db)
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    async def test_health_endpoint(self, api_client):
        """Health endpoint returns 200."""
        response = await api_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'

    async def test_insights_crud_flow(self, api_client):
        """Test full CRUD flow for insights."""
        # Create
        insight_data = {
            "category": "ANOMALY",
            "severity": "HIGH",
            "title": "Test Anomaly",
            "description": "Traffic spike detected"
        }
        response = await api_client.post("/api/insights", json=insight_data)
        assert response.status_code == 201
        insight_id = response.json()['id']

        # Read
        response = await api_client.get(f"/api/insights/{insight_id}")
        assert response.status_code == 200
        assert response.json()['title'] == "Test Anomaly"

        # Update
        response = await api_client.patch(
            f"/api/insights/{insight_id}",
            json={"status": "RESOLVED"}
        )
        assert response.status_code == 200

        # Verify update
        response = await api_client.get(f"/api/insights/{insight_id}")
        assert response.json()['status'] == "RESOLVED"

    async def test_filtering_and_pagination(self, api_client, seed_insights):
        """Test query filtering and pagination."""
        response = await api_client.get(
            "/api/insights",
            params={"category": "ANOMALY", "limit": 10, "offset": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert 'total' in data
        assert all(i['category'] == 'ANOMALY' for i in data['items'])


@pytest.mark.integration
class TestAgentOrchestration:
    """Test multi-agent workflow integration."""

    async def test_watcher_to_diagnostician_flow(self, test_db, mock_ollama):
        """Test insight flows from Watcher to Diagnostician."""
        from agents.watcher.watcher_agent import WatcherAgent
        from agents.diagnostician.diagnostician_agent import DiagnosticianAgent

        # Initialize agents
        watcher = WatcherAgent(db_pool=test_db, llm_client=mock_ollama)
        diagnostician = DiagnosticianAgent(db_pool=test_db, llm_client=mock_ollama)

        await watcher.initialize()
        await diagnostician.initialize()

        # Watcher detects anomaly
        anomaly = await watcher.process({'check_anomalies': True})

        if anomaly:
            # Diagnostician analyzes
            diagnosis = await diagnostician.process({'insight_id': anomaly.id})
            assert diagnosis is not None
            assert diagnosis.root_cause is not None

    async def test_full_pipeline_orchestration(self, test_db, mock_ollama):
        """Test complete agent pipeline."""
        from agents.dispatcher.dispatcher_agent import DispatcherAgent

        dispatcher = DispatcherAgent(
            db_pool=test_db,
            llm_client=mock_ollama
        )
        await dispatcher.initialize()

        # Run full pipeline
        result = await dispatcher.run_full_pipeline()

        assert result['status'] == 'completed'
        assert 'insights_generated' in result
        assert 'diagnoses_created' in result
        assert 'recommendations_made' in result
```

### 3.3 External Service Mocking

```python
# tests/integration/test_external_services.py
"""Test external service integrations with mocks."""

import pytest
from unittest.mock import AsyncMock, patch
import responses

@pytest.mark.integration
class TestGoogleAPIIntegration:
    """Test Google API integrations."""

    @responses.activate
    def test_gsc_api_authentication(self):
        """Test GSC API authentication flow."""
        responses.add(
            responses.POST,
            "https://oauth2.googleapis.com/token",
            json={"access_token": "test_token", "expires_in": 3600},
            status=200
        )

        from ingestors.api.api_ingestor import SearchAnalyticsAPIIngestor
        ingestor = SearchAnalyticsAPIIngestor.__new__(SearchAnalyticsAPIIngestor)
        token = ingestor._get_access_token()
        assert token == "test_token"

    @responses.activate
    def test_pagespeed_api_call(self):
        """Test PageSpeed Insights API."""
        responses.add(
            responses.GET,
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            json={
                "lighthouseResult": {
                    "audits": {
                        "largest-contentful-paint": {"numericValue": 2500},
                        "cumulative-layout-shift": {"numericValue": 0.1},
                        "total-blocking-time": {"numericValue": 200}
                    }
                }
            },
            status=200
        )

        from scripts.collect_cwv_data import fetch_cwv_metrics
        metrics = fetch_cwv_metrics("https://example.com")
        assert metrics['lcp'] == 2500
        assert metrics['cls'] == 0.1


@pytest.mark.integration
class TestOllamaIntegration:
    """Test Ollama LLM integration."""

    @pytest.fixture
    def mock_ollama_server(self):
        """Mock Ollama API responses."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:11434/api/generate",
                json={"response": "This is a test response from Ollama"},
                status=200
            )
            yield rsps

    def test_llm_reasoner_generates_response(self, mock_ollama_server):
        """Test LLM reasoner with mocked Ollama."""
        from agents.base.llm_reasoner import LLMReasoner

        reasoner = LLMReasoner(model="llama3.2")
        response = reasoner.reason("Analyze this traffic pattern")

        assert response is not None
        assert len(response) > 0
```

---

## Stage 4: End-to-End Tests (< 15 minutes)

### 4.1 Full Pipeline E2E

```python
# tests/e2e/test_complete_pipeline.py
"""End-to-end tests for complete data pipeline."""

import pytest
import asyncio
from datetime import date, timedelta

@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompletePipeline:
    """Test complete data pipeline from ingestion to insights."""

    async def test_daily_pipeline_execution(self, docker_services):
        """Test daily pipeline runs successfully."""
        from scheduler.scheduler import daily_pipeline

        result = await daily_pipeline()

        assert result['status'] == 'completed'
        assert result['steps_completed'] >= 5
        assert 'errors' not in result or len(result['errors']) == 0

    async def test_data_flows_through_system(self, docker_services, mock_gsc_api):
        """Test data flows from ingestion to API."""
        # 1. Ingest data
        from ingestors.api.api_ingestor import SearchAnalyticsAPIIngestor
        ingestor = SearchAnalyticsAPIIngestor(docker_services['db'])
        await ingestor.process_property('sc-domain:example.com')

        # 2. Run insights engine
        from insights_core.engine import InsightEngine
        engine = InsightEngine(docker_services['db'])
        insights = await engine.run_all_detectors()

        # 3. Query via API
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8000/api/insights",
                params={"property": "sc-domain:example.com"}
            )

        assert response.status_code == 200
        assert len(response.json()['items']) > 0

    async def test_insight_lifecycle(self, docker_services):
        """Test insight goes through complete lifecycle."""
        # Create insight via detector
        from insights_core.detectors.anomaly import AnomalyDetector
        detector = AnomalyDetector(docker_services['db'])
        insights = await detector.detect()

        if insights:
            insight = insights[0]

            # Verify in database
            from insights_core.repository import InsightRepository
            repo = InsightRepository(docker_services['db'])
            saved = await repo.get_by_id(insight.id)
            assert saved is not None
            assert saved.status == 'NEW'

            # Update status
            await repo.update(insight.id, {'status': 'DIAGNOSED'})

            # Verify update
            updated = await repo.get_by_id(insight.id)
            assert updated.status == 'DIAGNOSED'


@pytest.mark.e2e
class TestDashboardE2E:
    """End-to-end dashboard tests with Playwright."""

    @pytest.fixture
    async def browser_page(self, playwright):
        """Create browser page for testing."""
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await browser.close()

    async def test_grafana_dashboards_load(self, browser_page, docker_services):
        """All Grafana dashboards load without errors."""
        dashboards = [
            'ga4-overview',
            'gsc-overview',
            'hybrid-overview',
            'service-health',
            'infrastructure-overview',
            'database-performance',
            'cwv-monitoring',
            'serp-tracking',
            'actions-command-center',
            'alert-status',
            'application-metrics',
        ]

        for dashboard in dashboards:
            await browser_page.goto(
                f"http://localhost:3000/d/{dashboard}",
                wait_until="networkidle"
            )

            # Check no error panels
            error_panels = await browser_page.query_selector_all('[class*="panel-error"]')
            assert len(error_panels) == 0, f"Dashboard {dashboard} has error panels"

            # Check panels rendered
            panels = await browser_page.query_selector_all('[class*="panel-container"]')
            assert len(panels) > 0, f"Dashboard {dashboard} has no panels"

    async def test_dashboard_data_queries_succeed(self, browser_page, docker_services):
        """Dashboard queries return data."""
        await browser_page.goto(
            "http://localhost:3000/d/gsc-overview",
            wait_until="networkidle"
        )

        # Wait for data to load
        await browser_page.wait_for_selector('[class*="graph-panel"]', timeout=10000)

        # Verify no "No data" messages
        no_data = await browser_page.query_selector_all('text="No data"')
        # Some panels may legitimately have no data, but core panels should have data
        assert len(no_data) < 3, "Too many panels showing 'No data'"
```

### 4.2 API Contract Testing

```python
# tests/e2e/test_api_contracts.py
"""API contract testing with schema validation."""

import pytest
from jsonschema import validate, ValidationError
import httpx

@pytest.mark.e2e
class TestAPIContracts:
    """Validate API responses match expected schemas."""

    INSIGHT_SCHEMA = {
        "type": "object",
        "required": ["id", "category", "severity", "status", "title", "created_at"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "category": {"type": "string", "enum": [
                "ANOMALY", "CANNIBALIZATION", "CONTENT_QUALITY",
                "CWV_QUALITY", "DIAGNOSIS", "OPPORTUNITY",
                "TOPIC_STRATEGY", "TREND"
            ]},
            "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "status": {"type": "string", "enum": ["NEW", "DIAGNOSED", "RESOLVED"]},
            "title": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "entity_type": {"type": ["string", "null"]},
            "entity_id": {"type": ["string", "null"]},
            "metadata": {"type": ["object", "null"]},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": ["string", "null"], "format": "date-time"}
        }
    }

    INSIGHTS_LIST_SCHEMA = {
        "type": "object",
        "required": ["items", "total", "limit", "offset"],
        "properties": {
            "items": {"type": "array", "items": INSIGHT_SCHEMA},
            "total": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1},
            "offset": {"type": "integer", "minimum": 0}
        }
    }

    async def test_insights_list_schema(self, api_base_url):
        """GET /api/insights matches schema."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/api/insights")

        assert response.status_code == 200
        validate(instance=response.json(), schema=self.INSIGHTS_LIST_SCHEMA)

    async def test_insight_detail_schema(self, api_base_url, sample_insight_id):
        """GET /api/insights/{id} matches schema."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/api/insights/{sample_insight_id}")

        assert response.status_code == 200
        validate(instance=response.json(), schema=self.INSIGHT_SCHEMA)

    async def test_health_schema(self, api_base_url):
        """GET /api/health matches expected format."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/api/health")

        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert data['status'] in ['healthy', 'unhealthy', 'degraded']
```

### 4.3 Performance Testing

```python
# tests/e2e/test_performance.py
"""Automated performance regression tests."""

import pytest
import time
import statistics

@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceBaselines:
    """Test performance meets baseline requirements."""

    BASELINE_THRESHOLDS = {
        'api_health': 0.1,           # 100ms
        'api_insights_list': 0.5,     # 500ms
        'api_insight_detail': 0.2,    # 200ms
        'detector_anomaly': 5.0,      # 5s
        'detector_all': 30.0,         # 30s
        'dashboard_load': 3.0,        # 3s
    }

    async def test_api_response_times(self, api_base_url):
        """API endpoints respond within thresholds."""
        import httpx

        tests = [
            ('api_health', '/api/health'),
            ('api_insights_list', '/api/insights'),
        ]

        async with httpx.AsyncClient() as client:
            for name, endpoint in tests:
                times = []
                for _ in range(5):
                    start = time.perf_counter()
                    await client.get(f"{api_base_url}{endpoint}")
                    times.append(time.perf_counter() - start)

                avg_time = statistics.mean(times)
                assert avg_time < self.BASELINE_THRESHOLDS[name], \
                    f"{name} avg {avg_time:.3f}s exceeds {self.BASELINE_THRESHOLDS[name]}s"

    async def test_detector_performance(self, test_db):
        """Detectors run within time limits."""
        from insights_core.detectors.anomaly import AnomalyDetector

        detector = AnomalyDetector(test_db)

        start = time.perf_counter()
        await detector.detect()
        elapsed = time.perf_counter() - start

        assert elapsed < self.BASELINE_THRESHOLDS['detector_anomaly'], \
            f"Anomaly detector took {elapsed:.2f}s, exceeds {self.BASELINE_THRESHOLDS['detector_anomaly']}s"

    async def test_insight_engine_performance(self, test_db):
        """Full insight engine runs within limit."""
        from insights_core.engine import InsightEngine

        engine = InsightEngine(test_db)

        start = time.perf_counter()
        await engine.run_all_detectors()
        elapsed = time.perf_counter() - start

        assert elapsed < self.BASELINE_THRESHOLDS['detector_all'], \
            f"Full engine took {elapsed:.2f}s, exceeds {self.BASELINE_THRESHOLDS['detector_all']}s"


@pytest.mark.e2e
@pytest.mark.slow
class TestLoadTesting:
    """Basic load testing for critical paths."""

    async def test_api_handles_concurrent_requests(self, api_base_url):
        """API handles 50 concurrent requests."""
        import httpx
        import asyncio

        async def make_request(client, url):
            response = await client.get(url)
            return response.status_code

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [
                make_request(client, f"{api_base_url}/api/insights")
                for _ in range(50)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 45, f"Only {success_count}/50 requests succeeded"

    async def test_database_connection_pool(self, test_db):
        """Database handles connection pool exhaustion gracefully."""
        import asyncio

        async def run_query():
            return await test_db.fetchval("SELECT 1")

        # Run more queries than pool size
        tasks = [run_query() for _ in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r == 1)
        assert success_count == 100, "Some queries failed under load"
```

---

## Stage 5: Deployment Gates

### 5.1 Pre-Deployment Validation

```yaml
# .github/workflows/deploy.yml
name: Deploy with Gates
on:
  push:
    branches: [main]

jobs:
  # Previous stages must pass
  deploy-staging:
    needs: [static-analysis, unit-tests, integration-tests, e2e-tests]
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Staging
        run: |
          docker-compose -f docker-compose.prod.yml up -d

      - name: Wait for Services
        run: |
          ./scripts/wait-for-services.sh --timeout 120

      - name: Run Smoke Tests
        run: |
          pytest tests/smoke/ -v --tb=short

      - name: Verify Metrics Collection
        run: |
          curl -f http://localhost:9090/-/healthy
          curl -f http://localhost:3000/api/health
          curl -f http://localhost:8000/api/health

      - name: Run Canary Checks
        run: |
          python scripts/canary_checks.py --environment staging

  deploy-production:
    needs: [deploy-staging]
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Blue-Green Deployment
        run: |
          ./scripts/blue-green-deploy.sh

      - name: Health Check Loop
        run: |
          for i in {1..10}; do
            if curl -f http://prod.example.com/api/health; then
              echo "Health check $i passed"
            else
              echo "Health check $i failed"
              exit 1
            fi
            sleep 30
          done

      - name: Verify Data Pipeline
        run: |
          python scripts/verify_pipeline.py --environment production
```

### 5.2 Smoke Tests

```python
# tests/smoke/test_smoke.py
"""Quick smoke tests for deployment validation."""

import pytest
import httpx

@pytest.mark.smoke
class TestSmoke:
    """Fast smoke tests to verify deployment."""

    SERVICES = [
        ('API', 'http://localhost:8000/api/health'),
        ('Grafana', 'http://localhost:3000/api/health'),
        ('Prometheus', 'http://localhost:9090/-/healthy'),
        ('Metrics Exporter', 'http://localhost:8002/metrics'),
    ]

    @pytest.mark.parametrize("name,url", SERVICES)
    def test_service_healthy(self, name, url):
        """Service responds to health check."""
        response = httpx.get(url, timeout=10)
        assert response.status_code == 200, f"{name} unhealthy"

    def test_database_connected(self):
        """Database is accessible."""
        import asyncpg
        import os

        dsn = os.environ.get('WAREHOUSE_DSN')
        conn = asyncpg.connect(dsn)
        result = conn.fetchval("SELECT 1")
        assert result == 1

    def test_recent_data_exists(self):
        """Recent data exists in warehouse."""
        import asyncpg
        import os
        from datetime import datetime, timedelta

        dsn = os.environ.get('WAREHOUSE_DSN')
        conn = asyncpg.connect(dsn)

        cutoff = datetime.now() - timedelta(days=2)
        count = conn.fetchval(
            "SELECT COUNT(*) FROM gsc.fact_gsc_daily WHERE date > $1",
            cutoff
        )
        assert count > 0, "No recent data in warehouse"
```

### 5.3 Rollback Automation

```python
# scripts/rollback_automation.py
"""Automated rollback on failure detection."""

import asyncio
import httpx
import subprocess
from datetime import datetime

class RollbackManager:
    """Manages automated rollback on failure."""

    def __init__(self, health_endpoints: list[str], threshold: int = 3):
        self.health_endpoints = health_endpoints
        self.failure_threshold = threshold
        self.failure_count = 0
        self.last_healthy = None

    async def monitor_health(self):
        """Continuously monitor health and trigger rollback if needed."""
        while True:
            healthy = await self._check_all_endpoints()

            if healthy:
                self.failure_count = 0
                self.last_healthy = datetime.now()
            else:
                self.failure_count += 1
                print(f"Health check failed ({self.failure_count}/{self.failure_threshold})")

                if self.failure_count >= self.failure_threshold:
                    await self._trigger_rollback()
                    self.failure_count = 0

            await asyncio.sleep(30)

    async def _check_all_endpoints(self) -> bool:
        """Check all health endpoints."""
        async with httpx.AsyncClient(timeout=10) as client:
            for endpoint in self.health_endpoints:
                try:
                    response = await client.get(endpoint)
                    if response.status_code != 200:
                        return False
                except Exception:
                    return False
        return True

    async def _trigger_rollback(self):
        """Execute rollback procedure."""
        print("Triggering automatic rollback...")

        # Get previous version
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Tag}}", "gsc-warehouse"],
            capture_output=True, text=True
        )
        versions = result.stdout.strip().split('\n')
        if len(versions) > 1:
            previous_version = versions[1]

            # Rollback
            subprocess.run([
                "docker-compose", "-f", "docker-compose.prod.yml",
                "up", "-d", "--no-build"
            ], env={**os.environ, "VERSION": previous_version})

            print(f"Rolled back to version: {previous_version}")
```

---

## Quality Gate Summary

### Automated Checks Required for Deployment

| Gate | Threshold | Blocking |
|------|-----------|----------|
| Lint (flake8) | 0 errors | Yes |
| Type Check (mypy) | 0 errors | Yes |
| Security Scan | 0 high/critical | Yes |
| Unit Test Coverage | > 90% | Yes |
| All Unit Tests Pass | 100% | Yes |
| Integration Tests Pass | 100% | Yes |
| E2E Tests Pass | 100% | Yes |
| Performance Baseline | Within limits | Yes |
| Smoke Tests | 100% | Yes |
| Health Checks | All healthy | Yes |

### Automated Notifications

```yaml
# .github/workflows/notifications.yml
- name: Notify on Failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Pipeline Failed: ${{ github.workflow }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Pipeline Failed*\nRepo: ${{ github.repository }}\nBranch: ${{ github.ref }}\nCommit: ${{ github.sha }}"
            }
          }
        ]
      }
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Set up GitHub Actions workflows
- [ ] Configure code coverage enforcement
- [ ] Implement static analysis gates
- [ ] Add security scanning

### Phase 2: Test Expansion (Week 2-3)
- [ ] Add missing unit tests for 90%+ coverage
- [ ] Implement detector edge case tests
- [ ] Add ingestor mock tests
- [ ] Complete agent contract tests

### Phase 3: Integration (Week 4)
- [ ] Set up test database with Docker
- [ ] Implement database integration tests
- [ ] Add service integration tests
- [ ] Configure API contract tests

### Phase 4: E2E & Performance (Week 5)
- [ ] Implement full pipeline E2E tests
- [ ] Add Playwright dashboard tests
- [ ] Set up performance baselines
- [ ] Add load testing

### Phase 5: Deployment Automation (Week 6)
- [ ] Configure staging environment
- [ ] Implement smoke tests
- [ ] Set up canary deployments
- [ ] Add automated rollback

---

## File Structure for New Tests

```
tests/
├── static/                    # NEW: Static analysis tests
│   ├── test_configuration.py
│   ├── test_sql_syntax.py
│   └── test_schema_validation.py
├── unit/                      # Enhanced unit tests
│   ├── test_all_detectors.py
│   ├── test_agent_contracts.py
│   └── test_all_ingestors.py
├── integration/               # Enhanced integration tests
│   ├── test_database_operations.py
│   ├── test_service_integration.py
│   └── test_external_services.py
├── e2e/                       # Enhanced E2E tests
│   ├── test_complete_pipeline.py
│   ├── test_api_contracts.py
│   ├── test_performance.py
│   └── test_dashboard_e2e.py
├── smoke/                     # NEW: Deployment smoke tests
│   └── test_smoke.py
├── load/                      # Enhanced load tests
│   └── test_system_load.py
└── fixtures/                  # NEW: Shared test fixtures
    ├── sample_data.py
    ├── mock_apis.py
    └── docker_services.py
```

---

## Success Metrics

When fully implemented, this automated testing strategy will:

1. **Catch 99%+ of bugs before production** - Through comprehensive test coverage
2. **Reduce deployment time from hours to minutes** - Automated gates replace manual review
3. **Enable confident continuous deployment** - Every commit can potentially deploy
4. **Provide instant feedback** - Developers know within 15 minutes if changes are safe
5. **Eliminate "works on my machine" issues** - Consistent Docker-based testing
6. **Detect performance regressions automatically** - Baseline comparisons on every build
7. **Ensure security compliance** - Automated scanning catches vulnerabilities
8. **Enable rollback within minutes** - Automated health monitoring and rollback

---

## Next Steps

1. Review this plan and prioritize phases
2. Create GitHub Issues for each phase
3. Begin Phase 1 implementation
4. Schedule weekly reviews of test coverage metrics
