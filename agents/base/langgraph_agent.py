"""
LangGraph Base Agent - Intelligent Agent Framework
=================================================
Base class for LLM-powered agents using LangGraph:
- Stateful workflows with memory
- Tool use (SQL queries, web search, analysis)
- Reasoning and planning
- Multi-agent collaboration
- Context awareness

This replaces the simple procedural agents with intelligent systems
that can reason about data, plan investigations, and collaborate.
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import asyncpg
import httpx
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """
    Shared state for agent workflow

    This state is passed between agent nodes and maintains
    context throughout the agent's reasoning process.
    """
    # Input
    input_data: Dict[str, Any]
    property: str

    # Agent state
    current_step: str
    iteration: int
    max_iterations: int

    # Memory and context
    observations: List[str]
    findings: List[Dict]
    reasoning: List[str]

    # Tools used
    queries_executed: List[str]
    tools_used: List[str]

    # Output
    conclusion: Optional[str]
    recommendations: List[Dict]
    confidence: float

    # Metadata
    agent_name: str
    started_at: datetime
    completed_at: Optional[datetime]


class LangGraphAgent:
    """
    Base class for intelligent LangGraph-powered agents
    """

    def __init__(
        self,
        agent_name: str,
        db_dsn: str = None,
        ollama_url: str = None,
        model: str = "llama3.1:8b",
        max_iterations: int = 5
    ):
        """
        Initialize LangGraph agent

        Args:
            agent_name: Name of the agent
            db_dsn: Database connection string
            ollama_url: Ollama API URL
            model: LLM model to use
            max_iterations: Max reasoning iterations
        """
        self.agent_name = agent_name
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.ollama_url = ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model = model
        self.max_iterations = max_iterations
        self._pool: Optional[asyncpg.Pool] = None

        # Build workflow graph
        self.workflow = self._build_workflow()

        logger.info(f"{agent_name} initialized with LangGraph")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def _build_workflow(self) -> StateGraph:
        """
        Build the agent workflow graph

        Override in subclasses to define custom workflows

        Returns:
            StateGraph workflow
        """
        workflow = StateGraph(AgentState)

        # Default workflow: observe → reason → act → decide
        workflow.add_node("observe", self._observe_node)
        workflow.add_node("reason", self._reason_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("decide", self._decide_node)

        # Define edges
        workflow.set_entry_point("observe")
        workflow.add_edge("observe", "reason")
        workflow.add_edge("reason", "act")
        workflow.add_conditional_edges(
            "act",
            self._should_continue,
            {
                "continue": "decide",
                "iterate": "observe",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "decide",
            self._is_complete,
            {
                "complete": END,
                "continue": "observe"
            }
        )

        return workflow.compile()

    async def _observe_node(self, state: AgentState) -> AgentState:
        """
        Observe: Gather data and context

        Override in subclasses for specific observations
        """
        logger.info(f"{self.agent_name}: Observing...")

        state["observations"].append(
            f"Iteration {state['iteration']}: Gathering context"
        )
        state["current_step"] = "observe"

        return state

    async def _reason_node(self, state: AgentState) -> AgentState:
        """
        Reason: Use LLM to analyze observations and plan

        This is where the agent thinks about what it has observed
        and decides what to do next.
        """
        logger.info(f"{self.agent_name}: Reasoning...")

        # Build reasoning prompt
        prompt = self._build_reasoning_prompt(state)

        # Call LLM
        reasoning = await self._call_llm(prompt)

        state["reasoning"].append(reasoning)
        state["current_step"] = "reason"

        return state

    async def _act_node(self, state: AgentState) -> AgentState:
        """
        Act: Execute tools based on reasoning

        This is where the agent takes action based on its reasoning.
        Can execute SQL, call APIs, run analyses, etc.
        """
        logger.info(f"{self.agent_name}: Acting...")

        # Extract action from last reasoning
        last_reasoning = state["reasoning"][-1] if state["reasoning"] else ""

        # Determine what action to take
        # (Override in subclasses for specific actions)

        state["current_step"] = "act"
        state["iteration"] += 1

        return state

    async def _decide_node(self, state: AgentState) -> AgentState:
        """
        Decide: Evaluate results and form conclusions
        """
        logger.info(f"{self.agent_name}: Deciding...")

        # Build decision prompt
        prompt = self._build_decision_prompt(state)

        # Call LLM
        decision = await self._call_llm(prompt)

        state["conclusion"] = decision
        state["current_step"] = "decide"

        return state

    def _should_continue(self, state: AgentState) -> str:
        """
        Decide if agent should continue iterating

        Returns:
            "continue", "iterate", or "end"
        """
        if state["iteration"] >= state["max_iterations"]:
            return "end"

        # Check if we have enough information
        if len(state["findings"]) == 0:
            return "iterate"

        return "continue"

    def _is_complete(self, state: AgentState) -> str:
        """
        Check if agent work is complete

        Returns:
            "complete" or "continue"
        """
        if state.get("conclusion"):
            return "complete"

        if state["iteration"] >= state["max_iterations"]:
            return "complete"

        return "continue"

    def _build_reasoning_prompt(self, state: AgentState) -> str:
        """
        Build prompt for reasoning step

        Override in subclasses for specific reasoning
        """
        observations_text = "\n".join(state["observations"])
        findings_text = "\n".join([str(f) for f in state["findings"]])

        return f"""You are {self.agent_name}, an expert data analyst.

Observations:
{observations_text}

Findings so far:
{findings_text}

Based on these observations and findings, what should you investigate next?
Provide a clear, concise reasoning about what to do next."""

    def _build_decision_prompt(self, state: AgentState) -> str:
        """Build prompt for decision step"""
        reasoning_text = "\n".join(state["reasoning"])
        findings_text = "\n".join([str(f) for f in state["findings"]])

        return f"""Based on your investigation:

Reasoning:
{reasoning_text}

Findings:
{findings_text}

Provide a clear conclusion and actionable recommendations."""

    async def _call_llm(self, prompt: str, temperature: float = 0.1) -> str:
        """
        Call Ollama LLM

        Args:
            prompt: Prompt text
            temperature: Sampling temperature (lower = more deterministic)

        Returns:
            LLM response
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": temperature
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                else:
                    logger.error(f"LLM API error: {response.status_code}")
                    return "Error: Could not get LLM response"

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"Error: {str(e)}"

    async def execute_sql(self, sql: str) -> List[Dict]:
        """
        Execute SQL query (tool for agents)

        Args:
            sql: SQL query

        Returns:
            Query results
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Set timeout
                await conn.execute("SET statement_timeout = '30s'")

                # Execute query
                results = await conn.fetch(sql)

                # Convert to dicts
                return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            return []

    async def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the agent workflow

        Args:
            input_data: Input data for the agent

        Returns:
            Agent results
        """
        # Initialize state
        initial_state: AgentState = {
            "input_data": input_data,
            "property": input_data.get("property", ""),
            "current_step": "start",
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "observations": [],
            "findings": [],
            "reasoning": [],
            "queries_executed": [],
            "tools_used": [],
            "conclusion": None,
            "recommendations": [],
            "confidence": 0.0,
            "agent_name": self.agent_name,
            "started_at": datetime.utcnow(),
            "completed_at": None
        }

        # Run workflow
        logger.info(f"Starting {self.agent_name} workflow...")

        try:
            final_state = await self.workflow.ainvoke(initial_state)
            final_state["completed_at"] = datetime.utcnow()

            logger.info(f"{self.agent_name} completed in {final_state['iteration']} iterations")

            return {
                "agent": self.agent_name,
                "conclusion": final_state.get("conclusion"),
                "recommendations": final_state.get("recommendations", []),
                "confidence": final_state.get("confidence", 0.0),
                "iterations": final_state["iteration"],
                "findings": final_state.get("findings", []),
                "success": True
            }

        except Exception as e:
            logger.error(f"Error in {self.agent_name} workflow: {e}")
            return {
                "agent": self.agent_name,
                "error": str(e),
                "success": False
            }

    def invoke_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.invoke(input_data))


# Tool definitions for agents
class AgentTools:
    """
    Collection of tools that agents can use
    """

    @staticmethod
    async def query_performance(
        pool: asyncpg.Pool,
        property: str,
        page_path: str = None,
        days: int = 7
    ) -> List[Dict]:
        """Query page performance data"""
        async with pool.acquire() as conn:
            if page_path:
                results = await conn.fetch("""
                    SELECT *
                    FROM gsc.vw_unified_page_performance
                    WHERE property = $1
                        AND page_path = $2
                        AND date >= CURRENT_DATE - $3
                    ORDER BY date DESC
                """, property, page_path, days)
            else:
                results = await conn.fetch("""
                    SELECT *
                    FROM gsc.vw_unified_page_performance
                    WHERE property = $1
                        AND date >= CURRENT_DATE - $2
                    ORDER BY date DESC, gsc_clicks DESC
                    LIMIT 100
                """, property, days)

            return [dict(r) for r in results]

    @staticmethod
    async def query_anomalies(
        pool: asyncpg.Pool,
        property: str,
        days: int = 7
    ) -> List[Dict]:
        """Query recent anomalies"""
        async with pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT *
                FROM intelligence.vw_recent_anomalies
                WHERE property = $1
                    AND detection_date >= CURRENT_DATE - $2
                ORDER BY detection_date DESC, severity DESC
                LIMIT 50
            """, property, days)

            return [dict(r) for r in results]

    @staticmethod
    async def query_quality(
        pool: asyncpg.Pool,
        property: str,
        min_score: float = 0
    ) -> List[Dict]:
        """Query content quality scores"""
        async with pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT *
                FROM content.vw_content_quality
                WHERE property = $1
                    AND overall_score >= $2
                ORDER BY overall_score DESC
                LIMIT 100
            """, property, min_score)

            return [dict(r) for r in results]
