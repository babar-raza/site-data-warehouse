"""Agent contract and base interface for all agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class AgentStatus(Enum):
    """Agent operational status."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class AgentHealth:
    """Agent health status information."""
    agent_id: str
    status: AgentStatus
    uptime_seconds: float
    last_heartbeat: datetime
    error_count: int
    processed_count: int
    memory_usage_mb: float
    cpu_percent: float
    metadata: Dict[str, Any]


@dataclass
class AgentMetadata:
    """Agent metadata and configuration."""
    agent_id: str
    agent_type: str
    version: str
    capabilities: list[str]
    dependencies: list[str]
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentContract(ABC):
    """Base contract that all agents must implement."""

    def __init__(self, agent_id: str, agent_type: str, config: Optional[Dict[str, Any]] = None):
        """Initialize agent with ID and type.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type/category of agent
            config: Optional configuration dictionary
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config or {}
        self._status = AgentStatus.INITIALIZED
        self._start_time: Optional[datetime] = None
        self._error_count = 0
        self._processed_count = 0

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the agent and prepare for operation.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return results.
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processing results as dictionary
        """
        pass

    @abstractmethod
    async def health_check(self) -> AgentHealth:
        """Check agent health and return status.
        
        Returns:
            AgentHealth object with current status
        """
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        """Gracefully shutdown the agent.
        
        Returns:
            True if shutdown successful, False otherwise
        """
        pass

    def get_metadata(self) -> AgentMetadata:
        """Get agent metadata.
        
        Returns:
            AgentMetadata object
        """
        return AgentMetadata(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.config.get('version', '1.0.0'),
            capabilities=self.config.get('capabilities', []),
            dependencies=self.config.get('dependencies', []),
            config=self.config,
            created_at=self._start_time or datetime.now(),
            updated_at=datetime.now()
        )

    @property
    def status(self) -> AgentStatus:
        """Get current agent status."""
        return self._status

    def _set_status(self, status: AgentStatus):
        """Set agent status."""
        self._status = status

    def _increment_error_count(self):
        """Increment error counter."""
        self._error_count += 1

    def _increment_processed_count(self):
        """Increment processed items counter."""
        self._processed_count += 1
