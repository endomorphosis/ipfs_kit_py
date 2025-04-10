# ipfs_kit_py/wal_visualization_anyio.py

import os
import time
import json
import logging
import datetime
import warnings
from typing import Dict, List, Any, Optional, Tuple

# Import AnyIO for backend-agnostic async operations
import anyio
import sniffio

# Optional visualization imports
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from .high_level_api import IPFSSimpleAPI
except ImportError:
    from ipfs_kit_py import IPFSSimpleAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WALVisualizationAnyIO:
    """Visualization tools for the WAL system with AnyIO support."""
    
    def __init__(self, api: Optional[IPFSSimpleAPI] = None, config_path: Optional[str] = None):
        """Initialize the visualization tools with AnyIO support.
        
        Args:
            api: An existing IPFSSimpleAPI instance, or None to create a new one
            config_path: Path to configuration file (if api is None)
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available. Visualization will be limited to data collection only.")
        
        self.api = api or IPFSSimpleAPI(config_path=config_path)
        self.data_dir = os.path.expanduser("~/.ipfs_kit/visualizations")
        os.makedirs(self.data_dir, exist_ok=True)
    
    @staticmethod
    def get_backend() -> Optional[str]:
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name: str) -> None:
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    def collect_operation_stats(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Collect operation statistics for visualization.
        
        Args:
            timeframe_hours: Number of hours to look back
            
        Returns:
            Dictionary with operation statistics
        """
        self._warn_if_async_context("collect_operation_stats")
        # Start time (now - timeframe)
        start_time = time.time() - (timeframe_hours * 3600)
        
        try:
            # Get all WAL operations (this would be a method to implement in the WAL)
            all_operations = self.api.get_all_operations()
            
            # Filter operations by timeframe
            operations = [op for op in all_operations if op.get("timestamp", 0) >= start_time]
            
            # Group operations by status
            status_counts = defaultdict(int)
            for op in operations:
                status = op.get("status", "unknown")
                status_counts[status] += 1
            
            # Group operations by type
            type_counts = defaultdict(int)
            for op in operations:
                op_type = op.get("operation_type", "unknown")
                type_counts[op_type] += 1
            
            # Group operations by backend
            backend_counts = defaultdict(int)
            for op in operations:
                backend = op.get("backend", "unknown")
                backend_counts[backend] += 1
            
            # Calculate success rates by backend
            backend_success = defaultdict(lambda: {"total": 0, "success": 0})
            for op in operations:
                backend = op.get("backend", "unknown")
                backend_success[backend]["total"] += 1
                if op.get("status") == "completed":
                    backend_success[backend]["success"] += 1
            
            # Calculate success rates
            success_rates = {}
            for backend, counts in backend_success.items():
                if counts["total"] > 0:
                    success_rates[backend] = counts["success"] / counts["total"]
                else:
                    success_rates[backend] = 0.0
            
            # Calculate completion times by operation type
            completion_times = defaultdict(list)
            for op in operations:
                if op.get("status") == "completed" and op.get("completed_at") and op.get("timestamp"):
                    op_type = op.get("operation_type", "unknown")
                    start_time = op.get("timestamp") / 1000.0  # Convert to seconds
                    end_time = op.get("completed_at") / 1000.0  # Convert to seconds
                    duration = end_time - start_time
                    completion_times[op_type].append(duration)
            
            # Calculate average completion times
            avg_completion_times = {}
            for op_type, times in completion_times.items():
                if times:
                    avg_completion_times[op_type] = sum(times) / len(times)
                else:
                    avg_completion_times[op_type] = 0.0
            
            # Organize operations by time for timeline
            timeline_data = []
            for op in sorted(operations, key=lambda x: x.get("timestamp", 0)):
                timeline_data.append({
                    "operation_id": op.get("operation_id", "unknown"),
                    "operation_type": op.get("operation_type", "unknown"),
                    "backend": op.get("backend", "unknown"),
                    "status": op.get("status", "unknown"),
                    "timestamp": op.get("timestamp", 0),
                    "completed_at": op.get("completed_at"),
                    "error": op.get("error")
                })
            
            # Collect backend health data
            try:
                backend_health = self.api.wal.health_monitor.get_status()
            except (AttributeError, TypeError):
                # Health monitor not available
                backend_health = {}
            
            return {
                "success": True,
                "timeframe_hours": timeframe_hours,
                "total_operations": len(operations),
                "status_counts": dict(status_counts),
                "type_counts": dict(type_counts),
                "backend_counts": dict(backend_counts),
                "success_rates": success_rates,
                "avg_completion_times": avg_completion_times,
                "timeline_data": timeline_data,
                "backend_health": backend_health,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to collect operation stats: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def collect_operation_stats_async(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Collect operation statistics for visualization asynchronously.
        
        Args:
            timeframe_hours: Number of hours to look back
            
        Returns:
            Dictionary with operation statistics
        """
        # Start time (now - timeframe)
        start_time = time.time() - (timeframe_hours * 3600)
        
        try:
            # Get all WAL operations asynchronously if available
            if hasattr(self.api, "get_all_operations_async"):
                all_operations = await self.api.get_all_operations_async()
            else:
                # Fall back to synchronous method
                all_operations = await anyio.to_thread.run_sync(self.api.get_all_operations)
            
            # Filter operations by timeframe
            operations = [op for op in all_operations if op.get("timestamp", 0) >= start_time]
            
            # The rest of the processing can be done in a worker thread
            # since it's CPU-bound and doesn't involve I/O
            async def process_operations():
                # Group operations by status
                status_counts = defaultdict(int)
                for op in operations:
                    status = op.get("status", "unknown")
                    status_counts[status] += 1
                
                # Group operations by type
                type_counts = defaultdict(int)
                for op in operations:
                    op_type = op.get("operation_type", "unknown")
                    type_counts[op_type] += 1
                
                # Group operations by backend
                backend_counts = defaultdict(int)
                for op in operations:
                    backend = op.get("backend", "unknown")
                    backend_counts[backend] += 1
                
                # Calculate success rates by backend
                backend_success = defaultdict(lambda: {"total": 0, "success": 0})
                for op in operations:
                    backend = op.get("backend", "unknown")
                    backend_success[backend]["total"] += 1
                    if op.get("status") == "completed":
                        backend_success[backend]["success"] += 1
                
                # Calculate success rates
                success_rates = {}
                for backend, counts in backend_success.items():
                    if counts["total"] > 0:
                        success_rates[backend] = counts["success"] / counts["total"]
                    else:
                        success_rates[backend] = 0.0
                
                # Calculate completion times by operation type
                completion_times = defaultdict(list)
                for op in operations:
                    if op.get("status") == "completed" and op.get("completed_at") and op.get("timestamp"):
                        op_type = op.get("operation_type", "unknown")
                        start_time = op.get("timestamp") / 1000.0  # Convert to seconds
                        end_time = op.get("completed_at") / 1000.0  # Convert to seconds
                        duration = end_time - start_time
                        completion_times[op_type].append(duration)
                
                # Calculate average completion times
                avg_completion_times = {}
                for op_type, times in completion_times.items():
                    if times:
                        avg_completion_times[op_type] = sum(times) / len(times)
                    else:
                        avg_completion_times[op_type] = 0.0
                
                # Organize operations by time for timeline
                timeline_data = []
                for op in sorted(operations, key=lambda x: x.get("timestamp", 0)):
                    timeline_data.append({
                        "operation_id": op.get("operation_id", "unknown"),
                        "operation_type": op.get("operation_type", "unknown"),
                        "backend": op.get("backend", "unknown"),
                        "status": op.get("status", "unknown"),
                        "timestamp": op.get("timestamp", 0),
                        "completed_at": op.get("completed_at"),
                        "error": op.get("error")
                    })
                
                return {
                    "status_counts": dict(status_counts),
                    "type_counts": dict(type_counts),
                    "backend_counts": dict(backend_counts),
                    "success_rates": success_rates,
                    "avg_completion_times": avg_completion_times,
                    "timeline_data": timeline_data
                }
            
            # Process operations in a separate thread to avoid blocking
            processed_data = await anyio.to_thread.run_sync(lambda: process_operations())
            
            # Get backend health asynchronously if available
            if hasattr(self.api, "wal") and hasattr(self.api.wal, "health_monitor") and hasattr(self.api.wal.health_monitor, "get_status_async"):
                backend_health = await self.api.wal.health_monitor.get_status_async()
            else:
                # Fall back to synchronous method via thread pool
                try:
                    backend_health = await anyio.to_thread.run_sync(
                        lambda: self.api.wal.health_monitor.get_status()
                    )
                except (AttributeError, TypeError):
                    # Health monitor not available
                    backend_health = {}
            
            # Combine results
            return {
                "success": True,
                "timeframe_hours": timeframe_hours,
                "total_operations": len(operations),
                **processed_data,
                "backend_health": backend_health,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to collect operation stats asynchronously: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def save_stats(self, stats: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save collected statistics to a file.
        
        Args:
            stats: Statistics data to save
            filename: Optional filename, or None to generate a timestamp-based name
            
        Returns:
            Path to the saved file
        """
        self._warn_if_async_context("save_stats")
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wal_stats_{timestamp}.json"
        
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Saved WAL statistics to {filepath}")
        return filepath
    
    async def save_stats_async(self, stats: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save collected statistics to a file asynchronously.
        
        Args:
            stats: Statistics data to save
            filename: Optional filename, or None to generate a timestamp-based name
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wal_stats_{timestamp}.json"
        
        filepath = os.path.join(self.data_dir, filename)
        
        # Define a function to write the file
        def write_file():
            with open(filepath, 'w') as f:
                json.dump(stats, f, indent=2)
            return filepath
        
        # Run the file operation in a worker thread
        result = await anyio.to_thread.run_sync(write_file)
        
        logger.info(f"Saved WAL statistics to {filepath}")
        return result
    
    def load_stats(self, filepath: str) -> Dict[str, Any]:
        """Load statistics from a file.
        
        Args:
            filepath: Path to the statistics file
            
        Returns:
            Statistics data
        """
        self._warn_if_async_context("load_stats")
        with open(filepath, 'r') as f:
            stats = json.load(f)
        
        logger.info(f"Loaded WAL statistics from {filepath}")
        return stats
    
    async def load_stats_async(self, filepath: str) -> Dict[str, Any]:
        """Load statistics from a file asynchronously.
        
        Args:
            filepath: Path to the statistics file
            
        Returns:
            Statistics data
        """
        def read_file():
            with open(filepath, 'r') as f:
                return json.load(f)
        
        # Run the file operation in a worker thread
        stats = await anyio.to_thread.run_sync(read_file)
        
        logger.info(f"Loaded WAL statistics from {filepath}")
        return stats
    
    def plot_operation_status(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot operation status distribution.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        self._warn_if_async_context("plot_operation_status")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        status_counts = stats.get("status_counts", {})
        statuses = list(status_counts.keys())
        counts = [status_counts[status] for status in statuses]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        bars = plt.bar(statuses, counts, color=['#4CAF50', '#FF9800', '#F44336', '#2196F3'])
        
        # Add labels and title
        plt.title('Operation Status Distribution')
        plt.xlabel('Status')
        plt.ylabel('Count')
        plt.xticks(rotation=45, ha='right')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    '%d' % int(height), ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved operation status plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    async def plot_operation_status_async(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot operation status distribution asynchronously.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Define a function to create the plot
        def create_plot():
            # Extract data
            status_counts = stats.get("status_counts", {})
            statuses = list(status_counts.keys())
            counts = [status_counts[status] for status in statuses]
            
            # Create plot
            plt.figure(figsize=(10, 6))
            bars = plt.bar(statuses, counts, color=['#4CAF50', '#FF9800', '#F44336', '#2196F3'])
            
            # Add labels and title
            plt.title('Operation Status Distribution')
            plt.xlabel('Status')
            plt.ylabel('Count')
            plt.xticks(rotation=45, ha='right')
            
            # Add count labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        '%d' % int(height), ha='center', va='bottom')
            
            plt.tight_layout()
            
            # Save or display
            if output_path:
                plt.savefig(output_path)
                logger.info(f"Saved operation status plot to {output_path}")
                plt.close()
                return output_path
            else:
                plt.show()
                return None
        
        # Run the plotting in a worker thread
        return await anyio.to_thread.run_sync(create_plot)
    
    def plot_backend_success_rates(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot success rates by backend.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        self._warn_if_async_context("plot_backend_success_rates")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        success_rates = stats.get("success_rates", {})
        backends = list(success_rates.keys())
        rates = [success_rates[backend] * 100 for backend in backends]  # Convert to percentage
        
        # Create plot
        plt.figure(figsize=(10, 6))
        bars = plt.bar(backends, rates, color=['#4CAF50', '#2196F3', '#9C27B0'])
        
        # Add labels and title
        plt.title('Success Rates by Backend')
        plt.xlabel('Backend')
        plt.ylabel('Success Rate (%)')
        plt.ylim(0, 105)  # Give a little space above 100%
        
        # Add percentage labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                    '%.1f%%' % height, ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved backend success rates plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    async def plot_backend_success_rates_async(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot success rates by backend asynchronously.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Define a function to create the plot
        def create_plot():
            # Extract data
            success_rates = stats.get("success_rates", {})
            backends = list(success_rates.keys())
            rates = [success_rates[backend] * 100 for backend in backends]  # Convert to percentage
            
            # Create plot
            plt.figure(figsize=(10, 6))
            bars = plt.bar(backends, rates, color=['#4CAF50', '#2196F3', '#9C27B0'])
            
            # Add labels and title
            plt.title('Success Rates by Backend')
            plt.xlabel('Backend')
            plt.ylabel('Success Rate (%)')
            plt.ylim(0, 105)  # Give a little space above 100%
            
            # Add percentage labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                        '%.1f%%' % height, ha='center', va='bottom')
            
            plt.tight_layout()
            
            # Save or display
            if output_path:
                plt.savefig(output_path)
                logger.info(f"Saved backend success rates plot to {output_path}")
                plt.close()
                return output_path
            else:
                plt.show()
                return None
        
        # Run the plotting in a worker thread
        return await anyio.to_thread.run_sync(create_plot)
    
    def plot_completion_times(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot average completion times by operation type.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        self._warn_if_async_context("plot_completion_times")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        avg_times = stats.get("avg_completion_times", {})
        op_types = list(avg_times.keys())
        times = [avg_times[op_type] for op_type in op_types]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        bars = plt.bar(op_types, times, color=['#2196F3', '#9C27B0', '#FF9800'])
        
        # Add labels and title
        plt.title('Average Completion Times by Operation Type')
        plt.xlabel('Operation Type')
        plt.ylabel('Average Time (seconds)')
        plt.xticks(rotation=45, ha='right')
        
        # Add time labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    '%.2fs' % height, ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved completion times plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    async def plot_completion_times_async(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot average completion times by operation type asynchronously.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Define a function to create the plot
        def create_plot():
            # Extract data
            avg_times = stats.get("avg_completion_times", {})
            op_types = list(avg_times.keys())
            times = [avg_times[op_type] for op_type in op_types]
            
            # Create plot
            plt.figure(figsize=(10, 6))
            bars = plt.bar(op_types, times, color=['#2196F3', '#9C27B0', '#FF9800'])
            
            # Add labels and title
            plt.title('Average Completion Times by Operation Type')
            plt.xlabel('Operation Type')
            plt.ylabel('Average Time (seconds)')
            plt.xticks(rotation=45, ha='right')
            
            # Add time labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        '%.2fs' % height, ha='center', va='bottom')
            
            plt.tight_layout()
            
            # Save or display
            if output_path:
                plt.savefig(output_path)
                logger.info(f"Saved completion times plot to {output_path}")
                plt.close()
                return output_path
            else:
                plt.show()
                return None
        
        # Run the plotting in a worker thread
        return await anyio.to_thread.run_sync(create_plot)
    
    def plot_timeline(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot operation timeline.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        self._warn_if_async_context("plot_timeline")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        timeline_data = stats.get("timeline_data", [])
        
        if not timeline_data:
            logger.error("No timeline data available.")
            return None
        
        # Prepare data for plotting
        timestamps = [datetime.datetime.fromtimestamp(op["timestamp"] / 1000.0) for op in timeline_data]
        statuses = [op["status"] for op in timeline_data]
        backends = [op["backend"] for op in timeline_data]
        
        # Status color mapping
        status_colors = {
            "pending": "#FF9800",      # Orange
            "processing": "#2196F3",   # Blue
            "completed": "#4CAF50",    # Green
            "failed": "#F44336",       # Red
            "retrying": "#9C27B0",     # Purple
            "unknown": "#757575"       # Gray
        }
        
        # Create colors list based on status
        colors = [status_colors.get(status, "#757575") for status in statuses]
        
        # Create plot
        plt.figure(figsize=(12, 6))
        
        # Create scatter plot for each operation
        scatter = plt.scatter(timestamps, range(len(timestamps)), c=colors, s=100, alpha=0.8)
        
        # Add backend labels
        for i, (timestamp, backend) in enumerate(zip(timestamps, backends)):
            plt.text(timestamp, i, f" {backend}", verticalalignment='center')
        
        # Create legend based on unique statuses
        unique_statuses = list(set(statuses))
        legend_elements = [plt.Line2D([0], [0], marker='o', color='w', 
                            label=status, markerfacecolor=status_colors.get(status, "#757575"), 
                            markersize=10) 
                          for status in unique_statuses]
        plt.legend(handles=legend_elements, loc='upper left')
        
        # Format x-axis to show dates properly
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gcf().autofmt_xdate()
        
        # Remove y-axis ticks as they're not meaningful
        plt.gca().yaxis.set_visible(False)
        
        # Add labels and title
        plt.title('Operation Timeline')
        plt.xlabel('Time')
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved timeline plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    async def plot_timeline_async(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot operation timeline asynchronously.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Define a function to create the plot
        def create_plot():
            # Extract data
            timeline_data = stats.get("timeline_data", [])
            
            if not timeline_data:
                logger.error("No timeline data available.")
                return None
            
            # Prepare data for plotting
            timestamps = [datetime.datetime.fromtimestamp(op["timestamp"] / 1000.0) for op in timeline_data]
            statuses = [op["status"] for op in timeline_data]
            backends = [op["backend"] for op in timeline_data]
            
            # Status color mapping
            status_colors = {
                "pending": "#FF9800",      # Orange
                "processing": "#2196F3",   # Blue
                "completed": "#4CAF50",    # Green
                "failed": "#F44336",       # Red
                "retrying": "#9C27B0",     # Purple
                "unknown": "#757575"       # Gray
            }
            
            # Create colors list based on status
            colors = [status_colors.get(status, "#757575") for status in statuses]
            
            # Create plot
            plt.figure(figsize=(12, 6))
            
            # Create scatter plot for each operation
            scatter = plt.scatter(timestamps, range(len(timestamps)), c=colors, s=100, alpha=0.8)
            
            # Add backend labels
            for i, (timestamp, backend) in enumerate(zip(timestamps, backends)):
                plt.text(timestamp, i, f" {backend}", verticalalignment='center')
            
            # Create legend based on unique statuses
            unique_statuses = list(set(statuses))
            legend_elements = [plt.Line2D([0], [0], marker='o', color='w', 
                                label=status, markerfacecolor=status_colors.get(status, "#757575"), 
                                markersize=10) 
                              for status in unique_statuses]
            plt.legend(handles=legend_elements, loc='upper left')
            
            # Format x-axis to show dates properly
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            plt.gcf().autofmt_xdate()
            
            # Remove y-axis ticks as they're not meaningful
            plt.gca().yaxis.set_visible(False)
            
            # Add labels and title
            plt.title('Operation Timeline')
            plt.xlabel('Time')
            plt.grid(axis='x', linestyle='--', alpha=0.7)
            
            plt.tight_layout()
            
            # Save or display
            if output_path:
                plt.savefig(output_path)
                logger.info(f"Saved timeline plot to {output_path}")
                plt.close()
                return output_path
            else:
                plt.show()
                return None
        
        # Run the plotting in a worker thread
        return await anyio.to_thread.run_sync(create_plot)
    
    def plot_backend_health(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot backend health status.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        self._warn_if_async_context("plot_backend_health")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        backend_health = stats.get("backend_health", {})
        
        if not backend_health:
            logger.error("No backend health data available.")
            return None
        
        # Create a figure with subplots for each backend
        backends = list(backend_health.keys())
        n_backends = len(backends)
        
        if n_backends == 0:
            return None
        
        # Determine grid layout based on number of backends
        if n_backends <= 2:
            n_rows, n_cols = 1, n_backends
        else:
            n_rows = (n_backends + 1) // 2  # Ceiling division
            n_cols = 2
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(10*n_cols, 5*n_rows))
        
        # Handle case with only one subplot
        if n_backends == 1:
            axes = [axes]
        
        # Flatten axes array if necessary for easier iteration
        if n_rows > 1 and n_cols > 1:
            axes = axes.flatten()
        
        # Plot health check history for each backend
        for i, backend in enumerate(backends):
            status_data = backend_health[backend]
            check_history = status_data.get("check_history", [])
            
            if not check_history:
                continue
            
            # Convert boolean values to integers for plotting (1 for success, 0 for failure)
            history_values = [1 if check else 0 for check in check_history]
            # Create x-axis points (just the indices)
            history_indices = list(range(len(history_values)))
            
            # Plot the check history
            ax = axes[i]
            ax.plot(history_indices, history_values, 'o-', color='#2196F3', linewidth=2)
            
            # Add a background color based on current status
            status = status_data.get("status", "unknown")
            status_colors = {
                "online": "#E8F5E9",    # Light green
                "offline": "#FFEBEE",   # Light red
                "degraded": "#FFF3E0",  # Light orange
                "unknown": "#ECEFF1"    # Light gray
            }
            ax.set_facecolor(status_colors.get(status, "#ECEFF1"))
            
            # Add labels and title
            ax.set_title(f'{backend.upper()} Status: {status.capitalize()}')
            ax.set_xlabel('Check Index')
            ax.set_ylabel('Status (1=Online, 0=Offline)')
            
            # Set y-axis limits with a bit of padding
            ax.set_ylim(-0.1, 1.1)
            
            # Set y-axis ticks to only show 0 and 1
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Offline', 'Online'])
            
            # Make x-axis show integers only
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            
            # Add success rate text
            success_rate = sum(history_values) / len(history_values) if history_values else 0
            ax.text(0.05, 0.05, f'Success Rate: {success_rate:.1%}', 
                   transform=ax.transAxes, fontsize=12, 
                   bbox=dict(facecolor='white', alpha=0.8))
        
        # Remove empty subplots if any
        for i in range(n_backends, len(axes)):
            fig.delaxes(axes[i])
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved backend health plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    async def plot_backend_health_async(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """Plot backend health status asynchronously.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot, or None to display
            
        Returns:
            Path to the saved plot, or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Define a function to create the plot
        def create_plot():
            # Extract data
            backend_health = stats.get("backend_health", {})
            
            if not backend_health:
                logger.error("No backend health data available.")
                return None
            
            # Create a figure with subplots for each backend
            backends = list(backend_health.keys())
            n_backends = len(backends)
            
            if n_backends == 0:
                return None
            
            # Determine grid layout based on number of backends
            if n_backends <= 2:
                n_rows, n_cols = 1, n_backends
            else:
                n_rows = (n_backends + 1) // 2  # Ceiling division
                n_cols = 2
            
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(10*n_cols, 5*n_rows))
            
            # Handle case with only one subplot
            if n_backends == 1:
                axes = [axes]
            
            # Flatten axes array if necessary for easier iteration
            if n_rows > 1 and n_cols > 1:
                axes = axes.flatten()
            
            # Plot health check history for each backend
            for i, backend in enumerate(backends):
                status_data = backend_health[backend]
                check_history = status_data.get("check_history", [])
                
                if not check_history:
                    continue
                
                # Convert boolean values to integers for plotting (1 for success, 0 for failure)
                history_values = [1 if check else 0 for check in check_history]
                # Create x-axis points (just the indices)
                history_indices = list(range(len(history_values)))
                
                # Plot the check history
                ax = axes[i]
                ax.plot(history_indices, history_values, 'o-', color='#2196F3', linewidth=2)
                
                # Add a background color based on current status
                status = status_data.get("status", "unknown")
                status_colors = {
                    "online": "#E8F5E9",    # Light green
                    "offline": "#FFEBEE",   # Light red
                    "degraded": "#FFF3E0",  # Light orange
                    "unknown": "#ECEFF1"    # Light gray
                }
                ax.set_facecolor(status_colors.get(status, "#ECEFF1"))
                
                # Add labels and title
                ax.set_title(f'{backend.upper()} Status: {status.capitalize()}')
                ax.set_xlabel('Check Index')
                ax.set_ylabel('Status (1=Online, 0=Offline)')
                
                # Set y-axis limits with a bit of padding
                ax.set_ylim(-0.1, 1.1)
                
                # Set y-axis ticks to only show 0 and 1
                ax.set_yticks([0, 1])
                ax.set_yticklabels(['Offline', 'Online'])
                
                # Make x-axis show integers only
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
                
                # Add success rate text
                success_rate = sum(history_values) / len(history_values) if history_values else 0
                ax.text(0.05, 0.05, f'Success Rate: {success_rate:.1%}', 
                       transform=ax.transAxes, fontsize=12, 
                       bbox=dict(facecolor='white', alpha=0.8))
            
            # Remove empty subplots if any
            for i in range(n_backends, len(axes)):
                fig.delaxes(axes[i])
            
            plt.tight_layout()
            
            # Save or display
            if output_path:
                plt.savefig(output_path)
                logger.info(f"Saved backend health plot to {output_path}")
                plt.close()
                return output_path
            else:
                plt.show()
                return None
        
        # Run the plotting in a worker thread
        return await anyio.to_thread.run_sync(create_plot)
    
    def create_dashboard(self, stats: Optional[Dict[str, Any]] = None, 
                        timeframe_hours: int = 24,
                        output_dir: Optional[str] = None) -> Dict[str, str]:
        """Create a complete dashboard with all visualizations.
        
        Args:
            stats: Statistics data or None to collect new data
            timeframe_hours: Number of hours to look back if collecting new data
            output_dir: Directory to save plots or None to use default
            
        Returns:
            Dictionary with paths to all generated plots
        """
        self._warn_if_async_context("create_dashboard")
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create dashboard.")
            return {}
        
        # Collect stats if not provided
        if stats is None:
            stats = self.collect_operation_stats(timeframe_hours=timeframe_hours)
        
        # Use default output directory if not specified
        if output_dir is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(self.data_dir, f"dashboard_{timestamp}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save stats
        stats_path = os.path.join(output_dir, "wal_stats.json")
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Create all plots
        plots = {}
        
        # Plot operation status
        status_plot_path = os.path.join(output_dir, "operation_status.png")
        self.plot_operation_status(stats, status_plot_path)
        plots["status"] = status_plot_path
        
        # Plot backend success rates
        success_plot_path = os.path.join(output_dir, "backend_success.png")
        self.plot_backend_success_rates(stats, success_plot_path)
        plots["success_rates"] = success_plot_path
        
        # Plot completion times
        times_plot_path = os.path.join(output_dir, "completion_times.png")
        self.plot_completion_times(stats, times_plot_path)
        plots["completion_times"] = times_plot_path
        
        # Plot timeline
        timeline_plot_path = os.path.join(output_dir, "timeline.png")
        self.plot_timeline(stats, timeline_plot_path)
        plots["timeline"] = timeline_plot_path
        
        # Plot backend health
        health_plot_path = os.path.join(output_dir, "backend_health.png")
        self.plot_backend_health(stats, health_plot_path)
        plots["backend_health"] = health_plot_path
        
        # Create an HTML report
        html_path = self._create_html_report(stats, plots, output_dir)
        plots["html_report"] = html_path
        
        logger.info(f"Created WAL dashboard in {output_dir}")
        
        return plots
    
    async def create_dashboard_async(self, stats: Optional[Dict[str, Any]] = None, 
                                   timeframe_hours: int = 24,
                                   output_dir: Optional[str] = None) -> Dict[str, str]:
        """Create a complete dashboard with all visualizations asynchronously.
        
        Args:
            stats: Statistics data or None to collect new data
            timeframe_hours: Number of hours to look back if collecting new data
            output_dir: Directory to save plots or None to use default
            
        Returns:
            Dictionary with paths to all generated plots
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create dashboard.")
            return {}
        
        # Collect stats if not provided
        if stats is None:
            stats = await self.collect_operation_stats_async(timeframe_hours=timeframe_hours)
        
        # Use default output directory if not specified
        if output_dir is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(self.data_dir, f"dashboard_{timestamp}")
        
        # Create output directory
        await anyio.to_thread.run_sync(lambda: os.makedirs(output_dir, exist_ok=True))
        
        # Save stats
        stats_path = os.path.join(output_dir, "wal_stats.json")
        await self.save_stats_async(stats, os.path.basename(stats_path))
        
        # Create all plots concurrently using AnyIO task group
        plots = {}
        
        async with anyio.create_task_group() as tg:
            # Plot operation status
            status_plot_path = os.path.join(output_dir, "operation_status.png")
            
            async def create_status_plot():
                path = await self.plot_operation_status_async(stats, status_plot_path)
                plots["status"] = path
            
            tg.start_soon(create_status_plot)
            
            # Plot backend success rates
            success_plot_path = os.path.join(output_dir, "backend_success.png")
            
            async def create_success_plot():
                path = await self.plot_backend_success_rates_async(stats, success_plot_path)
                plots["success_rates"] = path
            
            tg.start_soon(create_success_plot)
            
            # Plot completion times
            times_plot_path = os.path.join(output_dir, "completion_times.png")
            
            async def create_times_plot():
                path = await self.plot_completion_times_async(stats, times_plot_path)
                plots["completion_times"] = path
            
            tg.start_soon(create_times_plot)
            
            # Plot timeline
            timeline_plot_path = os.path.join(output_dir, "timeline.png")
            
            async def create_timeline_plot():
                path = await self.plot_timeline_async(stats, timeline_plot_path)
                plots["timeline"] = path
            
            tg.start_soon(create_timeline_plot)
            
            # Plot backend health
            health_plot_path = os.path.join(output_dir, "backend_health.png")
            
            async def create_health_plot():
                path = await self.plot_backend_health_async(stats, health_plot_path)
                plots["backend_health"] = path
            
            tg.start_soon(create_health_plot)
        
        # Create an HTML report
        html_path = await anyio.to_thread.run_sync(
            lambda: self._create_html_report(stats, plots, output_dir)
        )
        plots["html_report"] = html_path
        
        logger.info(f"Created WAL dashboard in {output_dir}")
        
        return plots
    
    def _create_html_report(self, stats: Dict[str, Any], plots: Dict[str, str], 
                          output_dir: str) -> str:
        """Create an HTML report with all visualizations.
        
        Args:
            stats: Statistics data
            plots: Dictionary with paths to plots
            output_dir: Directory to save the report
            
        Returns:
            Path to the HTML report
        """
        # Convert absolute paths to relative for the HTML
        rel_plots = {}
        for key, path in plots.items():
            if path:
                rel_plots[key] = os.path.basename(path)
        
        # Generate timestamp
        timestamp = datetime.datetime.fromtimestamp(stats.get("timestamp", time.time()))
        timeframe = stats.get("timeframe_hours", 24)
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>WAL Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                h1, h2 {{ color: #333; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background-color: #2196F3; color: white; padding: 20px; margin-bottom: 20px; }}
                .section {{ background-color: white; padding: 20px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .stats {{ display: flex; flex-wrap: wrap; }}
                .stat-card {{ background-color: #f9f9f9; padding: 15px; margin: 10px; border-radius: 5px; min-width: 150px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .plot {{ margin: 20px 0; text-align: center; }}
                .plot img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 30px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>WAL Dashboard</h1>
                    <p>Report generated on {timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Showing data for the past {timeframe} hours</p>
                </div>
                
                <div class="section">
                    <h2>Summary</h2>
                    <div class="stats">
                        <div class="stat-card">
                            <h3>Total Operations</h3>
                            <div class="stat-value">{stats.get("total_operations", 0)}</div>
                        </div>
                        
                        <div class="stat-card">
                            <h3>Pending</h3>
                            <div class="stat-value">{stats.get("status_counts", {}).get("pending", 0)}</div>
                        </div>
                        
                        <div class="stat-card">
                            <h3>Completed</h3>
                            <div class="stat-value">{stats.get("status_counts", {}).get("completed", 0)}</div>
                        </div>
                        
                        <div class="stat-card">
                            <h3>Failed</h3>
                            <div class="stat-value">{stats.get("status_counts", {}).get("failed", 0)}</div>
                        </div>
                    </div>
                </div>
        """
        
        # Add operation status plot if available
        if "status" in rel_plots:
            html_content += f"""
                <div class="section">
                    <h2>Operation Status</h2>
                    <div class="plot">
                        <img src="{rel_plots['status']}" alt="Operation Status">
                    </div>
                </div>
            """
        
        # Add backend success rates plot if available
        if "success_rates" in rel_plots:
            html_content += f"""
                <div class="section">
                    <h2>Backend Success Rates</h2>
                    <div class="plot">
                        <img src="{rel_plots['success_rates']}" alt="Backend Success Rates">
                    </div>
                </div>
            """
        
        # Add completion times plot if available
        if "completion_times" in rel_plots:
            html_content += f"""
                <div class="section">
                    <h2>Average Completion Times</h2>
                    <div class="plot">
                        <img src="{rel_plots['completion_times']}" alt="Completion Times">
                    </div>
                </div>
            """
        
        # Add timeline plot if available
        if "timeline" in rel_plots:
            html_content += f"""
                <div class="section">
                    <h2>Operation Timeline</h2>
                    <div class="plot">
                        <img src="{rel_plots['timeline']}" alt="Operation Timeline">
                    </div>
                </div>
            """
        
        # Add backend health plot if available
        if "backend_health" in rel_plots:
            html_content += f"""
                <div class="section">
                    <h2>Backend Health</h2>
                    <div class="plot">
                        <img src="{rel_plots['backend_health']}" alt="Backend Health">
                    </div>
                </div>
            """
        
        # Add backend details
        html_content += f"""
                <div class="section">
                    <h2>Backend Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background-color: #f2f2f2;">
                            <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Backend</th>
                            <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Status</th>
                            <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Success Rate</th>
                            <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Operations</th>
                        </tr>
        """
        
        # Add rows for each backend
        backend_health = stats.get("backend_health", {})
        backend_counts = stats.get("backend_counts", {})
        success_rates = stats.get("success_rates", {})
        
        for backend in sorted(set(list(backend_health.keys()) + list(backend_counts.keys()))):
            status = backend_health.get(backend, {}).get("status", "unknown")
            rate = success_rates.get(backend, 0) * 100  # Convert to percentage
            count = backend_counts.get(backend, 0)
            
            # Set row color based on status
            row_color = "#ffffff"
            if status == "online":
                row_color = "#e8f5e9"
            elif status == "offline":
                row_color = "#ffebee"
            elif status == "degraded":
                row_color = "#fff3e0"
            
            html_content += f"""
                <tr style="background-color: {row_color};">
                    <td style="padding: 10px; border: 1px solid #ddd;">{backend}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{status.capitalize()}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{rate:.1f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{count}</td>
                </tr>
            """
        
        html_content += """
                    </table>
                </div>
                
                <div class="footer">
                    <p>Generated by IPFS Kit WAL Visualization Tool with AnyIO Support</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Write HTML file
        html_path = os.path.join(output_dir, "wal_report.html")
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Created HTML report at {html_path}")
        
        return html_path

async def main_async():
    """Main function to run the visualization tool with AnyIO support."""
    import argparse
    
    parser = argparse.ArgumentParser(description="WAL Visualization Tool with AnyIO support")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--timeframe", type=int, default=24, help="Timeframe in hours (default: 24)")
    parser.add_argument("--output", help="Output directory for dashboard")
    parser.add_argument("--stats", help="Path to existing stats file to use")
    parser.add_argument("--collect-only", action="store_true", help="Only collect stats, don't create plots")
    parser.add_argument("--async-mode", action="store_true", help="Use async methods")
    args = parser.parse_args()
    
    # Create visualization tool
    vis = WALVisualizationAnyIO(config_path=args.config)
    
    # Load existing stats if provided
    stats = None
    if args.stats:
        if args.async_mode:
            stats = await vis.load_stats_async(args.stats)
        else:
            stats = vis.load_stats(args.stats)
    
    # Collect stats if not loaded from file
    if stats is None:
        if args.async_mode:
            stats = await vis.collect_operation_stats_async(timeframe_hours=args.timeframe)
        else:
            stats = vis.collect_operation_stats(timeframe_hours=args.timeframe)
    
    # Save collected stats
    if args.async_mode:
        stats_path = await vis.save_stats_async(stats)
    else:
        stats_path = vis.save_stats(stats)
    print(f"Statistics saved to {stats_path}")
    
    # Create dashboard if not collect-only
    if not args.collect_only:
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib not available. Cannot create dashboard.")
            return 1
        
        if args.async_mode:
            dashboard = await vis.create_dashboard_async(stats, output_dir=args.output)
        else:
            dashboard = vis.create_dashboard(stats, output_dir=args.output)
            
        if dashboard and "html_report" in dashboard:
            print(f"Dashboard created. HTML report: {dashboard['html_report']}")
        else:
            print("Failed to create dashboard.")
            return 1
    
    return 0

def main():
    """Main function to run the visualization tool standalone."""
    import argparse
    
    parser = argparse.ArgumentParser(description="WAL Visualization Tool with AnyIO support")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--timeframe", type=int, default=24, help="Timeframe in hours (default: 24)")
    parser.add_argument("--output", help="Output directory for dashboard")
    parser.add_argument("--stats", help="Path to existing stats file to use")
    parser.add_argument("--collect-only", action="store_true", help="Only collect stats, don't create plots")
    parser.add_argument("--async-mode", action="store_true", help="Use async methods")
    parser.add_argument("--backend", choices=["asyncio", "trio"], default="asyncio", help="AnyIO backend to use")
    args = parser.parse_args()
    
    if args.async_mode:
        import anyio
        return anyio.run(main_async, backend=args.backend)
    else:
        # Create visualization tool
        vis = WALVisualizationAnyIO(config_path=args.config)
        
        # Load existing stats if provided
        stats = None
        if args.stats:
            stats = vis.load_stats(args.stats)
        
        # Collect stats if not loaded from file
        if stats is None:
            stats = vis.collect_operation_stats(timeframe_hours=args.timeframe)
        
        # Save collected stats
        stats_path = vis.save_stats(stats)
        print(f"Statistics saved to {stats_path}")
        
        # Create dashboard if not collect-only
        if not args.collect_only:
            if not MATPLOTLIB_AVAILABLE:
                print("Matplotlib not available. Cannot create dashboard.")
                return 1
            
            dashboard = vis.create_dashboard(stats, output_dir=args.output)
            if dashboard and "html_report" in dashboard:
                print(f"Dashboard created. HTML report: {dashboard['html_report']}")
            else:
                print("Failed to create dashboard.")
                return 1
        
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())