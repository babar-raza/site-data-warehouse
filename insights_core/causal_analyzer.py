"""
Causal Impact Analysis Module
==============================
Measure causal effect of interventions using Bayesian structural time series.

Uses CausalImpact library to determine if changes in traffic are truly
caused by interventions (content updates, technical fixes, etc.) or just
coincidental fluctuations.
"""
import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import asyncpg
import pandas as pd
from causalimpact import CausalImpact

logger = logging.getLogger(__name__)


class CausalAnalyzer:
    """
    Analyze causal impact of interventions

    Uses Bayesian structural time series to measure the causal effect
    of changes (interventions) on metrics like traffic, rankings, etc.
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize causal analyzer

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("CausalAnalyzer initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def fetch_time_series_data(
        self,
        property: str,
        page_path: Optional[str],
        metric: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """
        Fetch time series data for analysis

        Args:
            property: Property URL
            page_path: Page path (None for property-wide)
            metric: Metric to analyze (clicks, impressions, position, etc.)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with date index and metric values
        """
        try:
            pool = await self.get_pool()

            # Map metric names to column names
            metric_mapping = {
                'clicks': 'gsc_clicks',
                'impressions': 'gsc_impressions',
                'position': 'gsc_position',
                'ctr': 'gsc_ctr'
            }

            metric_column = metric_mapping.get(metric, metric)

            # Build query
            if page_path:
                query = f"""
                    SELECT
                        date,
                        {metric_column} as value
                    FROM gsc.vw_unified_page_performance
                    WHERE property = $1
                        AND page_path = $2
                        AND date >= $3
                        AND date <= $4
                    ORDER BY date
                """
                params = [property, page_path, start_date, end_date]
            else:
                # Property-wide aggregation
                query = f"""
                    SELECT
                        date,
                        SUM({metric_column}) as value
                    FROM gsc.vw_unified_page_performance
                    WHERE property = $1
                        AND date >= $2
                        AND date <= $3
                    GROUP BY date
                    ORDER BY date
                """
                params = [property, start_date, end_date]

            async with pool.acquire() as conn:
                results = await conn.fetch(query, *params)

            # Convert to DataFrame
            df = pd.DataFrame([dict(r) for r in results])

            if df.empty:
                logger.warning(f"No data found for {property}{page_path or ''} ({metric})")
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Fill missing dates with 0 or previous value
            df = df.asfreq('D', fill_value=0)

            logger.info(f"Fetched {len(df)} days of data for {metric}")
            return df

        except Exception as e:
            logger.error(f"Error fetching time series data: {e}")
            raise

    async def analyze_intervention(
        self,
        intervention_id: str,
        metric: str = 'clicks',
        pre_period_days: int = 30,
        post_period_days: int = 30,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Analyze causal impact of an intervention

        Args:
            intervention_id: Intervention UUID
            metric: Metric to analyze
            pre_period_days: Days before intervention for baseline
            post_period_days: Days after intervention to measure effect
            confidence_level: Confidence level for intervals (default 0.95)

        Returns:
            Analysis results
        """
        try:
            pool = await self.get_pool()

            # Get intervention details
            async with pool.acquire() as conn:
                intervention = await conn.fetchrow("""
                    SELECT *
                    FROM analytics.interventions
                    WHERE intervention_id = $1
                """, intervention_id)

            if not intervention:
                raise ValueError(f"Intervention {intervention_id} not found")

            property = intervention['property']
            page_path = intervention['page_path']
            intervention_date = intervention['intervention_date']

            # Define periods
            pre_start = intervention_date - timedelta(days=pre_period_days)
            pre_end = intervention_date - timedelta(days=1)
            post_start = intervention_date
            post_end = intervention_date + timedelta(days=post_period_days)

            # Fetch data
            df = await self.fetch_time_series_data(
                property,
                page_path,
                metric,
                pre_start,
                post_end
            )

            if df.empty or len(df) < pre_period_days + 5:
                logger.error("Insufficient data for causal impact analysis")
                return {
                    'success': False,
                    'error': 'insufficient_data',
                    'message': f'Need at least {pre_period_days + 5} days of data'
                }

            # Define pre and post periods for CausalImpact
            pre_period = [df.index.min(), pd.Timestamp(pre_end)]
            post_period = [pd.Timestamp(post_start), df.index.max()]

            # Run causal impact analysis
            logger.info(f"Running causal impact analysis for intervention {intervention_id}")

            ci = CausalImpact(
                df,
                pre_period,
                post_period,
                alpha=1 - confidence_level
            )

            # Extract results
            summary = ci.summary_data
            summary_stats = ci.summary()

            # Parse summary statistics
            absolute_effect = float(summary.loc['average', 'abs_effect'])
            absolute_effect_lower = float(summary.loc['average', 'abs_effect_lower'])
            absolute_effect_upper = float(summary.loc['average', 'abs_effect_upper'])

            relative_effect = float(summary.loc['average', 'rel_effect'])
            relative_effect_lower = float(summary.loc['average', 'rel_effect_lower'])
            relative_effect_upper = float(summary.loc['average', 'rel_effect_upper'])

            p_value = float(summary.loc['average', 'p'])

            is_significant = p_value < (1 - confidence_level)

            # Get point predictions
            point_predictions = ci.inferences.to_dict('records')

            # Calculate cumulative impact
            cumulative = ci.inferences['cum_effect'].to_dict()

            # Store results
            await self.store_causal_impact(
                intervention_id=intervention_id,
                metric=metric,
                pre_period_start=pre_start,
                pre_period_end=pre_end,
                post_period_start=post_start,
                post_period_end=post_end,
                absolute_effect=absolute_effect,
                relative_effect=relative_effect,
                p_value=p_value,
                is_significant=is_significant,
                confidence_level=confidence_level,
                absolute_effect_lower=absolute_effect_lower,
                absolute_effect_upper=absolute_effect_upper,
                relative_effect_lower=relative_effect_lower,
                relative_effect_upper=relative_effect_upper,
                summary_data=summary.to_dict(),
                point_predictions=point_predictions,
                cumulative_impact=cumulative
            )

            logger.info(
                f"Analysis complete: {metric} "
                f"effect={absolute_effect:.2f} "
                f"({relative_effect:.1%}), "
                f"p={p_value:.4f}, "
                f"significant={is_significant}"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'metric': metric,
                'absolute_effect': absolute_effect,
                'relative_effect': relative_effect,
                'p_value': p_value,
                'is_significant': is_significant,
                'confidence_level': confidence_level,
                'confidence_interval': [absolute_effect_lower, absolute_effect_upper],
                'summary': summary_stats,
                'interpretation': self._interpret_results(
                    absolute_effect,
                    relative_effect,
                    p_value,
                    is_significant,
                    metric
                )
            }

        except Exception as e:
            logger.error(f"Error in causal impact analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _interpret_results(
        self,
        absolute_effect: float,
        relative_effect: float,
        p_value: float,
        is_significant: bool,
        metric: str
    ) -> str:
        """Generate human-readable interpretation"""
        if not is_significant:
            return (
                f"The intervention did not have a statistically significant effect on {metric}. "
                f"The observed change ({absolute_effect:+.1f}, {relative_effect:+.1%}) "
                f"could be due to random variation (p={p_value:.3f})."
            )

        direction = "increased" if absolute_effect > 0 else "decreased"
        magnitude = "significantly" if abs(relative_effect) > 0.2 else "moderately"

        return (
            f"The intervention {magnitude} {direction} {metric} by "
            f"{abs(absolute_effect):.1f} ({abs(relative_effect):.1%}). "
            f"This effect is statistically significant (p={p_value:.3f}), "
            f"indicating it is very likely caused by the intervention rather than chance."
        )

    async def store_causal_impact(
        self,
        intervention_id: str,
        metric: str,
        pre_period_start: date,
        pre_period_end: date,
        post_period_start: date,
        post_period_end: date,
        absolute_effect: float,
        relative_effect: float,
        p_value: float,
        is_significant: bool,
        confidence_level: float,
        absolute_effect_lower: float,
        absolute_effect_upper: float,
        relative_effect_lower: float,
        relative_effect_upper: float,
        summary_data: Dict,
        point_predictions: List[Dict],
        cumulative_impact: Dict
    ):
        """Store causal impact results in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO analytics.causal_impact (
                        intervention_id,
                        metric,
                        pre_period_start,
                        pre_period_end,
                        post_period_start,
                        post_period_end,
                        absolute_effect,
                        relative_effect,
                        p_value,
                        is_significant,
                        confidence_level,
                        absolute_effect_lower,
                        absolute_effect_upper,
                        relative_effect_lower,
                        relative_effect_upper,
                        summary_data,
                        point_predictions,
                        cumulative_impact,
                        model_type
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19
                    )
                """,
                    intervention_id,
                    metric,
                    pre_period_start,
                    pre_period_end,
                    post_period_start,
                    post_period_end,
                    absolute_effect,
                    relative_effect,
                    p_value,
                    is_significant,
                    confidence_level,
                    absolute_effect_lower,
                    absolute_effect_upper,
                    relative_effect_lower,
                    relative_effect_upper,
                    summary_data,
                    point_predictions,
                    cumulative_impact,
                    'bayesian_structural'
                )

            logger.info(f"Stored causal impact for intervention {intervention_id}")

        except Exception as e:
            logger.error(f"Error storing causal impact: {e}")
            raise

    async def create_intervention(
        self,
        property: str,
        intervention_type: str,
        intervention_date: date,
        description: str,
        page_path: Optional[str] = None,
        related_action_id: Optional[str] = None,
        related_pr_url: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Create a new intervention record

        Args:
            property: Property URL
            intervention_type: Type of intervention
            intervention_date: Date of intervention
            description: Description of what changed
            page_path: Affected page (optional)
            related_action_id: Related action UUID (optional)
            related_pr_url: Related PR URL (optional)
            tags: Tags for categorization (optional)

        Returns:
            Intervention UUID
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                intervention_id = await conn.fetchval("""
                    INSERT INTO analytics.interventions (
                        property,
                        page_path,
                        intervention_type,
                        intervention_date,
                        description,
                        related_action_id,
                        related_pr_url,
                        tags
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING intervention_id
                """,
                    property,
                    page_path,
                    intervention_type,
                    intervention_date,
                    description,
                    related_action_id,
                    related_pr_url,
                    tags or []
                )

            logger.info(f"Created intervention {intervention_id}")
            return str(intervention_id)

        except Exception as e:
            logger.error(f"Error creating intervention: {e}")
            raise

    async def analyze_all_interventions(
        self,
        property: str = None,
        metrics: List[str] = None,
        days_back: int = 90
    ) -> Dict:
        """
        Analyze all recent interventions

        Args:
            property: Filter by property (optional)
            metrics: Metrics to analyze (default: ['clicks'])
            days_back: Only analyze interventions from last N days

        Returns:
            Summary of analyses
        """
        if metrics is None:
            metrics = ['clicks']

        try:
            pool = await self.get_pool()

            # Get interventions to analyze
            query = """
                SELECT intervention_id
                FROM analytics.interventions
                WHERE intervention_date >= CURRENT_DATE - $1
            """
            params = [days_back]

            if property:
                query += " AND property = $2"
                params.append(property)

            query += " ORDER BY intervention_date DESC"

            async with pool.acquire() as conn:
                interventions = await conn.fetch(query, *params)

            results = []
            success_count = 0
            error_count = 0

            for intervention in interventions:
                intervention_id = str(intervention['intervention_id'])

                for metric in metrics:
                    result = await self.analyze_intervention(
                        intervention_id,
                        metric=metric
                    )

                    results.append(result)

                    if result.get('success'):
                        success_count += 1
                    else:
                        error_count += 1

            logger.info(
                f"Analyzed {len(interventions)} interventions: "
                f"{success_count} successful, {error_count} errors"
            )

            return {
                'interventions_analyzed': len(interventions),
                'analyses_run': len(results),
                'success_count': success_count,
                'error_count': error_count,
                'results': results
            }

        except Exception as e:
            logger.error(f"Error analyzing interventions: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def analyze_intervention_sync(
        self,
        intervention_id: str,
        metric: str = 'clicks'
    ) -> Dict:
        """Synchronous wrapper for Celery"""
        return asyncio.run(self.analyze_intervention(intervention_id, metric))

    async def get_intervention_summary(
        self,
        property: str,
        days_back: int = 365
    ) -> Dict:
        """
        Get summary of intervention performance

        Args:
            property: Property URL
            days_back: Days to look back

        Returns:
            Summary statistics
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Get overall stats
                stats = await conn.fetchrow("""
                    SELECT *
                    FROM analytics.calculate_success_rate($1, $2)
                """, property, days_back)

                # Get by intervention type
                by_type = await conn.fetch("""
                    SELECT *
                    FROM analytics.vw_intervention_roi
                """)

                # Get top performers
                top = await conn.fetch("""
                    SELECT *
                    FROM analytics.vw_top_interventions
                    WHERE property = $1
                    LIMIT 10
                """, property)

            return {
                'total_interventions': stats['total_interventions'],
                'analyzed': stats['analyzed_interventions'],
                'significant': stats['significant_interventions'],
                'success_rate': stats['success_rate'],
                'by_type': [dict(r) for r in by_type],
                'top_interventions': [dict(r) for r in top]
            }

        except Exception as e:
            logger.error(f"Error getting intervention summary: {e}")
            return {}

    async def get_recent_significant_impacts(
        self,
        property: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get recent significant impacts"""
        try:
            pool = await self.get_pool()

            query = """
                SELECT *
                FROM analytics.vw_significant_impacts
            """

            if property:
                query += " WHERE property = $1"

            query += f" LIMIT {limit}"

            async with pool.acquire() as conn:
                if property:
                    results = await conn.fetch(query, property)
                else:
                    results = await conn.fetch(query)

            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"Error getting significant impacts: {e}")
            return []


__all__ = ['CausalAnalyzer']
