# Architecture Patterns & Design Decisions

This document explains intentional architectural patterns in the codebase that may appear to be duplicates but serve distinct purposes.

## Table of Contents

1. [Dual Implementation Pattern](#dual-implementation-pattern)
2. [Anomaly Detection Strategy](#anomaly-detection-strategy)
3. [Alert Management Architecture](#alert-management-architecture)
4. [Metrics Export Approaches](#metrics-export-approaches)
5. [SERP Tracking Complementary Systems](#serp-tracking-complementary-systems)
6. [Dispatcher Pattern Clarification](#dispatcher-pattern-clarification)

---

## Dual Implementation Pattern

Several components have multiple implementations that serve **different use cases**. This is an intentional architectural decision, not code duplication.

### Key Principle

> "Different tools for different jobs" - Simple implementations for real-time monitoring, advanced implementations for deep analysis.

---

## Anomaly Detection Strategy

### agents/watcher/anomaly_detector.py

**Purpose**: Real-time, lightweight statistical anomaly detection

**Use Case**:
- WatcherAgent continuous monitoring
- Quick threshold-based alerts
- Low computational overhead
- Immediate response to obvious anomalies

**Methods**:
- `detect_traffic_drop()` - Simple percentage drop detection
- `detect_position_drop()` - Ranking position changes
- `detect_ctr_anomaly()` - CTR threshold violations
- `detect_conversion_drop()` - Conversion rate monitoring

**Implementation**: Basic statistical methods (mean, stdev, Z-scores)

**When to Use**: Real-time monitoring, dashboard alerts, immediate notifications

### insights_core/anomaly_detector.py

**Purpose**: Advanced multi-method anomaly detection with ML

**Use Case**:
- Deep analysis via Celery background tasks
- Statistical validation of anomalies
- Trend forecasting
- Complex pattern recognition

**Methods**:
- `detect_serp_anomalies()` - Multi-method SERP analysis
- `detect_traffic_anomalies()` - Prophet forecasting + Isolation Forest
- `detect_with_prophet()` - Time series forecasting
- `detect_with_isolation_forest()` - ML-based outlier detection

**Implementation**:
- Facebook Prophet for forecasting
- Isolation Forest (sklearn) for ML detection
- Async database integration
- Multi-method result merging

**When to Use**: Scheduled analysis, insight generation, trend forecasting, ML-powered detection

### Why Both?

| Aspect | Watcher | Insights Core |
|--------|---------|---------------|
| **Latency** | < 1 second | Minutes |
| **Accuracy** | Good (80-85%) | Excellent (95%+) |
| **Resource Use** | Minimal | High (CPU, memory) |
| **False Positives** | Higher | Lower |
| **Use Case** | Alerts | Analysis |

**Decision Tree**:
```
Need immediate alert for major drop?
  → Use agents/watcher/anomaly_detector.py

Need validated insight with trend forecasting?
  → Use insights_core/anomaly_detector.py
```

---

## Alert Management Architecture

### agents/watcher/alert_manager.py

**Purpose**: Agent findings storage and retrieval

**Database Table**: `gsc.agent_findings`

**Responsibility**:
- Store findings from autonomous agents
- Track agent-generated alerts
- Provide audit trail for agent decisions
- Simple CRUD for agent findings

**Methods**:
- `create_alert()` - Store single finding
- `batch_create_alerts()` - Store multiple findings
- `get_unprocessed_alerts()` - Retrieve unprocessed findings
- `mark_processed()` - Update processing status

**When to Use**: Agent system wants to record a finding

### notifications/alert_manager.py

**Purpose**: Central alert orchestration and notification routing

**Database Tables**:
- `notifications.alert_rules`
- `notifications.alert_history`
- `notifications.notification_queue`

**Responsibility**:
- Rule-based alert triggering
- Multi-channel notification routing (Slack, Email, SMS, Webhook)
- Alert suppression and rate limiting
- Retry logic and delivery tracking
- Notification queue management

**Methods**:
- `create_alert_rule()` - Configure alerting rules
- `trigger_alert()` - Send notifications
- `check_and_trigger_serp_drop()` - Rule-based triggering
- `process_notification_queue()` - Queue processing
- `suppress_duplicate_alerts()` - Deduplication

**When to Use**: Need to send notifications to users/teams

### Why Both?

```
Flow:
1. Agent detects issue → agents/watcher/alert_manager.py (stores finding)
2. Finding triggers notification rule → notifications/alert_manager.py (sends alerts)
3. Users receive Slack/Email → End
```

**Separation of Concerns**:
- **Watcher Alert Manager**: "What did we find?" (Data storage)
- **Notifications Alert Manager**: "Who should know?" (Delivery orchestration)

---

## Metrics Export Approaches

### scheduler/metrics_exporter.py

**Purpose**: Simple Flask-based metrics HTTP endpoint

**Deployment**: Docker container (ACTIVE in production)

**Implementation**:
- Flask web server
- Synchronous psycopg2 queries
- Manual Prometheus format generation
- `/metrics` endpoint for scraping

**Characteristics**:
- Lightweight (~200 lines)
- Minimal dependencies
- Easy to understand and debug
- Currently deployed and running

**When to Use**: Current production deployment

### metrics_exporter/exporter.py

**Purpose**: Advanced Prometheus-native metrics collector

**Implementation**:
- prometheus_client library
- Async metric collection
- YAML-based configuration
- Comprehensive metric types (Gauge, Counter, Info)
- Periodic background collection

**Characteristics**:
- More robust (~350 lines)
- Rich metric types
- Better Prometheus integration
- Not yet deployed

**When to Use**: Future migration target

### Status

**Current**: Both exist, scheduler version is deployed
**Future**: Migrate to metrics_exporter/exporter.py for better Prometheus integration
**Action Required**: Test metrics_exporter/exporter.py in staging before production migration

---

## SERP Tracking Complementary Systems

### insights_core/serp_tracker.py

**Purpose**: General SERP position tracking with external APIs

**Features**:
- Hybrid mode (GSC + external APIs)
- Supports ValueSERP, SerpAPI, DataForSEO
- Scrapy integration
- Comprehensive SERP data collection

**When to Use**: Need external SERP API data, competitive analysis

### insights_core/gsc_serp_tracker.py

**Purpose**: GSC-based SERP position tracking (free alternative)

**Features**:
- Uses only GSC data (no external API costs)
- GSC position tracking
- Free tier friendly

**When to Use**: Budget constraints, GSC data sufficient

### Relationship

**Complementary, not duplicate**:
- `serp_tracker.py` = Full-featured with API costs
- `gsc_serp_tracker.py` = Free alternative using GSC only

**Decision Factors**:
```
Budget available for SERP APIs?
  YES → serp_tracker.py (comprehensive)
  NO  → gsc_serp_tracker.py (GSC-only)
```

---

## Dispatcher Pattern Clarification

### insights_core/dispatcher.py (InsightDispatcher)

**Purpose**: Route insights to notification channels

**Responsibility**:
- Insight routing based on severity/category
- Channel selection (Slack, Email, Jira, Webhook)
- Retry logic for delivery
- Dispatch tracking

**Input**: Insight objects
**Output**: Notifications sent to channels

**When to Use**: Send insights to stakeholders

### agents/dispatcher/dispatcher_agent.py (DispatcherAgent)

**Purpose**: Execute approved recommendations

**Responsibility**:
- Validate recommendations
- Execute approved actions
- Monitor outcomes
- Track execution results

**Input**: Approved recommendations
**Output**: Executed actions + outcome tracking

**When to Use**: Autonomous action execution

### Naming Clarification

Despite both using "Dispatcher" in the name, they dispatch **different things**:

| Component | Dispatches | To Where | Purpose |
|-----------|-----------|----------|---------|
| **InsightDispatcher** | Insights | Notification channels | Communication |
| **DispatcherAgent** | Recommendations | Execution engine | Action |

**Recommended Renaming** (Future):
- `insights_core/dispatcher.py` → `insights_core/insight_router.py`
- `agents/dispatcher/dispatcher_agent.py` → `agents/executor/executor_agent.py`

---

## Summary

### Intentional Patterns

1. **Lightweight + Advanced Pairs**: Fast simple version for real-time, robust version for analysis
2. **Storage + Orchestration Separation**: Data persistence vs. delivery management
3. **Free + Paid Alternatives**: Cost-flexible options for different deployments
4. **Specialized Dispatchers**: Communication routing vs. action execution

### Not Duplicates

These patterns reflect **architectural decisions** for:
- Performance optimization (real-time vs. batch)
- Separation of concerns (storage vs. notification)
- Cost flexibility (free vs. paid tiers)
- Different responsibilities (routing vs. execution)

### When to Consolidate

Only consolidate when:
1. One implementation is clearly obsolete
2. Use cases fully overlap
3. Performance trade-offs are acceptable
4. Migration path is tested and validated

### When to Keep Separate

Keep separate when:
1. Serve different performance requirements
2. Different deployment contexts
3. Different cost models
4. Different responsibility domains

---

## Migration Roadmap

### Phase 1: Current State (✅ Complete)
- Document all dual implementations
- Clarify architectural intent
- Add this guide for future developers

### Phase 2: Metrics Consolidation (Planned)
- Test `metrics_exporter/exporter.py` in staging
- Validate Prometheus integration
- Migrate production to new implementation
- Deprecate `scheduler/metrics_exporter.py`

### Phase 3: Naming Clarity (Future)
- Rename `insights_core/dispatcher.py` → `insight_router.py`
- Rename `agents/dispatcher/` → `agents/executor/`
- Update all references and tests

### Phase 4: Anomaly Detection Unification (Future)
- Create common interface for both detectors
- Standardize method signatures
- Allow runtime selection of detection strategy
- Maintain both implementations under unified API

---

## For New Developers

**Before reporting "duplicate code":**
1. Check this document
2. Verify both implementations are active (grep for imports)
3. Understand different use cases
4. Consult team before refactoring

**Questions to Ask**:
- Do they serve the same performance requirements?
- Do they have the same dependencies and cost models?
- Are they used in the same execution contexts?
- Is there a documented architectural reason for separation?

---

*Last Updated: 2025-01-23*
*Author: System Architecture Team*
