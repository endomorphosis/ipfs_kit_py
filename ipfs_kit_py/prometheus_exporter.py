"""
Prometheus metrics exporter for IPFS Kit.

This module provides a comprehensive Prometheus metrics exporter for IPFS Kit that exposes
various performance metrics from the PerformanceMetrics class in a format
that can be scraped by Prometheus.

The exporter integrates with the existing performance_metrics module and
exposes metrics via a dedicated HTTP endpoint that follows the Prometheus
exposition format. It includes specialized metrics for IPFS operations,
content management, and distributed state.
"""

import logging
import time
from typing import Dict, List, Optional, Set, Any

from .performance_metrics import PerformanceMetrics
# Import tiered_cache module for backward compatibility
import ipfs_kit_py.tiered_cache as tiered_cache

# Try to import Prometheus client
try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary, Info
    from prometheus_client.core import CollectorRegistry, GaugeMetricFamily, CounterMetricFamily
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for type checking
    class Counter:
        def inc(self, value=1):
            pass
        
    class Gauge:
        def set(self, value):
            pass
        
    class Histogram:
        def observe(self, value):
            pass
            
    class Summary:
        def observe(self, value):
            pass
    
    class Info:
        def info(self, info):
            pass
            
    class CollectorRegistry:
        def __init__(self):
            pass
    
    class GaugeMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass
            
    class CounterMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass


logger = logging.getLogger(__name__)


class IPFSMetricsCollector:
    """
    IPFS-specific metrics collector that provides additional metrics
    beyond the standard performance metrics.
    
    This collector can be registered with the Prometheus registry to
    provide specialized IPFS metrics like pin counts, peer connections,
    and content storage metrics.
    """
    
    def __init__(self, ipfs_instance, prefix="ipfs_specific"):
        """
        Initialize the IPFS metrics collector.
        
        Args:
            ipfs_instance: The IPFS instance to collect metrics from
            prefix: Prefix for metric names
        """
        self.ipfs = ipfs_instance
        self.prefix = prefix
        # Cache for expensive operations
        self.metrics_cache = {}
        self.last_update_time = 0
        self.cache_ttl = 30  # seconds
        
    def collect(self):
        """Collect IPFS-specific metrics."""
        # Check cache freshness
        current_time = time.time()
        if current_time - self.last_update_time > self.cache_ttl:
            self._update_metrics_cache()
            self.last_update_time = current_time
        
        # IPFS repo stats
        try:
            repo_stats = self.metrics_cache.get('repo_stats', {})
            repo_size = GaugeMetricFamily(
                f"{self.prefix}_repo_size_bytes",
                "Size of the IPFS repository in bytes",
                labels=["type"]
            )
            
            if repo_stats:
                repo_size.add_metric(["total"], repo_stats.get("repo_size", 0))
                repo_size.add_metric(["storage_max"], repo_stats.get("storage_max", 0))
                yield repo_size
                
                # Repo usage percentage
                repo_usage = GaugeMetricFamily(
                    f"{self.prefix}_repo_usage_percent",
                    "Usage percentage of the IPFS repository",
                    labels=[]
                )
                max_size = repo_stats.get("storage_max", 0)
                if max_size > 0:
                    usage_percent = (repo_stats.get("repo_size", 0) / max_size) * 100
                    repo_usage.add_metric([], usage_percent)
                    yield repo_usage
        except Exception as e:
            logger.warning(f"Error collecting repo metrics: {e}")
        
        # Pinned content metrics
        try:
            pin_stats = self.metrics_cache.get('pin_stats', {})
            pins_count = GaugeMetricFamily(
                f"{self.prefix}_pins_count",
                "Count of pinned content items",
                labels=["type"]
            )
            
            if pin_stats:
                pins_count.add_metric(["direct"], pin_stats.get("direct", 0))
                pins_count.add_metric(["recursive"], pin_stats.get("recursive", 0))
                pins_count.add_metric(["indirect"], pin_stats.get("indirect", 0))
                pins_count.add_metric(["total"], pin_stats.get("total", 0))
                yield pins_count
                
                # Pinned content size
                pinned_size = GaugeMetricFamily(
                    f"{self.prefix}_pinned_content_bytes",
                    "Size of pinned content in bytes",
                    labels=[]
                )
                pinned_size.add_metric([], pin_stats.get("size", 0))
                yield pinned_size
        except Exception as e:
            logger.warning(f"Error collecting pin metrics: {e}")
        
        # Peer connection metrics
        try:
            peer_stats = self.metrics_cache.get('peer_stats', {})
            peer_count = GaugeMetricFamily(
                f"{self.prefix}_peers_connected",
                "Number of connected peers",
                labels=[]
            )
            
            if peer_stats:
                peer_count.add_metric([], peer_stats.get("connected", 0))
                yield peer_count
                
                # Connection metrics by protocol 
                protocol_connections = GaugeMetricFamily(
                    f"{self.prefix}_protocol_connections",
                    "Number of connections by protocol",
                    labels=["protocol"]
                )
                
                for protocol, count in peer_stats.get("protocols", {}).items():
                    protocol_connections.add_metric([protocol], count)
                
                yield protocol_connections
        except Exception as e:
            logger.warning(f"Error collecting peer metrics: {e}")
        
        # Bandwidth metrics
        try:
            bandwidth_stats = self.metrics_cache.get('bandwidth_stats', {})
            if bandwidth_stats:
                bandwidth_rate = GaugeMetricFamily(
                    f"{self.prefix}_bandwidth_rate_bytes",
                    "Bandwidth rate in bytes per second",
                    labels=["direction"]
                )
                bandwidth_rate.add_metric(["in"], bandwidth_stats.get("rate_in", 0))
                bandwidth_rate.add_metric(["out"], bandwidth_stats.get("rate_out", 0))
                bandwidth_rate.add_metric(["total"], bandwidth_stats.get("rate_total", 0))
                yield bandwidth_rate
                
                # Total bandwidth
                bandwidth_total = CounterMetricFamily(
                    f"{self.prefix}_bandwidth_total_bytes",
                    "Total bandwidth used in bytes",
                    labels=["direction"]
                )
                bandwidth_total.add_metric(["in"], bandwidth_stats.get("total_in", 0))
                bandwidth_total.add_metric(["out"], bandwidth_stats.get("total_out", 0)) 
                bandwidth_total.add_metric(["total"], bandwidth_stats.get("total_in", 0) + bandwidth_stats.get("total_out", 0))
                yield bandwidth_total
        except Exception as e:
            logger.warning(f"Error collecting bandwidth metrics: {e}")
            
        # DHT metrics
        try:
            dht_stats = self.metrics_cache.get('dht_stats', {})
            if dht_stats:
                dht_peers = GaugeMetricFamily(
                    f"{self.prefix}_dht_peers",
                    "Number of peers in the DHT routing table",
                    labels=[]
                )
                dht_peers.add_metric([], dht_stats.get("peers", 0))
                yield dht_peers
                
                # DHT query metrics
                dht_queries = CounterMetricFamily(
                    f"{self.prefix}_dht_queries_total",
                    "Total number of DHT queries",
                    labels=["type"]
                )
                queries = dht_stats.get("queries", {})
                dht_queries.add_metric(["provider"], queries.get("provider", 0))
                dht_queries.add_metric(["find_peer"], queries.get("find_peer", 0))
                dht_queries.add_metric(["get_value"], queries.get("get_value", 0))
                yield dht_queries
        except Exception as e:
            logger.warning(f"Error collecting DHT metrics: {e}")
            
        # IPFS Cluster metrics (if available)
        try:
            cluster_stats = self.metrics_cache.get('cluster_stats', {})
            if cluster_stats:
                # Cluster peer count
                cluster_peers = GaugeMetricFamily(
                    f"{self.prefix}_cluster_peers",
                    "Number of peers in the IPFS cluster",
                    labels=[]
                )
                cluster_peers.add_metric([], cluster_stats.get("peer_count", 0))
                yield cluster_peers
                
                # Pins allocated to this node
                cluster_pins = GaugeMetricFamily(
                    f"{self.prefix}_cluster_pins",
                    "Number of pins allocated in the cluster",
                    labels=["status"]
                )
                pin_stats = cluster_stats.get("pins", {})
                cluster_pins.add_metric(["pinned"], pin_stats.get("pinned", 0))
                cluster_pins.add_metric(["pinning"], pin_stats.get("pinning", 0))
                cluster_pins.add_metric(["queued"], pin_stats.get("queued", 0))
                cluster_pins.add_metric(["error"], pin_stats.get("error", 0))
                yield cluster_pins
                
                # Cluster role
                cluster_role = GaugeMetricFamily(
                    f"{self.prefix}_cluster_role",
                    "Current role in the IPFS cluster (1=master, 2=worker, 3=leecher)",
                    labels=["role"]
                )
                role = cluster_stats.get("role", "")
                if role == "master":
                    cluster_role.add_metric(["master"], 1)
                    cluster_role.add_metric(["worker"], 0)
                    cluster_role.add_metric(["leecher"], 0)
                elif role == "worker":
                    cluster_role.add_metric(["master"], 0)
                    cluster_role.add_metric(["worker"], 1)
                    cluster_role.add_metric(["leecher"], 0)
                elif role == "leecher":
                    cluster_role.add_metric(["master"], 0)
                    cluster_role.add_metric(["worker"], 0)
                    cluster_role.add_metric(["leecher"], 1)
                yield cluster_role
        except Exception as e:
            logger.warning(f"Error collecting cluster metrics: {e}")
        
        # Cache-specific metrics
        try:
            cache_stats = self.metrics_cache.get('cache_stats', {})
            if cache_stats:
                cache_entries = GaugeMetricFamily(
                    f"{self.prefix}_cache_entries",
                    "Number of entries in the cache",
                    labels=["tier"]
                )
                
                for tier, stats in cache_stats.items():
                    cache_entries.add_metric([tier], stats.get("entries", 0))
                yield cache_entries
                
                # Cache size
                cache_size = GaugeMetricFamily(
                    f"{self.prefix}_cache_size_bytes",
                    "Size of the cache in bytes",
                    labels=["tier"]
                )
                
                for tier, stats in cache_stats.items():
                    cache_size.add_metric([tier], stats.get("size", 0))
                yield cache_size
                
                # Cache capacity
                cache_capacity = GaugeMetricFamily(
                    f"{self.prefix}_cache_capacity_bytes",
                    "Total capacity of the cache in bytes",
                    labels=["tier"]
                )
                
                for tier, stats in cache_stats.items():
                    cache_capacity.add_metric([tier], stats.get("capacity", 0))
                yield cache_capacity
                
                # Cache usage percentage
                cache_usage = GaugeMetricFamily(
                    f"{self.prefix}_cache_usage_percent",
                    "Usage percentage of the cache",
                    labels=["tier"]
                )
                
                for tier, stats in cache_stats.items():
                    capacity = stats.get("capacity", 0)
                    if capacity > 0:
                        usage_percent = (stats.get("size", 0) / capacity) * 100
                        cache_usage.add_metric([tier], usage_percent)
                yield cache_usage
        except Exception as e:
            logger.warning(f"Error collecting cache metrics: {e}")
    
    def _update_metrics_cache(self):
        """Update the metrics cache with current values (expensive operations)."""
        # Initialize cache
        self.metrics_cache = {}
        
        # Update repo stats
        try:
            repo_stats = self._get_repo_stats()
            if repo_stats:
                self.metrics_cache['repo_stats'] = repo_stats
        except Exception as e:
            logger.warning(f"Failed to get repo stats: {e}")
        
        # Update pin stats 
        try:
            pin_stats = self._get_pin_stats()
            if pin_stats:
                self.metrics_cache['pin_stats'] = pin_stats
        except Exception as e:
            logger.warning(f"Failed to get pin stats: {e}")
        
        # Update peer stats
        try:
            peer_stats = self._get_peer_stats()
            if peer_stats:
                self.metrics_cache['peer_stats'] = peer_stats
        except Exception as e:
            logger.warning(f"Failed to get peer stats: {e}")
            
        # Update bandwidth stats
        try:
            bandwidth_stats = self._get_bandwidth_stats()
            if bandwidth_stats:
                self.metrics_cache['bandwidth_stats'] = bandwidth_stats
        except Exception as e:
            logger.warning(f"Failed to get bandwidth stats: {e}")
            
        # Update DHT stats
        try:
            dht_stats = self._get_dht_stats()
            if dht_stats:
                self.metrics_cache['dht_stats'] = dht_stats
        except Exception as e:
            logger.warning(f"Failed to get DHT stats: {e}")
            
        # Update cluster stats if available
        try:
            cluster_stats = self._get_cluster_stats()
            if cluster_stats:
                self.metrics_cache['cluster_stats'] = cluster_stats
        except Exception as e:
            logger.warning(f"Failed to get cluster stats: {e}")
            
        # Update cache stats
        try:
            cache_stats = self._get_cache_stats()
            if cache_stats:
                self.metrics_cache['cache_stats'] = cache_stats
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
    
    def _get_repo_stats(self) -> Dict[str, Any]:
        """Get IPFS repository statistics."""
        # Using IPFS repo stat command
        if not hasattr(self.ipfs, "run_ipfs_command"):
            return {}
            
        try:
            result = self.ipfs.run_ipfs_command(["ipfs", "repo", "stat", "--human=false"])
            if result.get("success", False) and result.get("stdout"):
                import json
                stats = json.loads(result["stdout"])
                return {
                    "repo_size": int(stats.get("RepoSize", 0)),
                    "storage_max": int(stats.get("StorageMax", 0)),
                    "num_objects": int(stats.get("NumObjects", 0))
                }
        except Exception as e:
            logger.warning(f"Error getting repo stats: {e}")
            
        return {}
    
    def _get_pin_stats(self) -> Dict[str, Any]:
        """Get statistics about pinned content."""
        # Using IPFS pin ls command
        if not hasattr(self.ipfs, "ipfs_ls_pin"):
            return {}
            
        try:
            result = self.ipfs.ipfs_ls_pin()
            if result.get("success", False) and "pins" in result:
                pins = result["pins"]
                direct_count = sum(1 for p in pins if pins[p] == "direct")
                recursive_count = sum(1 for p in pins if pins[p] == "recursive")
                indirect_count = sum(1 for p in pins if pins[p] == "indirect")
                
                # Calculate size (approximate as we don't have size for each pin)
                # This is a placeholder - in a real implementation we would track this
                size = 0
                if hasattr(self.ipfs, "run_ipfs_command"):
                    # Get size for a few pins to estimate
                    sampled_pins = list(pins.keys())[:min(5, len(pins))]
                    for pin in sampled_pins:
                        try:
                            size_result = self.ipfs.run_ipfs_command(["ipfs", "object", "stat", pin])
                            if size_result.get("success", False) and size_result.get("stdout"):
                                import json
                                stat_data = json.loads(size_result["stdout"])
                                size += int(stat_data.get("CumulativeSize", 0))
                        except Exception:
                            pass
                    
                    # Extrapolate to estimate total size
                    if sampled_pins:
                        avg_size = size / len(sampled_pins)
                        size = avg_size * len(pins)
                
                return {
                    "direct": direct_count,
                    "recursive": recursive_count,
                    "indirect": indirect_count,
                    "total": len(pins),
                    "size": int(size)
                }
        except Exception as e:
            logger.warning(f"Error getting pin stats: {e}")
            
        return {}
    
    def _get_peer_stats(self) -> Dict[str, Any]:
        """Get statistics about peer connections."""
        if not hasattr(self.ipfs, "run_ipfs_command"):
            return {}
            
        try:
            # Get connected peers
            result = self.ipfs.run_ipfs_command(["ipfs", "swarm", "peers"])
            peers = []
            if result.get("success", False) and result.get("stdout"):
                peers = result["stdout"].decode().strip().split("\n")
                if peers and peers[0] == "":
                    peers = []
            
            # Get protocols for connected peers
            protocols = {}
            for peer in peers[:min(10, len(peers))]:  # Sample to avoid excessive queries
                try:
                    peer_id = peer.split("/")[8] if len(peer.split("/")) > 8 else peer
                    proto_result = self.ipfs.run_ipfs_command(["ipfs", "swarm", "connect", peer_id])
                    if proto_result.get("success", False) and proto_result.get("stdout"):
                        import json
                        proto_data = json.loads(proto_result["stdout"])
                        for protocol in proto_data.get("Protocols", []):
                            protocols[protocol] = protocols.get(protocol, 0) + 1
                except Exception:
                    pass
            
            return {
                "connected": len(peers),
                "protocols": protocols
            }
        except Exception as e:
            logger.warning(f"Error getting peer stats: {e}")
            
        return {}
    
    def _get_bandwidth_stats(self) -> Dict[str, Any]:
        """Get bandwidth statistics."""
        if not hasattr(self.ipfs, "run_ipfs_command"):
            return {}
            
        try:
            result = self.ipfs.run_ipfs_command(["ipfs", "stats", "bw"])
            if result.get("success", False) and result.get("stdout"):
                import json
                stats = json.loads(result["stdout"])
                return {
                    "total_in": int(stats.get("TotalIn", 0)),
                    "total_out": int(stats.get("TotalOut", 0)),
                    "rate_in": float(stats.get("RateIn", 0)),
                    "rate_out": float(stats.get("RateOut", 0)),
                    "rate_total": float(stats.get("RateIn", 0)) + float(stats.get("RateOut", 0))
                }
        except Exception as e:
            logger.warning(f"Error getting bandwidth stats: {e}")
            
        return {}
    
    def _get_dht_stats(self) -> Dict[str, Any]:
        """Get DHT statistics."""
        if not hasattr(self.ipfs, "run_ipfs_command"):
            return {}
            
        try:
            # Get DHT stats (this is a basic implementation)
            # In a real implementation, we would parse more detailed DHT stats
            peers_result = self.ipfs.run_ipfs_command(["ipfs", "stats", "dht"])
            dht_stats = {"peers": 0, "queries": {"provider": 0, "find_peer": 0, "get_value": 0}}
            
            if peers_result.get("success", False) and peers_result.get("stdout"):
                import re
                lines = peers_result["stdout"].decode().strip().split("\n")
                for line in lines:
                    if "routing table size" in line:
                        matches = re.search(r"routing table size: (\d+)", line)
                        if matches:
                            dht_stats["peers"] = int(matches.group(1))
                    
                    if "provider" in line:
                        matches = re.search(r"provider: (\d+)", line)
                        if matches:
                            dht_stats["queries"]["provider"] = int(matches.group(1))
                    
                    if "peer" in line and "provider" not in line:
                        matches = re.search(r"peer: (\d+)", line)
                        if matches:
                            dht_stats["queries"]["find_peer"] = int(matches.group(1))
                    
                    if "value" in line:
                        matches = re.search(r"value: (\d+)", line)
                        if matches:
                            dht_stats["queries"]["get_value"] = int(matches.group(1))
            
            return dht_stats
        except Exception as e:
            logger.warning(f"Error getting DHT stats: {e}")
            
        return {}
    
    def _get_cluster_stats(self) -> Dict[str, Any]:
        """Get IPFS Cluster statistics if available."""
        # This requires IPFS Cluster to be installed and configured
        if not hasattr(self.ipfs, "run_ipfs_command"):
            return {}
            
        try:
            # Check if ipfs-cluster-ctl is available
            import shutil
            if not shutil.which("ipfs-cluster-ctl"):
                return {}
                
            # Get peers
            peers_result = self.ipfs.run_ipfs_command(["ipfs-cluster-ctl", "peers", "ls", "--format=json"])
            peers = []
            if peers_result.get("success", False) and peers_result.get("stdout"):
                import json
                try:
                    peers = json.loads(peers_result["stdout"])
                except json.JSONDecodeError:
                    # Handle output formats that might not be valid JSON
                    peers = peers_result["stdout"].decode().strip().split("\n")
            
            # Get pin status
            pins_result = self.ipfs.run_ipfs_command(["ipfs-cluster-ctl", "pin", "ls", "--format=json"])
            pin_stats = {"pinned": 0, "pinning": 0, "queued": 0, "error": 0}
            
            if pins_result.get("success", False) and pins_result.get("stdout"):
                import json
                try:
                    pins = json.loads(pins_result["stdout"])
                    for pin in pins:
                        status = pin.get("status", "")
                        if "pinned" in status:
                            pin_stats["pinned"] += 1
                        elif "pinning" in status:
                            pin_stats["pinning"] += 1
                        elif "queued" in status:
                            pin_stats["queued"] += 1
                        elif "error" in status:
                            pin_stats["error"] += 1
                except json.JSONDecodeError:
                    # Handle non-JSON output
                    pass
            
            # Determine role
            role = "unknown"
            if hasattr(self.ipfs, "role"):
                role = self.ipfs.role
            
            return {
                "peer_count": len(peers),
                "pins": pin_stats,
                "role": role
            }
        except Exception as e:
            logger.warning(f"Error getting cluster stats: {e}")
            
        return {}
    
    def _get_cache_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get cache statistics."""
        # This requires the tiered cache system
        if not hasattr(self.ipfs, "cache") and not hasattr(self.ipfs, "tiered_cache"):
            cache = getattr(self.ipfs, "cache", getattr(self.ipfs, "tiered_cache", None))
            if not cache:
                return {}
            
        try:
            cache_stats = {}
            
            # Try to get memory cache stats
            if hasattr(self.ipfs, "cache") and hasattr(self.ipfs.cache, "memory_cache"):
                memory_cache = self.ipfs.cache.memory_cache
                cache_stats["memory"] = {
                    "entries": len(memory_cache),
                    "size": sum(len(v) for v in memory_cache.values() if hasattr(v, "__len__")),
                    "capacity": getattr(memory_cache, "maxsize", 0),
                }
            
            # Try to get disk cache stats
            if hasattr(self.ipfs, "cache") and hasattr(self.ipfs.cache, "disk_cache"):
                disk_cache = self.ipfs.cache.disk_cache
                import os
                cache_dir = getattr(disk_cache, "directory", "")
                size = 0
                entries = 0
                
                if cache_dir and os.path.exists(cache_dir):
                    for root, _, files in os.walk(cache_dir):
                        entries += len(files)
                        size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
                
                cache_stats["disk"] = {
                    "entries": entries,
                    "size": size,
                    "capacity": getattr(disk_cache, "size_limit", 0),
                }
                
            # Try to get parquet cache stats if available through tiered_cache module
            if hasattr(tiered_cache, "parquet_cache") and tiered_cache.parquet_cache:
                parquet_cache = tiered_cache.parquet_cache
                import os
                cache_dir = getattr(parquet_cache, "directory", "")
                size = 0
                entries = 0
                
                if cache_dir and os.path.exists(cache_dir):
                    for root, _, files in os.walk(cache_dir):
                        entries += len(files)
                        size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
                
                cache_stats["parquet"] = {
                    "entries": entries,
                    "size": size,
                    "capacity": getattr(parquet_cache, "size_limit", 0),
                }
            
            return cache_stats
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")
            
        return {}


class PrometheusExporter:
    """
    Exports IPFS Kit metrics in Prometheus format.
    
    This class creates and updates Prometheus metrics based on the PerformanceMetrics
    class data, exposing them in a format that can be scraped by Prometheus.
    
    It includes detailed metrics for cache performance, operation latency,
    bandwidth usage, and error rates, as well as IPFS-specific metrics for
    content addressing and distributed networks.
    """
    
    def __init__(
        self,
        metrics: PerformanceMetrics,
        prefix: str = "ipfs",
        registry: Optional[CollectorRegistry] = None,
        labels: Optional[Dict[str, str]] = None,
        ipfs_instance=None,
    ):
        """
        Initialize the Prometheus exporter.
        
        Args:
            metrics: PerformanceMetrics instance to export
            prefix: Prefix for metric names
            registry: Optional Prometheus registry to use
            labels: Common labels to apply to all metrics
            ipfs_instance: Optional IPFS instance for additional metrics
        """
        self.metrics = metrics
        self.prefix = prefix
        self.labels = labels or {}
        self.ipfs_instance = ipfs_instance
        
        # Check if Prometheus client is available
        if not PROMETHEUS_AVAILABLE:
            logger.debug(
                "Prometheus client not available. Install with 'pip install prometheus-client'"
            )
            self.enabled = False
            return
            
        self.enabled = True
        self.registry = registry or CollectorRegistry()
        
        # Create metrics
        self._create_metrics()
        
        # Add IPFS-specific collector if instance is provided
        if self.ipfs_instance:
            self.ipfs_collector = IPFSMetricsCollector(self.ipfs_instance, f"{self.prefix}_specific")
            self.registry.register(self.ipfs_collector)
        
        # Set of operation names we've seen (for dynamic metrics)
        self.known_operations = set()
        
        # Track last update time
        self.last_update = 0
        
        # Add version info
        if PROMETHEUS_AVAILABLE:
            ipfs_info = Info(f"{self.prefix}_version_info", "IPFS version information", registry=self.registry)
            try:
                if self.ipfs_instance and hasattr(self.ipfs_instance, "run_ipfs_command"):
                    result = self.ipfs_instance.run_ipfs_command(["ipfs", "version"])
                    if result.get("success", False) and result.get("stdout"):
                        version = result["stdout"].decode().strip()
                        ipfs_info.info({"version": version, "build": "ipfs-kit-py"})
            except Exception as e:
                logger.debug(f"Error getting IPFS version info: {e}")
                ipfs_info.info({"version": "unknown", "build": "ipfs-kit-py"})
        
    def _create_metrics(self):
        """Create Prometheus metrics."""
        # Cache metrics
        self.cache_hits = Counter(
            f"{self.prefix}_cache_hits_total",
            "Total number of cache hits",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.cache_misses = Counter(
            f"{self.prefix}_cache_misses_total",
            "Total number of cache misses",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.cache_hit_ratio = Gauge(
            f"{self.prefix}_cache_hit_ratio",
            "Ratio of cache hits to total accesses",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Tier-specific cache metrics are created dynamically
        self.tier_hits = {}
        self.tier_misses = {}
        
        # Operation metrics
        self.operation_count = Counter(
            f"{self.prefix}_operations_total",
            "Count of IPFS operations by type",
            ["operation"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.operation_latency = Histogram(
            f"{self.prefix}_operation_latency_seconds",
            "Latency of IPFS operations",
            ["operation"] + list(self.labels.keys()),
            buckets=(
                0.005, 0.01, 0.025, 0.05, 0.075, 
                0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0, 120.0
            ),
            registry=self.registry,
        )
        
        # Bandwidth metrics
        self.bandwidth_inbound = Counter(
            f"{self.prefix}_bandwidth_inbound_bytes_total",
            "Total inbound bandwidth used",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.bandwidth_outbound = Counter(
            f"{self.prefix}_bandwidth_outbound_bytes_total",
            "Total outbound bandwidth used",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Error metrics
        self.errors_total = Counter(
            f"{self.prefix}_errors_total",
            "Total number of errors",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.error_count_by_type = Counter(
            f"{self.prefix}_errors_by_type_total",
            "Count of errors by type",
            ["error_type"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        # System metrics
        self.cpu_usage = Gauge(
            f"{self.prefix}_cpu_usage_percent",
            "CPU usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.memory_usage = Gauge(
            f"{self.prefix}_memory_usage_percent",
            "Memory usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.memory_available = Gauge(
            f"{self.prefix}_memory_available_bytes",
            "Available memory in bytes",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.disk_usage = Gauge(
            f"{self.prefix}_disk_usage_percent",
            "Disk usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.disk_free = Gauge(
            f"{self.prefix}_disk_free_bytes",
            "Free disk space in bytes",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Throughput metrics
        self.operations_per_second = Gauge(
            f"{self.prefix}_operations_per_second",
            "Operations per second",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.bytes_per_second = Gauge(
            f"{self.prefix}_bytes_per_second",
            "Bytes per second (total)",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Content management metrics
        self.content_adds = Counter(
            f"{self.prefix}_content_adds_total",
            "Total number of content items added",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.content_retrievals = Counter(
            f"{self.prefix}_content_retrievals_total",
            "Total number of content retrievals",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.content_pin_operations = Counter(
            f"{self.prefix}_content_pin_operations_total",
            "Total number of pin operations",
            ["operation"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Cluster metrics
        self.cluster_operations = Counter(
            f"{self.prefix}_cluster_operations_total",
            "Total number of IPFS cluster operations",
            ["operation"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        # AI/ML metrics if detected
        self.has_ai_ml = False
        try:
            import importlib
            if importlib.util.find_spec("ipfs_kit_py.ai_ml_integration"):
                self.has_ai_ml = True
                
                # AI/ML operation counts
                self.ai_ml_operations = Counter(
                    f"{self.prefix}_ai_ml_operations_total",
                    "Total number of AI/ML operations",
                    ["operation"] + list(self.labels.keys()),
                    registry=self.registry,
                )
                
                # Model metrics
                self.model_loading_time = Histogram(
                    f"{self.prefix}_model_loading_seconds", 
                    "Time taken to load AI models",
                    ["model_type"] + list(self.labels.keys()),
                    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
                    registry=self.registry,
                )
                
                # Inference metrics
                self.inference_time = Histogram(
                    f"{self.prefix}_inference_seconds",
                    "Time taken for model inference",
                    ["model_type"] + list(self.labels.keys()),
                    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
                    registry=self.registry,
                )
        except Exception as e:
            logger.debug(f"AI/ML metrics not enabled: {e}")
        
    def _ensure_tier_metrics(self, tier: str):
        """Ensure metrics exist for a specific cache tier."""
        if tier not in self.tier_hits:
            self.tier_hits[tier] = Counter(
                f"{self.prefix}_cache_tier_hits_total",
                "Total number of cache hits by tier",
                ["tier"] + list(self.labels.keys()),
                registry=self.registry,
            )
            
        if tier not in self.tier_misses:
            self.tier_misses[tier] = Counter(
                f"{self.prefix}_cache_tier_misses_total",
                "Total number of cache misses by tier",
                ["tier"] + list(self.labels.keys()),
                registry=self.registry,
            )
            
    def update(self):
        """Update Prometheus metrics from the performance metrics."""
        if not self.enabled:
            logger.debug("Prometheus exporter not enabled")
            return
            
        # Update timestamp
        self.last_update = time.time()
        
        try:
            # Update cache metrics
            cache_hits = self.metrics.cache["hits"]
            cache_misses = self.metrics.cache["misses"]
            total_accesses = cache_hits + cache_misses
            
            # Update with difference since last update to avoid double counting
            hit_diff = cache_hits - getattr(self, "_last_cache_hits", 0)
            miss_diff = cache_misses - getattr(self, "_last_cache_misses", 0)
            
            if hit_diff > 0:
                self.cache_hits.inc(hit_diff, labels=self.labels)
            if miss_diff > 0:
                self.cache_misses.inc(miss_diff, labels=self.labels)
                
            # Store current values for next calculation
            self._last_cache_hits = cache_hits
            self._last_cache_misses = cache_misses
            
            # Update cache hit ratio
            if total_accesses > 0:
                self.cache_hit_ratio.set(cache_hits / total_accesses, labels=self.labels)
            
            # Update tier-specific cache metrics
            for tier, stats in self.metrics.cache["tiers"].items():
                self._ensure_tier_metrics(tier)
                
                tier_hits = stats["hits"]
                tier_misses = stats["misses"]
                
                # Calculate differences since last update
                last_tier_hits = getattr(self, f"_last_tier_hits_{tier}", 0)
                last_tier_misses = getattr(self, f"_last_tier_misses_{tier}", 0)
                
                tier_hit_diff = tier_hits - last_tier_hits
                tier_miss_diff = tier_misses - last_tier_misses
                
                # Update metrics
                if tier_hit_diff > 0:
                    self.tier_hits[tier].inc(tier_hit_diff, labels={"tier": tier, **self.labels})
                if tier_miss_diff > 0:
                    self.tier_misses[tier].inc(tier_miss_diff, labels={"tier": tier, **self.labels})
                    
                # Store current values
                setattr(self, f"_last_tier_hits_{tier}", tier_hits)
                setattr(self, f"_last_tier_misses_{tier}", tier_misses)
            
            # Update operation metrics
            for op, count in self.metrics.operations.items():
                last_count = getattr(self, f"_last_op_count_{op}", 0)
                count_diff = count - last_count
                
                if count_diff > 0:
                    self.operation_count.inc(count_diff, labels={"operation": op, **self.labels})
                    
                    # Update specific operation counters based on operation name
                    if "add" in op.lower():
                        self.content_adds.inc(count_diff, labels=self.labels)
                    elif any(term in op.lower() for term in ["get", "cat", "read"]):
                        self.content_retrievals.inc(count_diff, labels=self.labels)
                    elif "pin" in op.lower():
                        pin_op = "add" if "add" in op.lower() else "remove" if "rm" in op.lower() else "list"
                        self.content_pin_operations.inc(count_diff, labels={"operation": pin_op, **self.labels})
                    elif "cluster" in op.lower():
                        cluster_op = op.lower().split("_")[-1] if "_" in op.lower() else op
                        self.cluster_operations.inc(count_diff, labels={"operation": cluster_op, **self.labels})
                    
                    # Update AI/ML metrics if available
                    if self.has_ai_ml and any(term in op.lower() for term in ["embed", "model", "inference", "predict"]):
                        ai_op = op.lower().split("_")[-1] if "_" in op.lower() else op
                        self.ai_ml_operations.inc(count_diff, labels={"operation": ai_op, **self.labels})
                    
                setattr(self, f"_last_op_count_{op}", count)
                
                # Track this operation for latency metrics
                self.known_operations.add(op)
            
            # Update operation latency metrics
            # For each known operation, get the latest metrics
            for op in self.known_operations:
                if op in self.metrics.latency and self.metrics.latency[op]:
                    latency_values = list(self.metrics.latency[op])
                    last_latency_count = getattr(self, f"_last_latency_count_{op}", 0)
                    
                    # Only process new latency values
                    if len(latency_values) > last_latency_count:
                        new_values = latency_values[last_latency_count:]
                        for val in new_values:
                            self.operation_latency.observe(val, labels={"operation": op, **self.labels})
                            
                            # Update model loading time if it's a model operation
                            if self.has_ai_ml and "load_model" in op:
                                model_type = op.split("_")[0] if "_" in op else "generic"
                                self.model_loading_time.observe(val, labels={"model_type": model_type, **self.labels})
                            
                            # Update inference time if it's an inference operation
                            if self.has_ai_ml and "inference" in op:
                                model_type = op.split("_")[0] if "_" in op else "generic"
                                self.inference_time.observe(val, labels={"model_type": model_type, **self.labels})
                            
                        setattr(self, f"_last_latency_count_{op}", len(latency_values))
            
            # Update bandwidth metrics
            inbound_total = sum(item["size"] for item in self.metrics.bandwidth["inbound"])
            outbound_total = sum(item["size"] for item in self.metrics.bandwidth["outbound"])
            
            last_inbound = getattr(self, "_last_inbound_total", 0)
            last_outbound = getattr(self, "_last_outbound_total", 0)
            
            inbound_diff = inbound_total - last_inbound
            outbound_diff = outbound_total - last_outbound
            
            if inbound_diff > 0:
                self.bandwidth_inbound.inc(inbound_diff, labels=self.labels)
            if outbound_diff > 0:
                self.bandwidth_outbound.inc(outbound_diff, labels=self.labels)
                
            self._last_inbound_total = inbound_total
            self._last_outbound_total = outbound_total
            
            # Update error metrics
            error_count = self.metrics.errors["count"]
            last_error_count = getattr(self, "_last_error_count", 0)
            error_diff = error_count - last_error_count
            
            if error_diff > 0:
                self.errors_total.inc(error_diff, labels=self.labels)
                
            self._last_error_count = error_count
            
            # Update error type metrics
            for error_type, count in self.metrics.errors["by_type"].items():
                last_type_count = getattr(self, f"_last_error_type_{error_type}", 0)
                type_diff = count - last_type_count
                
                if type_diff > 0:
                    self.error_count_by_type.inc(
                        type_diff, labels={"error_type": error_type, **self.labels}
                    )
                    
                setattr(self, f"_last_error_type_{error_type}", count)
            
            # Update system metrics if available
            if self.metrics.track_system_resources and self.metrics.system_metrics["cpu"]:
                # Get latest metrics
                latest_cpu = list(self.metrics.system_metrics["cpu"])[-1]
                latest_memory = list(self.metrics.system_metrics["memory"])[-1]
                latest_disk = list(self.metrics.system_metrics["disk"])[-1]
                
                # Update gauges
                self.cpu_usage.set(latest_cpu["percent"], labels=self.labels)
                self.memory_usage.set(latest_memory["percent"], labels=self.labels)
                self.memory_available.set(latest_memory["available"], labels=self.labels)
                self.disk_usage.set(latest_disk["percent"], labels=self.labels)
                self.disk_free.set(latest_disk["free"], labels=self.labels)
            
            # Update throughput metrics
            throughput = self.metrics.get_current_throughput()
            self.operations_per_second.set(throughput["operations_per_second"], labels=self.labels)
            self.bytes_per_second.set(throughput["bytes_per_second"], labels=self.labels)
            
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}", exc_info=True)
    
    def collect(self):
        """
        Update metrics and return all metrics for Prometheus scraping.
        
        This method is called by the Prometheus client when scraping metrics.
        It updates the metrics and returns all collectors from the registry.
        """
        if not self.enabled:
            return []
            
        # Update metrics
        self.update()
        
        # Return all collectors from the registry
        return self.registry.collect()
        
    def generate_latest(self):
        """
        Generate Prometheus metrics output in text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        if not self.enabled:
            return b""
            
        # Update metrics first
        self.update()
        
        # Generate metrics in Prometheus format
        return prometheus_client.generate_latest(self.registry)
        
    def start_server(self, port=9100, addr=""):
        """
        Start a metrics server for Prometheus scraping.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
        """
        if not self.enabled:
            logger.error("Cannot start Prometheus metrics server: client not available")
            return False
            
        try:
            prometheus_client.start_http_server(port, addr, self.registry)
            logger.info(f"Started Prometheus metrics server on {addr or '0.0.0.0'}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {e}", exc_info=True)
            return False


def add_prometheus_metrics_endpoint(app, metrics_instance: PerformanceMetrics, path="/metrics"):
    """
    Add a Prometheus metrics endpoint to a FastAPI application.
    
    Args:
        app: FastAPI application instance
        metrics_instance: PerformanceMetrics instance
        path: Endpoint path for metrics
        
    Returns:
        True if successful, False otherwise
    """
    if not PROMETHEUS_AVAILABLE:
        logger.debug("Prometheus client not available, skipping metrics endpoint")
        return False
        
    try:
        from fastapi import Request
        from fastapi.responses import Response
        
        # Try to get IPFS instance from app state
        ipfs_instance = None
        if hasattr(app, "state") and hasattr(app.state, "ipfs_api"):
            ipfs_instance = app.state.ipfs_api
        
        # Create exporter with IPFS-specific metrics if instance is available
        exporter = PrometheusExporter(
            metrics_instance, 
            prefix="ipfs_kit",
            ipfs_instance=ipfs_instance
        )
        
        # Add endpoint
        @app.get(path)
        async def metrics(request: Request):
            return Response(
                content=exporter.generate_latest(),
                media_type="text/plain",
            )
            
        # Add metadata endpoint for metric descriptions
        @app.get(f"{path}/metadata")
        async def metrics_metadata(request: Request):
            # Create metadata response
            ipfs_info = {}
            if ipfs_instance:
                try:
                    # Get version info
                    version_result = ipfs_instance.run_ipfs_command(["ipfs", "version"])
                    if version_result.get("success", False):
                        ipfs_info["version"] = version_result.get("stdout", b"").decode().strip()
                        
                    # Get node ID
                    id_result = ipfs_instance.run_ipfs_command(["ipfs", "id", "--format=<id>"])
                    if id_result.get("success", False):
                        ipfs_info["node_id"] = id_result.get("stdout", b"").decode().strip()
                        
                    # Get peer count
                    peer_result = ipfs_instance.run_ipfs_command(["ipfs", "swarm", "peers"])
                    if peer_result.get("success", False):
                        peers = peer_result.get("stdout", b"").decode().strip().split("\n")
                        ipfs_info["peer_count"] = len(peers) if peers and peers[0] else 0
                        
                except Exception as e:
                    logger.warning(f"Error getting IPFS info: {e}")
            
            # Metrics metadata
            metadata = {
                "ipfs_info": ipfs_info,
                "metrics_available": [
                    # Core metrics
                    "ipfs_kit_operations_total",
                    "ipfs_kit_operation_latency_seconds",
                    "ipfs_kit_cache_hits_total",
                    "ipfs_kit_cache_misses_total",
                    "ipfs_kit_cache_hit_ratio",
                    "ipfs_kit_bandwidth_inbound_bytes_total",
                    "ipfs_kit_bandwidth_outbound_bytes_total",
                    "ipfs_kit_errors_total",
                    "ipfs_kit_operations_per_second",
                    
                    # IPFS-specific metrics
                    "ipfs_specific_repo_size_bytes",
                    "ipfs_specific_pins_count",
                    "ipfs_specific_peers_connected",
                    "ipfs_specific_bandwidth_rate_bytes",
                    
                    # Cluster metrics if available
                    "ipfs_specific_cluster_peers",
                    "ipfs_specific_cluster_pins",
                    
                    # Cache metrics
                    "ipfs_specific_cache_entries",
                    "ipfs_specific_cache_size_bytes",
                    "ipfs_specific_cache_usage_percent",
                    
                    # Content metrics
                    "ipfs_kit_content_adds_total",
                    "ipfs_kit_content_retrievals_total",
                    "ipfs_kit_content_pin_operations_total",
                ]
            }
            
            # Add AI/ML metrics if available
            if hasattr(exporter, "has_ai_ml") and exporter.has_ai_ml:
                metadata["metrics_available"].extend([
                    "ipfs_kit_ai_ml_operations_total",
                    "ipfs_kit_model_loading_seconds",
                    "ipfs_kit_inference_seconds",
                ])
                
            # Add documentation link
            metadata["documentation"] = "See /metrics for actual metrics data in Prometheus format"
            
            return metadata
            
        logger.info(f"Added Prometheus metrics endpoint at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add Prometheus metrics endpoint: {e}", exc_info=True)
        return False