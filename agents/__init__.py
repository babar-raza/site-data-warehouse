"""Agent infrastructure package."""

from agents.base.agent_contract import (
    AgentContract,
    AgentHealth,
    AgentMetadata,
    AgentStatus,
)
from agents.base.agent_registry import AgentRegistry, AgentRegistration
from agents.base.message_bus import Message, MessageBus
from agents.base.state_manager import AgentState, StateManager, StateSnapshot
from agents.config import AgentConfig, get_config

__version__ = "1.0.0"

__all__ = [
    # Contract
    "AgentContract",
    "AgentHealth",
    "AgentMetadata",
    "AgentStatus",
    # Registry
    "AgentRegistry",
    "AgentRegistration",
    # Message Bus
    "Message",
    "MessageBus",
    # State Manager
    "AgentState",
    "StateManager",
    "StateSnapshot",
    # Config
    "AgentConfig",
    "get_config",
]
