"""
Supervisor Agent - Multi-Agent Orchestration
=============================================
Coordinates specialist SEO agents using LangGraph.

Specialist Agents:
- SERP Analyst: Monitors rankings and competitors
- Performance Agent: CWV optimization
- Content Optimizer: Content improvement
- Impact Validator: ROI validation

Workflow Types:
- Daily Analysis: Automated health checks
- Emergency Response: React to sudden changes
- Optimization: Implement improvements
- Validation: Verify intervention success
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Annotated, Dict, List, Literal, TypedDict

import asyncpg
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


# =====================================================
# STATE DEFINITION
# =====================================================

class OrchestrationState(TypedDict):
    """State shared across all agents in the workflow"""
    # Input
    workflow_id: str
    workflow_type: str  # daily_analysis, emergency_response, optimization, validation
    trigger_event: Dict
    property: str
    page_path: str | None

    # Analysis results from specialist agents
    serp_analysis: Dict | None
    performance_analysis: Dict | None
    content_analysis: Dict | None
    impact_validation: Dict | None

    # Recommendations and decisions
    recommendations: List[Dict]
    priority_actions: List[Dict]

    # Execution
    actions_taken: List[Dict]
    execution_results: List[Dict]

    # State tracking
    current_step: str
    next_agent: str | None
    status: str  # running, completed, failed
    error_message: str | None


# =====================================================
# SUPERVISOR AGENT
# =====================================================

class SupervisorAgent:
    """
    Supervisor agent that coordinates specialist agents
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize supervisor agent

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: asyncpg.Pool | None = None

        # Specialist agents (will be registered)
        self.specialist_agents = {}

        logger.info("SupervisorAgent initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def register_agent(self, agent_name: str, agent):
        """Register a specialist agent"""
        self.specialist_agents[agent_name] = agent
        logger.info(f"Registered specialist agent: {agent_name}")

    # =====================================================
    # WORKFLOW ORCHESTRATION
    # =====================================================

    async def start_workflow(
        self,
        workflow_type: str,
        trigger_event: Dict,
        property: str,
        page_path: str = None,
        metadata: Dict = None
    ) -> str:
        """
        Start a new multi-agent workflow

        Args:
            workflow_type: Type of workflow
            trigger_event: Event that triggered workflow
            property: Property URL
            page_path: Page path (optional)
            metadata: Additional metadata

        Returns:
            workflow_id
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                workflow_id = await conn.fetchval("""
                    SELECT orchestration.start_workflow($1, $2, $3, $4, $5, $6)
                """,
                    f"{workflow_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    workflow_type,
                    trigger_event.get('type', 'manual'),
                    trigger_event,
                    property,
                    metadata
                )

            logger.info(f"Started workflow: {workflow_id} (type: {workflow_type})")
            return str(workflow_id)

        except Exception as e:
            logger.error(f"Error starting workflow: {e}")
            raise

    async def complete_workflow(
        self,
        workflow_id: str,
        status: str,
        result: Dict = None,
        error_message: str = None
    ):
        """Mark workflow as completed or failed"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    SELECT orchestration.complete_workflow($1, $2, $3, $4)
                """,
                    workflow_id,
                    status,
                    result,
                    error_message
                )

            logger.info(f"Workflow {workflow_id} completed with status: {status}")

        except Exception as e:
            logger.error(f"Error completing workflow: {e}")

    # =====================================================
    # DECISION MAKING
    # =====================================================

    async def analyze_situation(self, state: OrchestrationState) -> OrchestrationState:
        """
        Initial analysis to determine which agents to invoke

        Args:
            state: Current workflow state

        Returns:
            Updated state with next steps
        """
        try:
            workflow_type = state['workflow_type']
            trigger_event = state['trigger_event']

            logger.info(f"Analyzing situation for workflow: {workflow_type}")

            # Record workflow step
            step_id = await self._add_workflow_step(
                state['workflow_id'],
                'analyze_situation',
                'decision',
                'supervisor'
            )

            # Determine which agents to invoke based on workflow type
            if workflow_type == 'daily_analysis':
                # Daily health check - run all agents
                state['next_agent'] = 'serp_analyst'
                state['current_step'] = 'serp_analysis'

            elif workflow_type == 'emergency_response':
                # Emergency - prioritize based on trigger
                event_type = trigger_event.get('alert_type')

                if event_type == 'serp_drop':
                    state['next_agent'] = 'serp_analyst'
                    state['current_step'] = 'serp_analysis'
                elif event_type == 'cwv_violation':
                    state['next_agent'] = 'performance_agent'
                    state['current_step'] = 'performance_analysis'
                else:
                    state['next_agent'] = 'serp_analyst'  # Default
                    state['current_step'] = 'serp_analysis'

            elif workflow_type == 'optimization':
                # Optimization workflow - content first
                state['next_agent'] = 'content_optimizer'
                state['current_step'] = 'content_analysis'

            elif workflow_type == 'validation':
                # Validation - impact validator
                state['next_agent'] = 'impact_validator'
                state['current_step'] = 'impact_validation'

            # Complete step
            await self._complete_workflow_step(
                step_id,
                'completed',
                {'next_agent': state['next_agent']}
            )

            return state

        except Exception as e:
            logger.error(f"Error in analyze_situation: {e}")
            state['status'] = 'failed'
            state['error_message'] = str(e)
            return state

    async def make_decision(self, state: OrchestrationState) -> OrchestrationState:
        """
        Make final decision based on all agent analyses

        Args:
            state: Current workflow state

        Returns:
            Updated state with final decisions
        """
        try:
            logger.info("Making final decision based on agent analyses")

            # Record workflow step
            step_id = await self._add_workflow_step(
                state['workflow_id'],
                'make_decision',
                'decision',
                'supervisor'
            )

            # Aggregate recommendations from all agents
            all_recommendations = []

            if state.get('serp_analysis'):
                all_recommendations.extend(
                    state['serp_analysis'].get('recommendations', [])
                )

            if state.get('performance_analysis'):
                all_recommendations.extend(
                    state['performance_analysis'].get('recommendations', [])
                )

            if state.get('content_analysis'):
                all_recommendations.extend(
                    state['content_analysis'].get('recommendations', [])
                )

            # Sort by priority and confidence
            prioritized = self._prioritize_recommendations(all_recommendations)

            state['recommendations'] = all_recommendations
            state['priority_actions'] = prioritized[:5]  # Top 5 actions

            # Determine if actions should be executed automatically
            should_execute = self._should_auto_execute(state)

            if should_execute:
                state['next_agent'] = 'executor'
                state['current_step'] = 'execution'
            else:
                # Require human approval
                state['next_agent'] = None
                state['current_step'] = 'awaiting_approval'
                state['status'] = 'completed'

            # Complete step
            await self._complete_workflow_step(
                step_id,
                'completed',
                {
                    'total_recommendations': len(all_recommendations),
                    'priority_actions': len(state['priority_actions']),
                    'auto_execute': should_execute
                }
            )

            return state

        except Exception as e:
            logger.error(f"Error in make_decision: {e}")
            state['status'] = 'failed'
            state['error_message'] = str(e)
            return state

    def _prioritize_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """
        Prioritize recommendations by impact and confidence

        Args:
            recommendations: List of recommendations from agents

        Returns:
            Sorted list of recommendations
        """
        priority_scores = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }

        def score_recommendation(rec: Dict) -> float:
            priority = rec.get('priority', 'medium')
            confidence = rec.get('confidence', 0.5)
            estimated_impact = rec.get('estimated_impact', 'medium')

            priority_score = priority_scores.get(priority, 2)
            impact_score = priority_scores.get(estimated_impact, 2)

            # Combined score: priority * confidence * impact
            return priority_score * confidence * impact_score

        sorted_recs = sorted(
            recommendations,
            key=score_recommendation,
            reverse=True
        )

        return sorted_recs

    def _should_auto_execute(self, state: OrchestrationState) -> bool:
        """
        Determine if actions should be executed automatically

        Args:
            state: Current workflow state

        Returns:
            True if should auto-execute
        """
        # Auto-execute only if:
        # 1. High confidence recommendations (>0.8)
        # 2. Low-risk actions
        # 3. Emergency response workflow

        if state['workflow_type'] == 'emergency_response':
            # Emergency - auto-execute high confidence actions
            priority_actions = state.get('priority_actions', [])

            if not priority_actions:
                return False

            # Check if top action has high confidence
            top_action = priority_actions[0]
            confidence = top_action.get('confidence', 0)

            return confidence >= 0.8

        elif state['workflow_type'] == 'optimization':
            # Optimization - require approval
            return False

        else:
            # Daily analysis - auto-execute low-risk actions
            return False

    # =====================================================
    # ROUTING
    # =====================================================

    def route_to_next_agent(
        self,
        state: OrchestrationState
    ) -> Literal['serp_analyst', 'performance_agent', 'content_optimizer',
                 'impact_validator', 'decision', 'execute', 'end']:
        """
        Route to the next agent or step

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        next_agent = state.get('next_agent')

        if next_agent == 'serp_analyst':
            return 'serp_analyst'
        elif next_agent == 'performance_agent':
            return 'performance_agent'
        elif next_agent == 'content_optimizer':
            return 'content_optimizer'
        elif next_agent == 'impact_validator':
            return 'impact_validator'
        elif next_agent == 'executor':
            return 'execute'
        else:
            return 'end'

    # =====================================================
    # DATABASE HELPERS
    # =====================================================

    async def _add_workflow_step(
        self,
        workflow_id: str,
        step_name: str,
        step_type: str,
        agent_name: str,
        input_data: Dict = None
    ) -> str:
        """Add a workflow step to database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                step_id = await conn.fetchval("""
                    SELECT orchestration.add_workflow_step($1, $2, $3, $4, $5)
                """,
                    workflow_id,
                    step_name,
                    step_type,
                    agent_name,
                    input_data
                )

            return str(step_id)

        except Exception as e:
            logger.error(f"Error adding workflow step: {e}")
            raise

    async def _complete_workflow_step(
        self,
        step_id: str,
        status: str,
        output_data: Dict = None,
        error_message: str = None
    ):
        """Mark workflow step as completed"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    SELECT orchestration.complete_workflow_step($1, $2, $3, $4)
                """,
                    step_id,
                    status,
                    output_data,
                    error_message
                )

        except Exception as e:
            logger.error(f"Error completing workflow step: {e}")

    # =====================================================
    # BUILD WORKFLOW GRAPH
    # =====================================================

    def build_workflow_graph(self) -> StateGraph:
        """
        Build LangGraph workflow with all agents

        Returns:
            Compiled workflow graph
        """
        # Create graph
        workflow = StateGraph(OrchestrationState)

        # Add nodes
        workflow.add_node("analyze", self.analyze_situation)
        workflow.add_node("serp_analyst", self._call_serp_analyst)
        workflow.add_node("performance_agent", self._call_performance_agent)
        workflow.add_node("content_optimizer", self._call_content_optimizer)
        workflow.add_node("impact_validator", self._call_impact_validator)
        workflow.add_node("decision", self.make_decision)

        # Set entry point
        workflow.set_entry_point("analyze")

        # Add conditional routing from analyze
        workflow.add_conditional_edges(
            "analyze",
            self.route_to_next_agent,
            {
                'serp_analyst': 'serp_analyst',
                'performance_agent': 'performance_agent',
                'content_optimizer': 'content_optimizer',
                'impact_validator': 'impact_validator',
                'end': END
            }
        )

        # All agents route to decision
        workflow.add_edge("serp_analyst", "decision")
        workflow.add_edge("performance_agent", "decision")
        workflow.add_edge("content_optimizer", "decision")
        workflow.add_edge("impact_validator", "decision")

        # Decision routes to end
        workflow.add_edge("decision", END)

        # Compile
        return workflow.compile()

    async def _call_serp_analyst(self, state: OrchestrationState) -> OrchestrationState:
        """Call SERP analyst agent"""
        agent = self.specialist_agents.get('serp_analyst')
        if agent:
            analysis = await agent.analyze(state)
            state['serp_analysis'] = analysis
        else:
            logger.warning("SERP analyst not registered")
        return state

    async def _call_performance_agent(self, state: OrchestrationState) -> OrchestrationState:
        """Call performance agent"""
        agent = self.specialist_agents.get('performance_agent')
        if agent:
            analysis = await agent.analyze(state)
            state['performance_analysis'] = analysis
        else:
            logger.warning("Performance agent not registered")
        return state

    async def _call_content_optimizer(self, state: OrchestrationState) -> OrchestrationState:
        """Call content optimizer agent"""
        agent = self.specialist_agents.get('content_optimizer')
        if agent:
            analysis = await agent.analyze(state)
            state['content_analysis'] = analysis
        else:
            logger.warning("Content optimizer not registered")
        return state

    async def _call_impact_validator(self, state: OrchestrationState) -> OrchestrationState:
        """Call impact validator agent"""
        agent = self.specialist_agents.get('impact_validator')
        if agent:
            analysis = await agent.analyze(state)
            state['impact_validation'] = analysis
        else:
            logger.warning("Impact validator not registered")
        return state

    # =====================================================
    # RUN WORKFLOW
    # =====================================================

    async def run_workflow(
        self,
        workflow_type: str,
        trigger_event: Dict,
        property: str,
        page_path: str = None,
        metadata: Dict = None
    ) -> Dict:
        """
        Run a complete multi-agent workflow

        Args:
            workflow_type: Type of workflow
            trigger_event: Triggering event
            property: Property URL
            page_path: Page path (optional)
            metadata: Additional metadata

        Returns:
            Workflow result
        """
        try:
            # Start workflow
            workflow_id = await self.start_workflow(
                workflow_type,
                trigger_event,
                property,
                page_path,
                metadata
            )

            # Initialize state
            initial_state: OrchestrationState = {
                'workflow_id': workflow_id,
                'workflow_type': workflow_type,
                'trigger_event': trigger_event,
                'property': property,
                'page_path': page_path,
                'serp_analysis': None,
                'performance_analysis': None,
                'content_analysis': None,
                'impact_validation': None,
                'recommendations': [],
                'priority_actions': [],
                'actions_taken': [],
                'execution_results': [],
                'current_step': 'analyze',
                'next_agent': None,
                'status': 'running',
                'error_message': None
            }

            # Build and run workflow graph
            graph = self.build_workflow_graph()
            final_state = await graph.ainvoke(initial_state)

            # Complete workflow
            await self.complete_workflow(
                workflow_id,
                final_state['status'],
                {
                    'recommendations': final_state.get('recommendations', []),
                    'priority_actions': final_state.get('priority_actions', []),
                    'actions_taken': final_state.get('actions_taken', [])
                },
                final_state.get('error_message')
            )

            return {
                'success': final_state['status'] == 'completed',
                'workflow_id': workflow_id,
                'recommendations': final_state.get('recommendations', []),
                'priority_actions': final_state.get('priority_actions', []),
                'status': final_state['status']
            }

        except Exception as e:
            logger.error(f"Error running workflow: {e}")
            return {
                'success': False,
                'error': str(e)
            }


__all__ = ['SupervisorAgent', 'OrchestrationState']
