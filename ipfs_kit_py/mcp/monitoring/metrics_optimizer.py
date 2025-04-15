"""
Metrics Optimizer for MCP Server.

This module provides utilities to optimize the MCP metrics collection system,
helping to address high memory usage when tracking many metrics. It provides
tools for analyzing memory usage, upgrading to the optimized metrics collector,
and configuring memory-efficient collection policies.
"""

import logging
import os
import sys
import time
import json
import psutil
from typing import Dict, List, Any, Optional, Callable, Set, Union, Tuple
import threading
import importlib

# Import local modules
from ipfs_kit_py.mcp.monitoring.optimized_metrics import (
    get_optimized_metrics_collector,
    replace_default_collector_with_optimized,
)

# Configure logger
logger = logging.getLogger(__name__)

class MetricsMemoryAnalyzer:
    """
    Analyzer for metrics collection memory usage.
    
    Provides tools to measure and analyze the memory usage of the metrics
    collection system, identifying potential areas for optimization.
    """
    
    def __init__(self, snapshot_interval: int = 10, max_snapshots: int = 30):
        """
        Initialize the metrics memory analyzer.
        
        Args:
            snapshot_interval: Interval in seconds between memory usage snapshots
            max_snapshots: Maximum number of snapshots to keep
        """
        self.snapshot_interval = snapshot_interval
        self.max_snapshots = max_snapshots
        self._memory_snapshots = []
        self._collection_thread = None
        self._shutdown_event = threading.Event()
        self._collectors_analysis = {}
    
    def take_memory_snapshot(self) -> Dict[str, Any]:
        """
        Take a snapshot of current memory usage.
        
        Returns:
            Dictionary with memory usage information
        """
        process = psutil.Process(os.getpid())
        
        # Get memory info
        memory_info = process.memory_info()
        
        # Create snapshot
        snapshot = {
            "timestamp": time.time(),
            "rss_bytes": memory_info.rss,  # Resident Set Size
            "vms_bytes": memory_info.vms,  # Virtual Memory Size
            "rss_mb": memory_info.rss / (1024 * 1024),  # RSS in MB
            "vms_mb": memory_info.vms / (1024 * 1024),  # VMS in MB
            "percent": process.memory_percent(),  # Memory usage as percentage of total system memory
        }
        
        # Add system-wide memory usage
        system_memory = psutil.virtual_memory()
        snapshot["system_total_mb"] = system_memory.total / (1024 * 1024)
        snapshot["system_available_mb"] = system_memory.available / (1024 * 1024)
        snapshot["system_used_mb"] = system_memory.used / (1024 * 1024)
        snapshot["system_percent"] = system_memory.percent
        
        # Add to snapshots list
        self._memory_snapshots.append(snapshot)
        
        # Limit list size
        if len(self._memory_snapshots) > self.max_snapshots:
            self._memory_snapshots = self._memory_snapshots[-self.max_snapshots:]
        
        return snapshot
    
    def _snapshot_collection_loop(self) -> None:
        """Background thread function to periodically take memory snapshots."""
        logger.info(f"Starting automatic memory snapshot collection every {self.snapshot_interval} seconds")
        
        while not self._shutdown_event.is_set():
            try:
                self.take_memory_snapshot()
                logger.debug("Took memory usage snapshot")
            except Exception as e:
                logger.error(f"Error taking memory snapshot: {str(e)}", exc_info=True)
            
            # Wait for the next snapshot interval or until shutdown
            self._shutdown_event.wait(self.snapshot_interval)
    
    def start_snapshot_collection(self) -> None:
        """Start automatic memory snapshot collection in a background thread."""
        if self._collection_thread is not None and self._collection_thread.is_alive():
            logger.warning("Automatic memory snapshot collection already running")
            return
        
        self._shutdown_event.clear()
        self._collection_thread = threading.Thread(
            target=self._snapshot_collection_loop,
            daemon=True,
            name="memory-analyzer",
        )
        self._collection_thread.start()
        logger.info("Started automatic memory snapshot collection")
    
    def stop_snapshot_collection(self) -> None:
        """Stop automatic memory snapshot collection."""
        if self._collection_thread is None or not self._collection_thread.is_alive():
            logger.warning("Automatic memory snapshot collection not running")
            return
        
        self._shutdown_event.set()
        self._collection_thread.join(timeout=5.0)
        if self._collection_thread.is_alive():
            logger.warning("Memory analyzer thread did not terminate gracefully")
        else:
            logger.info("Stopped automatic memory snapshot collection")
        
        self._collection_thread = None
    
    def get_memory_trend(self) -> Dict[str, Any]:
        """
        Calculate memory usage trend from collected snapshots.
        
        Returns:
            Dictionary with memory trend information
        """
        if not self._memory_snapshots:
            return {"error": "No memory snapshots available"}
        
        # Need at least 2 snapshots for trend analysis
        if len(self._memory_snapshots) < 2:
            return {
                "current": self._memory_snapshots[0],
                "trend": "insufficient_data",
                "message": "Need at least 2 snapshots for trend analysis",
            }
        
        first_snapshot = self._memory_snapshots[0]
        last_snapshot = self._memory_snapshots[-1]
        
        # Calculate time difference
        time_diff = last_snapshot["timestamp"] - first_snapshot["timestamp"]
        if time_diff <= 0:
            return {
                "current": last_snapshot,
                "trend": "error",
                "message": "Invalid time difference between snapshots",
            }
        
        # Calculate memory difference
        rss_diff = last_snapshot["rss_bytes"] - first_snapshot["rss_bytes"]
        
        # Calculate rate of change (bytes per second)
        rss_rate = rss_diff / time_diff
        
        # Determine trend
        if abs(rss_rate) < 1024:  # Less than 1KB/s change
            trend = "stable"
        elif rss_rate > 0:
            if rss_rate > 1024 * 1024:  # More than 1MB/s increase
                trend = "rapidly_increasing"
            else:
                trend = "increasing"
        else:
            if abs(rss_rate) > 1024 * 1024:  # More than 1MB/s decrease
                trend = "rapidly_decreasing"
            else:
                trend = "decreasing"
        
        return {
            "first_snapshot": first_snapshot,
            "current": last_snapshot,
            "duration_seconds": time_diff,
            "rss_change_bytes": rss_diff,
            "rss_change_rate_bps": rss_rate,
            "rss_change_rate_mbps": rss_rate / (1024 * 1024),
            "trend": trend,
        }
    
    def analyze_collector_memory_usage(
        self, 
        collector_names: Optional[List[str]] = None,
        iterations: int = 5,
        collection_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Analyze memory usage of specific metrics collectors.
        
        Args:
            collector_names: List of collector names to analyze, or None for all
            iterations: Number of collection iterations for analysis
            collection_delay: Delay in seconds between collections
        
        Returns:
            Dictionary with collector memory usage analysis
        """
        try:
            # Try to import metrics collector
            from ipfs_kit_py.mcp.monitoring.metrics_collector import get_metrics_collector
            metrics_collector = get_metrics_collector()
            
            # Get list of available collectors
            available_collectors = list(metrics_collector._collectors.keys())
            
            if not available_collectors:
                return {"error": "No metrics collectors available"}
            
            if collector_names is None:
                # Analyze all collectors
                collector_names = available_collectors
            else:
                # Filter to only existing collectors
                collector_names = [name for name in collector_names if name in available_collectors]
                if not collector_names:
                    return {"error": "None of the specified collectors exist"}
            
            # Initialize analysis results
            results = {}
            
            # Analyze each collector
            for collector_name in collector_names:
                # Take initial memory snapshot
                process = psutil.Process(os.getpid())
                initial_memory = process.memory_info().rss
                
                # Collect metrics multiple times and measure memory impact
                memory_readings = []
                
                for i in range(iterations):
                    # Collect metrics
                    metrics_collector.collect_metrics(collector_name=collector_name)
                    
                    # Take memory reading
                    current_memory = process.memory_info().rss
                    memory_change = current_memory - initial_memory
                    memory_readings.append(memory_change)
                    
                    # Wait before next collection
                    if i < iterations - 1:
                        time.sleep(collection_delay)
                
                # Calculate average memory impact
                avg_memory_impact = sum(memory_readings) / len(memory_readings) if memory_readings else 0
                max_memory_impact = max(memory_readings) if memory_readings else 0
                
                # Store results
                results[collector_name] = {
                    "average_memory_impact_bytes": avg_memory_impact,
                    "average_memory_impact_mb": avg_memory_impact / (1024 * 1024),
                    "max_memory_impact_bytes": max_memory_impact,
                    "max_memory_impact_mb": max_memory_impact / (1024 * 1024),
                    "iterations": iterations,
                }
            
            # Store analysis for later reference
            self._collectors_analysis = results
            
            # Calculate total memory impact
            total_avg_impact = sum(result["average_memory_impact_bytes"] for result in results.values())
            
            return {
                "collectors": results,
                "total_average_memory_impact_bytes": total_avg_impact,
                "total_average_memory_impact_mb": total_avg_impact / (1024 * 1024),
                "analysis_time": time.time(),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing collector memory usage: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def generate_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Generate recommendations for metrics collection optimization.
        
        Returns:
            Dictionary with optimization recommendations
        """
        recommendations = []
        
        # Check memory trend
        memory_trend = self.get_memory_trend()
        if "trend" in memory_trend:
            if memory_trend["trend"] in ["increasing", "rapidly_increasing"]:
                recommendations.append({
                    "type": "retention_policy",
                    "priority": "high",
                    "message": "Implement time-based retention policy to limit stored metrics history",
                    "details": "Memory usage is trending upward, suggesting accumulation of metrics over time.",
                })
                
                recommendations.append({
                    "type": "adaptive_collection",
                    "priority": "high",
                    "message": "Enable memory-adaptive collection to reduce collection frequency under memory pressure",
                    "details": "Memory usage is trending upward, suggesting the need for adaptive collection.",
                })
            
            if memory_trend["trend"] == "rapidly_increasing":
                recommendations.append({
                    "type": "critical_triage",
                    "priority": "critical",
                    "message": "Memory usage is increasing rapidly - implement the optimized metrics collector immediately",
                    "details": f"Memory usage increasing at {memory_trend.get('rss_change_rate_mbps', 0):.2f} MB/s.",
                })
        
        # Check collector-specific memory usage
        if self._collectors_analysis:
            # Sort collectors by memory impact
            sorted_collectors = sorted(
                self._collectors_analysis.items(),
                key=lambda x: x[1]["average_memory_impact_bytes"],
                reverse=True
            )
            
            # Identify high-impact collectors
            high_impact_collectors = []
            for name, data in sorted_collectors:
                if data["average_memory_impact_mb"] > 1.0:  # More than 1MB impact
                    high_impact_collectors.append({
                        "name": name,
                        "impact_mb": data["average_memory_impact_mb"],
                    })
            
            if high_impact_collectors:
                recommendations.append({
                    "type": "collector_optimization",
                    "priority": "medium",
                    "message": f"Optimize {len(high_impact_collectors)} high-memory-impact collectors",
                    "details": "Mark as non-critical or reduce collection frequency for these collectors: " + 
                              ", ".join([c["name"] for c in high_impact_collectors]),
                    "collectors": high_impact_collectors,
                })
        
        # Check current memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        if memory_percent > 10.0:  # Using more than 10% of system memory
            recommendations.append({
                "type": "immediate_optimization",
                "priority": "high",
                "message": f"Process using {memory_percent:.1f}% of system memory - optimization recommended",
                "details": f"Current memory usage: {memory_info.rss / (1024 * 1024):.1f} MB",
            })
        
        # Check if we have the optimized collector available
        try:
            import ipfs_kit_py.mcp.monitoring.optimized_metrics
            is_optimized_available = True
        except ImportError:
            is_optimized_available = False
        
        # Check which collector is currently in use
        is_using_optimized = False
        try:
            from ipfs_kit_py.mcp.monitoring.metrics_collector import _default_collector
            if _default_collector is not None:
                is_using_optimized = hasattr(_default_collector, 'enable_memory_adaptive_collection')
        except Exception:
            pass
        
        if is_optimized_available and not is_using_optimized:
            recommendations.append({
                "type": "collector_upgrade",
                "priority": "medium",
                "message": "Upgrade to the optimized metrics collector",
                "details": "The optimized metrics collector is available but not currently in use.",
                "action": "Replace the default collector with replace_default_collector_with_optimized()",
            })
        
        return {
            "timestamp": time.time(),
            "current_memory_mb": memory_info.rss / (1024 * 1024),
            "memory_percent": memory_percent,
            "recommendations": recommendations,
            "memory_trend": memory_trend,
        }

def analyze_metrics_memory_usage(snapshot_duration: int = 60) -> Dict[str, Any]:
    """
    Analyze metrics collection memory usage over a period of time.
    
    Args:
        snapshot_duration: Duration in seconds to collect memory snapshots
    
    Returns:
        Dictionary with memory usage analysis and recommendations
    """
    analyzer = MetricsMemoryAnalyzer(snapshot_interval=2, max_snapshots=100)
    
    # Start snapshot collection
    analyzer.start_snapshot_collection()
    
    try:
        # Wait for specified duration
        logger.info(f"Collecting memory snapshots for {snapshot_duration} seconds...")
        time.sleep(snapshot_duration)
        
        # Analyze collector memory usage
        from ipfs_kit_py.mcp.monitoring.metrics_collector import get_metrics_collector
        metrics_collector = get_metrics_collector()
        collector_names = list(metrics_collector._collectors.keys())
        
        # Analyze a subset of collectors if there are many
        if len(collector_names) > 5:
            # Analyze the first 5 collectors
            collector_analysis = analyzer.analyze_collector_memory_usage(
                collector_names=collector_names[:5],
                iterations=3,
            )
        else:
            # Analyze all collectors
            collector_analysis = analyzer.analyze_collector_memory_usage(
                iterations=3,
            )
        
        # Generate recommendations
        recommendations = analyzer.generate_optimization_recommendations()
        
        return {
            "memory_trend": analyzer.get_memory_trend(),
            "collector_analysis": collector_analysis,
            "recommendations": recommendations,
        }
    
    finally:
        # Stop snapshot collection
        analyzer.stop_snapshot_collection()

def upgrade_to_optimized_metrics(
    retention_minutes: int = 60,
    max_entries_per_collector: int = 100,
    memory_pressure_threshold: float = 85.0,
    enable_memory_adaptive_collection: bool = True,
) -> Dict[str, Any]:
    """
    Upgrade the default metrics collector to the optimized version.
    
    Args:
        retention_minutes: Maximum retention time in minutes for cached metrics
        max_entries_per_collector: Maximum number of historical entries to keep per collector
        memory_pressure_threshold: Memory usage percentage above which to enable low-memory mode
        enable_memory_adaptive_collection: Whether to adapt collection based on memory pressure
    
    Returns:
        Dictionary with upgrade status information
    """
    try:
        # Get the original collector's state
        from ipfs_kit_py.mcp.monitoring.metrics_collector import _default_collector
        
        if _default_collector is None:
            return {
                "status": "error",
                "message": "Default metrics collector not initialized",
            }
        
        # Check if already using optimized collector
        if hasattr(_default_collector, 'enable_memory_adaptive_collection'):
            return {
                "status": "skipped",
                "message": "Already using optimized metrics collector",
            }
        
        # Get collector details before upgrade
        original_collectors = list(_default_collector._collectors.keys())
        had_collection_thread = (
            _default_collector._collection_thread is not None and 
            _default_collector._collection_thread.is_alive()
        )
        
        # Perform the upgrade
        optimized = replace_default_collector_with_optimized()
        
        # Configure optimized collector
        optimized.retention_minutes = retention_minutes
        optimized.max_entries_per_collector = max_entries_per_collector
        optimized.memory_pressure_threshold = memory_pressure_threshold
        optimized.enable_memory_adaptive_collection = enable_memory_adaptive_collection
        
        # Get collector details after upgrade
        new_collectors = list(optimized._collectors.keys())
        
        # Verify all collectors were transferred
        missing_collectors = [c for c in original_collectors if c not in new_collectors]
        
        return {
            "status": "success",
            "message": "Successfully upgraded to optimized metrics collector",
            "original_collector_count": len(original_collectors),
            "new_collector_count": len(new_collectors),
            "missing_collectors": missing_collectors,
            "collection_active": (
                optimized._collection_thread is not None and 
                optimized._collection_thread.is_alive()
            ),
            "had_collection_thread": had_collection_thread,
            "settings": {
                "retention_minutes": optimized.retention_minutes,
                "max_entries_per_collector": optimized.max_entries_per_collector,
                "memory_pressure_threshold": optimized.memory_pressure_threshold,
                "enable_memory_adaptive_collection": optimized.enable_memory_adaptive_collection,
            },
        }
    
    except Exception as e:
        logger.error(f"Error upgrading to optimized metrics collector: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error upgrading to optimized metrics collector: {str(e)}",
        }

def register_optimized_collector_with_fastapi(app: Any, path: str = "/metrics/optimize") -> Dict[str, Any]:
    """
    Register optimization endpoints with a FastAPI application.
    
    Args:
        app: FastAPI application to register with
        path: Base path for optimization endpoints
    
    Returns:
        Dictionary with registration status information
    """
    try:
        from fastapi import FastAPI, APIRouter, BackgroundTasks
        
        # Ensure the app is a FastAPI instance
        if not isinstance(app, FastAPI):
            return {
                "status": "error",
                "message": "app is not a FastAPI instance",
            }
        
        # Create a router for optimization endpoints
        router = APIRouter(tags=["Metrics Optimization"])
        
        # Add analyze endpoint
        @router.get(f"{path}/analyze")
        async def analyze_metrics(
            duration: int = 30,
            background_tasks: BackgroundTasks = None,
        ):
            """
            Analyze metrics collection memory usage.
            
            Args:
                duration: Duration in seconds to collect memory snapshots
                background_tasks: FastAPI background tasks
            
            Returns:
                Dictionary with memory usage analysis
            """
            if background_tasks:
                # Run analysis in background
                results = {"status": "running", "message": f"Analysis started (duration: {duration}s)"}
                
                def run_analysis():
                    # Run analysis
                    analysis_results = analyze_metrics_memory_usage(snapshot_duration=duration)
                    
                    # Store results in cache
                    app.state.metrics_analysis = {
                        "timestamp": time.time(),
                        "results": analysis_results,
                    }
                
                background_tasks.add_task(run_analysis)
                return results
            else:
                # Run analysis synchronously
                return analyze_metrics_memory_usage(snapshot_duration=duration)
        
        # Add get analysis results endpoint
        @router.get(f"{path}/analysis-results")
        async def get_analysis_results():
            """
            Get the most recent metrics analysis results.
            
            Returns:
                Dictionary with analysis results or status
            """
            if hasattr(app.state, "metrics_analysis"):
                return app.state.metrics_analysis
            else:
                return {"status": "not_found", "message": "No analysis results available yet"}
        
        # Add upgrade endpoint
        @router.post(f"{path}/upgrade")
        async def upgrade_metrics_collector(
            retention_minutes: int = 60,
            max_entries_per_collector: int = 100,
            memory_pressure_threshold: float = 85.0,
            enable_memory_adaptive_collection: bool = True,
        ):
            """
            Upgrade to the optimized metrics collector.
            
            Args:
                retention_minutes: Maximum retention time in minutes for cached metrics
                max_entries_per_collector: Maximum number of historical entries to keep per collector
                memory_pressure_threshold: Memory usage percentage above which to enable low-memory mode
                enable_memory_adaptive_collection: Whether to adapt collection based on memory pressure
            
            Returns:
                Dictionary with upgrade status information
            """
            return upgrade_to_optimized_metrics(
                retention_minutes=retention_minutes,
                max_entries_per_collector=max_entries_per_collector,
                memory_pressure_threshold=memory_pressure_threshold,
                enable_memory_adaptive_collection=enable_memory_adaptive_collection,
            )
        
        # Add status endpoint
        @router.get(f"{path}/status")
        async def get_optimization_status():
            """
            Get current optimization status.
            
            Returns:
                Dictionary with optimization status information
            """
            # Check which collector is in use
            from ipfs_kit_py.mcp.monitoring.metrics_collector import _default_collector, get_metrics_collector
            
            collector = get_metrics_collector()
            is_optimized = hasattr(collector, 'enable_memory_adaptive_collection')
            
            # Get process memory info
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            if is_optimized:
                # Get optimized collector info
                return {
                    "status": "optimized",
                    "message": "Using optimized metrics collector",
                    "settings": {
                        "retention_minutes": collector.retention_minutes,
                        "max_entries_per_collector": collector.max_entries_per_collector,
                        "memory_pressure_threshold": collector.memory_pressure_threshold,
                        "enable_memory_adaptive_collection": collector.enable_memory_adaptive_collection,
                        "collection_interval": collector.collection_interval,
                        "auto_collection_active": (
                            collector._collection_thread is not None and 
                            collector._collection_thread.is_alive()
                        ),
                        "under_memory_pressure": collector._under_memory_pressure,
                        "critical_collectors": list(collector._critical_collectors),
                    },
                    "memory_usage": {
                        "rss_mb": memory_info.rss / (1024 * 1024),
                        "vms_mb": memory_info.vms / (1024 * 1024),
                        "percent": process.memory_percent(),
                    },
                    "metrics_collectors": len(collector._collectors),
                }
            else:
                # Get standard collector info
                return {
                    "status": "standard",
                    "message": "Using standard metrics collector",
                    "settings": {
                        "collection_interval": collector.collection_interval,
                        "auto_collection_active": (
                            collector._collection_thread is not None and 
                            collector._collection_thread.is_alive()
                        ),
                    },
                    "memory_usage": {
                        "rss_mb": memory_info.rss / (1024 * 1024),
                        "vms_mb": memory_info.vms / (1024 * 1024),
                        "percent": process.memory_percent(),
                    },
                    "metrics_collectors": len(collector._collectors),
                }
        
        # Include the router in the app
        app.include_router(router)
        
        return {
            "status": "success",
            "message": f"Registered metrics optimization endpoints at {path}",
            "endpoints": [
                f"{path}/analyze",
                f"{path}/analysis-results",
                f"{path}/upgrade",
                f"{path}/status",
            ],
        }
    
    except Exception as e:
        logger.error(f"Error registering optimization endpoints: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error registering optimization endpoints: {str(e)}",
        }

def main():
    """CLI interface for metrics optimization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Metrics Optimizer")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze metrics collection memory usage")
    analyze_parser.add_argument(
        "--duration", type=int, default=60,
        help="Duration in seconds to collect memory snapshots"
    )
    analyze_parser.add_argument(
        "--output", type=str, default=None,
        help="Output file for analysis results (JSON format)"
    )
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade to optimized metrics collector")
    upgrade_parser.add_argument(
        "--retention", type=int, default=60,
        help="Retention time in minutes for metrics history"
    )
    upgrade_parser.add_argument(
        "--max-entries", type=int, default=100,
        help="Maximum entries per metrics collector"
    )
    upgrade_parser.add_argument(
        "--memory-threshold", type=float, default=85.0,
        help="Memory pressure threshold percentage"
    )
    upgrade_parser.add_argument(
        "--no-adaptive", action="store_true",
        help="Disable memory-adaptive collection"
    )
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        print(f"Analyzing metrics collection memory usage (duration: {args.duration}s)...")
        results = analyze_metrics_memory_usage(snapshot_duration=args.duration)
        
        # Print summary
        if "memory_trend" in results and "trend" in results["memory_trend"]:
            print(f"\nMemory Trend: {results['memory_trend']['trend']}")
        
        if "recommendations" in results and "recommendations" in results["recommendations"]:
            print("\nRecommendations:")
            for rec in results["recommendations"]["recommendations"]:
                print(f"  - [{rec['priority']}] {rec['message']}")
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed results written to {args.output}")
        else:
            print("\nDetailed results:")
            print(json.dumps(results, indent=2))
    
    elif args.command == "upgrade":
        print("Upgrading to optimized metrics collector...")
        results = upgrade_to_optimized_metrics(
            retention_minutes=args.retention,
            max_entries_per_collector=args.max_entries,
            memory_pressure_threshold=args.memory_threshold,
            enable_memory_adaptive_collection=not args.no_adaptive,
        )
        
        print(f"\nStatus: {results['status']}")
        print(f"Message: {results['message']}")
        
        if results['status'] == 'success':
            print("\nSettings:")
            for key, value in results['settings'].items():
                print(f"  - {key}: {value}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
