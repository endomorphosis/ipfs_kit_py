#!/usr/bin/env python3
"""
Example demonstrating the use of cluster state helper functions.

This script shows how to use the various helper functions to:
1. Query the cluster state
2. Find nodes and tasks matching specific criteria
3. Calculate metrics and statistics
4. Optimize resource allocation
"""

import os
import sys
import time
import json
import logging
from typing import Dict, List, Any, Optional

# Add parent directory to path so we can import the package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import helper functions
from ipfs_kit_py.cluster_state_helpers import (
    get_state_path_from_metadata,
    get_cluster_metadata,
    get_all_nodes,
    get_all_tasks,
    get_all_content,
    find_nodes_by_role,
    find_nodes_by_capability,
    find_nodes_with_gpu,
    find_tasks_by_status,
    find_tasks_by_resource_requirements,
    find_available_node_for_task,
    get_task_execution_metrics,
    find_orphaned_content,
    get_node_resource_utilization,
    estimate_time_to_completion,
    get_network_topology,
    get_content_availability_map,
    export_state_to_json
)

def setup_logging():
    """Set up logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def main():
    """Main function demonstrating helper usage."""
    logger = setup_logging()

    # Find the cluster state directory
    state_path = get_state_path_from_metadata()
    if not state_path:
        state_path = os.path.expanduser("~/.ipfs/cluster_state")
        logger.info(f"No state path found, using default: {state_path}")
    else:
        logger.info(f"Found cluster state at: {state_path}")

    # Example 1: Get basic cluster information
    logger.info("Example 1: Get basic cluster information")
    metadata = get_cluster_metadata(state_path)
    if metadata:
        print(f"Cluster ID: {metadata['cluster_id']}")
        print(f"Last updated: {metadata['updated_at']}")
        print(f"Node count: {metadata['node_count']}")
        print(f"Task count: {metadata['task_count']}")
        print(f"Content count: {metadata['content_count']}")
    else:
        print("No cluster metadata found")
    print()

    # Example 2: Find nodes with specific capabilities
    logger.info("Example 2: Find nodes with specific capabilities")
    gpu_nodes = find_nodes_with_gpu(state_path)
    print(f"Found {len(gpu_nodes)} nodes with GPU:")
    for node in gpu_nodes:
        gpu_count = node.get("resources", {}).get("gpu_count", 0)
        print(f"  - Node {node.get('id')}: {gpu_count} GPUs")
    print()

    # Example 3: Resource utilization monitoring
    logger.info("Example 3: Resource utilization monitoring")
    worker_nodes = find_nodes_by_role(state_path, "worker")
    for node in worker_nodes[:2]:  # Display first two workers only
        node_id = node.get("id")
        util = get_node_resource_utilization(state_path, node_id)
        if util:
            print(f"Node {node_id} utilization:")
            print(f"  - CPU: {util['cpu_utilization']:.1%}")
            print(f"  - Memory: {util['memory_utilization']:.1%}")
            print(f"  - Disk: {util['disk_utilization']:.1%}")
            if util['gpu_utilization'] is not None:
                print(f"  - GPU: {util['gpu_utilization']:.1%}")
            print(f"  - Load index: {util['load_index']:.2f}")
            print(f"  - Active tasks: {util['active_tasks']}")
    print()

    # Example 4: Task scheduling optimization
    logger.info("Example 4: Task scheduling optimization")
    # Find pending tasks that require GPU
    pending_tasks = find_tasks_by_status(state_path, "pending")
    gpu_tasks = find_tasks_by_resource_requirements(state_path, gpu_cores=1)
    pending_gpu_tasks = [t for t in pending_tasks if t in gpu_tasks]

    print(f"Found {len(pending_gpu_tasks)} pending tasks that require GPU")

    # Find best node for each task
    for task in pending_gpu_tasks[:2]:  # Process first two only
        task_id = task.get("id")
        print(f"Finding best node for task {task_id}:")
        best_node = find_available_node_for_task(state_path, task_id)
        if best_node:
            print(f"  - Best node: {best_node.get('id')}")
            print(f"  - CPU: {best_node.get('resources', {}).get('cpu_count')} cores")
            print(f"  - Memory: {best_node.get('resources', {}).get('memory_available') / (1024*1024*1024):.1f} GB available")
        else:
            print("  - No suitable node found")

        # Also estimate completion time
        etc = estimate_time_to_completion(state_path, task_id)
        if etc is not None:
            print(f"  - Estimated time to completion: {etc:.1f} seconds")
        else:
            print("  - Cannot estimate completion time")
    print()

    # Example 5: Content management
    logger.info("Example 5: Content management")
    orphaned = find_orphaned_content(state_path)
    print(f"Found {len(orphaned)} orphaned content items:")
    for item in orphaned[:3]:  # Show first three only
        print(f"  - CID: {item.get('cid')}")
        print(f"  - Size: {item.get('size', 0) / (1024*1024):.2f} MB")

    # Get content availability map
    avail_map = get_content_availability_map(state_path)
    print(f"\nContent availability across {len(avail_map)} items:")
    count = 0
    for cid, providers in avail_map.items():
        if count >= 3:  # Show first three only
            break
        print(f"  - {cid}: available on {len(providers)} nodes")
        count += 1
    print()

    # Example 6: Network topology
    logger.info("Example 6: Network topology")
    topology = get_network_topology(state_path)
    print(f"Network consists of {len(topology['nodes'])} nodes and {len(topology['connections'])} connections")

    # Count nodes by role
    roles = {}
    for node in topology['nodes']:
        role = node.get('role')
        if role not in roles:
            roles[role] = 0
        roles[role] += 1

    print("Nodes by role:")
    for role, count in roles.items():
        print(f"  - {role}: {count}")
    print()

    # Example 7: Task execution metrics
    logger.info("Example 7: Task execution metrics")
    metrics = get_task_execution_metrics(state_path)
    print("Task execution metrics:")
    print(f"  - Total tasks: {metrics['total_tasks']}")
    print(f"  - Completed: {metrics['completed_tasks']}")
    print(f"  - Failed: {metrics['failed_tasks']}")
    print(f"  - Pending: {metrics['pending_tasks']}")
    print(f"  - Running: {metrics['running_tasks']}")
    print(f"  - Completion rate: {metrics['completion_rate']:.1%}")
    print(f"  - Average execution time: {metrics['average_execution_time']:.1f} seconds")

    print("\nTask types:")
    for task_type, count in metrics['task_types'].items():
        print(f"  - {task_type}: {count}")
    print()

    # Example 8: Export state to JSON
    logger.info("Example 8: Export state to JSON")
    output_path = os.path.join(os.path.dirname(__file__), "cluster_state_export.json")
    success = export_state_to_json(state_path, output_path)
    if success:
        print(f"Successfully exported state to {output_path}")
    else:
        print("Failed to export state")

if __name__ == "__main__":
    main()
