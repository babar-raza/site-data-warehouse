"""
Base detector class
"""
from abc import ABC, abstractmethod
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig

logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """
    Abstract base class for all detectors
    """
    
    def __init__(self, repository: InsightRepository, config: InsightsConfig):
        """
        Initialize detector
        
        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
        """
        self.repository = repository
        self.config = config
        self.conn_string = config.warehouse_dsn
    
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.conn_string)
    
    @abstractmethod
    def detect(self, property: str = None) -> int:
        """
        Run detection logic
        
        Args:
            property: Optional property filter
            
        Returns:
            Number of insights created
        """
        pass
    
    def _get_recent_data(self, days: int = 7, property: str = None) -> list:
        """
        Helper to get recent data from unified view
        
        Args:
            days: Number of days to look back
            property: Optional property filter
            
        Returns:
            List of rows as dicts
        """
        conn = self._get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT *
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                """
                params = [days]
                
                if property:
                    query += " AND property = %s"
                    params.append(property)
                
                query += " ORDER BY date DESC"
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
