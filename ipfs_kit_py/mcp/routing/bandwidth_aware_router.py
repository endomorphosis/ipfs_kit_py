"""
Bandwidth-Aware Router Module

This module enhances the base data router with network-aware decision making capabilities:
- Bandwidth measurement and optimization
- Latency-based routing decisions
- Network congestion detection and avoidance
- Dynamic adjustments based on current network conditions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
import threading
import json
import random

from .data_router import (
    DataRouter, RoutingStrategy, RoutingPriority, ContentCategory, BackendMetrics
)

# Configure logging
logger = logging.getLogger(__name__)


class NetworkQuality(Enum):
    """Network quality classifications."""
    EXCELLENT = "excellent"  # High bandwidth, low latency, reliable
    GOOD = "good"            # Decent bandwidth, acceptable latency
    FAIR = "fair"            # Limited bandwidth or higher latency
    POOR = "poor"            # Low bandwidth or high latency
    UNUSABLE = "unusable"    # Extremely limited or unreliable connection


class NetworkMetrics:
    """Network performance metrics for a backend connection."""
    
    def __init__(
        self,
        backend_name: str,
        latency_ms: float = 0.0,
        bandwidth_mbps: float = 0.0,
        packet_loss_percent: float = 0.0,
        jitter_ms: float = 0.0,
        last_updated: Optional[datetime] = None
    ):
        """
        Initialize network metrics.
        
        Args:
            backend_name: Name of the backend
            latency_ms: Average latency in milliseconds
            bandwidth_mbps: Available bandwidth in Mbps
            packet_loss_percent: Packet loss percentage
            jitter_ms: Jitter in milliseconds
            last_updated: Timestamp of last update
        """
        self.backend_name = backend_name
        self.latency_ms = latency_ms
        self.bandwidth_mbps = bandwidth_mbps
        self.packet_loss_percent = packet_loss_percent
        self.jitter_ms = jitter_ms
        self.last_updated = last_updated or datetime.now()
        self.history = []  # Store historical measurements
        self.max_history_size = 20  # Limit history size
    
    def update(
        self,
        latency_ms: Optional[float] = None,
        bandwidth_mbps: Optional[float] = None,
        packet_loss_percent: Optional[float] = None,
        jitter_ms: Optional[float] = None
    ) -> None:
        """
        Update network metrics with new measurements.
        
        Args:
            latency_ms: New latency measurement
            bandwidth_mbps: New bandwidth measurement
            packet_loss_percent: New packet loss measurement
            jitter_ms: New jitter measurement
        """
        # Archive current values
        self.history.append({
            "timestamp": self.last_updated,
            "latency_ms": self.latency_ms,
            "bandwidth_mbps": self.bandwidth_mbps,
            "packet_loss_percent": self.packet_loss_percent,
            "jitter_ms": self.jitter_ms
        })
        
        # Limit history size
        if len(self.history) > self.max_history_size:
            self.history = self.history[-self.max_history_size:]
        
        # Update with new values
        if latency_ms is not None:
            self.latency_ms = latency_ms
        if bandwidth_mbps is not None:
            self.bandwidth_mbps = bandwidth_mbps
        if packet_loss_percent is not None:
            self.packet_loss_percent = packet_loss_percent
        if jitter_ms is not None:
            self.jitter_ms = jitter_ms
        
        # Update timestamp
        self.last_updated = datetime.now()
    
    def get_network_quality(self) -> NetworkQuality:
        """
        Get the overall network quality classification.
        
        Returns:
            NetworkQuality enum value
        """
        # Simple classification algorithm
        if (self.bandwidth_mbps >= 50 and 
            self.latency_ms <= 50 and 
            self.packet_loss_percent <= 0.1):
            return NetworkQuality.EXCELLENT
        
        elif (self.bandwidth_mbps >= 20 and 
              self.latency_ms <= 100 and 
              self.packet_loss_percent <= 1):
            return NetworkQuality.GOOD
        
        elif (self.bandwidth_mbps >= 5 and 
              self.latency_ms <= 200 and 
              self.packet_loss_percent <= 3):
            return NetworkQuality.FAIR
        
        elif (self.bandwidth_mbps >= 1 and 
              self.latency_ms <= 500 and 
              self.packet_loss_percent <= 10):
            return NetworkQuality.POOR
        
        else:
            return NetworkQuality.UNUSABLE
    
    def get_transfer_time_estimate(self, size_bytes: int) -> float:
        """
        Estimate time to transfer content of a given size.
        
        Args:
            size_bytes: Size of content in bytes
            
        Returns:
            Estimated transfer time in seconds
        """
        if self.bandwidth_mbps <= 0:
            return float('inf')  # Can't estimate with zero bandwidth
        
        # Convert bytes to bits
        size_bits = size_bytes * 8
        
        # Convert Mbps to bps
        bandwidth_bps = self.bandwidth_mbps * 1_000_000
        
        # Calculate transfer time in seconds
        transfer_time = size_bits / bandwidth_bps
        
        # Account for latency and packet loss
        # (Simplified model - real protocols have more complex behavior)
        packet_loss_factor = 1 + (self.packet_loss_percent / 100)
        latency_factor = 1 + (self.latency_ms / 1000)
        
        return transfer_time * packet_loss_factor * latency_factor
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to a dictionary.
        
        Returns:
            Dictionary representation of network metrics
        """
        return {
            "backend_name": self.backend_name,
            "latency_ms": self.latency_ms,
            "bandwidth_mbps": self.bandwidth_mbps,
            "packet_loss_percent": self.packet_loss_percent,
            "jitter_ms": self.jitter_ms,
            "last_updated": self.last_updated.isoformat(),
            "network_quality": self.get_network_quality().value
        }


class NetworkAwareRouter:
    """
    Enhanced router with network awareness capabilities.
    
    This class wraps a base data router and enhances it with network-aware
    decision making, considering bandwidth, latency, and other network metrics.
    """
    
    def __init__(
        self,
        base_router: DataRouter,
        measurement_interval_seconds: int = 300
    ):
        """
        Initialize the network-aware router.
        
        Args:
            base_router: Base data router instance to enhance
            measurement_interval_seconds: Interval for network measurements
        """
        self.base_router = base_router
        self.measurement_interval = measurement_interval_seconds
        
        # Network metrics for each backend
        self.network_metrics: Dict[str, NetworkMetrics] = {}
        
        # Initialize metrics for known backends
        if hasattr(base_router, 'backends'):
            for backend_name in base_router.backends:
                self.network_metrics[backend_name] = NetworkMetrics(backend_name)
        
        # Update thread for periodic network measurements
        self._measurement_thread = None
        self._stop_measurement = threading.Event()
    
    def start_measurements(self) -> None:
        """Start periodic network measurements."""
        if self._measurement_thread is not None:
            logger.warning("Network measurements already running")
            return
        
        self._stop_measurement.clear()
        self._measurement_thread = threading.Thread(
            target=self._measurement_loop,
            daemon=True
        )
        self._measurement_thread.start()
        logger.info("Started periodic network measurements")
    
    def stop_measurements(self) -> None:
        """Stop periodic network measurements."""
        if self._measurement_thread is None:
            logger.warning("Network measurements not running")
            return
        
        self._stop_measurement.set()
        self._measurement_thread.join(timeout=5)
        self._measurement_thread = None
        logger.info("Stopped periodic network measurements")
    
    def _measurement_loop(self) -> None:
        """Background thread for periodic network measurements."""
        while not self._stop_measurement.is_set():
            try:
                # Perform measurements for all backends
                for backend_name in self.network_metrics:
                    try:
                        # Simulate measurement for now
                        # In a real implementation, this would measure actual network performance
                        self._simulate_measurement(backend_name)
                    except Exception as e:
                        logger.error(f"Error measuring network for backend '{backend_name}': {e}")
            except Exception as e:
                logger.error(f"Error in network measurement loop: {e}")
            
            # Sleep until next measurement interval
            self._stop_measurement.wait(self.measurement_interval)
    
    def _simulate_measurement(self, backend_name: str) -> None:
        """
        Simulate a network measurement for testing.
        
        In a real implementation, this would be replaced with actual network
        performance measurements to each backend.
        
        Args:
            backend_name: Name of the backend to measure
        """
        # Get existing metrics
        metrics = self.network_metrics.get(backend_name)
        if metrics is None:
            metrics = NetworkMetrics(backend_name)
            self.network_metrics[backend_name] = metrics
        
        # Simulate measurements based on backend type
        if backend_name == "ipfs":
            # IPFS typically has lower latency for local nodes but variable bandwidth
            latency = random.uniform(5, 50)  # 5-50ms
            bandwidth = random.uniform(20, 100)  # 20-100 Mbps
        elif backend_name == "filecoin":
            # Filecoin typically has higher latency but decent bandwidth
            latency = random.uniform(100, 300)  # 100-300ms
            bandwidth = random.uniform(10, 50)  # 10-50 Mbps
        elif backend_name == "s3":
            # S3 typically has low latency and high bandwidth
            latency = random.uniform(20, 80)  # 20-80ms
            bandwidth = random.uniform(50, 200)  # 50-200 Mbps
        elif backend_name == "storacha":
            # Assuming Storacha has medium latency and bandwidth
            latency = random.uniform(50, 150)  # 50-150ms
            bandwidth = random.uniform(30, 80)  # 30-80 Mbps
        else:
            # Default values for unknown backends
            latency = random.uniform(50, 200)  # 50-200ms
            bandwidth = random.uniform(10, 50)  # 10-50 Mbps
        
        # Add some random packet loss and jitter
        packet_loss = random.uniform(0, 2)  # 0-2%
        jitter = random.uniform(1, 15)  # 1-15ms
        
        # Update metrics
        metrics.update(
            latency_ms=latency,
            bandwidth_mbps=bandwidth,
            packet_loss_percent=packet_loss,
            jitter_ms=jitter
        )
        
        logger.debug(f"Simulated network measurement for {backend_name}: {metrics.to_dict()}")
    
    def update_network_metrics(
        self,
        backend_name: str,
        latency_ms: Optional[float] = None,
        bandwidth_mbps: Optional[float] = None,
        packet_loss_percent: Optional[float] = None,
        jitter_ms: Optional[float] = None
    ) -> None:
        """
        Update network metrics for a backend.
        
        Args:
            backend_name: Name of the backend
            latency_ms: Measured latency in milliseconds
            bandwidth_mbps: Measured bandwidth in Mbps
            packet_loss_percent: Measured packet loss percentage
            jitter_ms: Measured jitter in milliseconds
        """
        # Get or create metrics for backend
        metrics = self.network_metrics.get(backend_name)
        if metrics is None:
            metrics = NetworkMetrics(backend_name)
            self.network_metrics[backend_name] = metrics
        
        # Update metrics
        metrics.update(
            latency_ms=latency_ms,
            bandwidth_mbps=bandwidth_mbps,
            packet_loss_percent=packet_loss_percent,
            jitter_ms=jitter_ms
        )
        
        logger.debug(f"Updated network metrics for {backend_name}: {metrics.to_dict()}")
    
    def get_backend_for_content(
        self,
        content_info: Dict[str, Any],
        strategy: Optional[RoutingStrategy] = None,
        priority: Optional[RoutingPriority] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Get the optimal backend for content based on network conditions.
        
        This method enhances the base router's selection by considering
        network metrics like bandwidth and latency.
        
        Args:
            content_info: Information about the content
            strategy: Optional routing strategy
            priority: Optional routing priority
            client_location: Optional client location coordinates
            
        Returns:
            Name of the selected backend
        """
        if strategy == RoutingStrategy.LATENCY:
            # For latency-focused routing, use network metrics
            return self.select_lowest_latency_backend(content_info)
        
        elif strategy == RoutingStrategy.BANDWIDTH:
            # For bandwidth-focused routing, use network metrics
            return self.select_highest_bandwidth_backend(content_info)
        
        elif strategy == RoutingStrategy.NETWORK_AWARE:
            # For network-aware routing, use transfer time estimates
            return self.select_fastest_transfer_backend(content_info)
        
        elif strategy == RoutingStrategy.BALANCED or strategy == RoutingStrategy.HYBRID:
            # For balanced/hybrid approach, combine base router with network awareness
            base_selection = self.base_router.select_backend(
                b"",  # Dummy content (using content_info instead)
                content_info,
                available_backends=list(self.network_metrics.keys()),
                strategy=strategy,
                priority=priority,
                client_location=client_location
            )
            
            network_selection = self.select_fastest_transfer_backend(content_info)
            
            # Select best option based on network quality
            if (self.network_metrics.get(network_selection) and 
                self.network_metrics[network_selection].get_network_quality() in 
                [NetworkQuality.EXCELLENT, NetworkQuality.GOOD]):
                return network_selection
            else:
                return base_selection
        
        # Otherwise, use base router's selection
        return self.base_router.select_backend(
            b"",  # Dummy content (using content_info instead)
            content_info,
            available_backends=list(self.network_metrics.keys()),
            strategy=strategy,
            priority=priority,
            client_location=client_location
        )
    
    def select_lowest_latency_backend(self, content_info: Dict[str, Any]) -> str:
        """
        Select the backend with the lowest latency.
        
        Args:
            content_info: Information about the content
            
        Returns:
            Name of the selected backend
        """
        # Get available backends with metrics
        available_backends = list(self.network_metrics.keys())
        if not available_backends:
            # Fall back to base router if no network metrics available
            return self.base_router.select_backend(b"", content_info)
        
        # Sort backends by latency (lowest first)
        backends_by_latency = sorted(
            available_backends,
            key=lambda b: self.network_metrics[b].latency_ms if b in self.network_metrics else float('inf')
        )
        
        # Return the backend with lowest latency
        return backends_by_latency[0]
    
    def select_highest_bandwidth_backend(self, content_info: Dict[str, Any]) -> str:
        """
        Select the backend with the highest bandwidth.
        
        Args:
            content_info: Information about the content
            
        Returns:
            Name of the selected backend
        """
        # Get available backends with metrics
        available_backends = list(self.network_metrics.keys())
        if not available_backends:
            # Fall back to base router if no network metrics available
            return self.base_router.select_backend(b"", content_info)
        
        # Sort backends by bandwidth (highest first)
        backends_by_bandwidth = sorted(
            available_backends,
            key=lambda b: self.network_metrics[b].bandwidth_mbps if b in self.network_metrics else 0,
            reverse=True
        )
        
        # Return the backend with highest bandwidth
        return backends_by_bandwidth[0]
    
    def select_fastest_transfer_backend(self, content_info: Dict[str, Any]) -> str:
        """
        Select the backend with the fastest estimated transfer time.
        
        Args:
            content_info: Information about the content
            
        Returns:
            Name of the selected backend
        """
        # Get available backends with metrics
        available_backends = list(self.network_metrics.keys())
        if not available_backends:
            # Fall back to base router if no network metrics available
            return self.base_router.select_backend(b"", content_info)
        
        # Get content size
        size_bytes = content_info.get("size_bytes", 0)
        if size_bytes <= 0:
            # For unknown size, prefer low latency
            return self.select_lowest_latency_backend(content_info)
        
        # Calculate transfer time estimates for each backend
        transfer_times = {}
        for backend in available_backends:
            if backend in self.network_metrics:
                transfer_times[backend] = self.network_metrics[backend].get_transfer_time_estimate(size_bytes)
            else:
                transfer_times[backend] = float('inf')
        
        # Sort backends by transfer time (shortest first)
        backends_by_transfer_time = sorted(
            available_backends,
            key=lambda b: transfer_times.get(b, float('inf'))
        )
        
        # Return the backend with shortest transfer time
        return backends_by_transfer_time[0]
    
    def get_network_metrics(self, backend_name: Optional[str] = None) -> Union[Dict[str, NetworkMetrics], Optional[NetworkMetrics]]:
        """
        Get network metrics for a backend or all backends.
        
        Args:
            backend_name: Optional backend name to get metrics for
            
        Returns:
            Network metrics for specified backend or all backends
        """
        if backend_name:
            return self.network_metrics.get(backend_name)
        else:
            return self.network_metrics.copy()
    
    def register_backend(self, backend_name: str) -> None:
        """
        Register a new backend for network measurements.
        
        Args:
            backend_name: Name of the backend to register
        """
        if backend_name not in self.network_metrics:
            self.network_metrics[backend_name] = NetworkMetrics(backend_name)
            logger.info(f"Registered backend '{backend_name}' for network measurements")
    
    def unregister_backend(self, backend_name: str) -> None:
        """
        Unregister a backend from network measurements.
        
        Args:
            backend_name: Name of the backend to unregister
        """
        if backend_name in self.network_metrics:
            del self.network_metrics[backend_name]
            logger.info(f"Unregistered backend '{backend_name}' from network measurements")


def enhance_router(base_router: DataRouter) -> NetworkAwareRouter:
    """
    Enhance a base router with network awareness capabilities.
    
    Args:
        base_router: Base data router instance
        
    Returns:
        Network-aware router instance
    """
    # Create network-aware router
    enhanced_router = NetworkAwareRouter(base_router)
    
    # Start network measurements
    enhanced_router.start_measurements()
    
    return enhanced_router