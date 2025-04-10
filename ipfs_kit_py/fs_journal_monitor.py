"""
Filesystem Journal Monitoring and Visualization for IPFS Kit.

This module provides monitoring and visualization tools for the filesystem journal,
enabling tracking of journal operations, storage tier migrations, and recovery status.
It helps administrators and developers understand the health, performance and usage
patterns of the filesystem journal and tiered storage backends.

Key features:
1. Journal operation monitoring and statistics
2. Tiered storage migration visualization
3. Recovery performance tracking
4. Health and performance dashboards
5. Alert generation for potential issues
"""

import os
import time
import json
import logging
import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict, deque

# Optional visualization imports
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Import journal components
from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal, 
    FilesystemJournalManager,
    JournalOperationType, 
    JournalEntryStatus
)
from ipfs_kit_py.fs_journal_backends import (
    StorageBackendType,
    TieredStorageJournalBackend
)

# Configure logging
logger = logging.getLogger(__name__)

class JournalHealthMonitor:
    """
    Monitors the health and performance of the filesystem journal.
    
    This component is responsible for:
    1. Tracking journal operation statistics
    2. Monitoring journal growth and checkpoint frequency
    3. Alerting on potential issues
    4. Providing health status of the journal
    """
    
    def __init__(
        self,
        journal: Optional[FilesystemJournal] = None,
        backend: Optional[TieredStorageJournalBackend] = None,
        check_interval: int = 60,
        alert_callback: Optional[callable] = None,
        stats_dir: str = "~/.ipfs_kit/journal_stats"
    ):
        """
        Initialize the journal health monitor.
        
        Args:
            journal: FilesystemJournal instance to monitor
            backend: Optional TieredStorageJournalBackend instance
            check_interval: How often to check health (seconds)
            alert_callback: Function to call for alerts
            stats_dir: Directory to store stats
        """
        self.journal = journal
        self.backend = backend
        self.check_interval = check_interval
        self.alert_callback = alert_callback
        self.stats_dir = os.path.expanduser(stats_dir)
        
        # Create stats directory
        os.makedirs(self.stats_dir, exist_ok=True)
        
        # Health state
        self.health_status = "unknown"
        self.issues = []
        self.alerts = []
        self.alert_history = deque(maxlen=100)  # Last 100 alerts
        
        # Historical statistics
        self.stats_history = deque(maxlen=1440)  # 24 hours at 1 minute intervals
        
        # Alert thresholds
        self.thresholds = {
            "journal_size_warning": 1000,  # Number of entries
            "journal_growth_rate_warning": 50,  # Entries per minute
            "checkpoint_age_warning": 3600,  # Seconds
            "error_rate_warning": 0.1,  # 10% of operations
            "transaction_time_warning": 30,  # Seconds
        }
        
        # Track active transactions
        self.active_transactions = {}
        
        # Start monitoring thread
        self._stop_monitor = False
        self._monitor_thread = None
        self._start_monitoring()
        
        logger.info("Journal health monitor initialized")
    
    def _start_monitoring(self):
        """Start the monitoring thread."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        
        import threading
        self._stop_monitor = False
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="journal-health-monitor"
        )
        self._monitor_thread.start()
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self._stop_monitor:
            try:
                # Collect stats
                stats = self.collect_stats()
                
                # Analyze journal health
                self._analyze_health(stats)
                
                # Save stats to history
                self.stats_history.append(stats)
                
                # Periodically save stats to disk
                self._save_stats_periodically(stats)
                
            except Exception as e:
                logger.error(f"Error in journal monitoring loop: {e}")
            
            # Sleep until next check
            time.sleep(self.check_interval)
    
    def collect_stats(self) -> Dict[str, Any]:
        """
        Collect comprehensive statistics about the journal.
        
        Returns:
            Dictionary with journal statistics
        """
        stats = {
            "timestamp": time.time(),
            "journal": {},
            "backend": {},
            "transactions": {},
            "performance": {},
            "health": {}
        }
        
        # Collect journal stats if available
        if self.journal:
            # Get journal metadata
            stats["journal"]["current_journal_id"] = getattr(self.journal, "current_journal_id", "unknown")
            stats["journal"]["entry_count"] = getattr(self.journal, "entry_count", 0)
            stats["journal"]["last_sync_time"] = getattr(self.journal, "last_sync_time", 0)
            stats["journal"]["last_checkpoint_time"] = getattr(self.journal, "last_checkpoint_time", 0)
            stats["journal"]["in_transaction"] = getattr(self.journal, "in_transaction", False)
            
            # Count entries by type and status
            if hasattr(self.journal, "journal_entries"):
                entry_types = defaultdict(int)
                entry_statuses = defaultdict(int)
                for entry in self.journal.journal_entries:
                    op_type = entry.get("operation_type", "unknown")
                    status = entry.get("status", "unknown")
                    entry_types[op_type] += 1
                    entry_statuses[status] += 1
                
                stats["journal"]["entry_types"] = dict(entry_types)
                stats["journal"]["entry_statuses"] = dict(entry_statuses)
                
                # Checkpoint age
                if stats["journal"]["last_checkpoint_time"] > 0:
                    checkpoint_age = time.time() - stats["journal"]["last_checkpoint_time"]
                    stats["journal"]["checkpoint_age"] = checkpoint_age
                
                # Pending entries
                stats["journal"]["pending_entries"] = entry_statuses.get(JournalEntryStatus.PENDING.value, 0)
                
                # Journal growth rate (comparing to last stats)
                if self.stats_history:
                    last_stats = self.stats_history[-1]
                    last_entry_count = last_stats.get("journal", {}).get("entry_count", 0)
                    time_diff = stats["timestamp"] - last_stats.get("timestamp", stats["timestamp"])
                    
                    if time_diff > 0:
                        growth_rate = (stats["journal"]["entry_count"] - last_entry_count) / time_diff * 60
                        stats["journal"]["growth_rate_per_minute"] = growth_rate
        
        # Collect backend stats if available
        if self.backend:
            # Get tier stats
            if hasattr(self.backend, "tier_stats") and callable(getattr(self.backend, "get_tier_stats", None)):
                tier_stats = self.backend.get_tier_stats()
                stats["backend"]["tier_stats"] = tier_stats
                
                # Sum up total content items and bytes
                total_items = 0
                total_bytes = 0
                for tier, tier_data in tier_stats.items():
                    total_items += tier_data.get("items", 0)
                    total_bytes += tier_data.get("bytes_stored", 0)
                
                stats["backend"]["total_items"] = total_items
                stats["backend"]["total_bytes"] = total_bytes
            
            # Count content items by tier
            if hasattr(self.backend, "content_locations"):
                tier_counts = defaultdict(int)
                for cid, location in self.backend.content_locations.items():
                    tier = location.get("tier", "unknown")
                    tier_counts[tier] += 1
                
                stats["backend"]["content_by_tier"] = dict(tier_counts)
        
        # Collect transaction stats
        if self.journal:
            # Active transaction count
            stats["transactions"]["active_count"] = len(self.active_transactions)
            
            # Transaction duration statistics
            if hasattr(self, "transaction_times"):
                stats["transactions"]["avg_duration"] = (
                    sum(self.transaction_times) / len(self.transaction_times)
                    if self.transaction_times else 0
                )
                stats["transactions"]["max_duration"] = max(self.transaction_times) if self.transaction_times else 0
                stats["transactions"]["min_duration"] = min(self.transaction_times) if self.transaction_times else 0
        
        # Performance metrics
        if hasattr(self, "operation_times"):
            # Group operation times by type
            op_times = defaultdict(list)
            for op_type, duration in self.operation_times:
                op_times[op_type].append(duration)
            
            # Calculate average times by operation type
            avg_times = {}
            for op_type, times in op_times.items():
                avg_times[op_type] = sum(times) / len(times) if times else 0
            
            stats["performance"]["avg_operation_times"] = avg_times
            
            # Calculate overall average
            all_times = [time for times in op_times.values() for time in times]
            stats["performance"]["overall_avg_time"] = sum(all_times) / len(all_times) if all_times else 0
        
        # Health metrics
        stats["health"]["status"] = self.health_status
        stats["health"]["issue_count"] = len(self.issues)
        stats["health"]["alert_count"] = len(self.alerts)
        
        # Error rate
        if "journal" in stats and "entry_statuses" in stats["journal"]:
            total_entries = sum(stats["journal"]["entry_statuses"].values())
            error_count = stats["journal"]["entry_statuses"].get(JournalEntryStatus.FAILED.value, 0)
            
            if total_entries > 0:
                stats["health"]["error_rate"] = error_count / total_entries
            else:
                stats["health"]["error_rate"] = 0
        
        return stats
    
    def _analyze_health(self, stats: Dict[str, Any]):
        """
        Analyze journal health and generate alerts.
        
        Args:
            stats: Current journal statistics
        """
        issues = []
        
        # Check journal size
        if stats["journal"].get("entry_count", 0) > self.thresholds["journal_size_warning"]:
            issues.append({
                "type": "journal_size",
                "severity": "warning",
                "message": f"Journal has {stats['journal']['entry_count']} entries, which is above the warning threshold of {self.thresholds['journal_size_warning']}"
            })
        
        # Check journal growth rate
        if stats["journal"].get("growth_rate_per_minute", 0) > self.thresholds["journal_growth_rate_warning"]:
            issues.append({
                "type": "growth_rate",
                "severity": "warning",
                "message": f"Journal is growing at {stats['journal']['growth_rate_per_minute']:.1f} entries per minute, which is above the warning threshold of {self.thresholds['journal_growth_rate_warning']}"
            })
        
        # Check checkpoint age
        if stats["journal"].get("checkpoint_age", 0) > self.thresholds["checkpoint_age_warning"]:
            issues.append({
                "type": "checkpoint_age",
                "severity": "warning",
                "message": f"Last checkpoint was {stats['journal']['checkpoint_age']:.1f} seconds ago, which is above the warning threshold of {self.thresholds['checkpoint_age_warning']} seconds"
            })
        
        # Check error rate
        if stats["health"].get("error_rate", 0) > self.thresholds["error_rate_warning"]:
            issues.append({
                "type": "error_rate",
                "severity": "critical",
                "message": f"Journal has an error rate of {stats['health']['error_rate']:.1%}, which is above the warning threshold of {self.thresholds['error_rate_warning'] * 100}%"
            })
        
        # Check for active transactions
        if stats["journal"].get("in_transaction", False):
            # Check if any transaction has been active for too long
            for tx_id, tx_data in self.active_transactions.items():
                duration = time.time() - tx_data.get("start_time", time.time())
                if duration > self.thresholds["transaction_time_warning"]:
                    issues.append({
                        "type": "long_transaction",
                        "severity": "warning",
                        "message": f"Transaction {tx_id} has been active for {duration:.1f} seconds, which is above the warning threshold of {self.thresholds['transaction_time_warning']} seconds"
                    })
        
        # Update health status
        if issues:
            if any(issue["severity"] == "critical" for issue in issues):
                self.health_status = "critical"
            else:
                self.health_status = "warning"
        else:
            self.health_status = "healthy"
        
        # Update issues list
        self.issues = issues
        
        # Generate alerts for new issues
        current_issue_types = {issue["type"] for issue in issues}
        previous_issue_types = {issue["type"] for issue in self.issues}
        
        new_issue_types = current_issue_types - previous_issue_types
        
        for issue_type in new_issue_types:
            issue = next((i for i in issues if i["type"] == issue_type), None)
            if issue:
                alert = {
                    "timestamp": time.time(),
                    "type": issue["type"],
                    "severity": issue["severity"],
                    "message": issue["message"]
                }
                
                self.alerts.append(alert)
                self.alert_history.append(alert)
                
                # Call alert callback if provided
                if self.alert_callback:
                    try:
                        self.alert_callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
    
    def _save_stats_periodically(self, stats: Dict[str, Any]):
        """
        Periodically save stats to disk.
        
        Args:
            stats: Current statistics
        """
        # Save hourly stats
        current_time = datetime.datetime.fromtimestamp(stats["timestamp"])
        # Save on the hour or if it's been a long time since last save
        if current_time.minute == 0 or not hasattr(self, "_last_stats_save_time") or \
           (stats["timestamp"] - getattr(self, "_last_stats_save_time", 0)) > 3600:
            
            # Create date directory
            date_str = current_time.strftime("%Y-%m-%d")
            date_dir = os.path.join(self.stats_dir, date_str)
            os.makedirs(date_dir, exist_ok=True)
            
            # Create filename
            hour_str = current_time.strftime("%H")
            filename = f"journal_stats_{hour_str}.json"
            filepath = os.path.join(date_dir, filename)
            
            # Save stats
            with open(filepath, 'w') as f:
                json.dump(stats, f, indent=2)
            
            # Update last save time
            self._last_stats_save_time = stats["timestamp"]
            
            logger.info(f"Saved journal stats to {filepath}")
    
    def track_transaction(self, transaction_id: str, status: str, data: Optional[Dict[str, Any]] = None):
        """
        Track transaction start/commit/rollback.
        
        Args:
            transaction_id: Transaction ID
            status: 'begin', 'commit', or 'rollback'
            data: Additional transaction data
        """
        if not hasattr(self, "transaction_times"):
            self.transaction_times = []
        
        if status == "begin":
            # Record transaction start
            self.active_transactions[transaction_id] = {
                "start_time": time.time(),
                "data": data or {}
            }
        elif status in ("commit", "rollback"):
            # Record transaction end
            if transaction_id in self.active_transactions:
                start_time = self.active_transactions[transaction_id].get("start_time", time.time())
                duration = time.time() - start_time
                
                # Add to transaction times history
                self.transaction_times.append(duration)
                
                # Keep only the last 1000 transaction times
                if len(self.transaction_times) > 1000:
                    self.transaction_times = self.transaction_times[-1000:]
                
                # Remove from active transactions
                del self.active_transactions[transaction_id]
    
    def track_operation(self, operation_type: str, duration: float):
        """
        Track operation duration.
        
        Args:
            operation_type: Type of operation
            duration: Duration in seconds
        """
        if not hasattr(self, "operation_times"):
            self.operation_times = []
        
        # Add to operation times history
        self.operation_times.append((operation_type, duration))
        
        # Keep only the last 10000 operation times
        if len(self.operation_times) > 10000:
            self.operation_times = self.operation_times[-10000:]
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the current health status of the journal.
        
        Returns:
            Dictionary with health status
        """
        return {
            "status": self.health_status,
            "issues": self.issues.copy(),
            "alerts": len(self.alerts),
            "threshold_values": self.thresholds.copy(),
            "active_transactions": len(self.active_transactions)
        }
    
    def get_alerts(self, count: Optional[int] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get active alerts.
        
        Args:
            count: Maximum number of alerts to return
            severity: Filter by alert severity
            
        Returns:
            List of alert dictionaries
        """
        filtered_alerts = self.alerts
        
        # Filter by severity if specified
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]
        
        # Limit count if specified
        if count is not None:
            filtered_alerts = filtered_alerts[:count]
        
        return filtered_alerts
    
    def clear_alerts(self, severity: Optional[str] = None) -> int:
        """
        Clear active alerts.
        
        Args:
            severity: Only clear alerts of this severity
            
        Returns:
            Number of alerts cleared
        """
        if severity:
            # Only clear alerts of the specified severity
            original_count = len(self.alerts)
            self.alerts = [a for a in self.alerts if a["severity"] != severity]
            return original_count - len(self.alerts)
        else:
            # Clear all alerts
            count = len(self.alerts)
            self.alerts = []
            return count
    
    def set_threshold(self, name: str, value: Any) -> bool:
        """
        Set a health threshold.
        
        Args:
            name: Threshold name
            value: New threshold value
            
        Returns:
            True if successful, False otherwise
        """
        if name in self.thresholds:
            self.thresholds[name] = value
            return True
        return False
    
    def stop(self):
        """Stop monitoring."""
        self._stop_monitor = True
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        logger.info("Journal health monitor stopped")


class JournalVisualization:
    """
    Visualization tools for the filesystem journal.
    
    This component is responsible for:
    1. Collecting and displaying journal statistics
    2. Visualizing journal operations and performance
    3. Creating health dashboards
    4. Tracking tier migration patterns
    """
    
    def __init__(
        self,
        journal: Optional[FilesystemJournal] = None,
        backend: Optional[TieredStorageJournalBackend] = None,
        monitor: Optional[JournalHealthMonitor] = None,
        output_dir: str = "~/.ipfs_kit/journal_visualizations"
    ):
        """
        Initialize the visualization tools.
        
        Args:
            journal: FilesystemJournal instance to visualize
            backend: TieredStorageJournalBackend instance
            monitor: JournalHealthMonitor instance
            output_dir: Directory to save visualizations
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available. Visualization will be limited to data collection only.")
        
        self.journal = journal
        self.backend = backend
        self.monitor = monitor
        self.output_dir = os.path.expanduser(output_dir)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info("Journal visualization tools initialized")
    
    def collect_operation_stats(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """
        Collect operation statistics for visualization.
        
        Args:
            timeframe_hours: Number of hours to look back
            
        Returns:
            Dictionary with operation statistics
        """
        # Use the monitor if available
        if self.monitor and hasattr(self.monitor, "stats_history"):
            stats_history = list(self.monitor.stats_history)
            
            # Filter by timeframe
            start_time = time.time() - (timeframe_hours * 3600)
            filtered_stats = [s for s in stats_history if s.get("timestamp", 0) >= start_time]
            
            if not filtered_stats:
                return {"success": False, "error": "No data available for the specified timeframe"}
            
            # Extract timestamps for timeline
            timestamps = [s.get("timestamp") for s in filtered_stats]
            
            # Extract journal metrics
            journal_entry_counts = [s.get("journal", {}).get("entry_count", 0) for s in filtered_stats]
            checkpoint_ages = [s.get("journal", {}).get("checkpoint_age", 0) for s in filtered_stats]
            growth_rates = [s.get("journal", {}).get("growth_rate_per_minute", 0) for s in filtered_stats]
            
            # Extract backend metrics
            total_items = [s.get("backend", {}).get("total_items", 0) for s in filtered_stats]
            total_bytes = [s.get("backend", {}).get("total_bytes", 0) for s in filtered_stats]
            
            # Extract performance metrics
            operation_times = {}
            for s in filtered_stats:
                avg_times = s.get("performance", {}).get("avg_operation_times", {})
                for op_type, avg_time in avg_times.items():
                    if op_type not in operation_times:
                        operation_times[op_type] = []
                    operation_times[op_type].append(avg_time)
            
            # Extract error rates
            error_rates = [s.get("health", {}).get("error_rate", 0) for s in filtered_stats]
            
            # Extract entries by type from the most recent stat
            latest_stat = filtered_stats[-1]
            entry_types = latest_stat.get("journal", {}).get("entry_types", {})
            entry_statuses = latest_stat.get("journal", {}).get("entry_statuses", {})
            
            # Extract content by tier
            content_by_tier = latest_stat.get("backend", {}).get("content_by_tier", {})
            
            # Extract tier stats for visualization
            tier_stats = latest_stat.get("backend", {}).get("tier_stats", {})
            
            return {
                "success": True,
                "timeframe_hours": timeframe_hours,
                "timestamps": timestamps,
                "journal_metrics": {
                    "entry_counts": journal_entry_counts,
                    "checkpoint_ages": checkpoint_ages,
                    "growth_rates": growth_rates
                },
                "backend_metrics": {
                    "total_items": total_items,
                    "total_bytes": total_bytes,
                    "content_by_tier": content_by_tier,
                    "tier_stats": tier_stats
                },
                "performance_metrics": {
                    "operation_times": operation_times,
                    "error_rates": error_rates
                },
                "entry_types": entry_types,
                "entry_statuses": entry_statuses,
                "health_status": latest_stat.get("health", {}).get("status", "unknown"),
                "active_transactions": latest_stat.get("transactions", {}).get("active_count", 0),
                "collected_at": time.time()
            }
        else:
            # Collect directly from the journal if monitor not available
            stats = {
                "success": True,
                "timeframe_hours": timeframe_hours,
                "timestamps": [time.time()],
                "journal_metrics": {},
                "backend_metrics": {},
                "performance_metrics": {},
                "entry_types": {},
                "entry_statuses": {},
                "health_status": "unknown",
                "active_transactions": 0,
                "collected_at": time.time()
            }
            
            # Collect journal metrics if available
            if self.journal:
                if hasattr(self.journal, "journal_entries"):
                    # Count entries by type and status
                    entry_types = defaultdict(int)
                    entry_statuses = defaultdict(int)
                    for entry in self.journal.journal_entries:
                        op_type = entry.get("operation_type", "unknown")
                        status = entry.get("status", "unknown")
                        entry_types[op_type] += 1
                        entry_statuses[status] += 1
                    
                    stats["entry_types"] = dict(entry_types)
                    stats["entry_statuses"] = dict(entry_statuses)
                
                stats["journal_metrics"] = {
                    "entry_counts": [getattr(self.journal, "entry_count", 0)],
                    "checkpoint_ages": [time.time() - getattr(self.journal, "last_checkpoint_time", time.time())],
                    "growth_rates": [0]  # No history available
                }
                
                stats["active_transactions"] = 1 if getattr(self.journal, "in_transaction", False) else 0
            
            # Collect backend metrics if available
            if self.backend:
                tier_stats = self.backend.get_tier_stats() if hasattr(self.backend, "get_tier_stats") else {}
                
                # Count items by tier
                content_by_tier = {}
                if hasattr(self.backend, "content_locations"):
                    for cid, location in self.backend.content_locations.items():
                        tier = location.get("tier", "unknown")
                        if tier not in content_by_tier:
                            content_by_tier[tier] = 0
                        content_by_tier[tier] += 1
                
                # Calculate totals
                total_items = sum(tier_data.get("items", 0) for tier_data in tier_stats.values())
                total_bytes = sum(tier_data.get("bytes_stored", 0) for tier_data in tier_stats.values())
                
                stats["backend_metrics"] = {
                    "total_items": [total_items],
                    "total_bytes": [total_bytes],
                    "content_by_tier": content_by_tier,
                    "tier_stats": tier_stats
                }
            
            return stats
    
    def save_stats(self, stats: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save statistics to a file.
        
        Args:
            stats: Statistics data
            filename: Optional filename (generated if not provided)
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"journal_stats_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Saved journal statistics to {filepath}")
        return filepath
    
    def load_stats(self, filepath: str) -> Dict[str, Any]:
        """
        Load statistics from a file.
        
        Args:
            filepath: Path to the statistics file
            
        Returns:
            Dictionary with statistics data
        """
        with open(filepath, 'r') as f:
            stats = json.load(f)
        
        logger.info(f"Loaded journal statistics from {filepath}")
        return stats
    
    def plot_entry_types(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot distribution of journal entry types.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        entry_types = stats.get("entry_types", {})
        if not entry_types:
            logger.error("No entry type data available")
            return None
        
        types = list(entry_types.keys())
        counts = [entry_types[t] for t in types]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        colors = plt.cm.tab10(np.linspace(0, 1, len(types)))
        bars = plt.bar(types, counts, color=colors)
        
        # Add labels and title
        plt.title('Journal Entry Types Distribution')
        plt.xlabel('Operation Type')
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
            logger.info(f"Saved entry types plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_entry_statuses(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot distribution of journal entry statuses.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        entry_statuses = stats.get("entry_statuses", {})
        if not entry_statuses:
            logger.error("No entry status data available")
            return None
        
        statuses = list(entry_statuses.keys())
        counts = [entry_statuses[s] for s in statuses]
        
        # Status color mapping
        status_colors = {
            JournalEntryStatus.PENDING.value: "#FF9800",  # Orange
            JournalEntryStatus.COMPLETED.value: "#4CAF50",  # Green
            JournalEntryStatus.FAILED.value: "#F44336",  # Red
            JournalEntryStatus.ROLLED_BACK.value: "#9C27B0",  # Purple
            "unknown": "#757575"  # Gray
        }
        
        # Map colors to statuses
        colors = [status_colors.get(s, "#757575") for s in statuses]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        bars = plt.bar(statuses, counts, color=colors)
        
        # Add labels and title
        plt.title('Journal Entry Status Distribution')
        plt.xlabel('Status')
        plt.ylabel('Count')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    '%d' % int(height), ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved entry statuses plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_journal_growth(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot journal growth over time.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        timestamps = stats.get("timestamps", [])
        entry_counts = stats.get("journal_metrics", {}).get("entry_counts", [])
        
        if not timestamps or not entry_counts or len(timestamps) != len(entry_counts):
            logger.error("Invalid data for journal growth plot")
            return None
        
        # Convert timestamps to datetime objects
        dates = [datetime.datetime.fromtimestamp(ts) for ts in timestamps]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        plt.plot(dates, entry_counts, 'b-', marker='o', linewidth=2)
        
        # Add labels and title
        plt.title('Journal Growth Over Time')
        plt.xlabel('Time')
        plt.ylabel('Number of Entries')
        
        # Format x-axis with date formatter
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gcf().autofmt_xdate()
        
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved journal growth plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_tier_distribution(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot content distribution across storage tiers.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        content_by_tier = stats.get("backend_metrics", {}).get("content_by_tier", {})
        
        if not content_by_tier:
            logger.error("No tier distribution data available")
            return None
        
        tiers = list(content_by_tier.keys())
        counts = [content_by_tier[t] for t in tiers]
        
        # Create color map
        cmap = plt.cm.viridis
        colors = cmap(np.linspace(0, 1, len(tiers)))
        
        # Create plot
        plt.figure(figsize=(10, 6))
        
        # If there are more than 5 tiers, use a pie chart
        if len(tiers) > 5:
            plt.pie(counts, labels=tiers, autopct='%1.1f%%', startangle=90, colors=colors)
            plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
            plt.title('Content Distribution Across Storage Tiers')
        else:
            # Otherwise use a bar chart
            bars = plt.bar(tiers, counts, color=colors)
            plt.title('Content Distribution Across Storage Tiers')
            plt.xlabel('Storage Tier')
            plt.ylabel('Item Count')
            
            # Add count labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        '%d' % int(height), ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved tier distribution plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_operation_times(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot average operation times by operation type.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        operation_times = stats.get("performance_metrics", {}).get("operation_times", {})
        
        if not operation_times:
            logger.error("No operation time data available")
            return None
        
        # Calculate average times for each operation type
        op_types = list(operation_times.keys())
        avg_times = [sum(operation_times[op])/len(operation_times[op]) if operation_times[op] else 0 
                    for op in op_types]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        bars = plt.bar(op_types, avg_times, color=plt.cm.tab20(np.linspace(0, 1, len(op_types))))
        
        # Add labels and title
        plt.title('Average Operation Times by Type')
        plt.xlabel('Operation Type')
        plt.ylabel('Average Time (seconds)')
        plt.xticks(rotation=45, ha='right')
        
        # Add time labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    '%.3fs' % height, ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved operation times plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_error_rate(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot error rate over time.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        timestamps = stats.get("timestamps", [])
        error_rates = stats.get("performance_metrics", {}).get("error_rates", [])
        
        if not timestamps or not error_rates or len(timestamps) != len(error_rates):
            logger.error("Invalid data for error rate plot")
            return None
        
        # Convert timestamps to datetime objects
        dates = [datetime.datetime.fromtimestamp(ts) for ts in timestamps]
        
        # Convert error rates to percentages
        error_percentages = [rate * 100 for rate in error_rates]
        
        # Create plot
        plt.figure(figsize=(10, 6))
        plt.plot(dates, error_percentages, 'r-', marker='o', linewidth=2)
        
        # Add threshold line if available
        if self.monitor and hasattr(self.monitor, "thresholds"):
            threshold = self.monitor.thresholds.get("error_rate_warning", 0.1) * 100
            plt.axhline(y=threshold, color='orange', linestyle='--', 
                       label=f'Warning Threshold ({threshold:.1f}%)')
            plt.legend()
        
        # Add labels and title
        plt.title('Error Rate Over Time')
        plt.xlabel('Time')
        plt.ylabel('Error Rate (%)')
        
        # Format x-axis with date formatter
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gcf().autofmt_xdate()
        
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved error rate plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def plot_tier_storage_usage(self, stats: Dict[str, Any], output_path: Optional[str] = None):
        """
        Plot storage usage by tier.
        
        Args:
            stats: Statistics data
            output_path: Optional path to save the plot
            
        Returns:
            Path to the saved plot or None if displayed
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create plot.")
            return None
        
        # Extract data
        tier_stats = stats.get("backend_metrics", {}).get("tier_stats", {})
        
        if not tier_stats:
            logger.error("No tier storage data available")
            return None
        
        tiers = []
        bytes_stored = []
        operations = []
        item_counts = []
        
        for tier, tier_data in tier_stats.items():
            tiers.append(tier)
            bytes_stored.append(tier_data.get("bytes_stored", 0))
            operations.append(tier_data.get("operations", 0))
            item_counts.append(tier_data.get("items", 0))
        
        # Convert bytes to MB for readability
        bytes_mb = [b / (1024 * 1024) for b in bytes_stored]
        
        # Create plot
        plt.figure(figsize=(12, 8))
        
        # Create subplots
        plt.subplot(2, 1, 1)
        bars1 = plt.bar(tiers, bytes_mb, color=plt.cm.viridis(np.linspace(0, 1, len(tiers))))
        plt.title('Storage Usage by Tier')
        plt.ylabel('Storage (MB)')
        plt.xticks(rotation=45, ha='right')
        
        # Add storage labels on top of bars
        for bar in bars1:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        '%.1f MB' % height, ha='center', va='bottom')
        
        # Second subplot for operations
        plt.subplot(2, 1, 2)
        bars2 = plt.bar(tiers, item_counts, color=plt.cm.plasma(np.linspace(0, 1, len(tiers))))
        plt.title('Item Count by Tier')
        plt.ylabel('Item Count')
        plt.xticks(rotation=45, ha='right')
        
        # Add count labels on top of bars
        for bar in bars2:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        '%d' % int(height), ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save or display
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Saved tier storage usage plot to {output_path}")
            plt.close()
            return output_path
        else:
            plt.show()
            return None
    
    def create_dashboard(self, stats: Optional[Dict[str, Any]] = None, 
                        timeframe_hours: int = 24,
                        output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Create a complete dashboard with all visualizations.
        
        Args:
            stats: Statistics data or None to collect fresh
            timeframe_hours: Number of hours to look back
            output_dir: Directory to save visualizations
            
        Returns:
            Dictionary with paths to generated plots
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("Matplotlib not available. Cannot create dashboard.")
            return {}
        
        # Collect stats if not provided
        if stats is None:
            stats = self.collect_operation_stats(timeframe_hours=timeframe_hours)
        
        # Use default output directory if not specified
        if output_dir is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(self.output_dir, f"dashboard_{timestamp}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save stats
        stats_path = os.path.join(output_dir, "journal_stats.json")
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Create all plots
        plots = {}
        
        # Plot entry types
        entry_types_path = os.path.join(output_dir, "entry_types.png")
        self.plot_entry_types(stats, entry_types_path)
        plots["entry_types"] = entry_types_path
        
        # Plot entry statuses
        entry_statuses_path = os.path.join(output_dir, "entry_statuses.png")
        self.plot_entry_statuses(stats, entry_statuses_path)
        plots["entry_statuses"] = entry_statuses_path
        
        # Plot journal growth
        journal_growth_path = os.path.join(output_dir, "journal_growth.png")
        self.plot_journal_growth(stats, journal_growth_path)
        plots["journal_growth"] = journal_growth_path
        
        # Plot tier distribution
        tier_distribution_path = os.path.join(output_dir, "tier_distribution.png")
        self.plot_tier_distribution(stats, tier_distribution_path)
        plots["tier_distribution"] = tier_distribution_path
        
        # Plot operation times
        operation_times_path = os.path.join(output_dir, "operation_times.png")
        self.plot_operation_times(stats, operation_times_path)
        plots["operation_times"] = operation_times_path
        
        # Plot error rate
        error_rate_path = os.path.join(output_dir, "error_rate.png")
        self.plot_error_rate(stats, error_rate_path)
        plots["error_rate"] = error_rate_path
        
        # Plot tier storage usage
        tier_storage_path = os.path.join(output_dir, "tier_storage.png")
        self.plot_tier_storage_usage(stats, tier_storage_path)
        plots["tier_storage"] = tier_storage_path
        
        # Create HTML report
        html_path = self._create_html_report(stats, plots, output_dir)
        plots["html_report"] = html_path
        
        logger.info(f"Created journal dashboard in {output_dir}")
        
        return plots
    
    def _create_html_report(self, stats: Dict[str, Any], plots: Dict[str, str], 
                          output_dir: str) -> str:
        """
        Create an HTML report with all visualizations.
        
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
        timestamp = datetime.datetime.fromtimestamp(stats.get("collected_at", time.time()))
        timeframe = stats.get("timeframe_hours", 24)
        
        # Extract high-level metrics
        health_status = stats.get("health_status", "unknown")
        total_entries = stats.get("journal_metrics", {}).get("entry_counts", [0])[-1]
        total_items = stats.get("backend_metrics", {}).get("total_items", [0])[-1]
        active_transactions = stats.get("active_transactions", 0)
        
        # Calculate completion rate
        entry_statuses = stats.get("entry_statuses", {})
        completed = entry_statuses.get(JournalEntryStatus.COMPLETED.value, 0)
        total = sum(entry_statuses.values())
        completion_rate = (completed / total) * 100 if total > 0 else 0
        
        # Get additional metrics for gauges
        checkpoint_age = stats.get("journal_metrics", {}).get("checkpoint_ages", [0])[-1] if stats.get("journal_metrics", {}).get("checkpoint_ages") else 0
        error_rate = stats.get("performance_metrics", {}).get("error_rates", [0])[-1] if stats.get("performance_metrics", {}).get("error_rates") else 0
        growth_rate = stats.get("journal_metrics", {}).get("growth_rates", [0])[-1] if stats.get("journal_metrics", {}).get("growth_rates") else 0
        
        # Calculate thresholds for gauges
        checkpoint_age_max = max(checkpoint_age * 2, 3600)  # At least 1 hour
        error_rate_max = max(error_rate * 2, 0.1)  # At least 10%
        growth_rate_max = max(growth_rate * 2, 50)  # At least 50 entries/min
        
        # Create HTML content with enhanced styling and interactive elements
        # Using string concatenation instead of f-strings to avoid JavaScript variable conflicts
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Filesystem Journal Dashboard</title>
            <style>
                :root {
                    --primary-color: #2196F3;
                    --secondary-color: #03A9F4;
                    --success-color: #4CAF50;
                    --warning-color: #FF9800;
                    --danger-color: #F44336;
                    --dark-color: #333;
                    --light-color: #f5f5f5;
                    --text-color: #212121;
                    --card-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    --chart-bg: #ffffff;
                }
                
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: var(--light-color);
                    color: var(--text-color);
                    line-height: 1.6;
                }
                
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                
                .header {{
                    background-color: var(--primary-color);
                    color: white;
                    padding: 25px;
                    margin-bottom: 30px;
                    border-radius: 8px;
                    box-shadow: var(--card-shadow);
                }}
                
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 600;
                }}
                
                .header p {{
                    margin: 5px 0 0;
                    opacity: 0.9;
                }}
                
                .status-banner {{
                    padding: 15px;
                    margin-bottom: 30px;
                    border-radius: 8px;
                    text-align: center;
                    font-weight: bold;
                    font-size: 18px;
                    box-shadow: var(--card-shadow);
                }}
                
                .status-healthy {{
                    background-color: var(--success-color);
                    color: white;
                }}
                
                .status-warning {{
                    background-color: var(--warning-color);
                    color: white;
                }}
                
                .status-critical {{
                    background-color: var(--danger-color);
                    color: white;
                }}
                
                .status-unknown {{
                    background-color: #9E9E9E;
                    color: white;
                }}
                
                .stats-row {{
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    margin-bottom: 30px;
                    gap: 20px;
                }}
                
                .stat-card {{
                    background-color: var(--chart-bg);
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: var(--card-shadow);
                    flex: 1;
                    min-width: 200px;
                    text-align: center;
                    transition: transform 0.2s ease-in-out;
                }}
                
                .stat-card:hover {{
                    transform: translateY(-5px);
                }}
                
                .stat-icon {{
                    font-size: 24px;
                    margin-bottom: 10px;
                    color: var(--primary-color);
                }}
                
                .stat-value {{
                    font-size: 28px;
                    font-weight: bold;
                    margin: 10px 0;
                    color: var(--dark-color);
                }}
                
                .stat-label {{
                    font-size: 14px;
                    color: #666;
                    margin-bottom: 5px;
                }}
                
                .plot-section {{
                    background-color: var(--chart-bg);
                    border-radius: 8px;
                    padding: 25px;
                    margin-bottom: 30px;
                    box-shadow: var(--card-shadow);
                }}
                
                .plot-section h2 {{
                    margin-top: 0;
                    color: var(--dark-color);
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                
                .plot-row {{
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    gap: 20px;
                }}
                
                .plot-card {{
                    flex: 1;
                    min-width: 300px;
                    transition: transform 0.2s ease-in-out;
                }}
                
                .plot-card:hover {{
                    transform: scale(1.02);
                }}
                
                .plot-card h3 {{
                    color: var(--dark-color);
                    margin-top: 0;
                    margin-bottom: 15px;
                }}
                
                .plot-card img {{
                    width: 100%;
                    height: auto;
                    border-radius: 8px;
                    border: 1px solid #eee;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                
                .data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                
                .data-table th {{
                    background-color: #f2f2f2;
                    padding: 12px;
                    text-align: left;
                    border: 1px solid #ddd;
                    font-weight: 600;
                }}
                
                .data-table td {{
                    padding: 12px;
                    border: 1px solid #ddd;
                }}
                
                .data-table tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                
                .data-table tr:hover {{
                    background-color: #f5f5f5;
                }}
                
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    color: #777;
                    padding: 20px 0;
                    border-top: 1px solid #eee;
                }}
                
                /* Gauge styles */
                .gauge-container {{
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    margin-bottom: 20px;
                    gap: 20px;
                }}
                
                .gauge-wrapper {{
                    flex: 1;
                    min-width: 200px;
                    text-align: center;
                }}
                
                .gauge {{
                    width: 150px;
                    height: 150px;
                    margin: 0 auto;
                    position: relative;
                }}
                
                .gauge-title {{
                    font-size: 14px;
                    font-weight: 600;
                    margin-top: 10px;
                }}
                
                .gauge-value {{
                    font-size: 20px;
                    font-weight: bold;
                    color: var(--dark-color);
                }}
                
                /* Responsive design */
                @media (max-width: 768px) {{
                    .container {{
                        padding: 15px;
                    }}
                    
                    .stats-row, .gauge-container {{
                        flex-direction: column;
                    }}
                    
                    .stat-card, .gauge-wrapper {{
                        width: 100%;
                    }}
                    
                    .plot-card {{
                        min-width: 100%;
                    }}
                }}

                /* Alert styles */
                .alert-box {{
                    border-left: 4px solid var(--primary-color);
                    background-color: rgba(33, 150, 243, 0.1);
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 4px;
                }}
                
                .alert-warning {{
                    border-left-color: var(--warning-color);
                    background-color: rgba(255, 152, 0, 0.1);
                }}
                
                .alert-critical {{
                    border-left-color: var(--danger-color);
                    background-color: rgba(244, 67, 54, 0.1);
                }}
                
                .alert-success {{
                    border-left-color: var(--success-color);
                    background-color: rgba(76, 175, 80, 0.1);
                }}
                
                .alert-title {{
                    margin-top: 0;
                    margin-bottom: 10px;
                    font-weight: 600;
                    font-size: 16px;
                }}
                
                .alert-message {{
                    margin: 0;
                    color: #555;
                }}
                
                /* Progress bars */
                .progress-container {{
                    margin-bottom: 15px;
                }}
                
                .progress-label {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 5px;
                }}
                
                .progress-bar {{
                    height: 10px;
                    background-color: #e0e0e0;
                    border-radius: 10px;
                    overflow: hidden;
                }}
                
                .progress-fill {{
                    height: 100%;
                    background-color: var(--primary-color);
                    border-radius: 10px;
                }}
                
                .progress-success {{
                    background-color: var(--success-color);
                }}
                
                .progress-warning {{
                    background-color: var(--warning-color);
                }}
                
                .progress-danger {{
                    background-color: var(--danger-color);
                }}
                
                /* Chart container styles */
                .chart-container {{
                    position: relative;
                    height: 300px;
                    margin-bottom: 20px;
                }}
                
                .dashboard-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                
                .dashboard-card {{
                    background-color: var(--chart-bg);
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: var(--card-shadow);
                }}
                
                .data-label {{
                    font-size: 13px;
                    color: #666;
                    margin-bottom: 5px;
                }}
                
                .data-value {{
                    font-size: 16px;
                    font-weight: 600;
                    color: var(--dark-color);
                    margin-bottom: 15px;
                }}
                
                /* Tabs for detailed views */
                .tabs {{
                    overflow: hidden;
                    border: 1px solid #ccc;
                    background-color: #f1f1f1;
                    border-radius: 8px 8px 0 0;
                }}
                
                .tab-button {{
                    background-color: inherit;
                    float: left;
                    border: none;
                    outline: none;
                    cursor: pointer;
                    padding: 14px 16px;
                    transition: 0.3s;
                    font-size: 16px;
                }}
                
                .tab-button:hover {{
                    background-color: #ddd;
                }}
                
                .tab-button.active {{
                    background-color: var(--primary-color);
                    color: white;
                }}
                
                .tab-content {{
                    display: none;
                    padding: 20px;
                    border: 1px solid #ccc;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
            </style>
            <!-- Include Chart.js for interactive charts -->
            <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.0/dist/chart.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/gauge-chart@0.5.3/dist/bundle.js"></script>
            <script>
                // Wait for page to load
                document.addEventListener('DOMContentLoaded', function() {
                    // Create gauge charts
                    // Values will be injected by the backend when generating the report
                    createGaugeChart('checkpoint-gauge', 50, 'Checkpoint Age', '30s');
                    createGaugeChart('error-gauge', 30, 'Error Rate', '0.1%');
                    createGaugeChart('growth-gauge', 20, 'Growth Rate', '10/min');
                    
                    // Setup tabs if they exist
                    var tabButtons = document.querySelectorAll('.tab-button');
                    if (tabButtons.length > 0) {
                        for (var i = 0; i < tabButtons.length; i++) {
                            tabButtons[i].addEventListener('click', function() {
                                var tabName = this.getAttribute('data-tab');
                                openTab(tabName);
                            });
                        }
                        
                        // Activate the first tab by default
                        tabButtons[0].click();
                    }
                });
                
                function createGaugeChart(elementId, value, title, displayValue) {
                    var element = document.getElementById(elementId);
                    if (!element) return;
                    
                    var options = {
                        arcWidth: 0.2,
                        width: 150,
                        height: 150,
                        arrow: true,
                        valueContainer: {
                            style: {
                                fontSize: '16px',
                                fontWeight: 'bold',
                                color: '#333'
                            }
                        },
                        arcColors: ['#4CAF50', '#FFEB3B', '#F44336'],
                        arcDelimiters: [33, 66]
                    };
                    
                    // Create the gauge
                    var gaugeChart = GaugeChart.create(element, options);
                    gaugeChart.updateValue(value / 100);
                    
                    // Set the value text
                    var valueElement = document.querySelector('#' + elementId + ' + .gauge-value');
                    if (valueElement) {
                        valueElement.textContent = displayValue;
                    }
                }
                
                function openTab(tabName) {
                    var tabContents = document.getElementsByClassName('tab-content');
                    for (var i = 0; i < tabContents.length; i++) {
                        tabContents[i].style.display = 'none';
                    }
                    
                    var tabButtons = document.getElementsByClassName('tab-button');
                    for (var i = 0; i < tabButtons.length; i++) {
                        tabButtons[i].className = tabButtons[i].className.replace(' active', '');
                    }
                    
                    document.getElementById(tabName).style.display = 'block';
                    document.querySelector('.tab-button[data-tab="' + tabName + '"]').className += ' active';
                }
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Filesystem Journal Dashboard</h1>
                    <p>Generated on {timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Showing data for the past {timeframe} hours</p>
                </div>
                
                <div class="status-banner status-{health_status}">
                    Journal Health Status: {health_status.upper()}
                </div>
                
                <!-- Summary metrics -->
                <div class="stats-row">
                    <div class="stat-card">
                        <div class="stat-icon">📝</div>
                        <div class="stat-label">Journal Entries</div>
                        <div class="stat-value">{total_entries}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">🗃️</div>
                        <div class="stat-label">Content Items</div>
                        <div class="stat-value">{total_items}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-label">Completion Rate</div>
                        <div class="stat-value">{completion_rate:.1f}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⚙️</div>
                        <div class="stat-label">Active Transactions</div>
                        <div class="stat-value">{active_transactions}</div>
                    </div>
                </div>
                
                <!-- Key Performance Indicators Gauges -->
                <div class="plot-section">
                    <h2>Key Performance Indicators</h2>
                    <div class="gauge-container">
                        <div class="gauge-wrapper">
                            <div class="gauge" id="checkpoint-gauge"></div>
                            <div class="gauge-title">Checkpoint Age</div>
                            <div class="gauge-value">{checkpoint_age:.1f}s</div>
                        </div>
                        <div class="gauge-wrapper">
                            <div class="gauge" id="error-gauge"></div>
                            <div class="gauge-title">Error Rate</div>
                            <div class="gauge-value">{error_rate:.2%}</div>
                        </div>
                        <div class="gauge-wrapper">
                            <div class="gauge" id="growth-gauge"></div>
                            <div class="gauge-title">Growth Rate</div>
                            <div class="gauge-value">{growth_rate:.1f}/min</div>
                        </div>
                    </div>
                </div>
        """
        
        # Add journal metrics section with plots
        html_content += """
                <div class="plot-section">
                    <h2>Journal Metrics</h2>
                    <div class="plot-row">
        """
        
        if "journal_growth" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Journal Growth</h3>
                            <img src="{rel_plots['journal_growth']}" alt="Journal Growth">
                        </div>
            """
        
        if "entry_types" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Entry Types</h3>
                            <img src="{rel_plots['entry_types']}" alt="Entry Types">
                        </div>
            """
        
        html_content += """
                    </div>
                    <div class="plot-row">
        """
        
        if "entry_statuses" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Entry Statuses</h3>
                            <img src="{rel_plots['entry_statuses']}" alt="Entry Statuses">
                        </div>
            """
        
        if "error_rate" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Error Rate</h3>
                            <img src="{rel_plots['error_rate']}" alt="Error Rate">
                        </div>
            """
        
        html_content += """
                    </div>
                </div>
        """
        
        # Add storage metrics section with plots
        html_content += """
                <div class="plot-section">
                    <h2>Storage Metrics</h2>
                    <div class="plot-row">
        """
        
        if "tier_distribution" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Content Distribution</h3>
                            <img src="{rel_plots['tier_distribution']}" alt="Tier Distribution">
                        </div>
            """
        
        if "tier_storage" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Storage Usage</h3>
                            <img src="{rel_plots['tier_storage']}" alt="Tier Storage Usage">
                        </div>
            """
        
        html_content += """
                    </div>
                </div>
        """
        
        # Add performance metrics section with plots
        html_content += """
                <div class="plot-section">
                    <h2>Performance Metrics</h2>
                    <div class="plot-row">
        """
        
        if "operation_times" in rel_plots:
            html_content += f"""
                        <div class="plot-card">
                            <h3>Operation Times</h3>
                            <img src="{rel_plots['operation_times']}" alt="Operation Times">
                        </div>
            """
        
        html_content += """
                    </div>
                </div>
        """
        
        # Add tabs for detailed data views
        html_content += """
                <div class="plot-section">
                    <h2>Detailed Data Analysis</h2>
                    <div class="tabs">
                        <button class="tab-button" data-tab="storage-tab">Storage Tiers</button>
                        <button class="tab-button" data-tab="journal-tab">Journal Entries</button>
                        <button class="tab-button" data-tab="health-tab">Health Status</button>
                    </div>
                    
                    <!-- Storage Tiers Tab -->
                    <div id="storage-tab" class="tab-content">
        """
        
        # Add storage tier details
        tier_stats = stats.get("backend_metrics", {}).get("tier_stats", {})
        if tier_stats:
            html_content += """
                        <h3>Storage Tier Details</h3>
                        <table class="data-table">
                            <tr>
                                <th>Tier</th>
                                <th>Items</th>
                                <th>Storage Used</th>
                                <th>Operations</th>
                                <th>Usage Percentage</th>
                            </tr>
            """
            
            total_storage = sum(data.get("bytes_stored", 0) for data in tier_stats.values())
            
            for tier, data in tier_stats.items():
                items = data.get("items", 0)
                bytes_stored = data.get("bytes_stored", 0)
                operations = data.get("operations", 0)
                
                # Calculate percentage
                percentage = (bytes_stored / total_storage * 100) if total_storage > 0 else 0
                
                # Format bytes for display
                if bytes_stored < 1024:
                    storage_str = f"{bytes_stored} B"
                elif bytes_stored < 1024 * 1024:
                    storage_str = f"{bytes_stored / 1024:.1f} KB"
                elif bytes_stored < 1024 * 1024 * 1024:
                    storage_str = f"{bytes_stored / (1024 * 1024):.1f} MB"
                else:
                    storage_str = f"{bytes_stored / (1024 * 1024 * 1024):.1f} GB"
                
                # Determine progress bar color
                progress_class = "progress-fill"
                if percentage > 80:
                    progress_class += " progress-danger"
                elif percentage > 60:
                    progress_class += " progress-warning"
                else:
                    progress_class += " progress-success"
                
                html_content += f"""
                            <tr>
                                <td>{tier}</td>
                                <td>{items}</td>
                                <td>{storage_str}</td>
                                <td>{operations}</td>
                                <td>
                                    <div class="progress-container">
                                        <div class="progress-label">
                                            <span>Usage</span>
                                            <span>{percentage:.1f}%</span>
                                        </div>
                                        <div class="progress-bar">
                                            <div class="{progress_class}" style="width: {percentage}%"></div>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                """
            
            html_content += """
                        </table>
            """
        else:
            html_content += """
                        <div class="alert-box">
                            <h4 class="alert-title">No Storage Tier Data</h4>
                            <p class="alert-message">No storage tier data is available for this time period.</p>
                        </div>
            """
            
        html_content += """
                    </div>
                    
                    <!-- Journal Entries Tab -->
                    <div id="journal-tab" class="tab-content">
        """
        
        # Add journal entry details
        entry_types = stats.get("entry_types", {})
        entry_statuses = stats.get("entry_statuses", {})
        
        if entry_types or entry_statuses:
            html_content += """
                        <div class="dashboard-grid">
            """
            
            if entry_types:
                html_content += """
                            <div class="dashboard-card">
                                <h3>Operations by Type</h3>
                                <table class="data-table">
                                    <tr>
                                        <th>Operation Type</th>
                                        <th>Count</th>
                                        <th>Percentage</th>
                                    </tr>
                """
                
                total_entries = sum(entry_types.values())
                for op_type, count in sorted(entry_types.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_entries * 100) if total_entries > 0 else 0
                    html_content += f"""
                                    <tr>
                                        <td>{op_type}</td>
                                        <td>{count}</td>
                                        <td>
                                            <div class="progress-container">
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width: {percentage}%"></div>
                                                </div>
                                                {percentage:.1f}%
                                            </div>
                                        </td>
                                    </tr>
                    """
                
                html_content += """
                                </table>
                            </div>
                """
            
            if entry_statuses:
                html_content += """
                            <div class="dashboard-card">
                                <h3>Entries by Status</h3>
                                <table class="data-table">
                                    <tr>
                                        <th>Status</th>
                                        <th>Count</th>
                                        <th>Percentage</th>
                                    </tr>
                """
                
                total_status = sum(entry_statuses.values())
                for status, count in sorted(entry_statuses.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_status * 100) if total_status > 0 else 0
                    
                    # Determine progress bar class based on status
                    progress_class = "progress-fill"
                    if status == JournalEntryStatus.COMPLETED.value:
                        progress_class += " progress-success"
                    elif status == JournalEntryStatus.PENDING.value:
                        progress_class += " progress-warning"
                    elif status == JournalEntryStatus.FAILED.value:
                        progress_class += " progress-danger"
                    
                    html_content += f"""
                                    <tr>
                                        <td>{status}</td>
                                        <td>{count}</td>
                                        <td>
                                            <div class="progress-container">
                                                <div class="progress-bar">
                                                    <div class="{progress_class}" style="width: {percentage}%"></div>
                                                </div>
                                                {percentage:.1f}%
                                            </div>
                                        </td>
                                    </tr>
                    """
                
                html_content += """
                                </table>
                            </div>
                """
            
            html_content += """
                        </div>
            """
            
            # Add journal growth rate analysis if available
            journal_metrics = stats.get("journal_metrics", {})
            if journal_metrics.get("growth_rates") and len(journal_metrics.get("growth_rates", [])) > 1:
                # Calculate average growth rate
                growth_rates = journal_metrics.get("growth_rates", [])
                avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
                max_growth = max(growth_rates) if growth_rates else 0
                
                html_content += f"""
                        <div class="alert-box">
                            <h4 class="alert-title">Journal Growth Analysis</h4>
                            <p class="alert-message">
                                The journal is growing at an average rate of <strong>{avg_growth:.1f}</strong> entries per minute.
                                Peak growth rate was <strong>{max_growth:.1f}</strong> entries per minute.
                                At the current average rate, the journal will reach {total_entries + (avg_growth * 60 * 24):.0f} entries in 24 hours.
                            </p>
                        </div>
                """
        else:
            html_content += """
                        <div class="alert-box">
                            <h4 class="alert-title">No Journal Entry Data</h4>
                            <p class="alert-message">No journal entry data is available for this time period.</p>
                        </div>
            """
            
        html_content += """
                    </div>
                    
                    <!-- Health Status Tab -->
                    <div id="health-tab" class="tab-content">
        """
        
        # Add health status details
        issues = stats.get("issues", [])
        if issues:
            html_content += """
                        <h3>Current Health Issues</h3>
            """
            
            for issue in issues:
                issue_type = issue.get("type", "unknown")
                severity = issue.get("severity", "warning")
                message = issue.get("message", "No details available")
                
                alert_class = "alert-box"
                if severity == "critical":
                    alert_class += " alert-critical"
                elif severity == "warning":
                    alert_class += " alert-warning"
                
                html_content += f"""
                        <div class="{alert_class}">
                            <h4 class="alert-title">{issue_type.replace('_', ' ').title()} ({severity.upper()})</h4>
                            <p class="alert-message">{message}</p>
                        </div>
                """
        else:
            html_content += """
                        <div class="alert-box alert-success">
                            <h4 class="alert-title">No Health Issues</h4>
                            <p class="alert-message">No health issues detected. The journal is functioning normally.</p>
                        </div>
            """
            
        # Add threshold values if available
        threshold_values = stats.get("threshold_values", {})
        if threshold_values:
            html_content += """
                        <h3>Health Thresholds</h3>
                        <table class="data-table">
                            <tr>
                                <th>Threshold</th>
                                <th>Current Value</th>
                                <th>Status</th>
                            </tr>
            """
            
            # Mapping for thresholds and current values
            threshold_mapping = {
                "journal_size_warning": ("Journal Size", total_entries, "entries"),
                "journal_growth_rate_warning": ("Growth Rate", growth_rate, "entries/min"),
                "checkpoint_age_warning": ("Checkpoint Age", checkpoint_age, "seconds"),
                "error_rate_warning": ("Error Rate", error_rate, "%"),
                "transaction_time_warning": ("Transaction Time", active_transactions > 0, "active")
            }
            
            for threshold_key, threshold_value in threshold_values.items():
                if threshold_key in threshold_mapping:
                    name, current_value, unit = threshold_mapping[threshold_key]
                    
                    # Determine threshold status
                    status = "OK"
                    status_class = "progress-success"
                    
                    # Format displayed values based on unit
                    display_value = current_value
                    display_threshold = threshold_value
                    
                    if threshold_key == "error_rate_warning":
                        display_value = f"{current_value * 100:.1f}%"
                        display_threshold = f"{threshold_value * 100:.1f}%"
                        if current_value > threshold_value:
                            status = "EXCEEDED"
                            status_class = "progress-danger"
                    elif threshold_key == "checkpoint_age_warning":
                        display_value = f"{current_value:.1f}s"
                        display_threshold = f"{threshold_value:.1f}s"
                        if current_value > threshold_value:
                            status = "EXCEEDED"
                            status_class = "progress-danger"
                    elif threshold_key == "journal_size_warning":
                        if current_value > threshold_value:
                            status = "EXCEEDED"
                            status_class = "progress-danger"
                    elif threshold_key == "journal_growth_rate_warning":
                        display_value = f"{current_value:.1f}/min"
                        display_threshold = f"{threshold_value:.1f}/min"
                        if current_value > threshold_value:
                            status = "EXCEEDED"
                            status_class = "progress-danger"
                    elif threshold_key == "transaction_time_warning":
                        display_value = "Active" if current_value else "None"
                        display_threshold = f"{threshold_value}s warning"
                    
                    html_content += f"""
                            <tr>
                                <td>{name}</td>
                                <td>{display_value} (threshold: {display_threshold})</td>
                                <td><span style="padding: 3px 8px; border-radius: 3px; color: white; background-color: {'#F44336' if status == 'EXCEEDED' else '#4CAF50'}">{status}</span></td>
                            </tr>
                    """
            
            html_content += """
                        </table>
            """
            
        html_content += """
                    </div>
                </div>
        """
        
        # Add footer
        html_content += """
                <div class="footer">
                    <p>Generated by IPFS Kit Filesystem Journal Visualization Tool</p>
                    <p>This dashboard is automatically refreshed when regenerated. All visualizations and data analytics are based on the collected metrics.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Write the HTML file
        html_path = os.path.join(output_dir, "journal_dashboard.html")
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Created HTML dashboard at {html_path}")
        
        return html_path


# Export key classes
__all__ = [
    'JournalHealthMonitor',
    'JournalVisualization'
]

def main():
    """Command-line interface for journal visualization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Filesystem Journal Visualization Tool")
    parser.add_argument("--journal-path", help="Path to journal directory")
    parser.add_argument("--timeframe", type=int, default=24, help="Timeframe in hours (default: 24)")
    parser.add_argument("--output", help="Output directory for dashboard")
    parser.add_argument("--stats", help="Path to existing stats file to use")
    parser.add_argument("--collect-only", action="store_true", help="Only collect stats, don't create plots")
    args = parser.parse_args()
    
    # Create journal instance if path provided
    journal = None
    if args.journal_path:
        journal = FilesystemJournal(base_path=args.journal_path)
    
    # Create visualization tool
    vis = JournalVisualization(journal=journal)
    
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