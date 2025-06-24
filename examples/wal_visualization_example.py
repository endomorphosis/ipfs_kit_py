# examples/wal_visualization_example.py

#!/usr/bin/env python3
"""
Example demonstrating the WAL visualization tools.

This script shows how to use the visualization module to collect statistics,
create plots, and generate dashboards for monitoring WAL operations and backend health.
"""

import os
import time
import logging
import random
import uuid
import sys
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py import IPFSSimpleAPI
from ipfs_kit_py.wal_visualization import WALVisualization

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_sample_data(api, num_operations=20):
    """Generate sample operations data for demonstration purposes.

    Args:
        api: IPFSSimpleAPI instance
        num_operations: Number of operations to generate

    Returns:
        List of generated operations
    """
    # This is a simulation that adds operations to the API's internal storage
    # In a real implementation, you would use the actual WAL to store operations

    # Create a sample operations list if it doesn't exist
    if not hasattr(api, '_sample_operations'):
        api._sample_operations = []

    logger.info(f"Generating {num_operations} sample operations")

    # Generate operations spread over the last 24 hours
    now = time.time() * 1000  # Current time in milliseconds

    # Operation types to simulate
    operation_types = ["add", "pin", "unpin", "get", "cat", "remove"]
    backends = ["ipfs", "s3", "storacha"]
    statuses = ["pending", "processing", "completed", "failed"]
    status_weights = [0.1, 0.15, 0.65, 0.1]  # Probabilities for each status

    for i in range(num_operations):
        # Generate random timestamp within the last 24 hours
        hours_ago = random.uniform(0, 24)
        timestamp = now - (hours_ago * 3600 * 1000)

        # Select random operation type, backend, and status
        operation_type = random.choice(operation_types)
        backend = random.choice(backends)
        status = random.choices(statuses, weights=status_weights)[0]

        # Create operation ID
        operation_id = str(uuid.uuid4())

        # Calculate completed time if applicable
        completed_at = None
        if status in ["completed", "failed"]:
            # Add some random processing time (between 0.5 and 10 seconds)
            processing_time = random.uniform(0.5, 10) * 1000  # milliseconds
            completed_at = timestamp + processing_time

        # Generate some random parameters
        params = {
            "path": f"/tmp/sample_{i}.txt",
            "size": random.randint(1024, 10 * 1024 * 1024)  # 1KB to 10MB
        }

        # Add error for failed operations
        error = None
        if status == "failed":
            errors = [
                "Connection timeout",
                "Backend unavailable",
                "Invalid CID format",
                "Permission denied",
                "Content not found"
            ]
            error = random.choice(errors)

        # Create the operation object
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "backend": backend,
            "status": status,
            "timestamp": timestamp,
            "completed_at": completed_at,
            "parameters": params,
            "error": error
        }

        # Add some result for completed operations
        if status == "completed":
            # Generate a fake CID
            cid = f"Qm{''.join(random.choices('abcdef0123456789', k=44))}"
            operation["result"] = {"cid": cid}

        # Add to the operations list
        api._sample_operations.append(operation)

    return api._sample_operations

def mock_backend_health(api):
    """Generate mock backend health data for demonstration.

    Args:
        api: IPFSSimpleAPI instance

    Returns:
        Mock health data
    """
    # Define the backends
    backends = ["ipfs", "s3", "storacha"]

    # Generate random health check histories for each backend
    health_data = {}
    for backend in backends:
        # Generate a history of health checks (True for success, False for failure)
        # With different patterns for each backend
        history = []
        if backend == "ipfs":
            # IPFS is mostly reliable with occasional failures
            history = [True] * 15 + [False] + [True] * 5 + [False] + [True] * 3
        elif backend == "s3":
            # S3 is very reliable
            history = [True] * 25
        elif backend == "storacha":
            # Storacha has some intermittent issues
            history = [True] * 5 + [False] * 2 + [True] * 3 + [False] * 1 + [True] * 14

        # Shuffle slightly to avoid perfect patterns
        if backend != "s3":  # Keep S3 perfect for contrast
            # Identify some positions to potentially flip
            flip_positions = random.sample(range(len(history)), 3)
            for pos in flip_positions:
                if random.random() < 0.3:  # 30% chance to flip
                    history[pos] = not history[pos]

        # Calculate current status based on recent history
        recent_history = history[-5:]
        failure_rate = recent_history.count(False) / len(recent_history)

        if failure_rate == 0:
            status = "online"
        elif failure_rate > 0.5:
            status = "offline"
        else:
            status = "degraded"

        # Add to health data
        health_data[backend] = {
            "status": status,
            "check_history": history,
            "last_check": time.time()
        }

    # Store on the API object for retrieval by the visualization
    api.wal = type('obj', (object,), {
        'health_monitor': type('obj', (object,), {
            'get_status': lambda backend=None: (
                health_data.get(backend, {"status": "unknown"}) if backend else health_data
            )
        })
    })

    return health_data

def patch_api_for_visualization(api):
    """Patch the API with methods needed for visualization.

    Args:
        api: IPFSSimpleAPI instance

    Returns:
        Patched API instance
    """
    # Add a get_all_operations method
    api.get_all_operations = lambda: getattr(api, '_sample_operations', [])

    # Add a get_wal_stats method if not present
    if not hasattr(api, 'get_wal_stats'):
        api.get_wal_stats = lambda: {
            "enabled": True,
            "stats": {
                "total_operations": len(getattr(api, '_sample_operations', [])),
                "pending": len([op for op in getattr(api, '_sample_operations', []) if op.get("status") == "pending"]),
                "processing": len([op for op in getattr(api, '_sample_operations', []) if op.get("status") == "processing"]),
                "completed": len([op for op in getattr(api, '_sample_operations', []) if op.get("status") == "completed"]),
                "failed": len([op for op in getattr(api, '_sample_operations', []) if op.get("status") == "failed"]),
                "retrying": 0,
                "partitions": 1,
                "archives": 0,
                "processing_active": True
            }
        }

    # Add get_pending_operations method
    api.get_pending_operations = lambda limit=10: {
        "success": True,
        "operations": [op for op in getattr(api, '_sample_operations', [])
                     if op.get("status") == "pending"][:limit]
    }

    # Add get_wal_status method
    api.get_wal_status = lambda operation_id: {
        "success": True,
        **next((op for op in getattr(api, '_sample_operations', [])
               if op.get("operation_id") == operation_id),
              {"success": False, "error": "Operation not found"})
    }

    # Add wait_for_operation method
    api.wait_for_operation = lambda operation_id, timeout=60, check_interval=1: {
        "success": True,
        "status": next((op.get("status") for op in getattr(api, '_sample_operations', [])
                      if op.get("operation_id") == operation_id),
                     "unknown"),
        "result": next((op.get("result") for op in getattr(api, '_sample_operations', [])
                      if op.get("operation_id") == operation_id and op.get("status") == "completed"),
                     None),
        "error": next((op.get("error") for op in getattr(api, '_sample_operations', [])
                     if op.get("operation_id") == operation_id and op.get("status") == "failed"),
                    None)
    }

    # Add cleanup_wal method
    api.cleanup_wal = lambda: {
        "success": True,
        "removed_count": 0
    }

    return api

def demonstrate_visualization():
    """Run a demonstration of the WAL visualization tools."""
    logger.info("=== WAL Visualization Demonstration ===")

    # Create API instance
    api = IPFSSimpleAPI()

    # Generate sample data
    generate_sample_data(api, num_operations=50)

    # Generate mock backend health data
    mock_backend_health(api)

    # Patch API with additional methods needed for visualization
    patch_api_for_visualization(api)

    # Create visualization instance with API
    vis = WALVisualization(api=api)

    # Collect operation statistics
    logger.info("Collecting operation statistics...")
    stats = vis.collect_operation_stats(timeframe_hours=24)

    # Save statistics to file
    stats_path = vis.save_stats(stats)
    logger.info(f"Saved statistics to {stats_path}")

    # Create full dashboard
    logger.info("Creating dashboard...")
    dashboard = vis.create_dashboard(stats)

    if dashboard and "html_report" in dashboard:
        logger.info(f"Dashboard created. HTML report: {dashboard['html_report']}")
        logger.info("Open the HTML report in a web browser to view the full dashboard.")

    # Return the important paths
    return {
        "stats_path": stats_path,
        "dashboard_dir": os.path.dirname(dashboard.get("html_report", "")) if dashboard else None
    }

def main():
    """Main function demonstrating WAL visualization."""
    parser = argparse.ArgumentParser(description="WAL Visualization Demo")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Run the demonstration
        results = demonstrate_visualization()

        # Show results
        print("\n=== Demo Completed Successfully ===")
        print(f"Statistics saved to: {results['stats_path']}")
        if results['dashboard_dir']:
            print(f"Dashboard created in: {results['dashboard_dir']}")
            print(f"Open {results['dashboard_dir']}/wal_report.html in a web browser to view the dashboard.")

    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
