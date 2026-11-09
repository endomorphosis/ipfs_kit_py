#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/__init__.py

"""
Routing Algorithms for Optimized Data Routing.

This module provides various routing strategies for selecting the optimal
storage backend based on different criteria such as content type, cost,
geographic location, and performance metrics.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any, Union

from ..router import (
    Backend, ContentType, OperationType, 
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)

# Import specialized routers
from .content_aware import ContentAwareRouter
from .cost_based import CostBasedRouter
from .geographic import GeographicRouter
from .performance import PerformanceRouter
from .composite import CompositeRouter

__all__ = [
    'ContentAwareRouter',
    'CostBasedRouter',
    'GeographicRouter',
    'PerformanceRouter',
    'CompositeRouter'
]