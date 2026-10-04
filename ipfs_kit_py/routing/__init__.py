"""
IPFS Kit Optimized Data Routing Module

This module provides optimized data routing capabilities for efficient content placement,
retrieval, and management across multiple storage backends.

Core features:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization 
- Bandwidth and latency analysis
- Metrics collection and analysis
- Dashboard for monitoring and managing routing

This module can be used independently or integrated with the MCP server.
"""

from .router import DataRouter as Router  # Alias DataRouter as Router for backward compatibility
from .routing_manager import RoutingManager, RoutingManagerSettings
from .data_router import DataRouter, RoutingPriority
from .optimized_router import OptimizedRouter, RoutingStrategy, ContentCategory

__all__ = [
    'Router',
    'RoutingManager', 
    'RoutingManagerSettings',
    'DataRouter',
    'RoutingPriority',
    'OptimizedRouter',
    'RoutingStrategy',
    'ContentCategory',
]