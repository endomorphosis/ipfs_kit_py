#!/usr/bin/env python3
"""
Example of using the Lotus monitoring functionality, especially for macOS.

This script demonstrates how to use the integrated monitoring capabilities
of ipfs_kit_py to manage and monitor Lotus daemon on macOS systems.
"""

import os
import sys
import time
import json
import platform
import logging
from pathlib import Path

# Add parent directory to path for running from example directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipfs_kit_py.lotus_kit import lotus_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("lotus_monitor_example")


def check_platform():
    """Check if current platform is supported."""
    current_platform = platform.system()
    
    if current_platform == 'Darwin':
        print(f"Running on macOS ({platform.mac_ver()[0]})")
        return True
    else:
        print(f"This example is primarily for macOS. Current platform: {current_platform}")
        print("The monitoring functionality may be limited on this platform.")
        return False


def setup_lotus():
    """Initialize the Lotus kit with monitor-friendly configuration."""
    # Custom configuration for monitoring
    metadata = {
        "auto_start_daemon": True,  # Auto-start daemon if not running
        "lotus_path": os.path.expanduser("~/.lotus"),  # Default Lotus path
        "monitor_config": {
            "interval": 60,  # Check every 60 seconds
            "auto_restart": True,  # Auto-restart daemon if crashed
            "max_memory_percent": 80,  # Alert if memory usage exceeds 80%
            "report_dir": os.path.expanduser("~/lotus_monitor_reports"),
            "notification_enabled": False  # Enable for production
        }
    }
    
    # Initialize lotus_kit with our configuration
    kit = lotus_kit(metadata=metadata)
    
    return kit


def monitor_start_example(kit):
    """Example of starting the Lotus daemon monitoring service."""
    print("\n=== Starting Lotus Monitor ===")
    
    # Start the monitor with our configuration
    result = kit.monitor_start(
        interval=30,  # Override default interval
        auto_restart=True,
        report_path=os.path.expanduser("~/lotus_monitor_reports")
    )
    
    if result.get("success", False):
        print(f"Monitor started successfully: {result.get('status', '')}")
        print(f"Monitor PID: {result.get('pid', 'unknown')}")
    else:
        print(f"Failed to start monitor: {result.get('error', 'Unknown error')}")
    
    return result


def monitor_status_example(kit):
    """Example of checking the Lotus monitor status."""
    print("\n=== Checking Lotus Monitor Status ===")
    
    # Get basic status
    result = kit.monitor_status()
    
    if result.get("success", False):
        print(f"Monitor status: {result.get('status', 'unknown')}")
        print(f"Running: {result.get('running', False)}")
        print(f"Daemon health: {result.get('daemon_health', 'unknown')}")
        print(f"Last check: {result.get('last_check_time', 'never')}")
    else:
        print(f"Failed to get monitor status: {result.get('error', 'Unknown error')}")
    
    # Get detailed status
    result = kit.monitor_status(detailed=True)
    
    if result.get("success", False) and result.get("metrics"):
        metrics = result.get("metrics", {})
        print("\nDetailed Metrics:")
        print(f"  CPU Usage: {metrics.get('cpu_percent', 'unknown')}%")
        print(f"  Memory Usage: {metrics.get('memory_percent', 'unknown')}%")
        print(f"  Disk Usage: {metrics.get('disk_percent', 'unknown')}%")
        print(f"  Uptime: {metrics.get('uptime', 'unknown')} seconds")
        
        if "peer_count" in metrics:
            print(f"  Connected Peers: {metrics.get('peer_count')}")
    
    return result


def monitor_optimize_example(kit):
    """Example of optimizing the Lotus daemon for macOS."""
    print("\n=== Optimizing Lotus Daemon for macOS ===")
    
    # Optimize with default settings
    result = kit.monitor_optimize()
    
    if result.get("success", False):
        print("Optimization completed successfully")
        
        # Show the optimizations that were applied
        for target, changes in result.get("optimizations", {}).items():
            print(f"\n{target.upper()} optimizations:")
            for key, value in changes.items():
                print(f"  {key}: {value}")
    else:
        print(f"Optimization failed: {result.get('error', 'Unknown error')}")
    
    return result


def monitor_report_example(kit):
    """Example of generating a Lotus daemon performance report."""
    print("\n=== Generating Lotus Performance Report ===")
    
    # Generate a report in JSON format
    result = kit.monitor_report(
        format="json",
        period="day",
        output_path=os.path.expanduser("~/lotus_monitor_reports/report.json")
    )
    
    if result.get("success", False):
        print(f"Report generated successfully")
        print(f"Report saved to: {result.get('report_path')}")
        
        # Display a summary of the report
        if "summary" in result:
            summary = result["summary"]
            print("\nReport Summary:")
            print(f"  Period: {summary.get('period', 'unknown')}")
            print(f"  Daemon restarts: {summary.get('restart_count', 0)}")
            print(f"  Avg CPU usage: {summary.get('avg_cpu', 'unknown')}%")
            print(f"  Avg memory usage: {summary.get('avg_memory', 'unknown')}%")
            print(f"  Max memory usage: {summary.get('max_memory', 'unknown')}%")
    else:
        print(f"Failed to generate report: {result.get('error', 'Unknown error')}")
    
    return result


def monitor_stop_example(kit):
    """Example of stopping the Lotus monitor."""
    print("\n=== Stopping Lotus Monitor ===")
    
    result = kit.monitor_stop()
    
    if result.get("success", False):
        print("Monitor stopped successfully")
    else:
        print(f"Failed to stop monitor: {result.get('error', 'Unknown error')}")
    
    return result


def main():
    """Main function running all examples."""
    print("=== Lotus Monitor Example ===")
    
    # Check if platform is macOS
    check_platform()
    
    # Setup Lotus kit
    kit = setup_lotus()
    
    # Start the monitor
    monitor_start_example(kit)
    
    # Wait a moment for the monitor to collect some data
    print("\nWaiting 10 seconds for the monitor to collect initial data...")
    time.sleep(10)
    
    # Check the monitor status
    monitor_status_example(kit)
    
    # Optimize the daemon for macOS
    monitor_optimize_example(kit)
    
    # Generate a performance report
    monitor_report_example(kit)
    
    # Stop the monitor
    monitor_stop_example(kit)
    
    print("\nExample completed successfully!")


if __name__ == "__main__":
    main()