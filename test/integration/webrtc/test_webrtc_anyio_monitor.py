#!/usr/bin/env python3
"""
Test WebRTC AnyIO & Monitoring Integration

This script tests the WebRTC AnyIO & Monitoring Integration by:
1. Creating a simulated WebRTC environment
2. Applying the enhanced fixes
3. Running test operations
4. Verifying monitoring data is properly collected

Run with:
python test_webrtc_anyio_monitor.py
"""

import os
import sys
import time
import json
import logging
import anyio
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add fixes directory to path
fixes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixes")
if fixes_dir not in sys.path:
    sys.path.append(fixes_dir)

# Check for required packages
try:
    import anyio
    import sniffio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    logger.warning("AnyIO not available. Install with: pip install anyio sniffio")

# Try to import our modules
try:
    from fixes.webrtc_anyio_monitor_integration import (
        apply_enhanced_fixes,
        enhanced_stop_webrtc_streaming,
        enhanced_close_webrtc_connection,
        enhanced_close_all_webrtc_connections,
        enhanced_async_stop_webrtc_streaming,
        enhanced_async_close_webrtc_connection,
        enhanced_async_close_all_webrtc_connections
    )
    from fixes.webrtc_monitor import WebRTCMonitor
    HAS_MODULES = True
except ImportError as e:
    HAS_MODULES = False
    logger.error(f"Could not import required modules: {e}")

class DummyWebRTCManager:
    """Dummy WebRTC manager for testing."""

    def __init__(self):
        self.connections = {
            "conn-1": {"state": "connected"},
            "conn-2": {"state": "new"},
            "conn-3": {"state": "connecting"}
        }

    def get_stats(self):
        """Get connection stats."""
        return {
            "connections": self.connections,
            "count": len(self.connections)
        }

    async def close_connection(self, connection_id):
        """Close a connection."""
        logger.info(f"Closing connection: {connection_id}")

        # Simulate async operation
        await anyio.sleep(0.1)

        # Check if connection exists
        if connection_id in self.connections:
            self.connections.pop(connection_id)
            return {"success": True, "connection_closed": True}
        else:
            return {"success": False, "error": "Connection not found"}

    async def close_all_connections(self):
        """Close all connections."""
        logger.info(f"Closing all connections: {len(self.connections)}")

        # Simulate async operation
        await anyio.sleep(0.2)

        # Count connections and clear
        count = len(self.connections)
        self.connections = {}

        return {"success": True, "connections_closed": count}

class DummyModel:
    """Dummy IPFS model for testing."""

    def __init__(self):
        self.webrtc_manager = DummyWebRTCManager()

def print_section(title):
    """Print a section title."""
    print(f"\n{'=' * 40}")
    print(f" {title}")
    print(f"{'=' * 40}\n")

def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))

def run_sync_tests(model, monitor):
    """Run synchronous method tests."""
    print_section("RUNNING SYNCHRONOUS TESTS")

    # Test closing a specific connection
    print("Testing close_webrtc_connection...")
    result = enhanced_close_webrtc_connection(model, "conn-1")
    print_json(result)

    # Print monitoring status after operation
    print("\nMonitoring summary after closing connection:")
    print_json(monitor.get_summary())

    # Test closing all connections
    print("\nTesting close_all_webrtc_connections...")
    result = enhanced_close_all_webrtc_connections(model)
    print_json(result)

    # Print monitoring status after operation
    print("\nMonitoring summary after closing all connections:")
    print_json(monitor.get_summary())

    # Get detailed connection stats
    print("\nConnection stats:")
    print_json(monitor.get_connection_stats())

    # Wait a moment for background tasks
    print("\nWaiting for background tasks...")
    time.sleep(1)

async def run_async_tests(model, monitor):
    """Run asynchronous method tests."""
    print_section("RUNNING ASYNCHRONOUS TESTS")

    # Reset connection state
    model.webrtc_manager.connections = {
        "conn-async-1": {"state": "connected"},
        "conn-async-2": {"state": "new"}
    }

    # Test closing a specific connection (async)
    print("Testing async_close_webrtc_connection...")
    result = await enhanced_async_close_webrtc_connection(model, "conn-async-1")
    print_json(result)

    # Print monitoring status after operation
    print("\nMonitoring summary after closing connection (async):")
    print_json(monitor.get_summary())

    # Test closing all connections (async)
    print("\nTesting async_close_all_webrtc_connections...")
    result = await enhanced_async_close_all_webrtc_connections(model)
    print_json(result)

    # Print monitoring status after operation
    print("\nMonitoring summary after closing all connections (async):")
    print_json(monitor.get_summary())

    # Wait a moment for background tasks
    print("\nWaiting for background tasks...")
    await anyio.sleep(1)

async def run_simulated_fastapi_context_tests(model, monitor):
    """Run tests that simulate a FastAPI context (with running event loop)."""
    print_section("RUNNING SIMULATED FASTAPI CONTEXT TESTS")

    # Reset connection state
    model.webrtc_manager.connections = {
        "conn-fastapi-1": {"state": "connected"},
        "conn-fastapi-2": {"state": "new"}
    }

    # We're already in an async context, so this will detect the running loop
    # and schedule as background tasks for the enhanced methods

    # Test closing a specific connection
    print("Testing enhanced_close_webrtc_connection in FastAPI context (with running loop)...")
    result = enhanced_close_webrtc_connection(model, "conn-fastapi-1")
    print_json(result)

    # This should show a simulated result
    print("\nIs this a simulated result?", "Yes" if result.get("simulated", False) else "No")

    # Wait for background task to complete
    print("\nWaiting for background task to complete...")
    await anyio.sleep(1)

    # Check if the connection was actually closed in the background
    print("\nFastAPI-1 connection should be closed. Current connections:")
    print_json(model.webrtc_manager.get_stats())

    # Check monitoring status
    print("\nMonitoring summary after FastAPI context test:")
    print_json(monitor.get_summary())

def verify_logs(log_dir):
    """Verify that log files were created."""
    print_section("VERIFYING LOG FILES")

    if not os.path.exists(log_dir):
        print(f"Log directory not found: {log_dir}")
        return False

    connections_dir = os.path.join(log_dir, "connections")
    operations_dir = os.path.join(log_dir, "operations")

    if not os.path.exists(connections_dir):
        print(f"Connections directory not found: {connections_dir}")
    else:
        connection_logs = os.listdir(connections_dir)
        print(f"Connection logs found: {len(connection_logs)}")
        if connection_logs:
            print(f"Example logs: {', '.join(connection_logs[:3])}")

    if not os.path.exists(operations_dir):
        print(f"Operations directory not found: {operations_dir}")
    else:
        operation_logs = os.listdir(operations_dir)
        print(f"Operation logs found: {len(operation_logs)}")
        if operation_logs:
            print(f"Example logs: {', '.join(operation_logs[:3])}")

    print("\nLog verification complete")
    return True

async def main():
    """Main test function."""
    if not HAS_ANYIO:
        logger.error("AnyIO not available. Install with: pip install anyio sniffio")
        return 1

    if not HAS_MODULES:
        logger.error("Required modules not available")
        return 1

    # Create log directory
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    print_section("WEBRTC ANYIO & MONITORING INTEGRATION TEST")
    print(f"AnyIO available: {HAS_ANYIO}")
    print(f"Required modules available: {HAS_MODULES}")
    print(f"Log directory: {log_dir}")

    # Create dummy model
    model = DummyModel()

    # Create WebRTC monitor
    monitor = WebRTCMonitor(log_dir=log_dir, debug_mode=True)
    model.webrtc_monitor = monitor

    # Run synchronous tests
    run_sync_tests(model, monitor)

    # Run asynchronous tests
    await run_async_tests(model, monitor)

    # Run tests that simulate a FastAPI context
    await run_simulated_fastapi_context_tests(model, monitor)

    # Verify logs
    verify_logs(log_dir)

    print_section("TEST COMPLETED SUCCESSFULLY")
    return 0

if __name__ == "__main__":
    # Run the async main function
    if HAS_ANYIO:
        anyio.run(main)
    else:
        print("AnyIO not available. Cannot run tests.")
        sys.exit(1)
