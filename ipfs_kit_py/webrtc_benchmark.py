"""
WebRTC Performance Benchmarking for IPFS Kit.

This module provides comprehensive benchmarking capabilities for WebRTC 
connections, enabling detailed performance analysis of streaming from IPFS content.

Key features:
1. Connection Metrics: Detailed timing for ICE, DTLS, etc.
2. Media Performance: Frame rates, resolution, bitrate analysis
3. Network Analysis: RTT, jitter, packet loss statistics
4. Resource Utilization: CPU, memory, bandwidth tracking
5. Quality Scoring: Quantitative measures of streaming quality
6. Report Generation: Comprehensive performance reports
7. Regression Testing: Comparison between benchmark runs

This module can be used standalone or integrated with WebRTCStreamingManager.
"""

import os
import time
import json
import anyio
import logging
import uuid
import statistics
from typing import Dict, List, Optional, Union, Any, Set, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class WebRTCFrameStat:
    """Statistics for a single frame's processing and delivery."""
    
    timestamp: float = field(default_factory=time.time)
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    size_bytes: int = 0
    codec: str = ""
    encode_start_time: Optional[float] = None
    encode_end_time: Optional[float] = None
    send_start_time: Optional[float] = None
    send_end_time: Optional[float] = None
    receive_time: Optional[float] = None
    decode_start_time: Optional[float] = None
    decode_end_time: Optional[float] = None
    render_time: Optional[float] = None
    is_keyframe: bool = False
    
    # Derived metrics (computed on demand)
    @property
    def encode_time_ms(self) -> Optional[float]:
        """Time taken to encode the frame in milliseconds."""
        if self.encode_start_time and self.encode_end_time:
            return (self.encode_end_time - self.encode_start_time) * 1000
        return None
    
    @property
    def transfer_time_ms(self) -> Optional[float]:
        """Time taken to transfer the frame over the network in milliseconds."""
        if self.send_start_time and self.receive_time:
            return (self.receive_time - self.send_start_time) * 1000
        return None
    
    @property
    def decode_time_ms(self) -> Optional[float]:
        """Time taken to decode the frame in milliseconds."""
        if self.decode_start_time and self.decode_end_time:
            return (self.decode_end_time - self.decode_start_time) * 1000
        return None
    
    @property
    def total_latency_ms(self) -> Optional[float]:
        """Total end-to-end latency for the frame in milliseconds."""
        if self.encode_start_time and self.render_time:
            return (self.render_time - self.encode_start_time) * 1000
        return None


class WebRTCBenchmark:
    """Comprehensive benchmarking system for WebRTC streaming performance.
    
    This class enables detailed performance benchmarking of WebRTC connections,
    providing insights into network conditions, codec efficiency, latency,
    and resource utilization.
    
    Features:
    - Connection establishment timing
    - Network throughput and stability analysis
    - Video codec performance benchmarking
    - End-to-end latency measurement
    - Resource utilization tracking (CPU, memory, bandwidth)
    - Quality of Experience metrics
    - Regression testing capabilities
    - Automatic report generation
    
    The benchmarking system operates with minimal performance impact on the 
    actual streaming process and can be enabled/disabled as needed.
    """
    
    def __init__(self, 
                 connection_id: str, 
                 cid: str,
                 enable_frame_stats: bool = True,
                 max_frame_stats: int = 1000,
                 interval_ms: int = 500,
                 report_dir: Optional[str] = None):
        """
        Initialize a new benchmark session for a WebRTC connection.
        
        Args:
            connection_id: Unique ID of the WebRTC connection
            cid: Content ID being streamed
            enable_frame_stats: Whether to collect per-frame statistics
            max_frame_stats: Maximum number of frame stats to keep in memory
            interval_ms: Interval between periodic measurements in milliseconds
            report_dir: Directory to save benchmark reports
        """
        # Connection information
        self.connection_id = connection_id
        self.cid = cid
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        
        # Configuration
        self.enable_frame_stats = enable_frame_stats
        self.max_frame_stats = max_frame_stats
        self.interval_ms = interval_ms
        self.report_dir = report_dir
        
        # Create report directory if specified
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        
        # Basic metrics
        self.connection_metrics = {
            "ice_gathering_time_ms": None,
            "ice_connection_time_ms": None,
            "dtls_setup_time_ms": None,
            "first_frame_time_ms": None,
            "reconnection_count": 0,
            "reconnection_times_ms": [],
            "ice_candidate_counts": {
                "host": 0,
                "srflx": 0,
                "prflx": 0,
                "relay": 0
            }
        }
        
        # Detailed time series metrics
        self.time_series = {
            "timestamps": [],
            "rtt_ms": [],
            "jitter_ms": [],
            "packet_loss_percent": [],
            "bitrate_kbps": [],
            "available_bitrate_kbps": [],
            "frames_per_second": [],
            "resolution_width": [],
            "resolution_height": [],
            "cpu_percent": [],
            "quality_score": []
        }
        
        # Frame statistics
        self.frame_stats: List[WebRTCFrameStat] = []
        self.frame_count = 0
        self.keyframe_count = 0
        
        # Network stats
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_lost = 0
        
        # Codec information
        self.video_codec = ""
        self.audio_codec = ""
        self.video_parameters = {}
        self.audio_parameters = {}
        
        # Internal state
        self._active = True
        self._task = None
        self._lock = anyio.Lock()
        
        # Start the benchmark
        logger.info(f"Starting WebRTC benchmark for connection {connection_id}")
    
    async def start_monitoring(self):
        """Start the periodic monitoring task."""
        if self._task is None:
            self._task = anyio.create_task(self._monitoring_task())
            logger.debug(f"Benchmark monitoring started for connection {self.connection_id}")
    
    async def stop(self):
        """Stop the benchmark and finalize measurements."""
        if not self._active:
            return
            
        self._active = False
        self.end_time = time.time()
        
        # Cancel the monitoring task if it exists
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except anyio.CancelledError:
                pass
            self._task = None
        
        # Generate final report
        if self.report_dir:
            await self.generate_report()
            
        logger.info(f"Benchmark stopped for connection {self.connection_id} after " 
                   f"{self.end_time - self.start_time:.2f} seconds")
    
    async def _monitoring_task(self):
        """Background task for periodic metric collection."""
        try:
            while self._active:
                await self._collect_periodic_metrics()
                await anyio.sleep(self.interval_ms / 1000)
        except anyio.CancelledError:
            logger.debug(f"Benchmark monitoring task cancelled for {self.connection_id}")
            raise
        except Exception as e:
            logger.error(f"Error in benchmark monitoring task: {e}")
    
    async def _collect_periodic_metrics(self):
        """Collect periodic metrics at regular intervals."""
        # This method is meant to be overridden by the WebRTCStreamingManager integration
        # Default implementation does nothing
        pass
    
    def record_connection_event(self, event_type: str, data: Dict[str, Any]):
        """
        Record a connection lifecycle event.
        
        Args:
            event_type: Type of event (e.g., 'ice_candidate', 'connected', 'first_frame')
            data: Event-specific data
        """
        now = time.time()
        
        if event_type == "ice_gathering_start":
            # Mark the start of ICE gathering
            self._ice_gathering_start = now
            
        elif event_type == "ice_gathering_complete":
            # Record ICE gathering time
            if hasattr(self, "_ice_gathering_start"):
                self.connection_metrics["ice_gathering_time_ms"] = (now - self._ice_gathering_start) * 1000
        
        elif event_type == "ice_connection_start":
            # Mark the start of ICE connection establishment
            self._ice_connection_start = now
            
        elif event_type == "ice_connected":
            # Record ICE connection time
            if hasattr(self, "_ice_connection_start"):
                self.connection_metrics["ice_connection_time_ms"] = (now - self._ice_connection_start) * 1000
        
        elif event_type == "dtls_start":
            # Mark the start of DTLS handshake
            self._dtls_start = now
            
        elif event_type == "dtls_connected":
            # Record DTLS setup time
            if hasattr(self, "_dtls_start"):
                self.connection_metrics["dtls_setup_time_ms"] = (now - self._dtls_start) * 1000
        
        elif event_type == "first_frame":
            # Record time to first frame
            self.connection_metrics["first_frame_time_ms"] = (now - self.start_time) * 1000
        
        elif event_type == "reconnection":
            # Record reconnection event
            self.connection_metrics["reconnection_count"] += 1
            if "duration_ms" in data:
                self.connection_metrics["reconnection_times_ms"].append(data["duration_ms"])
        
        elif event_type == "ice_candidate":
            # Count ICE candidate types
            if "candidate_type" in data:
                candidate_type = data["candidate_type"]
                if candidate_type in self.connection_metrics["ice_candidate_counts"]:
                    self.connection_metrics["ice_candidate_counts"][candidate_type] += 1
                    
        elif event_type == "codec_selected":
            # Record codec information
            if "kind" in data:
                if data["kind"] == "video":
                    self.video_codec = data.get("codec", "")
                    self.video_parameters = data.get("parameters", {})
                elif data["kind"] == "audio":
                    self.audio_codec = data.get("codec", "")
                    self.audio_parameters = data.get("parameters", {})
    
    def update_stats(self, stats: Dict[str, Any]):
        """
        Update benchmark with current WebRTC stats.
        
        Args:
            stats: WebRTC stats dictionary containing network and media metrics
        """
        # Record timestamp
        now = time.time()
        self.time_series["timestamps"].append(now)
        
        # Extract metrics from stats
        rtt_ms = stats.get("rtt", 0)
        jitter_ms = stats.get("jitter", 0)
        packet_loss = stats.get("packet_loss", 0)
        bitrate = stats.get("bitrate", 0) / 1000  # Convert to kbps
        available_bitrate = stats.get("bandwidth_estimate", 0) / 1000  # Convert to kbps
        fps = stats.get("frames_per_second", 0)
        width = stats.get("resolution_width", 0)
        height = stats.get("resolution_height", 0)
        cpu = stats.get("cpu_percent", 0)
        
        # Calculate quality score (simple weighted formula)
        # Lower RTT, jitter, and packet loss are better; higher bitrate is better
        quality_score = 0
        if rtt_ms > 0 and jitter_ms > 0 and bitrate > 0:
            # Normalize metrics to 0-1 scale
            normalized_rtt = min(1.0, rtt_ms / 500)  # 500ms or higher = 1.0
            normalized_jitter = min(1.0, jitter_ms / 100)  # 100ms or higher = 1.0
            normalized_loss = min(1.0, packet_loss / 10)  # 10% or higher = 1.0
            normalized_bitrate = min(1.0, bitrate / 4000)  # 4Mbps or higher = 1.0
            
            # Compute quality score (0-100)
            quality_score = 100 * (
                0.3 * (1 - normalized_rtt) +
                0.2 * (1 - normalized_jitter) +
                0.3 * (1 - normalized_loss) +
                0.2 * normalized_bitrate
            )
        
        # Update cumulative stats
        self.bytes_sent += stats.get("bytes_sent_delta", 0)
        self.bytes_received += stats.get("bytes_received_delta", 0)
        self.packets_sent += stats.get("packets_sent_delta", 0)
        self.packets_received += stats.get("packets_received_delta", 0)
        self.packets_lost += stats.get("packets_lost_delta", 0)
        
        # Update time series
        self.time_series["rtt_ms"].append(rtt_ms)
        self.time_series["jitter_ms"].append(jitter_ms)
        self.time_series["packet_loss_percent"].append(packet_loss)
        self.time_series["bitrate_kbps"].append(bitrate)
        self.time_series["available_bitrate_kbps"].append(available_bitrate)
        self.time_series["frames_per_second"].append(fps)
        self.time_series["resolution_width"].append(width)
        self.time_series["resolution_height"].append(height)
        self.time_series["cpu_percent"].append(cpu)
        self.time_series["quality_score"].append(quality_score)
    
    def add_frame_stat(self, frame_stat: WebRTCFrameStat):
        """
        Add a new frame statistic to the benchmark.
        
        Args:
            frame_stat: Statistics for a single frame
        """
        if not self.enable_frame_stats:
            return
            
        # Add to frame stats list, respecting maximum limit
        self.frame_stats.append(frame_stat)
        if len(self.frame_stats) > self.max_frame_stats:
            self.frame_stats.pop(0)  # Remove oldest stat
        
        # Update frame counters
        self.frame_count += 1
        
        # Update keyframe counter if this is a keyframe
        if frame_stat.is_keyframe:
            self.keyframe_count += 1
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get a summary of important benchmark statistics.
        
        Returns:
            Dictionary with summary statistics
        """
        duration = (self.end_time or time.time()) - self.start_time
        
        # Calculate average values for time series metrics
        avg_rtt = statistics.mean(self.time_series["rtt_ms"]) if self.time_series["rtt_ms"] else 0
        avg_jitter = statistics.mean(self.time_series["jitter_ms"]) if self.time_series["jitter_ms"] else 0
        avg_loss = statistics.mean(self.time_series["packet_loss_percent"]) if self.time_series["packet_loss_percent"] else 0
        avg_bitrate = statistics.mean(self.time_series["bitrate_kbps"]) if self.time_series["bitrate_kbps"] else 0
        avg_fps = statistics.mean(self.time_series["frames_per_second"]) if self.time_series["frames_per_second"] else 0
        avg_quality = statistics.mean(self.time_series["quality_score"]) if self.time_series["quality_score"] else 0
        
        # Calculate latency metrics from frame stats
        frame_latencies = [fs.total_latency_ms for fs in self.frame_stats if fs.total_latency_ms is not None]
        avg_latency = statistics.mean(frame_latencies) if frame_latencies else None
        p50_latency = statistics.median(frame_latencies) if frame_latencies else None
        p95_latency = None
        if frame_latencies:
            frame_latencies.sort()
            p95_index = int(0.95 * len(frame_latencies))
            p95_latency = frame_latencies[p95_index]
        
        # Throughput calculations
        bytes_per_second = self.bytes_sent / duration if duration > 0 else 0
        
        return {
            "connection_id": self.connection_id,
            "cid": self.cid,
            "duration_sec": duration,
            "ice_gathering_time_ms": self.connection_metrics["ice_gathering_time_ms"],
            "ice_connection_time_ms": self.connection_metrics["ice_connection_time_ms"],
            "first_frame_time_ms": self.connection_metrics["first_frame_time_ms"],
            "reconnection_count": self.connection_metrics["reconnection_count"],
            "avg_rtt_ms": avg_rtt,
            "avg_jitter_ms": avg_jitter,
            "avg_packet_loss_percent": avg_loss,
            "avg_bitrate_kbps": avg_bitrate,
            "avg_frames_per_second": avg_fps,
            "total_frames": self.frame_count,
            "keyframe_ratio": self.keyframe_count / self.frame_count if self.frame_count > 0 else 0,
            "avg_end_to_end_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "throughput_bytes_per_sec": bytes_per_second,
            "throughput_mbps": bytes_per_second * 8 / 1_000_000,
            "packet_loss_rate": self.packets_lost / max(1, self.packets_sent + self.packets_received),
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "avg_quality_score": avg_quality,
            "ice_candidates": self.connection_metrics["ice_candidate_counts"]
        }
    
    async def generate_report(self) -> str:
        """
        Generate a comprehensive benchmark report.
        
        Returns:
            Path to the saved report file
        """
        if not self.report_dir:
            logger.warning("Cannot generate report: report_dir not specified")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"webrtc_benchmark_{self.connection_id}_{timestamp}.json")
        
        # Prepare summary report
        summary = self.get_summary_stats()
        
        # Add time series data
        time_series = {
            key: value for key, value in self.time_series.items()
            if key != "timestamps"  # Exclude raw timestamps
        }
        
        # Add connection events timeline
        events = []
        if self.connection_metrics["ice_gathering_time_ms"]:
            events.append({
                "event": "ICE Gathering Complete",
                "time_ms": self.connection_metrics["ice_gathering_time_ms"]
            })
        if self.connection_metrics["ice_connection_time_ms"]:
            events.append({
                "event": "ICE Connected",
                "time_ms": self.connection_metrics["ice_connection_time_ms"]
            })
        if self.connection_metrics["dtls_setup_time_ms"]:
            events.append({
                "event": "DTLS Connected",
                "time_ms": self.connection_metrics["dtls_setup_time_ms"]
            })
        if self.connection_metrics["first_frame_time_ms"]:
            events.append({
                "event": "First Frame",
                "time_ms": self.connection_metrics["first_frame_time_ms"]
            })
        
        # Full report structure
        report = {
            "summary": summary,
            "time_series": time_series,
            "events": events,
            "config": {
                "enable_frame_stats": self.enable_frame_stats,
                "max_frame_stats": self.max_frame_stats,
                "interval_ms": self.interval_ms
            }
        }
        
        # Write report to file
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Benchmark report saved to {report_file}")
        return report_file
    
    @staticmethod
    async def compare_benchmarks(benchmark1: str, benchmark2: str) -> Dict[str, Any]:
        """
        Compare two benchmark reports and generate a comparison report.
        
        Args:
            benchmark1: Path to first benchmark report
            benchmark2: Path to second benchmark report
            
        Returns:
            Dictionary with comparison metrics
        """
        # Load benchmark reports
        try:
            with open(benchmark1, 'r') as f1:
                report1 = json.load(f1)
                
            with open(benchmark2, 'r') as f2:
                report2 = json.load(f2)
                
            summary1 = report1["summary"]
            summary2 = report2["summary"]
            
            # Calculate differences and percentage changes
            comparison = {}
            for key in summary1:
                if key in summary2 and isinstance(summary1[key], (int, float)) and summary1[key] != 0:
                    difference = summary2[key] - summary1[key]
                    percent_change = (difference / summary1[key]) * 100
                    
                    comparison[key] = {
                        "baseline": summary1[key],
                        "current": summary2[key],
                        "difference": difference,
                        "percent_change": percent_change,
                        "regression": WebRTCBenchmark._is_regression(key, percent_change)
                    }
            
            # Generate regression indicators
            regressions = [k for k, v in comparison.items() if v.get("regression", False)]
            improvements = [k for k, v in comparison.items() 
                          if "regression" in v and v["percent_change"] != 0 and not v["regression"]]
            
            # Overall assessment
            if len(regressions) > len(improvements):
                assessment = "Performance regression detected"
            elif len(improvements) > len(regressions):
                assessment = "Performance improvement detected"
            else:
                assessment = "Performance unchanged"
                
            return {
                "comparison": comparison,
                "regressions": regressions,
                "improvements": improvements,
                "assessment": assessment
            }
            
        except Exception as e:
            logger.error(f"Error comparing benchmarks: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _is_regression(metric: str, percent_change: float) -> bool:
        """
        Determine if a metric change represents a regression.
        
        Args:
            metric: Metric name
            percent_change: Percentage change in the metric
            
        Returns:
            Boolean indicating if this is a regression
        """
        # Define which direction is a regression for each metric
        regression_if_increases = {
            "ice_gathering_time_ms", "ice_connection_time_ms", "first_frame_time_ms",
            "reconnection_count", "avg_rtt_ms", "avg_jitter_ms", "avg_packet_loss_percent",
            "p50_latency_ms", "p95_latency_ms", "keyframe_ratio", "avg_end_to_end_latency_ms",
            "packet_loss_rate"
        }
        
        regression_if_decreases = {
            "avg_bitrate_kbps", "avg_frames_per_second", "throughput_bytes_per_sec",
            "throughput_mbps", "avg_quality_score"
        }
        
        # Threshold for significant change (5%)
        threshold = 5.0
        
        if abs(percent_change) < threshold:
            return False  # Change not significant enough
            
        if metric in regression_if_increases and percent_change > 0:
            return True
            
        if metric in regression_if_decreases and percent_change < 0:
            return True
            
        return False


class WebRTCStreamingManagerBenchmarkIntegration:
    """Helper class to integrate WebRTCBenchmark with WebRTCStreamingManager."""
    
    @staticmethod
    def add_benchmarking_to_manager(manager, enable_benchmarking=True, benchmark_reports_dir=None):
        """
        Add benchmarking capabilities to an existing WebRTCStreamingManager instance.
        
        Args:
            manager: WebRTCStreamingManager instance
            enable_benchmarking: Whether to enable benchmarking
            benchmark_reports_dir: Directory to save benchmark reports
            
        Returns:
            Modified manager with benchmarking capabilities
        """
        # Add benchmarking attributes
        manager.enable_benchmarking = enable_benchmarking
        manager.benchmark_reports_dir = benchmark_reports_dir
        
        if enable_benchmarking and not benchmark_reports_dir:
            # Default to a reports directory
            manager.benchmark_reports_dir = os.path.join(
                os.path.expanduser("~"), ".ipfs_kit", "webrtc_benchmarks"
            )
            os.makedirs(manager.benchmark_reports_dir, exist_ok=True)
        
        # Initialize benchmarks dictionary
        manager.benchmarks = {}
        
        # Add benchmarking methods to the manager
        manager.start_benchmark = WebRTCStreamingManagerBenchmarkIntegration._start_benchmark.__get__(manager)
        manager.stop_benchmark = WebRTCStreamingManagerBenchmarkIntegration._stop_benchmark.__get__(manager)
        manager._record_benchmark_stats = WebRTCStreamingManagerBenchmarkIntegration._record_benchmark_stats.__get__(manager)
        manager.get_benchmark_stats = WebRTCStreamingManagerBenchmarkIntegration._get_benchmark_stats.__get__(manager)
        manager.generate_benchmark_report = WebRTCStreamingManagerBenchmarkIntegration._generate_benchmark_report.__get__(manager)
        manager.record_frame_stat = WebRTCStreamingManagerBenchmarkIntegration._record_frame_stat.__get__(manager)
        
        # Add static method
        manager.compare_benchmark_reports = WebRTCBenchmark.compare_benchmarks
        
        # Patch create_offer to record benchmark events
        original_create_offer = manager.create_offer
        
        async def patched_create_offer(*args, **kwargs):
            result = await original_create_offer(*args, **kwargs)
            
            # Auto-start benchmark for new connections if enabled
            if getattr(manager, 'enable_benchmarking', False) and result and 'pc_id' in result:
                pc_id = result['pc_id']
                
                # Record ICE gathering start
                if hasattr(manager, 'benchmarks') and pc_id in manager.benchmarks:
                    manager.benchmarks[pc_id].record_connection_event(
                        "ice_gathering_start", {}
                    )
                # Otherwise auto-start benchmark
                elif getattr(manager, 'enable_benchmarking', False):
                    cid = args[0] if len(args) > 0 else kwargs.get('cid')
                    _ = manager.start_benchmark(pc_id=pc_id)
                    if hasattr(manager, 'benchmarks') and pc_id in manager.benchmarks:
                        manager.benchmarks[pc_id].record_connection_event(
                            "ice_gathering_start", {}
                        )
                    
            return result
            
        manager.create_offer = patched_create_offer
        
        # Also patch other connection-related methods
        if hasattr(manager, '_update_connection_stats'):
            original_update_stats = manager._update_connection_stats
            
            async def patched_update_stats(*args, **kwargs):
                result = await original_update_stats(*args, **kwargs)
                
                # Record stats for benchmarks if available
                pc_id = args[0] if len(args) > 0 else None
                if pc_id and hasattr(manager, 'benchmarks') and pc_id in manager.benchmarks:
                    await manager._record_benchmark_stats(pc_id)
                    
                return result
                
            manager._update_connection_stats = patched_update_stats
        
        # Override handle_ice_state_change to record events
        if hasattr(manager, '_handle_ice_connection_state_change'):
            original_ice_state = manager._handle_ice_connection_state_change
            
            async def patched_ice_state(pc_id, state):
                result = await original_ice_state(pc_id, state)
                
                # Record state change in benchmark
                if hasattr(manager, 'benchmarks') and pc_id in manager.benchmarks:
                    if state == "connected":
                        manager.benchmarks[pc_id].record_connection_event(
                            "ice_connected", {}
                        )
                    
                return result
                
            manager._handle_ice_connection_state_change = patched_ice_state
        
        return manager
    
    @staticmethod
    def _start_benchmark(self, pc_id=None, include_frame_stats=True, max_frame_stats=1000):
        """Start benchmarking a specific WebRTC connection or all connections."""
        result = {"success": False, "benchmarks_started": []}
        
        # Exit early if benchmarking is not enabled
        if not getattr(self, 'enable_benchmarking', False):
            logger.warning("Benchmarking is not enabled. Initialize WebRTCStreamingManager with enable_benchmarking=True")
            result["error"] = "Benchmarking not enabled"
            return result
            
        # Get connections to benchmark
        connections = []
        if pc_id:
            if pc_id in self.peer_connections:
                connections = [(pc_id, self.peer_connections[pc_id])]
            else:
                result["error"] = f"Connection {pc_id} not found"
                return result
        else:
            connections = list(self.peer_connections.items())
            
        # Start benchmarks for each connection
        for conn_id, pc in connections:
            if conn_id in getattr(self, 'benchmarks', {}):
                # Already benchmarking this connection
                result["benchmarks_started"].append({"pc_id": conn_id, "status": "already_running"})
                continue
                
            # Get CID for this connection
            cid = None
            if conn_id in self.connection_stats:
                cid = self.connection_stats[conn_id].get("cid", "unknown")
                
            # Create benchmark
            try:
                if not hasattr(self, 'benchmarks'):
                    self.benchmarks = {}
                    
                self.benchmarks[conn_id] = WebRTCBenchmark(
                    connection_id=conn_id,
                    cid=cid,
                    enable_frame_stats=include_frame_stats,
                    max_frame_stats=max_frame_stats,
                    report_dir=getattr(self, 'benchmark_reports_dir', None)
                )
                
                # Start monitoring
                anyio.create_task(self.benchmarks[conn_id].start_monitoring())
                
                # Record ICE events if we already have them
                if conn_id in self.connection_stats:
                    stats = self.connection_stats[conn_id]
                    if "ice_gathering_time" in stats:
                        self.benchmarks[conn_id].record_connection_event(
                            "ice_gathering_complete", 
                            {"duration_ms": stats["ice_gathering_time"]}
                        )
                        
                    if "connection_time" in stats:
                        self.benchmarks[conn_id].record_connection_event(
                            "ice_connected", 
                            {"duration_ms": stats["connection_time"]}
                        )
                
                # Set up to record RTC stats
                anyio.create_task(self._record_benchmark_stats(conn_id))
                
                result["benchmarks_started"].append({"pc_id": conn_id, "status": "started"})
                
            except Exception as e:
                logger.error(f"Error starting benchmark for {conn_id}: {e}")
                result["benchmarks_started"].append({"pc_id": conn_id, "status": "error", "error": str(e)})
                
        result["success"] = any(item["status"] == "started" for item in result["benchmarks_started"])
        return result
    
    @staticmethod
    def _stop_benchmark(self, pc_id=None):
        """Stop benchmarking a specific WebRTC connection or all connections."""
        result = {"success": False, "benchmarks_stopped": []}
        
        # Make sure we have benchmarks
        if not hasattr(self, 'benchmarks') or not self.benchmarks:
            result["error"] = "No active benchmarks found"
            return result
            
        # Get benchmarks to stop
        benchmarks_to_stop = []
        if pc_id:
            if pc_id in self.benchmarks:
                benchmarks_to_stop = [pc_id]
            else:
                result["error"] = f"No active benchmark for connection {pc_id}"
                return result
        else:
            benchmarks_to_stop = list(self.benchmarks.keys())
            
        # Stop each benchmark
        for conn_id in benchmarks_to_stop:
            try:
                # Get summary before stopping
                summary = self.benchmarks[conn_id].get_summary_stats()
                
                # Schedule stop task
                anyio.create_task(self.benchmarks[conn_id].stop())
                
                # Record result
                result["benchmarks_stopped"].append({
                    "pc_id": conn_id,
                    "status": "stopped",
                    "summary": summary
                })
                
                # Remove from active benchmarks (leave in dictionary until fully stopped)
                
            except Exception as e:
                logger.error(f"Error stopping benchmark for {conn_id}: {e}")
                result["benchmarks_stopped"].append({
                    "pc_id": conn_id, 
                    "status": "error", 
                    "error": str(e)
                })
                
        result["success"] = any(item["status"] == "stopped" for item in result["benchmarks_stopped"])
        return result
    
    @staticmethod
    async def _record_benchmark_stats(self, pc_id):
        """Record WebRTC statistics to benchmark object."""
        if not hasattr(self, 'benchmarks') or pc_id not in self.benchmarks:
            return
            
        # Make sure connection exists
        if pc_id not in self.peer_connections:
            return
            
        try:
            pc = self.peer_connections[pc_id]
            
            # Get connection stats from WebRTC
            if pc.connectionState == "connected":
                # Get stats from the peer connection
                rtc_stats = await pc.getStats()
                
                # Extract relevant metrics for the benchmark
                processed_stats = {
                    "rtt": 0,
                    "jitter": 0,
                    "packet_loss": 0,
                    "bitrate": 0,
                    "bandwidth_estimate": 0,
                    "frames_per_second": 0,
                    "bytes_sent_delta": 0,
                    "bytes_received_delta": 0,
                    "packets_sent_delta": 0,
                    "packets_received_delta": 0,
                    "packets_lost_delta": 0,
                    "resolution_width": 0,
                    "resolution_height": 0,
                    "cpu_percent": 0
                }
                
                # Process various statistics from different stat types
                for stat in rtc_stats.values():
                    if stat.type == "candidate-pair" and stat.state == "succeeded":
                        # ICE candidate pair statistics
                        processed_stats["rtt"] = getattr(stat, "currentRoundTripTime", 0) * 1000  # Convert to ms
                        
                    elif stat.type in ["outbound-rtp", "outboundrtp"]:
                        # Outbound media statistics
                        if hasattr(stat, "framesPerSecond"):
                            processed_stats["frames_per_second"] = stat.framesPerSecond
                            
                        if hasattr(stat, "framesSent") and pc_id in self.connection_stats:
                            last_frames = self.connection_stats[pc_id].get("frames_sent", 0)
                            current_frames = getattr(stat, "framesSent", 0)
                            processed_stats["frames_per_second"] = current_frames - last_frames
                            
                        # Bytes sent
                        if hasattr(stat, "bytesSent"):
                            last_bytes = self.connection_stats[pc_id].get("bytes_sent", 0) if pc_id in self.connection_stats else 0
                            current_bytes = getattr(stat, "bytesSent", 0)
                            processed_stats["bytes_sent_delta"] = current_bytes - last_bytes
                            
                            # Calculate bitrate
                            time_delta = time.time() - self.connection_stats[pc_id].get("last_update", time.time() - 1) if pc_id in self.connection_stats else 1
                            if time_delta > 0:
                                processed_stats["bitrate"] = ((current_bytes - last_bytes) * 8) / time_delta  # in bps
                                
                        # Resolution for video
                        if hasattr(stat, "frameWidth") and hasattr(stat, "frameHeight"):
                            processed_stats["resolution_width"] = stat.frameWidth
                            processed_stats["resolution_height"] = stat.frameHeight
                            
                        # Packets sent
                        if hasattr(stat, "packetsSent"):
                            last_packets = self.connection_stats[pc_id].get("packets_sent", 0) if pc_id in self.connection_stats else 0
                            current_packets = getattr(stat, "packetsSent", 0)
                            processed_stats["packets_sent_delta"] = current_packets - last_packets
                            
                    elif stat.type in ["inbound-rtp", "inboundrtp"]:
                        # Inbound media statistics
                        if hasattr(stat, "jitter"):
                            processed_stats["jitter"] = stat.jitter * 1000  # Convert to ms
                            
                        if hasattr(stat, "packetsLost") and hasattr(stat, "packetsReceived"):
                            last_lost = self.connection_stats[pc_id].get("packets_lost", 0) if pc_id in self.connection_stats else 0
                            current_lost = getattr(stat, "packetsLost", 0)
                            processed_stats["packets_lost_delta"] = current_lost - last_lost
                            
                            total_packets = stat.packetsReceived + stat.packetsLost
                            if total_packets > 0:
                                processed_stats["packet_loss"] = (stat.packetsLost / total_packets) * 100
                                
                        # Bytes received
                        if hasattr(stat, "bytesReceived"):
                            last_bytes = self.connection_stats[pc_id].get("bytes_received", 0) if pc_id in self.connection_stats else 0
                            current_bytes = getattr(stat, "bytesReceived", 0)
                            processed_stats["bytes_received_delta"] = current_bytes - last_bytes
                            
                        # Packets received
                        if hasattr(stat, "packetsReceived"):
                            last_packets = self.connection_stats[pc_id].get("packets_received", 0) if pc_id in self.connection_stats else 0
                            current_packets = getattr(stat, "packetsReceived", 0)
                            processed_stats["packets_received_delta"] = current_packets - last_packets
                            
                    elif stat.type == "transport":
                        # Transport statistics including bandwidth estimation
                        if hasattr(stat, "availableOutgoingBitrate"):
                            processed_stats["bandwidth_estimate"] = stat.availableOutgoingBitrate  # in bps
                
                # Try to get CPU usage
                try:
                    import psutil
                    processed_stats["cpu_percent"] = psutil.cpu_percent(interval=None)
                except:
                    pass
                    
                # Update the benchmark with these stats
                self.benchmarks[pc_id].update_stats(processed_stats)
                
        except Exception as e:
            logger.error(f"Error recording benchmark stats for {pc_id}: {e}")
    
    @staticmethod
    def _get_benchmark_stats(self, pc_id=None):
        """Get current benchmark statistics for a connection or all connections."""
        result = {"success": False}
        
        # Make sure we have benchmarks
        if not hasattr(self, 'benchmarks') or not self.benchmarks:
            result["error"] = "No active benchmarks found"
            return result
            
        # Get stats for specific connection or all
        if pc_id:
            if pc_id in self.benchmarks:
                result["stats"] = self.benchmarks[pc_id].get_summary_stats()
                result["success"] = True
            else:
                result["error"] = f"No active benchmark for connection {pc_id}"
        else:
            # Get stats for all connections
            all_stats = {}
            for conn_id, benchmark in self.benchmarks.items():
                all_stats[conn_id] = benchmark.get_summary_stats()
                
            result["all_stats"] = all_stats
            result["success"] = True
            
        return result
    
    @staticmethod
    async def _generate_benchmark_report(self, pc_id=None):
        """Generate a benchmark report for a connection or all connections."""
        result = {"success": False, "reports": []}
        
        # Make sure we have benchmarks
        if not hasattr(self, 'benchmarks') or not self.benchmarks:
            result["error"] = "No active benchmarks found"
            return result
            
        # Generate reports for specific connection or all
        if pc_id:
            if pc_id in self.benchmarks:
                report_file = await self.benchmarks[pc_id].generate_report()
                result["reports"].append({"pc_id": pc_id, "report_file": report_file})
                result["success"] = True
            else:
                result["error"] = f"No active benchmark for connection {pc_id}"
        else:
            # Generate reports for all connections
            for conn_id, benchmark in self.benchmarks.items():
                report_file = await benchmark.generate_report()
                result["reports"].append({"pc_id": conn_id, "report_file": report_file})
                
            result["success"] = len(result["reports"]) > 0
            
        return result
    
    @staticmethod
    def _record_frame_stat(self, pc_id, frame_stat):
        """Record a frame statistic for benchmarking."""
        if not hasattr(self, 'benchmarks') or pc_id not in self.benchmarks:
            return False
            
        try:
            self.benchmarks[pc_id].add_frame_stat(frame_stat)
            return True
        except Exception as e:
            logger.error(f"Error recording frame stat for {pc_id}: {e}")
            return False


# Helper functions for creating frame stats
def create_frame_stat(
    size_bytes=0,
    codec="",
    is_keyframe=False,
    encode_start_time=None,
    encode_end_time=None
):
    """Create a new frame statistic object with the given parameters."""
    frame_stat = WebRTCFrameStat(
        size_bytes=size_bytes,
        codec=codec,
        is_keyframe=is_keyframe
    )
    
    if encode_start_time:
        frame_stat.encode_start_time = encode_start_time
        
    if encode_end_time:
        frame_stat.encode_end_time = encode_end_time
        
    return frame_stat


def track_frame_timing(frame_stat):
    """
    Context manager for tracking frame timing.
    
    Usage:
        frame_stat = create_frame_stat(size_bytes=1024, codec="VP8")
        with track_frame_timing(frame_stat) as tracker:
            # Process frame
            tracker.mark_send_start()
            # Send frame
            tracker.mark_send_end()
    """
    class FrameTracker:
        def __init__(self, frame_stat):
            self.frame_stat = frame_stat
            
        def mark_encode_start(self):
            self.frame_stat.encode_start_time = time.time()
            
        def mark_encode_end(self):
            self.frame_stat.encode_end_time = time.time()
            
        def mark_send_start(self):
            self.frame_stat.send_start_time = time.time()
            
        def mark_send_end(self):
            self.frame_stat.send_end_time = time.time()
            
        def mark_receive(self):
            self.frame_stat.receive_time = time.time()
            
        def mark_decode_start(self):
            self.frame_stat.decode_start_time = time.time()
            
        def mark_decode_end(self):
            self.frame_stat.decode_end_time = time.time()
            
        def mark_render(self):
            self.frame_stat.render_time = time.time()
    
    tracker = FrameTracker(frame_stat)
    return tracker