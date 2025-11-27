# Multi-Agent System - Complete Guide

**Version:** 2.0
**Last Updated:** 2025
**Audience:** Developers, System Architects, Advanced Users

---

## Table of Contents

1. [What Is the Multi-Agent System?](#what-is-the-multi-agent-system)
2. [Agent Architecture](#agent-architecture)
3. [Agent Types](#agent-types)
4. [Communication & Coordination](#communication--coordination)
5. [Workflow Examples](#workflow-examples)
6. [Deployment & Operations](#deployment--operations)
7. [Extending the System](#extending-the-system)
8. [Troubleshooting](#troubleshooting)

---

## What Is the Multi-Agent System?

The **Multi-Agent System** is an advanced layer of intelligence built on top of the Insight Engine that adds:

1. **Autonomous Analysis**: Agents independently monitor, analyze, and act
2. **Collaborative Problem-Solving**: Agents work together on complex issues
3. **Automated Remediation**: Agents can execute fixes with approval
4. **Continuous Learning**: System improves through outcome monitoring

### Insight Engine vs Multi-Agent System

| Capability | Insight Engine | Multi-Agent System |
|------------|----------------|-------------------|
| **Detection** | ✅ Automated | ✅ Automated + Advanced |
| **Diagnosis** | ✅ Basic | ✅ Deep analysis |
| **Recommendations** | ❌ Manual | ✅ Automated |
| **Execution** | ❌ Manual | ✅ Automated (with approval) |
| **Learning** | ❌ Static rules | ✅ Outcome-based learning |
| **Collaboration** | ❌ Single process | ✅ Multiple agents cooperate |

### Why Multiple Agents?

**Single-Agent Problems**:
- One process doing everything = complexity explosion
- Hard to test and maintain
- Cannot parallelize work
- No specialization

**Multi-Agent Benefits**:
- ✅ **Specialization**: Each agent excels at specific tasks
- ✅ **Parallelization**: Run analyses concurrently
- ✅ **Fault Isolation**: One agent failing doesn't crash system
- ✅ **Scalability**: Add more agents as needed
- ✅ **Testability**: Test agents independently

---

## Agent Architecture

### Core Principles

#### 1. Agent Contract
All agents implement the same interface:

```python
class AgentContract(ABC):
    """Base interface for all agents"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Setup connections, load config"""

    @abstractmethod
    async def process(self, input_data: Dict) -> Dict:
        """Main processing logic"""

    @abstractmethod
    async def health_check(self) -> AgentHealth:
        """Return current health status"""

    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup resources"""
```

**Benefits**:
- Standardized interface
- Easy to add new agents
- Simple health monitoring
- Graceful shutdown

#### 2. Asynchronous Processing
All agents use `async/await` for:
- Non-blocking I/O
- Concurrent operations
- Efficient resource usage

```python
async def process(self, input_data: Dict) -> Dict:
    # Can await multiple operations concurrently
    results = await asyncio.gather(
        self.fetch_data(),
        self.analyze_patterns(),
        self.generate_insights()
    )
    return results
```

#### 3. Message-Driven Communication
Agents communicate via messages, not direct calls:

```python
# Don't do this (tight coupling)
result = diagnostician_agent.diagnose(anomaly)

# Do this (loose coupling)
await message_bus.publish(Event(
    type='anomaly_detected',
    data={'anomaly_id': anomaly.id}
))
```

#### 4. State Persistence
Agent state persists across restarts:

```python
class StateManager:
    """Persist agent state to database"""

    async def save_state(self, agent_id: str, state: Dict):
        """Save current state"""

    async def load_state(self, agent_id: str) -> Dict:
        """Load previous state"""
```

---

### Agent Lifecycle

```
┌──────────────┐
│ INITIALIZED  │  Agent created, not yet running
└──────┬───────┘
       │ initialize()
       ▼
┌──────────────┐
│   RUNNING    │  Processing messages, performing work
└──────┬───────┘
       │ on error
       ▼
┌──────────────┐
│    ERROR     │  Temporary failure, attempting recovery
└──────┬───────┘
       │ shutdown()
       ▼
┌──────────────┐
│   SHUTDOWN   │  Stopped cleanly, resources released
└──────────────┘
```

**State Transitions**:

1. **INITIALIZED → RUNNING**
   - Database connections established
   - Sub-components initialized
   - Ready to process messages

2. **RUNNING → ERROR**
   - Exception caught during processing
   - Error counter incremented
   - Retry logic triggered

3. **ERROR → RUNNING**
   - Successful recovery
   - Error counter may be reset

4. **Any → SHUTDOWN**
   - Graceful shutdown requested
   - Current work completed
   - Resources released

---

## Agent Types

### 1. WatcherAgent

**Purpose**: First line of defense - monitors metrics and detects anomalies in real-time

**Responsibilities**:
- Continuous metric monitoring
- Statistical anomaly detection
- Trend analysis
- Alert generation

**Process Flow**:
```
1. Fetch active pages with recent data
   ↓
2. For each page:
   ├─ Get historical baseline (30+ days)
   ├─ Get current metrics (last 7 days)
   ├─ Run statistical tests
   └─ Create anomalies if detected
   ↓
3. Generate alerts
   ↓
4. Publish events to message bus
```

**Detection Methods**:

**1. Traffic Drop Detection**
```python
async def detect_traffic_drop(
    self,
    current_value: float,
    historical_values: List[float],
    threshold_percent: float = 30.0
) -> Optional[Anomaly]:
    """
    Z-score test:
    - Calculate mean and standard deviation of baseline
    - Z-score = (current - mean) / stdev
    - Anomaly if z < -2.5 AND percent drop > threshold
    """
    mean = statistics.mean(historical_values)
    stdev = statistics.stdev(historical_values)

    z_score = (current_value - mean) / stdev if stdev > 0 else 0
    pct_change = ((current_value - mean) / mean) * 100

    if z_score < -2.5 and pct_change < -threshold_percent:
        return Anomaly(
            metric_name='clicks',
            current_value=current_value,
            expected_value=mean,
            deviation_percent=pct_change,
            z_score=z_score,
            severity='high' if pct_change < -50 else 'medium'
        )
```

**2. Position Change Detection**
```python
async def detect_position_drop(
    self,
    current_position: float,
    historical_positions: List[float],
    threshold_positions: float = 5.0
) -> Optional[Anomaly]:
    """
    Absolute position change:
    - Position worsened by >5 spots = anomaly
    - Position 3 → 8 = problem
    - Position 15 → 20 = less critical
    """
    mean_position = statistics.mean(historical_positions)
    position_change = current_position - mean_position

    if position_change > threshold_positions:
        return Anomaly(
            metric_name='position',
            current_value=current_position,
            expected_value=mean_position,
            deviation_positions=position_change,
            severity='high' if position_change > 10 else 'medium'
        )
```

**3. CTR Anomaly Detection**
```python
async def detect_ctr_anomaly(
    self,
    current_ctr: float,
    historical_ctrs: List[float]
) -> Optional[Anomaly]:
    """
    Percentage point change:
    - CTR from 4% to 2% = -2 percentage points
    - Relative change = -50%
    - Anomaly if below 2 standard deviations
    """
    mean_ctr = statistics.mean(historical_ctrs)
    stdev_ctr = statistics.stdev(historical_ctrs)

    z_score = (current_ctr - mean_ctr) / stdev_ctr if stdev_ctr > 0 else 0

    if z_score < -2.0:
        return Anomaly(
            metric_name='ctr',
            current_value=current_ctr,
            expected_value=mean_ctr,
            severity='medium'
        )
```

**4. Zero Traffic Detection**
```python
async def detect_zero_traffic(
    self,
    current_clicks: int,
    current_impressions: int,
    historical_clicks: List[int]
) -> Optional[Anomaly]:
    """
    Dead page detection:
    - Previously had traffic (avg > 10 clicks/day)
    - Now has zero clicks AND zero impressions
    - Indicates de-indexing or technical issue
    """
    avg_historical = statistics.mean(historical_clicks)

    if avg_historical > 10 and current_clicks == 0 and current_impressions == 0:
        return Anomaly(
            metric_name='traffic',
            current_value=0,
            expected_value=avg_historical,
            severity='high',
            context={'likely_cause': 'de-indexed or blocked'}
        )
```

**5. Trend Detection**
```python
async def detect_linear_trend(
    self,
    values: List[float],
    min_confidence: float = 0.7
) -> Optional[Trend]:
    """
    Linear regression:
    - Fit line: y = mx + b
    - Calculate R² (goodness of fit)
    - If R² > 0.7 and slope significant → trend detected
    """
    import numpy as np
    from scipy import stats

    x = np.arange(len(values))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)

    r_squared = r_value ** 2

    if r_squared > min_confidence and p_value < 0.05:
        magnitude = (slope * len(values)) / values[0] * 100  # % change

        return Trend(
            trend_type='increasing' if slope > 0 else 'decreasing',
            slope=slope,
            confidence=r_squared,
            magnitude_percent=magnitude,
            duration_days=len(values)
        )
```

**Output**:
Creates `Alert` objects stored in database and published to message bus:

```python
@dataclass
class Alert:
    agent_name: str
    finding_type: str  # 'anomaly' or 'trend'
    severity: str  # 'low', 'medium', 'high'
    affected_pages: List[str]
    metrics: Dict[str, Any]
    notes: str
    metadata: Dict[str, Any]
```

---

### 2. DiagnosticianAgent

**Purpose**: Investigates detected anomalies and determines root causes

**Responsibilities**:
- Root cause analysis
- Hypothesis testing
- Correlation analysis
- Issue classification

**Process Flow**:
```
1. Receive anomaly alert from Watcher
   ↓
2. Gather comprehensive context:
   ├─ Historical data for affected pages
   ├─ Related pages (same directory, similar patterns)
   ├─ External events (algorithm updates, deployments)
   └─ Technical metrics (speed, errors)
   ↓
3. Generate hypotheses:
   ├─ Technical issue
   ├─ Content change
   ├─ Algorithm update
   ├─ Seasonal pattern
   └─ Competitive pressure
   ↓
4. Test each hypothesis
   ↓
5. Rank hypotheses by probability
   ↓
6. Create diagnosis report
   ↓
7. Publish to message bus
```

**Sub-Components**:

#### Issue Classifier
```python
class IssueClassifier:
    """Categorize issues by type"""

    def classify(self, anomaly: Anomaly, context: Dict) -> str:
        """
        Returns: 'technical', 'content', 'seo', 'competitive', 'seasonal'
        """
        # Check for technical indicators
        if context.get('4xx_errors') > 0:
            return 'technical'

        # Check for content changes
        if context.get('last_modified') within_days(7):
            return 'content'

        # Check for algorithm update correlation
        if context.get('algo_update') within_days(7):
            return 'seo'

        # Check for seasonal pattern
        if self._matches_seasonal_pattern(context):
            return 'seasonal'

        return 'unknown'
```

#### Correlation Engine
```python
class CorrelationEngine:
    """Find correlated events and patterns"""

    async def find_correlations(
        self,
        anomaly: Anomaly,
        context: Dict
    ) -> List[Correlation]:
        """
        Returns list of correlations with strength scores
        """
        correlations = []

        # Check for directory-wide issues
        similar_pages = await self._find_pages_in_same_directory(
            anomaly.page_path
        )

        affected_count = sum(
            1 for p in similar_pages
            if p.has_similar_drop(anomaly.detected_at, tolerance_days=3)
        )

        if affected_count >= 3:
            correlations.append(Correlation(
                type='directory_wide',
                strength=affected_count / len(similar_pages),
                description=f'{affected_count} pages in same directory affected'
            ))

        # Check for timing correlation with deployment
        deployments = await self._get_recent_deployments(days=7)

        for deployment in deployments:
            days_apart = (anomaly.detected_at - deployment.date).days

            if days_apart <= 2:
                correlations.append(Correlation(
                    type='deployment',
                    strength=1.0 - (days_apart / 7),
                    description=f'Drop occurred {days_apart} days after deployment',
                    metadata={'deployment_id': deployment.id}
                ))

        return correlations
```

#### Root Cause Analyzer
```python
class RootCauseAnalyzer:
    """Generate and test hypotheses"""

    async def analyze(
        self,
        anomaly: Anomaly,
        context: Dict,
        correlations: List[Correlation]
    ) -> List[Hypothesis]:
        """
        Returns ranked list of probable root causes
        """
        hypotheses = []

        # Hypothesis 1: Technical issue
        if context.get('avg_load_time') > 3.0:
            hypotheses.append(Hypothesis(
                cause='slow_page_speed',
                probability=0.8,
                evidence=[
                    f"Page load time increased to {context['avg_load_time']}s",
                    f"Correlation: {context.get('bounce_rate_increase', 0):.1f}% bounce increase"
                ],
                recommendation="Optimize page speed (compress images, minify JS/CSS)"
            ))

        # Hypothesis 2: Content change
        content_correlation = next(
            (c for c in correlations if c.type == 'deployment'),
            None
        )

        if content_correlation and content_correlation.strength > 0.7:
            hypotheses.append(Hypothesis(
                cause='content_update',
                probability=content_correlation.strength,
                evidence=[
                    content_correlation.description,
                    "No other technical issues detected"
                ],
                recommendation="Review recent content changes for SEO issues"
            ))

        # Rank by probability
        hypotheses.sort(key=lambda h: h.probability, reverse=True)

        return hypotheses
```

**Output**:
Creates `Diagnosis` objects:

```python
@dataclass
class Diagnosis:
    anomaly_id: str
    root_cause: str  # Most likely cause
    probability: float  # Confidence 0.0-1.0
    evidence: List[str]  # Supporting evidence
    hypotheses: List[Hypothesis]  # All tested hypotheses
    recommendations: List[str]  # What to do
    metadata: Dict[str, Any]
```

---

### 3. StrategistAgent

**Purpose**: Generates actionable recommendations based on diagnoses

**Responsibilities**:
- Recommendation generation
- Impact estimation
- Priority ranking
- Action planning

**Process Flow**:
```
1. Receive diagnosis from Diagnostician
   ↓
2. Generate solution options:
   ├─ Quick fix (low effort, medium impact)
   ├─ Proper fix (medium effort, high impact)
   └─ Strategic fix (high effort, very high impact)
   ↓
3. Estimate impact for each:
   ├─ Traffic gain
   ├─ Conversion gain
   ├─ Revenue impact
   └─ Implementation effort
   ↓
4. Calculate ROI
   ↓
5. Rank by priority
   ↓
6. Create recommendation report
   ↓
7. Store in database
```

**Sub-Components**:

#### Recommendation Engine
```python
class RecommendationEngine:
    """Generate specific actionable recommendations"""

    async def generate(
        self,
        diagnosis: Diagnosis
    ) -> List[Recommendation]:
        """
        Returns list of recommendations with details
        """
        recommendations = []

        if diagnosis.root_cause == 'slow_page_speed':
            recommendations.extend([
                Recommendation(
                    type='optimize_images',
                    effort='low',
                    impact='medium',
                    description='Compress images to reduce page weight',
                    steps=[
                        'Identify images >200KB',
                        'Use ImageOptim or similar tool',
                        'Convert to WebP format',
                        'Implement lazy loading'
                    ],
                    estimated_time_hours=2
                ),
                Recommendation(
                    type='enable_caching',
                    effort='medium',
                    impact='high',
                    description='Configure browser and CDN caching',
                    steps=[
                        'Add Cache-Control headers',
                        'Configure CDN cache rules',
                        'Implement service worker for offline caching'
                    ],
                    estimated_time_hours=4
                )
            ])

        elif diagnosis.root_cause == 'content_update':
            recommendations.append(
                Recommendation(
                    type='revert_content',
                    effort='low',
                    impact='high',
                    description='Revert problematic content changes',
                    steps=[
                        'Identify specific content changes',
                        'Revert to previous version',
                        'Monitor for recovery'
                    ],
                    estimated_time_hours=1
                )
            )

        return recommendations
```

#### Impact Estimator
```python
class ImpactEstimator:
    """Estimate potential impact of recommendations"""

    async def estimate(
        self,
        recommendation: Recommendation,
        current_metrics: Dict
    ) -> Impact:
        """
        Calculate expected outcome if recommendation executed
        """
        if recommendation.type == 'optimize_images':
            # Improved speed → better engagement → better rankings → more traffic
            speed_improvement = 40  # % faster load time
            engagement_lift = speed_improvement * 0.3  # 30% of speed improvement
            ranking_lift = engagement_lift * 0.5  # 50% of engagement lift
            traffic_lift = ranking_lift * 2  # 2x multiplier for traffic

            current_traffic = current_metrics['monthly_clicks']
            estimated_gain = current_traffic * (traffic_lift / 100)

            return Impact(
                metric='traffic',
                current_value=current_traffic,
                estimated_value=current_traffic + estimated_gain,
                gain_absolute=estimated_gain,
                gain_percent=traffic_lift,
                confidence=0.6,  # Medium confidence
                time_to_impact_days=30  # Expect results in 30 days
            )

        elif recommendation.type == 'improve_ctr':
            # CTR optimization = immediate traffic gain
            current_impressions = current_metrics['monthly_impressions']
            current_ctr = current_metrics['ctr']
            target_ctr = 0.04  # 4% industry average

            if current_ctr < target_ctr:
                current_clicks = current_impressions * current_ctr
                potential_clicks = current_impressions * target_ctr
                gain = potential_clicks - current_clicks

                return Impact(
                    metric='traffic',
                    current_value=current_clicks,
                    estimated_value=potential_clicks,
                    gain_absolute=gain,
                    gain_percent=((target_ctr - current_ctr) / current_ctr) * 100,
                    confidence=0.8,  # High confidence
                    time_to_impact_days=7  # Quick results
                )
```

#### Prioritizer
```python
class Prioritizer:
    """Rank recommendations by priority"""

    def prioritize(
        self,
        recommendations: List[Recommendation],
        impacts: List[Impact]
    ) -> List[PrioritizedRecommendation]:
        """
        Score = (Impact / Effort) × Confidence

        Returns sorted list with priority scores
        """
        prioritized = []

        for rec, impact in zip(recommendations, impacts):
            effort_score = {
                'low': 1,
                'medium': 2,
                'high': 3
            }[rec.effort]

            impact_score = impact.gain_absolute

            priority_score = (impact_score / effort_score) * impact.confidence

            prioritized.append(PrioritizedRecommendation(
                recommendation=rec,
                impact=impact,
                priority_score=priority_score,
                rank=0  # Will be set after sorting
            ))

        # Sort by priority score
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)

        # Assign ranks
        for i, item in enumerate(prioritized, 1):
            item.rank = i

        return prioritized
```

**Output**:
Creates `StrategyReport` objects:

```python
@dataclass
class StrategyReport:
    diagnosis_id: str
    recommendations: List[PrioritizedRecommendation]
    estimated_total_impact: Impact
    recommended_action_plan: str  # Step-by-step plan
    priority: str  # 'urgent', 'high', 'medium', 'low'
    estimated_total_effort_hours: float
    expected_roi: float
```

---

### 4. DispatcherAgent

**Purpose**: Executes approved recommendations and monitors outcomes

**Responsibilities**:
- Execution orchestration
- Validation
- Rollback on failure
- Outcome monitoring

**Process Flow**:
```
1. Receive approved recommendation
   ↓
2. Pre-execution validation:
   ├─ Check prerequisites
   ├─ Verify permissions
   └─ Create rollback plan
   ↓
3. Execute via integration:
   ├─ WordPress API (content updates)
   ├─ Cloudflare API (CDN config)
   ├─ GitHub API (code deployments)
   └─ Custom scripts
   ↓
4. Post-execution validation:
   ├─ Verify changes applied
   ├─ Check for errors
   └─ Test functionality
   ↓
5. If validation fails → Rollback
   ↓
6. Start outcome monitoring (7-30 days)
   ↓
7. Report results
```

**Sub-Components**:

#### Execution Engine
```python
class ExecutionEngine:
    """Execute recommendations via integrations"""

    async def execute_recommendation(
        self,
        recommendation_id: int,
        dry_run: bool = False
    ) -> ExecutionResult:
        """
        Execute recommendation with rollback capability
        """
        # 1. Get recommendation details
        rec = await self._get_recommendation(recommendation_id)

        # 2. Create execution record
        execution = await self._create_execution_record(rec, dry_run)

        # 3. Create rollback plan
        rollback_plan = await self._create_rollback_plan(rec)

        try:
            # 4. Execute based on type
            if rec.type == 'update_meta_tags':
                result = await self._update_meta_tags(
                    rec.target_url,
                    rec.parameters['meta_tags'],
                    dry_run
                )

            elif rec.type == 'optimize_images':
                result = await self._optimize_images(
                    rec.target_url,
                    rec.parameters,
                    dry_run
                )

            elif rec.type == 'enable_caching':
                result = await self._configure_caching(
                    rec.parameters,
                    dry_run
                )

            # 5. Update execution record
            await self._update_execution_record(
                execution.id,
                status='completed',
                result=result
            )

            return ExecutionResult(
                success=True,
                execution_id=execution.id,
                message='Recommendation executed successfully',
                changes_made=result.changes,
                rollback_available=True
            )

        except Exception as e:
            # Execution failed
            await self._update_execution_record(
                execution.id,
                status='failed',
                error=str(e)
            )

            return ExecutionResult(
                success=False,
                execution_id=execution.id,
                message=f'Execution failed: {str(e)}',
                error=str(e)
            )
```

#### Validator
```python
class Validator:
    """Validate execution success"""

    async def validate_execution(
        self,
        execution_id: int
    ) -> ValidationResult:
        """
        Verify changes were applied correctly
        """
        execution = await self._get_execution(execution_id)
        rec = await self._get_recommendation(execution.recommendation_id)

        validations = []

        if rec.type == 'update_meta_tags':
            # Fetch page HTML
            html = await self._fetch_page_html(rec.target_url)

            # Extract meta tags
            meta_tags = self._extract_meta_tags(html)

            # Compare to expected
            expected = rec.parameters['meta_tags']

            for tag, value in expected.items():
                actual = meta_tags.get(tag)

                validations.append(Validation(
                    check=f'meta_{tag}',
                    expected=value,
                    actual=actual,
                    passed=(actual == value)
                ))

        # Aggregate results
        all_passed = all(v.passed for v in validations)

        return ValidationResult(
            execution_id=execution_id,
            passed=all_passed,
            validations=validations
        )

    async def should_rollback(
        self,
        validation_result: ValidationResult
    ) -> bool:
        """
        Determine if execution should be rolled back
        """
        # Rollback if any critical validation failed
        critical_failures = [
            v for v in validation_result.validations
            if not v.passed and v.get('critical', True)
        ]

        return len(critical_failures) > 0
```

#### Outcome Monitor
```python
class OutcomeMonitor:
    """Monitor metrics after execution"""

    async def start_monitoring(
        self,
        execution_id: int,
        duration_days: int = 30
    ) -> MonitoringSession:
        """
        Track metrics for specified duration
        """
        execution = await self._get_execution(execution_id)
        rec = await self._get_recommendation(execution.recommendation_id)

        # Capture baseline (before execution)
        baseline = await self._capture_baseline(
            rec.target_url,
            days_before=7
        )

        # Create monitoring session
        session = await self._create_monitoring_session(
            execution_id=execution_id,
            baseline=baseline,
            target_metrics=rec.expected_impact.metrics,
            duration_days=duration_days
        )

        # Schedule periodic metric collection
        await self._schedule_metric_collection(session.id)

        return session

    async def collect_metrics(
        self,
        execution_id: int
    ) -> MetricsSnapshot:
        """
        Collect current metrics for comparison
        """
        execution = await self._get_execution(execution_id)
        rec = await self._get_recommendation(execution.recommendation_id)

        # Query current metrics
        metrics = await self._query_metrics(
            rec.target_url,
            days=7  # Last 7 days average
        )

        # Store snapshot
        await self._store_metrics_snapshot(execution_id, metrics)

        return metrics

    async def evaluate_outcome(
        self,
        execution_id: int
    ) -> OutcomeEvaluation:
        """
        Evaluate if execution achieved expected impact
        """
        session = await self._get_monitoring_session(execution_id)
        current = await self.collect_metrics(execution_id)

        # Compare to baseline
        improvements = {}
        for metric, baseline_value in session.baseline.items():
            current_value = current.metrics.get(metric, 0)
            change = current_value - baseline_value
            change_pct = (change / baseline_value * 100) if baseline_value > 0 else 0

            improvements[metric] = {
                'baseline': baseline_value,
                'current': current_value,
                'change': change,
                'change_pct': change_pct
            }

        # Check if target achieved
        target = session.target_metrics
        achieved = all(
            improvements[m]['change_pct'] >= target[m]['target_pct']
            for m in target.keys()
        )

        return OutcomeEvaluation(
            execution_id=execution_id,
            achieved=achieved,
            improvements=improvements,
            recommendation='Continue monitoring' if achieved else 'Consider additional optimization'
        )
```

**Output**:
Creates `ExecutionRecord` with full history and outcomes.

---

## Communication & Coordination

### Message Bus

**Architecture**:
```python
class MessageBus:
    """Event-driven message bus for agent communication"""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.message_queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, event_type: str, handler: Callable):
        """Register handler for event type"""
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publish event to all subscribers"""
        logger.info(f"Publishing event: {event.type}")

        for handler in self.subscribers[event.type]:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler failed: {e}")

    async def publish_async(self, event: Event):
        """Publish event asynchronously (non-blocking)"""
        await self.message_queue.put(event)
```

**Event Types**:

| Event Type | Publisher | Subscribers | Data |
|------------|-----------|-------------|------|
| `anomaly_detected` | WatcherAgent | DiagnosticianAgent | Anomaly object |
| `diagnosis_complete` | DiagnosticianAgent | StrategistAgent | Diagnosis object |
| `recommendation_created` | StrategistAgent | DispatcherAgent (manual) | Recommendation object |
| `execution_started` | DispatcherAgent | OutcomeMonitor | Execution ID |
| `execution_completed` | DispatcherAgent | All | Execution result |
| `outcome_evaluated` | OutcomeMonitor | StrategistAgent | Outcome evaluation |

**Event Format**:
```python
@dataclass
class Event:
    type: str  # Event type (e.g., 'anomaly_detected')
    data: Dict[str, Any]  # Event payload
    timestamp: datetime
    source_agent: str  # Which agent published
    correlation_id: str  # Links related events
    priority: str  # 'low', 'medium', 'high', 'urgent'
```

---

### State Manager

**Purpose**: Persist agent state across restarts

```python
class StateManager:
    """Manage agent state persistence"""

    async def save_state(
        self,
        agent_id: str,
        state: Dict[str, Any]
    ):
        """Save current agent state"""
        await self._db.execute(
            """
            INSERT INTO agent_state (agent_id, state, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (agent_id) DO UPDATE
                SET state = $2, updated_at = $3
            """,
            agent_id,
            json.dumps(state),
            datetime.now()
        )

    async def load_state(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """Load previous agent state"""
        row = await self._db.fetchrow(
            """
            SELECT state FROM agent_state
            WHERE agent_id = $1
            """,
            agent_id
        )

        if row:
            return json.loads(row['state'])

        return {}
```

**Use Cases**:
1. **Resume processing** after restart
2. **Track processed items** (avoid re-processing)
3. **Maintain agent configuration**
4. **Store learning data**

---

## Workflow Examples

### Example 1: Automatic Traffic Drop Investigation

```
DAY 1, 2:00 AM - Scheduled Watcher Run
┌─────────────────────────────────────────┐
│ WatcherAgent detects traffic drop       │
│ - Page: /blog/popular-post              │
│ - Clicks down 45% WoW                    │
│ - Conversions down 32% WoW               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          Create Alert & Publish Event
          (type: 'anomaly_detected')
                  │
                  ▼
┌─────────────────────────────────────────┐
│ DiagnosticianAgent receives event       │
│ - Gathers context                        │
│ - Tests hypotheses:                      │
│   ✓ Deployment on Nov 18                │
│   ✓ Page load time increased to 4.2s    │
│   ✗ No algorithm updates                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          Create Diagnosis & Publish Event
          (type: 'diagnosis_complete')
          Root Cause: Slow page speed after deployment
                  │
                  ▼
┌─────────────────────────────────────────┐
│ StrategistAgent receives event          │
│ - Generates recommendations:             │
│   1. Optimize images (effort: low)       │
│   2. Enable caching (effort: medium)     │
│   3. Rollback deployment (effort: low)   │
│ - Estimates impact for each              │
│ - Ranks by ROI                           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          Create Recommendations
          Notify team via Slack/email
          Wait for approval
                  │
                  ▼
DAY 1, 10:00 AM - Team Approves "Optimize Images"
┌─────────────────────────────────────────┐
│ DispatcherAgent executes                 │
│ - Compresses images via WordPress API    │
│ - Validates changes applied              │
│ - Starts outcome monitoring              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
DAY 8, 2:00 AM - Outcome Evaluation
┌─────────────────────────────────────────┐
│ OutcomeMonitor evaluates                 │
│ - Page speed improved: 4.2s → 1.8s       │
│ - Clicks recovered: -45% → -5%           │
│ - Conversions recovered: -32% → +2%      │
│ - Verdict: Success ✅                    │
└─────────────────────────────────────────┘
```

**Total Time**: Issue detected → Fixed → Verified = 7 days (vs weeks manually)

---

### Example 2: Opportunity Discovery and Execution

```
DAY 1, 2:00 AM - Scheduled Watcher Run
┌─────────────────────────────────────────┐
│ WatcherAgent detects opportunity         │
│ - Page: /products/widget-pro             │
│ - Impressions: 50,000/month              │
│ - CTR: 2.1% (industry avg: 4.5%)        │
│ - Position: 3.2 (good)                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          Create Opportunity Alert
          (type: 'opportunity_detected')
                  │
                  ▼
┌─────────────────────────────────────────┐
│ StrategistAgent analyzes                 │
│ - Potential: +1,200 clicks/month         │
│ - Action: Improve meta tags              │
│ - ROI: High (low effort, high impact)    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          Create Recommendation
          Notify team
                  │
                  ▼
DAY 2, 9:00 AM - Team Approves
┌─────────────────────────────────────────┐
│ DispatcherAgent executes                 │
│ - Updates meta title and description     │
│ - Validates changes                      │
│ - Starts monitoring                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
DAY 30, 2:00 AM - Outcome Evaluation
┌─────────────────────────────────────────┐
│ OutcomeMonitor evaluates                 │
│ - CTR improved: 2.1% → 3.8%              │
│ - Clicks gained: +850/month              │
│ - Target: +1,200 (achieved 71%)          │
│ - Verdict: Partial success               │
│ - Recommendation: Further optimization   │
└─────────────────────────────────────────┘
```

---

## LLM-First Intelligence

### Overview

The Multi-Agent System includes **LLM-First Intelligence** capabilities that enhance agent reasoning with local language models (via Ollama). This provides:

1. **Natural language reasoning** for root cause analysis
2. **Intelligent recommendation generation**
3. **Automated hypothesis testing with explanations**
4. **Resource-aware model selection**

### Architecture Components

#### SystemResourceMonitor

Monitors system resources to ensure LLM operations don't overwhelm the system:

```python
from agents.base.resource_monitor import SystemResourceMonitor

monitor = SystemResourceMonitor()
metrics = monitor.get_resource_metrics()

# Returns:
# {
#     'cpu_percent': 45.2,
#     'memory_percent': 62.1,
#     'memory_available_mb': 4096,
#     'disk_percent': 55.3
# }

# Check if safe to run LLM
if monitor.can_run_llm(min_memory_mb=2048):
    # Proceed with LLM reasoning
    pass
```

#### OllamaModelSelector

Intelligently selects the best available Ollama model based on task and resources:

```python
from agents.base.model_selector import OllamaModelSelector

selector = OllamaModelSelector(ollama_host="http://localhost:11434")

# Get best model for task type
model = selector.select_model(
    task_type='analysis',       # 'analysis', 'generation', 'classification'
    required_context_length=4000,
    prefer_speed=False          # True for faster but smaller models
)

# Returns model name like 'qwen2.5:7b', 'llama3.2:3b', etc.
```

**Model Selection Hierarchy**:
1. **Large models** (7B+): Complex analysis, detailed reasoning
2. **Medium models** (3B): Standard tasks, balanced speed/quality
3. **Small models** (1B-): Quick classification, simple queries

#### LLMReasoner

Core reasoning engine that integrates with agents:

```python
from agents.base.llm_reasoner import LLMReasoner

reasoner = LLMReasoner(
    ollama_host="http://localhost:11434",
    default_model="qwen2.5:7b"
)

# Root cause analysis
diagnosis = await reasoner.analyze_root_cause(
    anomaly={
        'metric': 'clicks',
        'page_path': '/products/widget',
        'change_pct': -45.2,
        'context': {...}
    }
)

# Returns structured analysis:
# {
#     'primary_cause': 'Content update removed key sections',
#     'confidence': 0.82,
#     'evidence': ['Content length decreased by 40%', ...],
#     'recommendations': ['Restore removed content sections', ...],
#     'reasoning': 'The timing of the traffic drop correlates with...'
# }
```

### Agent Integration

#### Enhanced WatcherAgent with LLM

The WatcherAgent (`agents/watcher/intelligent_watcher.py`) uses LLM for:

```python
class IntelligentWatcherAgent:
    """Watcher with LLM-enhanced pattern recognition"""

    async def analyze_with_llm(self, anomalies: List[Anomaly]) -> List[EnrichedAnomaly]:
        """Use LLM to provide context and initial hypotheses"""

        for anomaly in anomalies:
            # LLM generates initial assessment
            assessment = await self.reasoner.assess_anomaly(
                anomaly=anomaly,
                historical_context=self._get_historical_context(anomaly)
            )

            anomaly.initial_assessment = assessment
            anomaly.suggested_priority = assessment.priority

        return anomalies
```

#### Enhanced DiagnosticianAgent with LLM

```python
class LLMDiagnosticianAgent:
    """Diagnostician with deep LLM reasoning"""

    async def diagnose(self, anomaly: Anomaly) -> Diagnosis:
        # 1. Gather context
        context = await self._gather_comprehensive_context(anomaly)

        # 2. Generate hypotheses using LLM
        hypotheses = await self.reasoner.generate_hypotheses(
            anomaly=anomaly,
            context=context
        )

        # 3. Test hypotheses with data
        tested = await self._test_hypotheses(hypotheses)

        # 4. LLM synthesizes final diagnosis
        diagnosis = await self.reasoner.synthesize_diagnosis(
            anomaly=anomaly,
            tested_hypotheses=tested,
            context=context
        )

        return diagnosis
```

#### Enhanced StrategistAgent with LLM

```python
class LLMStrategistAgent:
    """Strategist with LLM-powered recommendations"""

    async def generate_recommendations(self, diagnosis: Diagnosis) -> List[Recommendation]:
        # LLM generates tailored recommendations
        recommendations = await self.reasoner.generate_recommendations(
            diagnosis=diagnosis,
            site_context=self._get_site_context(),
            available_actions=self._get_available_actions()
        )

        # Estimate impact for each
        for rec in recommendations:
            rec.estimated_impact = await self._estimate_impact(rec)

        return self._prioritize(recommendations)
```

### Prompt Templates

The system uses structured prompts (`agents/base/prompt_templates.py`):

```python
ANOMALY_ASSESSMENT_PROMPT = """
Analyze this traffic anomaly:

Page: {page_path}
Metric: {metric}
Change: {change_pct}%
Period: {date_range}

Context:
- Previous week traffic: {prev_week_traffic}
- Historical average: {historical_avg}
- Page age: {page_age_days} days
- Content type: {content_type}

Provide:
1. Severity assessment (critical/high/medium/low)
2. Initial hypothesis for the cause
3. Recommended investigation steps
4. Estimated urgency

Response format:
{format_specification}
"""

ROOT_CAUSE_PROMPT = """
Analyze the root cause of this SEO issue:

Anomaly: {anomaly_description}
Timeline: {timeline}
Correlating events: {events}

Consider these possible causes:
{possible_causes}

For each cause:
1. Probability score (0-1)
2. Supporting evidence
3. Contradicting evidence
4. Investigation steps

Synthesize a final diagnosis with:
- Primary cause
- Contributing factors
- Confidence level
- Recommended actions
"""
```

### Configuration

Configure LLM reasoning in your environment:

```bash
# .env configuration
OLLAMA_HOST=http://localhost:11434
LLM_DEFAULT_MODEL=qwen2.5:7b
LLM_FALLBACK_MODEL=llama3.2:3b

# Resource thresholds
LLM_MIN_MEMORY_MB=2048
LLM_MAX_CPU_PERCENT=80
LLM_REQUEST_TIMEOUT=30

# Feature flags
LLM_ENABLED=true
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_SECONDS=3600
```

### Testing LLM Integration

```bash
# Test LLM connection
python -m tests.test_live_ollama_e2e

# Test with mock (no Ollama required)
pytest tests/agents/test_intelligent_watcher.py -v

# Integration test
python -m agents.watcher.intelligent_watcher --test-mode
```

### Fallback Behavior

When LLM is unavailable or resource-constrained, agents gracefully degrade:

```python
async def process(self, data: Dict) -> Dict:
    try:
        if self.resource_monitor.can_run_llm():
            return await self._process_with_llm(data)
        else:
            logger.warning("LLM unavailable, using rule-based processing")
            return await self._process_with_rules(data)
    except OllamaConnectionError:
        return await self._process_with_rules(data)
```

---

## Deployment & Operations

### Running Agents

**Option 1: Docker Compose** (Recommended)
```yaml
services:
  watcher_agent:
    build: ./agents
    command: python -m agents.watcher.watcher_agent --initialize --detect
    depends_on:
      - warehouse
    restart: unless-stopped

  diagnostician_agent:
    build: ./agents
    command: python -m agents.diagnostician.diagnostician_agent
    depends_on:
      - warehouse
    restart: unless-stopped
```

**Option 2: Manual**
```bash
# WatcherAgent
python -m agents.watcher.watcher_agent \
  --initialize \
  --detect \
  --days 7

# DiagnosticianAgent
python -m agents.diagnostician.diagnostician_agent \
  --process-pending
```

**Option 3: API**
```bash
# Trigger via API
curl -X POST http://localhost:8000/agents/watcher/detect \
  -H "Content-Type: application/json" \
  -d '{"days": 7}'
```

---

### Health Monitoring

**Check Agent Health**:
```python
# Via CLI
python -m agents.watcher.watcher_agent --health

# Via API
curl http://localhost:8000/agents/watcher/health
```

**Response**:
```json
{
  "agent_id": "watcher_001",
  "status": "running",
  "uptime_seconds": 86400,
  "last_heartbeat": "2024-11-20T15:30:00Z",
  "error_count": 2,
  "processed_count": 1234,
  "memory_usage_mb": 156.2,
  "cpu_percent": 12.5,
  "metadata": {
    "anomalies_detected": 42,
    "trends_detected": 15
  }
}
```

---

### Logs & Debugging

**Structured Logging**:
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "anomaly_detected",
    agent_id="watcher_001",
    page_path="/blog/post",
    metric="clicks",
    change_pct=-45.2,
    severity="high"
)
```

**Log Format** (JSON):
```json
{
  "timestamp": "2024-11-20T08:23:15Z",
  "level": "info",
  "event": "anomaly_detected",
  "agent_id": "watcher_001",
  "page_path": "/blog/post",
  "metric": "clicks",
  "change_pct": -45.2,
  "severity": "high"
}
```

**Query Logs**:
```bash
# View all logs
docker compose logs -f watcher_agent

# Filter by event
docker compose logs watcher_agent | grep "anomaly_detected"

# Last 100 lines
docker compose logs --tail 100 watcher_agent
```

---

## Extending the System

### Creating a Custom Agent

**Step 1: Create Agent Class**
```python
# agents/custom/my_agent.py

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus

class MyAgent(AgentContract):
    """Custom agent for specific task"""

    def __init__(self, agent_id: str, config: Dict):
        super().__init__(agent_id, "my_agent", config)
        self.db_config = config['database']

    async def initialize(self) -> bool:
        """Setup resources"""
        self._pool = await asyncpg.create_pool(**self.db_config)
        self._set_status(AgentStatus.RUNNING)
        return True

    async def process(self, input_data: Dict) -> Dict:
        """Main logic"""
        # Your custom logic here
        result = await self.do_custom_work(input_data)
        self._increment_processed_count()
        return result

    async def health_check(self) -> AgentHealth:
        """Health status"""
        uptime = (datetime.now() - self._start_time).total_seconds()
        return AgentHealth(
            agent_id=self.agent_id,
            status=self._status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=0.0,
            cpu_percent=0.0,
            metadata={}
        )

    async def shutdown(self) -> bool:
        """Cleanup"""
        if self._pool:
            await self._pool.close()
        return True

    async def do_custom_work(self, input_data: Dict) -> Dict:
        """Your custom logic"""
        # Implement your agent's functionality
        pass
```

**Step 2: Register with Message Bus**
```python
# Subscribe to events
message_bus.subscribe('custom_event', my_agent.process)

# Publish events
await message_bus.publish(Event(
    type='custom_event',
    data={'key': 'value'},
    source_agent='my_agent',
    timestamp=datetime.now(),
    correlation_id=uuid.uuid4()
))
```

**Step 3: Add to Deployment**
```yaml
# docker-compose.yml
my_agent:
  build: ./agents
  command: python -m agents.custom.my_agent
  depends_on:
    - warehouse
```

---

## Troubleshooting

### Agent Not Starting

**Check Logs**:
```bash
docker compose logs my_agent | tail -50
```

**Common Issues**:
1. Database connection failed
2. Missing configuration
3. Invalid credentials

**Solution**:
```bash
# Check database connectivity
docker compose exec warehouse pg_isready

# Verify environment variables
docker compose config | grep -A 5 my_agent

# Test agent manually
python -m agents.my_agent.my_agent --initialize
```

---

### Agent Stuck in ERROR State

**Diagnosis**:
```python
# Check agent state
state = await state_manager.load_state('my_agent_001')
print(state)
```

**Reset Agent**:
```python
# Clear state
await state_manager.save_state('my_agent_001', {})

# Restart agent
docker compose restart my_agent
```

---

### High Memory Usage

**Monitor**:
```bash
docker stats my_agent
```

**Solutions**:
1. Reduce batch size
2. Add connection pooling
3. Implement pagination
4. Clear caches periodically

---

**Document Version**: 1.0
**Last Updated**: 2025
**Next Review**: Q2 2025
