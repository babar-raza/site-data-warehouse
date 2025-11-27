"""
Insights API Routes Package

This package contains modular API route handlers for different endpoints.
"""

from insights_api.routes.aggregations import router as aggregations_router
from insights_api.routes.actions import router as actions_router

__all__ = ['aggregations_router', 'actions_router']
