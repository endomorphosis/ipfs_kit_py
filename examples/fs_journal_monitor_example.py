#!/usr/bin/env python3
"""
Filesystem Journal Monitoring and Visualization Example

This example demonstrates how to use the monitoring and visualization tools
for the filesystem journal. It shows how to track journal health, collect
performance metrics, and create visualizations and dashboards.

Key features demonstrated:
1. Setting up a journal health monitor
2. Tracking transactions and operations
3. Analyzing journal health metrics
4. Generating visualizations of journal performance
5. Creating a comprehensive monitoring dashboard
6. Setting up alerts for potential issues
"""

import os
import time
import shutil
import logging
import tempfile
import threading
import webbrowser
from datetime import datetime
from typing import Dict, Any

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.filesystem_journal import JournalOperationType
from ipfs_kit_py.fs_journal_backends import (
    StorageBackendType,
    TieredJournalManagerFactory
)
from ipfs_kit_py.fs_journal_monitor import JournalHealthMonitor, JournalVisualization
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Alert callback for demonstration purposes
def handle_alert(alert: Dict[str, Any]):
    """Handle alert from journal monitor."""
    severity = alert.get("severity", "").upper()
    message = alert.get("message", "Unknown alert")
    timestamp = datetime.fromtimestamp(alert.get("timestamp", time.time()))
    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # Print alert with appropriate color based on severity
    if severity == "CRITICAL":
        prefix = "\033[91m" # Red
    elif severity == "WARNING":
        prefix = "\033[93m" # Yellow
    else:
        prefix = "\033[0m"  # Default

    print(f"{prefix}[{formatted_time}] {severity} ALERT: {message}\033[0m")

def simulate_workload(journal_backend, cycles=3, delay=0.5):
    """
    Simulate a journal workload to generate metrics.

    Args:
        journal_backend: Journal backend with tiered storage
        cycles: Number of operation cycles to run
        delay: Delay between operations (seconds)
    """
    logger.info(f"Starting simulated workload with {cycles} cycles")

    # Create sample content for operations
    content_small = b"Small test content" * 10  # ~200 bytes
    content_medium = b"Medium test content" * 100  # ~2KB
    content_large = os.urandom(1024 * 100)  # 100KB of random data

    # Track CIDs for later use
    cids = []

    # Run multiple cycles of operations
    for cycle in range(cycles):
        logger.info(f"Running operation cycle {cycle+1}/{cycles}")

        # Add content to different tiers
        cid_small = journal_backend.store_content(
            content=content_small,
            target_tier=StorageBackendType.MEMORY,
            metadata={"cycle": cycle, "size": "small"}
        )["cid"]
        cids.append(cid_small)
        time.sleep(delay)

        cid_medium = journal_backend.store_content(
            content=content_medium,
            target_tier=StorageBackendType.DISK,
            metadata={"cycle": cycle, "size": "medium"}
        )["cid"]
        cids.append(cid_medium)
        time.sleep(delay)

        # Try IPFS tier if available, fallback to disk if not
        try:
            cid_large = journal_backend.store_content(
                content=content_large,
                target_tier=StorageBackendType.IPFS,
                metadata={"cycle": cycle, "size": "large"}
            )["cid"]
            cids.append(cid_large)
        except Exception as e:
            logger.warning(f"IPFS tier not available: {e}")
            # Fallback to disk
            cid_large = journal_backend.store_content(
                content=content_large,
                target_tier=StorageBackendType.DISK,
                metadata={"cycle": cycle, "size": "large", "fallback": True}
            )["cid"]
            cids.append(cid_large)
        time.sleep(delay)

        # Retrieve content
        for cid in cids[:3]:  # Use just a few CIDs to avoid too much output
            journal_backend.retrieve_content(cid)
            time.sleep(delay)

        # Move content between tiers
        if cycle > 0 and cids:
            # Move a random content item between tiers
            import random
            cid_to_move = random.choice(cids)
            target_tier = random.choice([
                StorageBackendType.MEMORY,
                StorageBackendType.DISK
            ])

            try:
                journal_backend.move_content_to_tier(
                    cid=cid_to_move,
                    target_tier=target_tier,
                    keep_in_source=False
                )
            except Exception as e:
                logger.warning(f"Failed to move content: {e}")

            time.sleep(delay)

        # Create checkpoint periodically
        if cycle % 2 == 0:
            journal_backend.journal.create_checkpoint()
            logger.info("Created journal checkpoint")
            time.sleep(delay)

    logger.info("Completed simulated workload")
    return cids

def run_example():
    """Run the filesystem journal monitoring and visualization example."""
    logger.info("Starting filesystem journal monitoring example")

    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp(prefix="fs_journal_monitor_example_")
    logger.info(f"Created temporary directory: {temp_dir}")

    try:
        # Set up paths
        cache_dir = os.path.join(temp_dir, "cache")
        journal_dir = os.path.join(temp_dir, "journal")
        stats_dir = os.path.join(temp_dir, "stats")
        visualization_dir = os.path.join(temp_dir, "visualizations")

        # Create directories
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(stats_dir, exist_ok=True)
        os.makedirs(visualization_dir, exist_ok=True)

        # 1. Set up tiered cache and journal backend
        logger.info("1. Setting up tiered cache and journal backend")

        # Create tiered cache manager
        cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB for testing
            'local_cache_size': 20 * 1024 * 1024,  # 20MB for testing
            'local_cache_path': cache_dir,
        }
        tiered_cache = TieredCacheManager(config=cache_config)

        # Create journal backend
        journal_backend = TieredJournalManagerFactory.create_for_tiered_cache(
            tiered_cache_manager=tiered_cache,
            journal_base_path=journal_dir,
            auto_recovery=True
        )

        # 2. Set up health monitor
        logger.info("2. Setting up journal health monitor")
        monitor = JournalHealthMonitor(
            journal=journal_backend.journal,
            backend=journal_backend,
            check_interval=5,  # Check every 5 seconds for demo purposes
            alert_callback=handle_alert,
            stats_dir=stats_dir
        )

        # Customize some thresholds for demonstration
        monitor.set_threshold("journal_size_warning", 20)  # Warn after 20 entries
        monitor.set_threshold("checkpoint_age_warning", 30)  # Warn after 30 seconds

        # 3. Set up visualization tools
        logger.info("3. Setting up journal visualization tools")
        visualizer = JournalVisualization(
            journal=journal_backend.journal,
            backend=journal_backend,
            monitor=monitor,
            output_dir=visualization_dir
        )

        # 4. Run a simulated workload to generate metrics
        logger.info("4. Running simulated workload to generate metrics")

        # Define some operation IDs for tracking
        operations = [
            JournalOperationType.CREATE.value,
            JournalOperationType.UPDATE.value,
            JournalOperationType.DELETE.value,
            JournalOperationType.MOVE.value
        ]

        # Simulate some transaction tracking
        for tx_id in range(5):
            # Start transaction
            tx_id_str = f"tx-{tx_id}"
            monitor.track_transaction(tx_id_str, "begin", {"type": "test_transaction"})

            # Track some operation durations
            for op_type in operations:
                # Simulate operation duration (0.05-0.2 seconds)
                import random
                duration = random.uniform(0.05, 0.2)
                monitor.track_operation(op_type, duration)
                time.sleep(0.1)  # Small delay between operations

            # End transaction
            result = "commit" if tx_id % 3 != 0 else "rollback"  # Occasionally rollback
            monitor.track_transaction(tx_id_str, result)

        # Run more substantial workload to generate data across tiers
        cids = simulate_workload(journal_backend, cycles=3, delay=0.2)

        # Sleep to allow monitor to collect some data points
        logger.info("Waiting for monitor to collect metrics...")
        time.sleep(10)

        # 5. Check health status
        logger.info("5. Checking journal health status")
        health_status = monitor.get_health_status()

        logger.info(f"Health status: {health_status['status']}")
        if health_status["issues"]:
            logger.info("Current issues:")
            for issue in health_status["issues"]:
                logger.info(f"  - {issue['severity'].upper()}: {issue['message']}")
        else:
            logger.info("No issues detected")

        # 6. Collect operation statistics
        logger.info("6. Collecting operation statistics")
        stats = visualizer.collect_operation_stats()

        if stats["success"]:
            # Log some key metrics
            entry_types = stats.get("entry_types", {})
            entry_statuses = stats.get("entry_statuses", {})
            content_by_tier = stats.get("backend_metrics", {}).get("content_by_tier", {})

            logger.info("Journal statistics:")
            logger.info(f"  - Entry types: {entry_types}")
            logger.info(f"  - Entry statuses: {entry_statuses}")
            logger.info(f"  - Content by tier: {content_by_tier}")

            # Save the statistics
            stats_path = visualizer.save_stats(stats)
            logger.info(f"Saved statistics to {stats_path}")
        else:
            logger.error(f"Failed to collect stats: {stats.get('error', 'Unknown error')}")

        # 7. Create visualizations
        logger.info("7. Creating visualizations")

        # Individual plots
        if stats["success"]:
            try:
                # Plot entry types
                entry_types_path = os.path.join(visualization_dir, "entry_types.png")
                visualizer.plot_entry_types(stats, entry_types_path)

                # Plot tier distribution
                tier_dist_path = os.path.join(visualization_dir, "tier_distribution.png")
                visualizer.plot_tier_distribution(stats, tier_dist_path)

                logger.info("Created individual visualizations")
            except Exception as e:
                logger.warning(f"Could not create some visualizations: {e}")
                logger.warning("You may need to install matplotlib for visualizations")

        # 8. Create a complete dashboard
        logger.info("8. Creating a complete dashboard")
        try:
            dashboard = visualizer.create_dashboard(stats)

            if dashboard and "html_report" in dashboard:
                dashboard_path = dashboard["html_report"]
                logger.info(f"Created dashboard at {dashboard_path}")

                # Try to open the dashboard in a browser if possible
                try:
                    webbrowser.open(f"file://{dashboard_path}")
                    logger.info("Opened dashboard in browser")
                except Exception as e:
                    logger.warning(f"Could not open browser: {e}")
            else:
                logger.warning("Dashboard creation failed or returned no HTML report")
        except Exception as e:
            logger.warning(f"Could not create dashboard: {e}")
            logger.warning("You may need to install matplotlib for dashboard creation")

        # 9. Demonstrate alert generation
        logger.info("9. Demonstrating alert generation")

        # Force a checkpoint age alert
        logger.info("Waiting to trigger checkpoint age alert...")
        time.sleep(35)  # Should exceed our 30-second checkpoint_age_warning threshold

        # Get any alerts
        alerts = monitor.get_alerts()
        if alerts:
            logger.info(f"Collected {len(alerts)} alerts:")
            for alert in alerts:
                timestamp = datetime.fromtimestamp(alert["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"  - [{timestamp}] {alert['severity'].upper()}: {alert['message']}")

            # Clear alerts
            monitor.clear_alerts()
            logger.info("Cleared alerts")
        else:
            logger.info("No alerts collected")

        # 10. Shutdown monitor
        logger.info("10. Shutting down monitor")
        monitor.stop()

        logger.info("\nFilesystem journal monitoring example completed")
        logger.info(f"Visualizations and dashboard can be found in: {visualization_dir}")
        logger.info("You can manually clean up this directory when finished")

        # Keep directory for manual inspection
        print(f"\nTemporary directory with results: {temp_dir}")
        print("Delete this directory manually when you're done exploring the results")

        # Wait for user input before cleaning up
        input("Press Enter to clean up and exit...")

    finally:
        # Clean up temporary directory
        try:
            logger.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")

if __name__ == "__main__":
    run_example()
