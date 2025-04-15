"""
Bandwidth and Latency Analysis Module for Optimized Data Routing

This module enhances the data routing system with comprehensive bandwidth and latency analysis:
- Real-time bandwidth measurement between client and backends
- Latency profiling for dynamic route selection
- Network congestion detection and avoidance
- Adaptive routing based on network conditions
- Historical performance tracking for predictive routing

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import time
import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
import random
import math

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class NetworkMetrics:
    """Network performance metrics between client and backend."""
    backend_id: str
    
    # Latency measurements (milliseconds)
    latency_min_ms: float = 0.0
    latency_max_ms: float = 0.0
    latency_avg_ms: float = 0.0
    latency_median_ms: float = 0.0
    latency_jitter_ms: float = 0.0  # Standard deviation of latency
    
    # Bandwidth measurements (Mbps)
    download_bandwidth_mbps: float = 0.0
    upload_bandwidth_mbps: float = 0.0
    
    # Packet loss and reliability
    packet_loss_percent: float = 0.0
    connection_stability: float = 1.0  # 0.0-1.0 score
    
    # Routing information
    hop_count: Optional[int] = None
    route_congestion_level: float = 0.0  # 0.0-1.0 score
    
    # Last measurement timestamp
    last_measured: datetime = field(default_factory=datetime.now)
    measurement_count: int = 0
    
    # Historical data for trends
    historical_latency: List[Tuple[datetime, float]] = field(default_factory=list)
    historical_bandwidth: List[Tuple[datetime, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "backend_id": self.backend_id,
            "latency": {
                "min_ms": self.latency_min_ms,
                "max_ms": self.latency_max_ms,
                "avg_ms": self.latency_avg_ms,
                "median_ms": self.latency_median_ms,
                "jitter_ms": self.latency_jitter_ms
            },
            "bandwidth": {
                "download_mbps": self.download_bandwidth_mbps,
                "upload_mbps": self.upload_bandwidth_mbps
            },
            "reliability": {
                "packet_loss_percent": self.packet_loss_percent,
                "connection_stability": self.connection_stability
            },
            "routing": {
                "hop_count": self.hop_count,
                "congestion_level": self.route_congestion_level
            },
            "last_measured": self.last_measured.isoformat(),
            "measurement_count": self.measurement_count
        }
        
        # Include historical data if available
        if self.historical_latency:
            result["historical_latency"] = [
                {"timestamp": ts.isoformat(), "value_ms": val}
                for ts, val in self.historical_latency[-20:]  # Last 20 measurements
            ]
        
        if self.historical_bandwidth:
            result["historical_bandwidth"] = [
                {"timestamp": ts.isoformat(), "value_mbps": val}
                for ts, val in self.historical_bandwidth[-20:]  # Last 20 measurements
            ]
        
        return result
    
    def update_latency(self, latency_ms: float) -> None:
        """
        Update latency measurements with a new sample.
        
        Args:
            latency_ms: New latency measurement in milliseconds
        """
        # Update min/max
        if self.measurement_count == 0 or latency_ms < self.latency_min_ms:
            self.latency_min_ms = latency_ms
        
        if self.measurement_count == 0 or latency_ms > self.latency_max_ms:
            self.latency_max_ms = latency_ms
        
        # Update historical data
        now = datetime.now()
        self.historical_latency.append((now, latency_ms))
        
        # Keep only last 100 measurements
        if len(self.historical_latency) > 100:
            self.historical_latency.pop(0)
        
        # Calculate statistics from historical data
        if self.historical_latency:
            latency_values = [val for _, val in self.historical_latency]
            self.latency_avg_ms = statistics.mean(latency_values)
            self.latency_median_ms = statistics.median(latency_values)
            
            if len(latency_values) > 1:
                self.latency_jitter_ms = statistics.stdev(latency_values)
        
        # Update last measured time and count
        self.last_measured = now
        self.measurement_count += 1
    
    def update_bandwidth(self, download_mbps: float, upload_mbps: Optional[float] = None) -> None:
        """
        Update bandwidth measurements with new samples.
        
        Args:
            download_mbps: Download bandwidth in Mbps
            upload_mbps: Upload bandwidth in Mbps (optional)
        """
        # Update download bandwidth
        self.download_bandwidth_mbps = download_mbps
        
        # Update upload bandwidth if provided
        if upload_mbps is not None:
            self.upload_bandwidth_mbps = upload_mbps
        
        # Update historical data
        now = datetime.now()
        self.historical_bandwidth.append((now, download_mbps))
        
        # Keep only last 100 measurements
        if len(self.historical_bandwidth) > 100:
            self.historical_bandwidth.pop(0)
        
        # Update last measured time
        self.last_measured = now
    
    def update_reliability(self, packet_loss_percent: float, connection_stability: Optional[float] = None) -> None:
        """
        Update reliability measurements.
        
        Args:
            packet_loss_percent: Packet loss percentage (0-100)
            connection_stability: Connection stability score (0.0-1.0)
        """
        self.packet_loss_percent = packet_loss_percent
        
        if connection_stability is not None:
            self.connection_stability = max(0.0, min(1.0, connection_stability))
        
        # Update last measured time
        self.last_measured = datetime.now()
    
    def update_routing(self, hop_count: Optional[int] = None, congestion_level: Optional[float] = None) -> None:
        """
        Update routing measurements.
        
        Args:
            hop_count: Number of network hops to backend
            congestion_level: Route congestion level (0.0-1.0)
        """
        if hop_count is not None:
            self.hop_count = hop_count
        
        if congestion_level is not None:
            self.route_congestion_level = max(0.0, min(1.0, congestion_level))
        
        # Update last measured time
        self.last_measured = datetime.now()
    
    def is_recent(self, max_age_seconds: int = 300) -> bool:
        """
        Check if measurements are recent.
        
        Args:
            max_age_seconds: Maximum age in seconds to be considered recent
            
        Returns:
            True if measurements are recent
        """
        age = datetime.now() - self.last_measured
        return age.total_seconds() < max_age_seconds
    
    def get_performance_score(self) -> float:
        """
        Calculate overall performance score based on all metrics.
        
        Returns:
            Performance score (0.0-1.0, higher is better)
        """
        # Normalize latency (0-1000ms range, lower is better)
        latency_score = max(0.0, 1.0 - (self.latency_avg_ms / 1000.0))
        
        # Normalize bandwidth (0-100Mbps range, higher is better)
        bandwidth_score = min(1.0, self.download_bandwidth_mbps / 100.0)
        
        # Normalize jitter (0-100ms range, lower is better)
        jitter_score = max(0.0, 1.0 - (self.latency_jitter_ms / 100.0))
        
        # Normalize packet loss (0-10% range, lower is better)
        packet_loss_score = max(0.0, 1.0 - (self.packet_loss_percent / 10.0))
        
        # Calculate weighted average
        weights = {
            "latency": 0.3,
            "bandwidth": 0.3,
            "jitter": 0.1,
            "packet_loss": 0.2,
            "stability": 0.1
        }
        
        score = (
            latency_score * weights["latency"] +
            bandwidth_score * weights["bandwidth"] +
            jitter_score * weights["jitter"] +
            packet_loss_score * weights["packet_loss"] +
            self.connection_stability * weights["stability"]
        )
        
        return max(0.0, min(1.0, score))


class BandwidthAnalyzer:
    """
    Analyzes and measures bandwidth between client and storage backends.
    
    This class provides methods to measure, analyze, and predict bandwidth
    performance for different storage backends.
    """
    
    def __init__(self, backend_manager=None):
        """
        Initialize the bandwidth analyzer.
        
        Args:
            backend_manager: Storage backend manager (optional)
        """
        self.backend_manager = backend_manager
        self.network_metrics: Dict[str, NetworkMetrics] = {}
        self.measurement_interval_seconds = 300  # 5 minutes between measurements
        self.last_global_measurement = datetime.now() - timedelta(minutes=10)  # Force initial measurement
    
    async def measure_latency(self, backend_id: str, sample_count: int = 5) -> float:
        """
        Measure latency to a backend.
        
        Args:
            backend_id: Backend identifier
            sample_count: Number of samples to take
            
        Returns:
            Average latency in milliseconds
        """
        if not self.backend_manager:
            # Simulate latency for testing
            return self._simulate_latency(backend_id)
        
        try:
            backend = self.backend_manager.get_backend(backend_id)
            if not backend:
                logger.warning(f"Backend {backend_id} not found")
                return 0.0
            
            # Measure latency with sample_count pings
            latency_samples = []
            for _ in range(sample_count):
                start_time = time.time()
                
                # Attempt a simple operation like a health check
                if hasattr(backend, "health_check"):
                    await backend.health_check()
                elif hasattr(backend, "ipfs") and hasattr(backend.ipfs, "ipfs_ping"):
                    await backend.ipfs.ipfs_ping()
                else:
                    # Fallback to a generic stateless operation
                    if backend_id == "ipfs":
                        # For IPFS, use id command which is lightweight
                        await backend.ipfs.ipfs_id()
                    elif backend_id == "s3":
                        # For S3, use list_buckets which is lightweight
                        await backend.client.list_buckets()
                    elif backend_id == "storacha":
                        # For Storacha, use a status check
                        await backend.get_status()
                    else:
                        # Generic fallback
                        pass
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                latency_samples.append(latency_ms)
                
                # Small delay between measurements
                await asyncio.sleep(0.1)
            
            # Calculate average latency
            if latency_samples:
                avg_latency = statistics.mean(latency_samples)
                
                # Update metrics
                self._get_or_create_metrics(backend_id).update_latency(avg_latency)
                
                return avg_latency
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error measuring latency for backend {backend_id}: {e}")
            return 0.0
    
    async def measure_bandwidth(self, backend_id: str, test_size_kb: int = 1024) -> Tuple[float, float]:
        """
        Measure bandwidth to a backend using a test upload/download.
        
        Args:
            backend_id: Backend identifier
            test_size_kb: Size of test data in KB
            
        Returns:
            Tuple of (download_mbps, upload_mbps)
        """
        if not self.backend_manager:
            # Simulate bandwidth for testing
            download, upload = self._simulate_bandwidth(backend_id)
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_bandwidth(download, upload)
            
            return download, upload
        
        try:
            backend = self.backend_manager.get_backend(backend_id)
            if not backend:
                logger.warning(f"Backend {backend_id} not found")
                return 0.0, 0.0
            
            # Create test data (random bytes)
            test_data = b'x' * (test_size_kb * 1024)  # Simple repeating pattern
            test_metadata = {"name": "bandwidth_test", "test_id": f"bw_test_{int(time.time())}"}
            
            # Measure upload bandwidth
            start_time = time.time()
            upload_result = await backend.add_content(test_data, test_metadata)
            upload_end_time = time.time()
            
            if not upload_result.get("success", False):
                logger.warning(f"Failed to upload test data to {backend_id}")
                return 0.0, 0.0
            
            # Get content ID or reference from the result
            content_id = upload_result.get("content_id") or upload_result.get("cid") or upload_result.get("hash")
            if not content_id:
                logger.warning(f"Failed to get content ID from upload result")
                return 0.0, 0.0
            
            # Measure download bandwidth
            start_time_dl = time.time()
            content = await backend.get_content(content_id)
            download_end_time = time.time()
            
            # Calculate bandwidth in Mbps
            upload_time = upload_end_time - start_time
            upload_mbps = (test_size_kb * 8 / 1000) / upload_time if upload_time > 0 else 0
            
            download_time = download_end_time - start_time_dl
            download_mbps = (test_size_kb * 8 / 1000) / download_time if download_time > 0 else 0
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_bandwidth(download_mbps, upload_mbps)
            
            # Clean up test data if possible
            try:
                if hasattr(backend, "delete_content"):
                    await backend.delete_content(content_id)
            except:
                pass
            
            return download_mbps, upload_mbps
            
        except Exception as e:
            logger.error(f"Error measuring bandwidth for backend {backend_id}: {e}")
            return 0.0, 0.0
    
    async def measure_reliability(self, backend_id: str, sample_count: int = 10) -> Tuple[float, float]:
        """
        Measure reliability metrics for a backend.
        
        Args:
            backend_id: Backend identifier
            sample_count: Number of samples to take
            
        Returns:
            Tuple of (packet_loss_percent, connection_stability)
        """
        if not self.backend_manager:
            # Simulate reliability for testing
            loss, stability = self._simulate_reliability(backend_id)
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_reliability(loss, stability)
            
            return loss, stability
        
        try:
            backend = self.backend_manager.get_backend(backend_id)
            if not backend:
                logger.warning(f"Backend {backend_id} not found")
                return 0.0, 1.0
            
            # Simulate pings to measure packet loss and stability
            success_count = 0
            response_times = []
            
            for i in range(sample_count):
                try:
                    start_time = time.time()
                    
                    # Perform a simple operation
                    if hasattr(backend, "health_check"):
                        result = await backend.health_check()
                        success = result.get("success", False) if isinstance(result, dict) else bool(result)
                    elif hasattr(backend, "ipfs") and hasattr(backend.ipfs, "ipfs_id"):
                        result = await backend.ipfs.ipfs_id()
                        success = result.get("success", False) if isinstance(result, dict) else bool(result)
                    else:
                        # Fallback
                        success = True
                    
                    end_time = time.time()
                    
                    if success:
                        success_count += 1
                        response_times.append(end_time - start_time)
                    
                    # Small delay between tests
                    await asyncio.sleep(0.2)
                    
                except Exception:
                    # Count as failure
                    pass
            
            # Calculate packet loss
            packet_loss = 100.0 * (1 - (success_count / sample_count)) if sample_count > 0 else 0.0
            
            # Calculate connection stability based on variance in response times
            stability = 1.0
            if len(response_times) >= 2:
                mean_time = statistics.mean(response_times)
                if mean_time > 0:
                    # Calculate coefficient of variation
                    stdev = statistics.stdev(response_times)
                    cv = stdev / mean_time
                    # Map CV to stability score (lower CV = higher stability)
                    stability = max(0.0, min(1.0, 1.0 - min(1.0, cv * 2)))
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_reliability(packet_loss, stability)
            
            return packet_loss, stability
            
        except Exception as e:
            logger.error(f"Error measuring reliability for backend {backend_id}: {e}")
            return 0.0, 1.0
    
    async def analyze_route(self, backend_id: str) -> Tuple[Optional[int], float]:
        """
        Analyze the network route to a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (hop_count, congestion_level)
        """
        if not self.backend_manager:
            # Simulate routing metrics for testing
            hops, congestion = self._simulate_routing(backend_id)
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_routing(hops, congestion)
            
            return hops, congestion
        
        try:
            # This would normally use traceroute or similar to get hop count
            # For now, use simulated data since we can't run traceroute from within the script
            hops, congestion = self._simulate_routing(backend_id)
            
            # Update metrics
            metrics = self._get_or_create_metrics(backend_id)
            metrics.update_routing(hops, congestion)
            
            return hops, congestion
            
        except Exception as e:
            logger.error(f"Error analyzing route for backend {backend_id}: {e}")
            return None, 0.0
    
    async def measure_all_metrics(self, backend_id: str) -> NetworkMetrics:
        """
        Measure all network metrics for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            NetworkMetrics object with measurements
        """
        # Get existing metrics or create new
        metrics = self._get_or_create_metrics(backend_id)
        
        # Skip if recent measurements exist
        if metrics.is_recent(self.measurement_interval_seconds):
            return metrics
        
        # Run all measurements
        await self.measure_latency(backend_id)
        await self.measure_bandwidth(backend_id)
        await self.measure_reliability(backend_id)
        await self.analyze_route(backend_id)
        
        return metrics
    
    async def measure_all_backends(self) -> Dict[str, NetworkMetrics]:
        """
        Measure network metrics for all available backends.
        
        Returns:
            Dict mapping backend IDs to NetworkMetrics
        """
        # Skip if global measurement interval hasn't elapsed
        now = datetime.now()
        if (now - self.last_global_measurement).total_seconds() < self.measurement_interval_seconds:
            return self.network_metrics
        
        # Get list of backends
        backend_ids = []
        if self.backend_manager:
            backend_ids = self.backend_manager.list_backends()
        else:
            # Default to common backends
            backend_ids = ["ipfs", "filecoin", "s3", "storacha"]
        
        # Measure each backend
        for backend_id in backend_ids:
            try:
                await self.measure_all_metrics(backend_id)
            except Exception as e:
                logger.error(f"Error measuring metrics for {backend_id}: {e}")
        
        # Update last measurement time
        self.last_global_measurement = now
        
        return self.network_metrics
    
    def get_network_metrics(self, backend_id: str) -> Optional[NetworkMetrics]:
        """
        Get network metrics for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            NetworkMetrics object or None if not found
        """
        return self.network_metrics.get(backend_id)
    
    def get_all_network_metrics(self) -> Dict[str, NetworkMetrics]:
        """
        Get network metrics for all backends.
        
        Returns:
            Dict mapping backend IDs to NetworkMetrics
        """
        return self.network_metrics.copy()
    
    def rank_backends_by_performance(self, backend_ids: Optional[List[str]] = None) -> List[str]:
        """
        Rank backends by overall network performance.
        
        Args:
            backend_ids: Optional list of backend IDs to rank
            
        Returns:
            List of backend IDs sorted by performance (best first)
        """
        if not backend_ids:
            backend_ids = list(self.network_metrics.keys())
        
        # Filter to backends with metrics
        backends_with_metrics = [
            backend_id for backend_id in backend_ids
            if backend_id in self.network_metrics
        ]
        
        # Sort by performance score
        return sorted(
            backends_with_metrics,
            key=lambda bid: self.network_metrics[bid].get_performance_score(),
            reverse=True
        )
    
    def predict_transfer_time(
        self, 
        backend_id: str, 
        size_bytes: int, 
        upload: bool = False
    ) -> Optional[float]:
        """
        Predict transfer time for a specific backend and file size.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            upload: Whether this is an upload (True) or download (False)
            
        Returns:
            Predicted transfer time in seconds or None if insufficient data
        """
        metrics = self.network_metrics.get(backend_id)
        if not metrics:
            return None
        
        # Convert size to megabits
        size_megabits = size_bytes * 8 / 1000000
        
        # Get bandwidth
        bandwidth = metrics.upload_bandwidth_mbps if upload else metrics.download_bandwidth_mbps
        
        # Check if we have valid bandwidth data
        if bandwidth <= 0:
            return None
        
        # Calculate base transfer time
        transfer_time = size_megabits / bandwidth
        
        # Add latency and jitter factors
        latency_factor = metrics.latency_avg_ms / 1000  # Convert to seconds
        jitter_factor = metrics.latency_jitter_ms / 2000  # Half the jitter in seconds
        
        # Add reliability factor (packet loss increases time)
        reliability_factor = 1.0 + (metrics.packet_loss_percent / 100)
        
        # Combine factors
        predicted_time = (transfer_time + latency_factor) * reliability_factor * (1.0 + jitter_factor)
        
        # Return prediction
        return max(0.1, predicted_time)  # Minimum 0.1 seconds
    
    def _get_or_create_metrics(self, backend_id: str) -> NetworkMetrics:
        """
        Get existing metrics for a backend or create new ones.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            NetworkMetrics object
        """
        if backend_id not in self.network_metrics:
            self.network_metrics[backend_id] = NetworkMetrics(backend_id)
        
        return self.network_metrics[backend_id]
    
    def _simulate_latency(self, backend_id: str) -> float:
        """
        Simulate latency for testing purposes.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Simulated latency in milliseconds
        """
        # Baseline latency depends on backend type
        baseline = {
            "ipfs": 50.0,  # IPFS tends to be faster for reads
            "filecoin": 300.0,  # Filecoin has higher latency
            "s3": 80.0,  # S3 has moderate latency
            "storacha": 100.0,  # Storacha has moderate-high latency
            "huggingface": 120.0,  # HuggingFace has moderate-high latency
            "lassie": 200.0,  # Lassie has higher latency
        }.get(backend_id, 100.0)
        
        # Add some randomness
        jitter = random.uniform(-20.0, 50.0)
        latency = max(5.0, baseline + jitter)
        
        # Update metrics
        self._get_or_create_metrics(backend_id).update_latency(latency)
        
        return latency
    
    def _simulate_bandwidth(self, backend_id: str) -> Tuple[float, float]:
        """
        Simulate bandwidth for testing purposes.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (download_mbps, upload_mbps)
        """
        # Baseline bandwidth depends on backend type
        baseline_download = {
            "ipfs": 25.0,  # IPFS tends to have good read bandwidth
            "filecoin": 15.0,  # Filecoin has lower bandwidth
            "s3": 50.0,  # S3 has high bandwidth
            "storacha": 30.0,  # Storacha has moderate bandwidth
            "huggingface": 40.0,  # HuggingFace has good bandwidth
            "lassie": 20.0,  # Lassie has moderate bandwidth
        }.get(backend_id, 20.0)
        
        # Upload is usually slower than download
        baseline_upload = baseline_download * 0.7
        
        # Add some randomness
        download = max(1.0, baseline_download * random.uniform(0.8, 1.2))
        upload = max(0.5, baseline_upload * random.uniform(0.8, 1.2))
        
        return download, upload
    
    def _simulate_reliability(self, backend_id: str) -> Tuple[float, float]:
        """
        Simulate reliability for testing purposes.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (packet_loss_percent, connection_stability)
        """
        # Baseline packet loss depends on backend type
        baseline_loss = {
            "ipfs": 1.0,  # IPFS has low packet loss
            "filecoin": 3.0,  # Filecoin has higher packet loss
            "s3": 0.5,  # S3 has very low packet loss
            "storacha": 2.0,  # Storacha has moderate packet loss
            "huggingface": 1.0,  # HuggingFace has low packet loss
            "lassie": 2.5,  # Lassie has moderate-high packet loss
        }.get(backend_id, 2.0)
        
        # Baseline stability depends on backend type
        baseline_stability = {
            "ipfs": 0.95,  # IPFS has good stability
            "filecoin": 0.85,  # Filecoin has lower stability
            "s3": 0.99,  # S3 has excellent stability
            "storacha": 0.90,  # Storacha has good stability
            "huggingface": 0.95,  # HuggingFace has good stability
            "lassie": 0.88,  # Lassie has moderate stability
        }.get(backend_id, 0.90)
        
        # Add some randomness
        loss = max(0.0, min(10.0, baseline_loss * random.uniform(0.7, 1.5)))
        stability = max(0.7, min(1.0, baseline_stability * random.uniform(0.95, 1.05)))
        
        return loss, stability
    
    def _simulate_routing(self, backend_id: str) -> Tuple[int, float]:
        """
        Simulate routing metrics for testing purposes.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (hop_count, congestion_level)
        """
        # Baseline hop count depends on backend type
        baseline_hops = {
            "ipfs": 4,  # IPFS typically has fewer hops
            "filecoin": 7,  # Filecoin has more hops
            "s3": 5,  # S3 has moderate hop count
            "storacha": 6,  # Storacha has moderate-high hop count
            "huggingface": 5,  # HuggingFace has moderate hop count
            "lassie": 6,  # Lassie has moderate-high hop count
        }.get(backend_id, 5)
        
        # Baseline congestion depends on backend type
        baseline_congestion = {
            "ipfs": 0.3,  # IPFS has moderate congestion
            "filecoin": 0.5,  # Filecoin has higher congestion
            "s3": 0.1,  # S3 has low congestion
            "storacha": 0.4,  # Storacha has moderate congestion
            "huggingface": 0.3,  # HuggingFace has moderate congestion
            "lassie": 0.4,  # Lassie has moderate congestion
        }.get(backend_id, 0.3)
        
        # Add some randomness
        hops = max(2, baseline_hops + random.randint(-1, 2))
        congestion = max(0.0, min(1.0, baseline_congestion * random.uniform(0.8, 1.3)))
        
        return hops, congestion


class BandwidthAwareRouter:
    """
    Router that uses bandwidth and latency analysis for optimal backend selection.
    
    This router extends the DataRouter with network-aware decision making
    to optimize content routing based on current network conditions.
    """
    
    def __init__(self, data_router=None, backend_manager=None):
        """
        Initialize the bandwidth-aware router.
        
        Args:
            data_router: DataRouter instance
            backend_manager: Storage backend manager
        """
        self.data_router = data_router
        self.backend_manager = backend_manager
        self.bandwidth_analyzer = BandwidthAnalyzer(backend_manager)
        
        # Network awareness parameters
        self.network_weight = 0.4  # Weight of network metrics in routing decisions
        self.content_weight = 0.6  # Weight of content analysis in routing decisions
        
        # Network score components
        self.latency_importance = 0.3
        self.bandwidth_importance = 0.4
        self.reliability_importance = 0.3
        
        # Last measurement timestamp
        self.last_measurement = datetime.now() - timedelta(minutes=10)  # Force initial measurement
        self.measurement_interval = 300  # 5 minutes
    
    async def initialize(self):
        """Initialize the router with initial measurements."""
        # Initial measurement
        await self.update_network_metrics()
    
    async def update_network_metrics(self) -> None:
        """Update network metrics for all backends."""
        now = datetime.now()
        if (now - self.last_measurement).total_seconds() < self.measurement_interval:
            # Skip if interval hasn't elapsed
            return
        
        # Update metrics
        await self.bandwidth_analyzer.measure_all_backends()
        self.last_measurement = now
    
    async def select_backend(
        self,
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        content_size: Optional[int] = None,
        available_backends: Optional[List[str]] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the optimal backend based on content and network conditions.
        
        Args:
            content: Content to store (or sample for large content)
            metadata: Optional metadata about the content
            content_size: Actual content size (if content is a sample)
            available_backends: Optional list of available backends
            client_location: Optional client location (lat/lon)
            
        Returns:
            Name of the selected backend
        """
        if not self.data_router:
            logger.warning("DataRouter not available for content analysis")
            # Fall back to network-only analysis
            return await self._select_by_network(
                content_size or (len(content) if isinstance(content, bytes) else len(content.encode())),
                available_backends
            )
        
        # Update network metrics if needed
        await self.update_network_metrics()
        
        # Get available backends
        if available_backends is None:
            if self.backend_manager:
                available_backends = self.backend_manager.list_backends()
            else:
                # Default to common backends
                available_backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # If no backends available, return default
        if not available_backends:
            return "ipfs"  # Default to IPFS
        elif len(available_backends) == 1:
            return available_backends[0]  # Only one backend available
        
        # Get content analysis from data router
        content_analysis = self.data_router.content_analyzer.analyze(content, metadata)
        
        # Get actual size (either from parameter or content)
        if content_size is not None:
            size_bytes = content_size
        else:
            size_bytes = content_analysis["size_bytes"]
        
        # Calculate scores for each backend
        scores = {}
        
        for backend_id in available_backends:
            # Calculate content-based score (using DataRouter's logic)
            content_score = self._calculate_content_score(backend_id, content_analysis, size_bytes)
            
            # Calculate network score
            network_score = self._calculate_network_score(backend_id, size_bytes)
            
            # Combine scores
            combined_score = (
                content_score * self.content_weight +
                network_score * self.network_weight
            )
            
            scores[backend_id] = combined_score
        
        # Select backend with highest score
        if not scores:
            # Fallback if no scores calculated
            return available_backends[0]
        
        # Return highest scoring backend
        return max(scores.items(), key=lambda x: x[1])[0]
    
    async def predict_transfer_times(
        self,
        content_size: int,
        backend_ids: Optional[List[str]] = None,
        upload: bool = True
    ) -> Dict[str, float]:
        """
        Predict transfer times for content across different backends.
        
        Args:
            content_size: Size in bytes
            backend_ids: Optional list of backend IDs to predict for
            upload: Whether this is an upload (True) or download (False)
            
        Returns:
            Dict mapping backend IDs to predicted transfer times in seconds
        """
        # Update network metrics if needed
        await self.update_network_metrics()
        
        # Get backends to predict for
        if backend_ids is None:
            if self.backend_manager:
                backend_ids = self.backend_manager.list_backends()
            else:
                # Default to common backends
                backend_ids = ["ipfs", "filecoin", "s3", "storacha"]
        
        # Calculate predictions
        predictions = {}
        
        for backend_id in backend_ids:
            predicted_time = self.bandwidth_analyzer.predict_transfer_time(
                backend_id, content_size, upload
            )
            
            if predicted_time is not None:
                predictions[backend_id] = predicted_time
        
        return predictions
    
    async def select_backend_for_client(
        self,
        client_id: str,
        content_size: int,
        content_type: str,
        available_backends: Optional[List[str]] = None
    ) -> str:
        """
        Select optimal backend for a specific client based on historical performance.
        
        Args:
            client_id: Client identifier
            content_size: Size in bytes
            content_type: Content MIME type
            available_backends: Optional list of available backends
            
        Returns:
            Name of the selected backend
        """
        # This would normally use client-specific historical data
        # For now, just use general network analysis
        return await self._select_by_network(content_size, available_backends)
    
    async def get_network_analysis(
        self,
        backends: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed network analysis for all backends.
        
        Args:
            backends: Optional list of backends to analyze
            
        Returns:
            Dict with network analysis
        """
        # Update network metrics if needed
        await self.update_network_metrics()
        
        # Get backends to analyze
        if backends is None:
            if self.backend_manager:
                backends = self.backend_manager.list_backends()
            else:
                backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # Get all metrics
        all_metrics = self.bandwidth_analyzer.get_all_network_metrics()
        
        # Filter to requested backends
        filtered_metrics = {
            backend: all_metrics.get(backend)
            for backend in backends
            if backend in all_metrics
        }
        
        # Convert to dict
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "backends": {
                backend: metrics.to_dict()
                for backend, metrics in filtered_metrics.items()
            },
            "ranking": self.bandwidth_analyzer.rank_backends_by_performance(backends)
        }
    
    def get_bandwidth_analyzer(self) -> BandwidthAnalyzer:
        """
        Get the bandwidth analyzer instance.
        
        Returns:
            BandwidthAnalyzer instance
        """
        return self.bandwidth_analyzer
    
    async def _select_by_network(
        self,
        content_size: int,
        available_backends: Optional[List[str]] = None
    ) -> str:
        """
        Select backend based only on network metrics.
        
        Args:
            content_size: Size in bytes
            available_backends: Optional list of available backends
            
        Returns:
            Name of the selected backend
        """
        # Get available backends
        if available_backends is None:
            if self.backend_manager:
                available_backends = self.backend_manager.list_backends()
            else:
                available_backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # If no backends available, return default
        if not available_backends:
            return "ipfs"  # Default to IPFS
        elif len(available_backends) == 1:
            return available_backends[0]  # Only one backend available
        
        # Calculate scores
        scores = {}
        
        for backend_id in available_backends:
            scores[backend_id] = self._calculate_network_score(backend_id, content_size)
        
        # Select backend with highest score
        if not scores:
            return available_backends[0]
        
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def _calculate_content_score(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any],
        size_bytes: int
    ) -> float:
        """
        Calculate content-based score for a backend.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis from DataRouter
            size_bytes: Size in bytes
            
        Returns:
            Score from 0.0 to 1.0
        """
        if not self.data_router:
            # No content router, use default score
            return 0.5
        
        # This would normally use the DataRouter's scoring logic
        # For now, use simple heuristics
        
        category = content_analysis.get("category", "other")
        size_category = content_analysis.get("size_category", "medium_file")
        
        # Score based on backend specialty
        if backend_id == "ipfs":
            # IPFS is good for small files and documents
            if size_category == "small_file":
                return 0.9
            elif category == "document":
                return 0.8
            elif size_category == "large_file":
                return 0.3
            else:
                return 0.6
                
        elif backend_id == "filecoin":
            # Filecoin is good for large files
            if size_category == "large_file":
                return 0.9
            elif size_category == "medium_file":
                return 0.7
            elif category == "encrypted":
                return 0.8
            else:
                return 0.4
                
        elif backend_id == "s3":
            # S3 is good for medium files and media
            if size_category == "medium_file":
                return 0.8
            elif category == "media":
                return 0.9
            else:
                return 0.7
                
        elif backend_id == "storacha":
            # Storacha is good for media and documents
            if category == "media":
                return 0.85
            elif category == "document":
                return 0.75
            else:
                return 0.6
                
        elif backend_id == "huggingface":
            # HuggingFace is optimized for ML models
            if category == "binary" and "model" in str(content_analysis.get("patterns_matched", [])):
                return 0.95
            else:
                return 0.5
                
        elif backend_id == "lassie":
            # Lassie is good for content retrieval
            return 0.7
            
        else:
            # Default score for unknown backends
            return 0.5
    
    def _calculate_network_score(self, backend_id: str, size_bytes: int) -> float:
        """
        Calculate network-based score for a backend.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            
        Returns:
            Score from 0.0 to 1.0
        """
        # Get network metrics
        metrics = self.bandwidth_analyzer.get_network_metrics(backend_id)
        
        # If no metrics, use default score
        if not metrics:
            return 0.5
        
        # Calculate score components
        
        # Latency score (lower is better)
        latency_score = max(0.0, 1.0 - (metrics.latency_avg_ms / 1000.0))
        
        # Bandwidth score based on content size
        size_mb = size_bytes / (1024 * 1024)
        if size_mb < 1:  # Small file
            # For small files, latency is more important than bandwidth
            bandwidth_score = 0.7  # Default good score for small files
        else:
            # For larger files, bandwidth becomes more important
            # Higher bandwidth = better score
            bandwidth_score = min(1.0, metrics.download_bandwidth_mbps / 50.0)
        
        # Reliability score
        reliability_score = 1.0 - (metrics.packet_loss_percent / 20.0)  # 0% loss = 1.0, 20% loss = 0.0
        reliability_score = max(0.0, min(1.0, reliability_score))
        
        # Calculate transfer time estimate
        transfer_time = self.bandwidth_analyzer.predict_transfer_time(backend_id, size_bytes, True)
        if transfer_time is not None:
            # Convert to score (lower time = higher score)
            # Use logarithmic scale to handle wide range of file sizes
            max_acceptable_time = 60.0 * (1.0 + math.log10(1.0 + size_mb / 10.0))  # Scale with file size
            time_score = max(0.0, 1.0 - (transfer_time / max_acceptable_time))
        else:
            time_score = 0.5  # Default if can't predict
        
        # Calculate weighted score
        score = (
            latency_score * self.latency_importance +
            bandwidth_score * self.bandwidth_importance +
            reliability_score * self.reliability_importance
        )
        
        # Adjust by time score
        score = score * 0.7 + time_score * 0.3
        
        return max(0.0, min(1.0, score))


# Factory function to create a bandwidth-aware router
def create_bandwidth_aware_router(data_router=None, backend_manager=None) -> BandwidthAwareRouter:
    """
    Create a bandwidth-aware router.
    
    Args:
        data_router: DataRouter instance
        backend_manager: Backend manager
        
    Returns:
        BandwidthAwareRouter instance
    """
    router = BandwidthAwareRouter(data_router, backend_manager)
    
    # Initialize router in background
    asyncio.create_task(router.initialize())
    
    return router