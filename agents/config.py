"""Configuration for agents system."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AgentConfig:
    """Base configuration for agents."""
    
    # Agent identification
    agent_id_prefix: str = "agent"
    agent_version: str = "1.0.0"
    
    # State management
    state_storage_path: str = "./data/agent_states"
    state_history_limit: int = 100
    state_persist_interval_seconds: int = 60
    
    # Message bus
    message_storage_path: str = "./data/messages"
    message_history_limit: int = 1000
    message_queue_max_size: int = 1000
    message_default_ttl_seconds: int = 3600
    
    # Registry
    registry_storage_path: str = "./data/registry"
    registry_heartbeat_timeout_seconds: int = 30
    registry_health_check_interval_seconds: int = 10
    
    # Performance
    max_concurrent_agents: int = 100
    agent_startup_timeout_seconds: int = 30
    agent_shutdown_timeout_seconds: int = 30
    
    # Monitoring
    metrics_enabled: bool = True
    metrics_collection_interval_seconds: int = 60
    log_level: str = "INFO"
    
    # Recovery
    auto_restart_on_failure: bool = True
    max_restart_attempts: int = 3
    restart_backoff_seconds: int = 5
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AgentConfig':
        """Create config from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            AgentConfig instance
        """
        return cls(**{
            k: v for k, v in config_dict.items()
            if k in cls.__annotations__
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary.
        
        Returns:
            Configuration dictionary
        """
        return {
            k: getattr(self, k)
            for k in self.__annotations__
        }


# Default configuration
DEFAULT_CONFIG = AgentConfig()


# Environment-specific configurations
DEVELOPMENT_CONFIG = AgentConfig(
    state_persist_interval_seconds=30,
    registry_heartbeat_timeout_seconds=60,
    log_level="DEBUG"
)

PRODUCTION_CONFIG = AgentConfig(
    max_concurrent_agents=500,
    registry_heartbeat_timeout_seconds=15,
    auto_restart_on_failure=True,
    log_level="WARNING"
)

TEST_CONFIG = AgentConfig(
    state_storage_path="./test_data/agent_states",
    message_storage_path="./test_data/messages",
    registry_storage_path="./test_data/registry",
    registry_heartbeat_timeout_seconds=5,
    registry_health_check_interval_seconds=2,
    log_level="DEBUG"
)


def get_config(environment: str = "default") -> AgentConfig:
    """Get configuration for environment.
    
    Args:
        environment: Environment name (default, development, production, test)
        
    Returns:
        AgentConfig instance
    """
    configs = {
        "default": DEFAULT_CONFIG,
        "development": DEVELOPMENT_CONFIG,
        "production": PRODUCTION_CONFIG,
        "test": TEST_CONFIG
    }
    
    return configs.get(environment.lower(), DEFAULT_CONFIG)
