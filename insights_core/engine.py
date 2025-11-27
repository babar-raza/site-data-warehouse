"""
Insight Engine - Orchestrates all detectors
"""
import logging
from typing import List
from datetime import datetime

from insights_core.models import Insight
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
from insights_core.detectors import (
    AnomalyDetector,
    CannibalizationDetector,
    ContentQualityDetector,
    CWVQualityDetector,
    DiagnosisDetector,
    OpportunityDetector,
    TopicStrategyDetector,
    TrendDetector,
)

logger = logging.getLogger(__name__)


class InsightEngine:
    """
    Main orchestration engine for insight detection

    Runs detectors in sequence:
    1. AnomalyDetector - finds traffic anomalies
    2. CannibalizationDetector - detects keyword cannibalization issues
    3. ContentQualityDetector - detects content quality issues
    4. CWVQualityDetector - detects Core Web Vitals performance issues
    5. DiagnosisDetector - diagnoses existing risks
    6. OpportunityDetector - finds optimization opportunities
    7. TopicStrategyDetector - analyzes topic coverage and cannibalization
    8. TrendDetector - identifies gradual traffic trends
    """
    
    def __init__(self, config: InsightsConfig = None):
        """
        Initialize engine with configuration
        
        Args:
            config: InsightsConfig instance (creates default if None)
        """
        self.config = config or InsightsConfig()
        self.repository = InsightRepository(self.config.warehouse_dsn)
        
        # Initialize detectors
        self.detectors = [
            AnomalyDetector(self.repository, self.config),
            CannibalizationDetector(self.repository, self.config),
            ContentQualityDetector(self.repository, self.config),
            CWVQualityDetector(self.repository, self.config),
            DiagnosisDetector(self.repository, self.config),
            OpportunityDetector(self.repository, self.config),
            TopicStrategyDetector(self.repository, self.config),
            TrendDetector(self.repository, self.config),
        ]
        
        logger.info(f"InsightEngine initialized with {len(self.detectors)} detectors")
    
    def refresh(self, property: str = None, generate_actions: bool = True) -> dict:
        """
        Run all detectors and return statistics

        Args:
            property: Optional property filter (None = all properties)
            generate_actions: Whether to auto-generate actions from insights (default: True)

        Returns:
            Dict with execution stats
        """
        start_time = datetime.utcnow()
        logger.info("=" * 60)
        logger.info("Starting Insight Engine refresh")
        if property:
            logger.info(f"Property filter: {property}")
        logger.info(f"Action generation: {'enabled' if generate_actions else 'disabled'}")
        logger.info("=" * 60)

        stats = {
            'start_time': start_time.isoformat(),
            'property_filter': property,
            'detectors_run': 0,
            'detectors_succeeded': 0,
            'detectors_failed': 0,
            'total_insights_created': 0,
            'insights_by_detector': {},
            'errors': []
        }

        for detector in self.detectors:
            detector_name = detector.__class__.__name__
            logger.info(f"\n--- Running {detector_name} ---")

            try:
                insights_created = detector.detect(property=property)
                stats['detectors_run'] += 1
                stats['detectors_succeeded'] += 1
                stats['total_insights_created'] += insights_created
                stats['insights_by_detector'][detector_name] = insights_created

                logger.info(f"{detector_name} created {insights_created} insights")

            except Exception as e:
                stats['detectors_run'] += 1
                stats['detectors_failed'] += 1
                stats['insights_by_detector'][detector_name] = 0
                stats['errors'].append({
                    'detector': detector_name,
                    'error': str(e)
                })
                logger.error(f"{detector_name} failed: {e}", exc_info=True)

        # Generate actions if enabled and insights were created
        if generate_actions and stats['total_insights_created'] > 0:
            logger.info("\n--- Generating Actions ---")
            action_start_time = datetime.utcnow()

            try:
                from services.action_generator import ActionGenerator

                action_gen = ActionGenerator(db_dsn=self.config.warehouse_dsn)

                # Generate actions for the property (or all properties if None)
                # Limit to 100 to avoid overwhelming the system
                action_limit = 100
                if property:
                    actions = action_gen.generate_batch(property, limit=action_limit)
                    stats['actions_generated'] = len(actions)
                else:
                    # If no property specified, skip action generation to avoid processing too much
                    logger.info("Skipping action generation for all-property refresh (specify property to generate actions)")
                    stats['actions_generated'] = 0
                    stats['action_skipped'] = True

                action_duration = (datetime.utcnow() - action_start_time).total_seconds()
                stats['action_duration_seconds'] = action_duration

                if stats.get('actions_generated', 0) > 0:
                    logger.info(f"Generated {stats['actions_generated']} actions in {action_duration:.2f}s")

            except Exception as e:
                # Don't fail the entire refresh if action generation fails
                logger.error(f"Action generation failed: {e}", exc_info=True)
                stats['actions_generated'] = 0
                stats['action_error'] = str(e)
        else:
            stats['actions_generated'] = 0
            if not generate_actions:
                logger.info("Action generation disabled")
            elif stats['total_insights_created'] == 0:
                logger.info("No insights created, skipping action generation")

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        stats['end_time'] = end_time.isoformat()
        stats['duration_seconds'] = duration

        logger.info("=" * 60)
        logger.info(f"Insight Engine completed in {duration:.2f}s")
        logger.info(f"Total insights created: {stats['total_insights_created']}")
        logger.info(f"Detectors succeeded: {stats['detectors_succeeded']}/{stats['detectors_run']}")
        if generate_actions and 'actions_generated' in stats:
            logger.info(f"Actions generated: {stats['actions_generated']}")
        logger.info("=" * 60)

        return stats
    
    def get_detector_stats(self) -> dict:
        """Get statistics about available detectors"""
        return {
            'total_detectors': len(self.detectors),
            'detectors': [
                {
                    'name': d.__class__.__name__,
                    'type': d.__class__.__name__.replace('Detector', '').lower()
                }
                for d in self.detectors
            ]
        }
