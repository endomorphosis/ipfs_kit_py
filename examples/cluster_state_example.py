#!/usr/bin/env python3
"""
Example demonstrating the Arrow-based cluster state functionality.

This script shows how to:
1. Set up a master node with cluster state
2. Create and manage tasks
3. Access the cluster state from an external process
4. Query and analyze the cluster state
"""

import os
import time
import sys
import uuid
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py import cluster_state_helpers

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def run_master_example():
    """Example of a master node managing the cluster state."""
    print_section("MASTER NODE EXAMPLE")
    
    # Initialize master node
    print("Initializing master node...")
    master_kit = ipfs_kit(
        role="master",
        resources={
            "cpu_count": 8,
            "memory_total": 16 * 1024 * 1024 * 1024,  # 16GB
            "gpu_count": 2
        },
        metadata={
            "description": "Master node for demo"
        }
    )
    
    # Check readiness
    ready = master_kit('ipfs_kit_ready')
    print(f"Master node ready: {ready['ready']}")
    
    if not ready['ready']:
        print("Master node not ready. Please check IPFS daemon and try again.")
        return
    
    # Get cluster status
    status = master_kit('get_cluster_status')
    print(f"Cluster status: {status['success']}")
    
    # Create a task
    print("\nCreating a sample task...")
    task_result = master_kit('create_task', 
                            task_type="example_task", 
                            parameters={"param1": "value1", "param2": 42},
                            priority=5)
    
    if not task_result['success']:
        print(f"Failed to create task: {task_result.get('error', 'Unknown error')}")
        return
    
    task_id = task_result['task_id']
    print(f"Created task: {task_id}")
    
    # Check task status
    time.sleep(1)  # Give a moment for the state to update
    status_result = master_kit('get_task_status', task_id=task_id)
    print(f"Task status: {status_result.get('status', 'unknown')}")
    
    # Get state interface info
    state_info = master_kit('get_state_interface_info')
    if state_info['success']:
        print("\nState interface information:")
        print(f"  State path: {state_info['state_path']}")
        print(f"  Access method: {state_info['access_method']}")
        
        # Save state path for external access
        state_path = state_info['state_path']
        with open("/tmp/ipfs_state_path.txt", "w") as f:
            f.write(state_path)
        print(f"Saved state path to /tmp/ipfs_state_path.txt for external process access")
    else:
        print(f"Failed to get state interface info: {state_info.get('error', 'Unknown error')}")
    
    print("\nMaster node running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down master node...")

def run_external_access_example():
    """Example of accessing the cluster state from an external process."""
    print_section("EXTERNAL PROCESS ACCESS EXAMPLE")
    
    # Try to read state path from file
    try:
        with open("/tmp/ipfs_state_path.txt", "r") as f:
            state_path = f.read().strip()
    except FileNotFoundError:
        print("State path file not found. Please run the master example first.")
        # Try to find state path in standard locations
        state_path = cluster_state_helpers.get_state_path_from_metadata()
        if not state_path:
            print("Could not find state path. Exiting.")
            return
    
    print(f"Using state path: {state_path}")
    
    # Get cluster metadata
    print("\nRetrieving cluster metadata...")
    metadata = cluster_state_helpers.get_cluster_metadata(state_path)
    
    if not metadata:
        print("Failed to retrieve cluster metadata. Is the master node running?")
        return
    
    print(f"Cluster ID: {metadata['cluster_id']}")
    print(f"Master node: {metadata['master_id']}")
    print(f"Last updated: {time.ctime(metadata['updated_at'])}")
    print(f"Nodes: {metadata['node_count']}")
    print(f"Tasks: {metadata['task_count']}")
    print(f"Content items: {metadata['content_count']}")
    
    # Get a more detailed cluster summary
    print("\nGetting detailed cluster status...")
    summary = cluster_state_helpers.get_cluster_status_summary(state_path)
    
    if summary:
        print("\nCluster Status Summary:")
        print(f"  Active nodes: {summary['nodes']['active']} / {summary['nodes']['total']}")
        print(f"  Roles: {summary['nodes']['by_role']}")
        print(f"  Resources:")
        print(f"    CPU cores: {summary['resources']['cpu_cores']}")
        print(f"    GPU cores: {summary['resources']['gpu_cores']['available']} available / {summary['resources']['gpu_cores']['total']} total")
        print(f"    Memory: {summary['resources']['memory_gb']['available']}GB available / {summary['resources']['memory_gb']['total']}GB total")
        print(f"  Tasks:")
        print(f"    Total: {summary['tasks']['total']}")
        print(f"    By status: {summary['tasks']['by_status']}")
    else:
        print("Failed to get cluster status summary.")
    
    # Get all nodes
    print("\nListing all nodes:")
    nodes = cluster_state_helpers.get_all_nodes(state_path)
    
    if nodes:
        for node in nodes:
            role = node.get('role', 'unknown')
            status = node.get('status', 'unknown')
            print(f"  Node {node['id']} ({role}): {status}")
    else:
        print("Failed to retrieve nodes.")
    
    # Get all tasks
    print("\nListing all tasks:")
    tasks = cluster_state_helpers.get_all_tasks(state_path)
    
    if tasks:
        for task in tasks:
            task_type = task.get('type', 'unknown')
            status = task.get('status', 'unknown')
            print(f"  Task {task['id']} ({task_type}): {status}")
    else:
        print("Failed to retrieve tasks.")
    
    # Try to find worker nodes with GPU capability
    print("\nFinding worker nodes with GPUs:")
    gpu_nodes = cluster_state_helpers.find_nodes_with_gpu(state_path)
    
    if gpu_nodes:
        for node in gpu_nodes:
            gpu_count = node.get('resources', {}).get('gpu_count', 0)
            print(f"  Node {node['id']} has {gpu_count} GPUs available")
    else:
        print("No nodes with available GPUs found.")

def main():
    """Main function that dispatches to the appropriate example."""
    if len(sys.argv) < 2:
        print("Usage: python cluster_state_example.py [master|external]")
        print("  master: Run the master node example (creates and manages the cluster state)")
        print("  external: Run the external process access example (reads the cluster state)")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "master":
        run_master_example()
    elif mode == "external":
        run_external_access_example()
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: master, external")
        sys.exit(1)

if __name__ == "__main__":
    main()