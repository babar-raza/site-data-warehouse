"""
Intelligent Watcher Agent - LangGraph-Powered Monitoring
========================================================
Monitors traffic patterns using LLM-powered reasoning:
- Detects anomalies with context awareness
- Considers seasonality and trends
- Reasons about root causes
- Plans investigation steps
- Provides actionable recommendations

Replaces simple threshold-based detection with intelligent analysis.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from agents.base.langgraph_agent import AgentState, LangGraphAgent, AgentTools

logger = logging.getLogger(__name__)


class IntelligentWatcherAgent(LangGraphAgent):
    """
    LLM-powered Watcher that monitors and analyzes traffic patterns
    """

    def __init__(self, db_dsn: str = None, ollama_url: str = None):
        """Initialize Intelligent Watcher"""
        super().__init__(
            agent_name="IntelligentWatcher",
            db_dsn=db_dsn,
            ollama_url=ollama_url,
            max_iterations=3
        )

    async def _observe_node(self, state: AgentState) -> AgentState:
        """
        Observe: Gather traffic data and context
        """
        logger.info("IntelligentWatcher: Observing traffic patterns...")

        property = state["property"]
        pool = await self.get_pool()

        # Get recent performance data
        performance_data = await AgentTools.query_performance(
            pool, property, days=30
        )

        # Get recent anomalies from Prophet
        anomaly_data = await AgentTools.query_anomalies(
            pool, property, days=7
        )

        # Analyze patterns
        if performance_data:
            # Calculate aggregate metrics
            total_pages = len(set(p['page_path'] for p in performance_data))
            total_clicks = sum(p.get('gsc_clicks', 0) for p in performance_data)
            avg_position = sum(p.get('gsc_position', 0) for p in performance_data) / len(performance_data)

            observation = f"""Performance Summary (Last 30 days):
- Total Pages: {total_pages}
- Total Clicks: {total_clicks:,}
- Average Position: {avg_position:.2f}
- Data Points: {len(performance_data)}

Recent Anomalies: {len(anomaly_data)} detected by Prophet

Top Issues:
"""
            # Find top issues
            issues = []
            for page in performance_data[:20]:  # Top 20 pages
                delta_7d = page.get('clicks_delta_pct_7d', 0)
                if delta_7d and delta_7d < -15:  # 15%+ drop
                    issues.append(
                        f"  - {page['page_path']}: {delta_7d:.1f}% traffic drop"
                    )

            if issues:
                observation += "\n".join(issues[:5])
            else:
                observation += "  - No major issues detected"

            state["observations"].append(observation)

            # Store findings
            if anomaly_data:
                for anomaly in anomaly_data[:5]:
                    state["findings"].append({
                        "type": "anomaly",
                        "page": anomaly['page_path'],
                        "metric": anomaly['metric_name'],
                        "severity": anomaly['severity'],
                        "deviation": anomaly['deviation_pct']
                    })

        state["current_step"] = "observe"
        return state

    async def _reason_node(self, state: AgentState) -> AgentState:
        """
        Reason: Analyze observations with LLM
        """
        logger.info("IntelligentWatcher: Reasoning about observations...")

        # Build detailed reasoning prompt
        observations_text = "\n\n".join(state["observations"])
        findings_text = "\n".join([
            f"- {f['type']}: {f['page']} ({f.get('severity', 'unknown')} severity)"
            for f in state["findings"]
        ])

        prompt = f"""You are an expert SEO analyst monitoring website traffic.

OBSERVATIONS:
{observations_text}

DETECTED ANOMALIES:
{findings_text}

TASK:
Analyze these observations and anomalies. Consider:
1. Are these real issues or normal fluctuations?
2. What patterns do you see?
3. What could be the root causes?
4. Which issues are most urgent?
5. What additional data would help?

Provide your reasoning in a clear, structured format:
- Pattern Analysis: [What patterns you see]
- Severity Assessment: [How serious are these issues]
- Likely Causes: [Possible root causes]
- Priority: [What to investigate first]
- Next Steps: [What to check next]
"""

        reasoning = await self._call_llm(prompt, temperature=0.1)
        state["reasoning"].append(reasoning)
        state["tools_used"].append("llm_reasoning")
        state["current_step"] = "reason"

        return state

    async def _act_node(self, state: AgentState) -> AgentState:
        """
        Act: Investigate specific issues identified by reasoning
        """
        logger.info("IntelligentWatcher: Acting on reasoning...")

        property = state["property"]
        pool = await self.get_pool()

        # Extract pages to investigate from findings
        pages_to_investigate = [
            f['page'] for f in state["findings"]
            if f.get('severity') in ['high', 'critical']
        ][:3]  # Top 3 issues

        # Investigate each page
        for page_path in pages_to_investigate:
            # Get detailed page data
            page_data = await AgentTools.query_performance(
                pool, property, page_path=page_path, days=30
            )

            if page_data:
                # Analyze trend
                recent = [p['gsc_clicks'] for p in page_data[:7]]
                older = [p['gsc_clicks'] for p in page_data[7:14]]

                recent_avg = sum(recent) / len(recent) if recent else 0
                older_avg = sum(older) / len(older) if older else 0
                trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

                state["findings"].append({
                    "type": "detailed_analysis",
                    "page": page_path,
                    "trend": f"{trend:+.1f}%",
                    "recent_avg_clicks": round(recent_avg),
                    "investigation_complete": True
                })

        state["tools_used"].append("sql_query")
        state["iteration"] += 1
        state["current_step"] = "act"

        return state

    async def _decide_node(self, state: AgentState) -> AgentState:
        """
        Decide: Form conclusions and recommendations
        """
        logger.info("IntelligentWatcher: Forming conclusions...")

        # Build decision prompt
        reasoning_text = "\n\n".join(state["reasoning"])
        findings_summary = "\n".join([
            f"- {f.get('type', 'finding')}: {f.get('page', 'N/A')} - {f.get('trend', f.get('deviation', 'N/A'))}"
            for f in state["findings"]
        ])

        prompt = f"""You are an expert SEO analyst completing your analysis.

YOUR REASONING:
{reasoning_text}

YOUR FINDINGS:
{findings_summary}

TASK:
Provide a clear conclusion and 3-5 actionable recommendations:

Conclusion: [Summary of what you found]

Recommendations:
1. [Most important action]
2. [Second priority action]
3. [Third priority action]
...

Confidence: [Rate your confidence 0.0-1.0]
"""

        decision = await self._call_llm(prompt, temperature=0.1)

        # Parse decision
        state["conclusion"] = decision

        # Extract recommendations (simple parsing)
        import re
        rec_matches = re.findall(r'\d+\.\s*\[?(.*?)\]?(?:\n|$)', decision)

        for i, rec in enumerate(rec_matches[:5], 1):
            if rec.strip():
                state["recommendations"].append({
                    "priority": i,
                    "action": rec.strip(),
                    "category": "traffic_monitoring"
                })

        # Estimate confidence
        if "high confidence" in decision.lower():
            state["confidence"] = 0.9
        elif "medium confidence" in decision.lower():
            state["confidence"] = 0.7
        elif "low confidence" in decision.lower():
            state["confidence"] = 0.5
        else:
            # Try to extract number
            conf_match = re.search(r'confidence[:\s]*(\d+\.?\d*)', decision.lower())
            if conf_match:
                state["confidence"] = float(conf_match.group(1))
            else:
                state["confidence"] = 0.6

        state["current_step"] = "decide"
        return state

    async def analyze_property(self, property: str) -> Dict[str, Any]:
        """
        Complete property analysis workflow

        Args:
            property: Property URL to analyze

        Returns:
            Analysis results
        """
        input_data = {
            "property": property,
            "analysis_type": "traffic_monitoring"
        }

        result = await self.invoke(input_data)

        # Store results in database
        if result.get("success"):
            await self._store_results(property, result)

        return result

    async def _store_results(self, property: str, result: Dict) -> None:
        """Store analysis results in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Store in agent_executions
                await conn.execute("""
                    INSERT INTO gsc.agent_executions (
                        agent_name,
                        execution_status,
                        input_data,
                        output_data,
                        execution_time_seconds,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    self.agent_name,
                    "completed" if result.get("success") else "failed",
                    {"property": property},
                    result,
                    result.get("iterations", 0) * 5,  # Rough estimate
                    datetime.utcnow()
                )

                # Store findings
                for finding in result.get("findings", []):
                    if finding.get("page"):
                        await conn.execute("""
                            INSERT INTO gsc.agent_findings (
                                agent_name,
                                property,
                                page_path,
                                finding_type,
                                severity,
                                details,
                                confidence_score,
                                created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                            self.agent_name,
                            property,
                            finding.get("page"),
                            finding.get("type", "anomaly"),
                            finding.get("severity", "medium"),
                            finding,
                            result.get("confidence", 0.5),
                            datetime.utcnow()
                        )

            logger.info(f"Stored results for {property}")

        except Exception as e:
            logger.error(f"Error storing results: {e}")

    def analyze_property_sync(self, property: str) -> Dict[str, Any]:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.analyze_property(property))
