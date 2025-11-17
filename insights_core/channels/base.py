"""
Base channel interface for dispatching insights
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Result of a dispatch attempt"""
    success: bool
    channel: str
    insight_id: str
    timestamp: datetime
    error: Optional[str] = None
    retry_count: int = 0
    response: Optional[Dict[str, Any]] = None


class Channel(ABC):
    """Base class for all dispatch channels"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize channel with configuration
        
        Args:
            config: Channel-specific configuration
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.dry_run = config.get('dry_run', False)
        self.rate_limit = config.get('rate_limit', 10)  # requests per minute
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def send(self, insight: Any, **kwargs) -> DispatchResult:
        """
        Send insight to this channel
        
        Args:
            insight: Insight object to dispatch
            **kwargs: Additional channel-specific parameters
            
        Returns:
            DispatchResult with success status and details
        """
        pass
    
    @abstractmethod
    def format_message(self, insight: Any) -> Dict[str, Any]:
        """
        Format insight into channel-specific message format
        
        Args:
            insight: Insight object
            
        Returns:
            Formatted message dict
        """
        pass
    
    def validate_config(self) -> bool:
        """
        Validate channel configuration
        
        Returns:
            True if config is valid
        """
        return self.enabled
    
    def __repr__(self):
        return f"{self.__class__.__name__}(enabled={self.enabled})"
