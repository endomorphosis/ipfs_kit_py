#!/usr/bin/env python3
"""
Advanced IPFS Kit Cluster Management Example.

This example demonstrates the use of the advanced cluster management features:
1. Registering task handlers for distributed processing
2. Proposing configuration changes with consensus
3. Getting comprehensive cluster metrics
4. Setting up automated alert handling for cluster health
"""

import os
import time
import json
import logging
import argparse
import threading
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("cluster-advanced-example")

# Import ipfs_kit_py
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Task handlers
def image_processing_task_handler(payload):
    """Example task handler for image processing tasks."""
    logger.info(f"Processing image task: {payload.get('task_id')}")
    
    # Simulate processing time
    time.sleep(2)
    
    # Return result
    return {
        "success": True,
        "task_id": payload.get("task_id"),
        "processed_at": time.time(),
        "dimensions": payload.get("dimensions", [800, 600]),
        "format": payload.get("format", "jpeg"),
        "processing_time_ms": 2000
    }

def data_analysis_task_handler(payload):
    """Example task handler for data analysis tasks."""
    logger.info(f"Processing data analysis task: {payload.get('task_id')}")
    
    # Simulate processing time
    time.sleep(3)
    
    # Return result with simulated analysis
    return {
        "success": True,
        "task_id": payload.get("task_id"),
        "analyzed_at": time.time(),
        "record_count": payload.get("record_count", 1000),
        "analysis": {
            "mean": 42.5,
            "median": 40.2,
            "std_dev": 12.3,
            "outliers": 15
        },
        "processing_time_ms": 3000
    }

# Alert handler
def handle_cluster_alert(alert):
    """Handle alerts from the cluster monitoring system."""
    severity = alert.get("severity", "info")
    source = alert.get("source", "unknown")
    message = alert.get("message", "No message")
    
    if severity == "critical":
        logger.critical(f"CRITICAL ALERT from {source}: {message}")
        # Could trigger emergency actions here
    elif severity == "error":
        logger.error(f"ERROR ALERT from {source}: {message}")
    elif severity == "warning":
        logger.warning(f"WARNING from {source}: {message}")
    else:
        logger.info(f"INFO from {source}: {message}")

def run_master_node():
    """Run a master node with advanced management features."""
    logger.info("Starting master node...")
    
    # Initialize IPFS Kit with cluster management enabled
    kit = ipfs_kit(
        role="master",
        resources={
            "ipfs_path": os.path.expanduser("~/.ipfs-master"),
            "max_storage_gb": 10
        },
        metadata={
            "enable_cluster_management": True,
            "cluster_id": "advanced-example-cluster",
            "node_id": "master-node"
        }
    )
    
    # Register task handlers
    logger.info("Registering task handlers...")
    
    image_result = kit.register_task_handler(
        task_type="image_processing",
        handler_func=image_processing_task_handler
    )
    logger.info(f"Image processing handler registered: {image_result.get('success', False)}")
    
    data_result = kit.register_task_handler(
        task_type="data_analysis",
        handler_func=data_analysis_task_handler
    )
    logger.info(f"Data analysis handler registered: {data_result.get('success', False)}")
    
    # Get initial cluster status
    status = kit.get_cluster_status()
    logger.info(f"Cluster status: {json.dumps(status, indent=2)}")
    
    # Propose a configuration change
    logger.info("Proposing configuration change...")
    config_result = kit.propose_config_change(
        key="task_timeout_default",
        value=120  # 2 minutes
    )
    logger.info(f"Configuration proposal result: {json.dumps(config_result, indent=2)}")
    
    # Monitor cluster health in background thread
    def monitor_cluster():
        while True:
            try:
                # Get comprehensive metrics
                metrics = kit.get_cluster_metrics(include_history=True)
                
                # Log summarized metrics
                logger.info(f"Cluster metrics update:")
                logger.info(f"- Node count: {len(metrics.get('member_metrics', {})) + 1}")
                
                if 'node_metrics' in metrics:
                    node_metrics = metrics['node_metrics']
                    logger.info(f"- CPU: {node_metrics.get('cpu_percent', 'N/A')}%")
                    logger.info(f"- Memory: {node_metrics.get('memory_percent', 'N/A')}%")
                
                if 'task_statistics' in metrics:
                    task_stats = metrics['task_statistics']
                    logger.info(f"- Tasks: {task_stats.get('total', 0)} total, "
                                f"{task_stats.get('pending', 0)} pending, "
                                f"{task_stats.get('running', 0)} running, "
                                f"{task_stats.get('completed', 0)} completed, "
                                f"{task_stats.get('failed', 0)} failed")
                
                # Sleep for a minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in monitoring thread: {e}")
                time.sleep(30)
    
    # Start monitoring thread
    monitor_thread = threading.Thread(
        target=monitor_cluster,
        daemon=True
    )
    monitor_thread.start()
    
    # Return the initialized kit for further operations
    return kit

def run_worker_node(master_address, worker_id=None):
    """Run a worker node that connects to the master."""
    if not worker_id:
        import uuid
        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting worker node {worker_id}...")
    
    # Initialize IPFS Kit with cluster management enabled
    kit = ipfs_kit(
        role="worker",
        resources={
            "ipfs_path": os.path.expanduser(f"~/.ipfs-{worker_id}"),
            "max_storage_gb": 5
        },
        metadata={
            "enable_cluster_management": True,
            "master_address": master_address,
            "node_id": worker_id
        }
    )
    
    # Register task handlers (workers should register what they can process)
    logger.info("Registering task handlers...")
    
    image_result = kit.register_task_handler(
        task_type="image_processing",
        handler_func=image_processing_task_handler
    )
    logger.info(f"Image processing handler registered: {image_result.get('success', False)}")
    
    data_result = kit.register_task_handler(
        task_type="data_analysis",
        handler_func=data_analysis_task_handler
    )
    logger.info(f"Data analysis handler registered: {data_result.get('success', False)}")
    
    # Get cluster status
    status = kit.get_cluster_status()
    logger.info(f"Connected to cluster: {status.get('success', False)}")
    
    # Return the initialized kit
    return kit

def submit_example_tasks(kit, count=5):
    """Submit example tasks to the cluster."""
    logger.info(f"Submitting {count} example tasks...")
    
    task_results = []
    
    # Submit image processing tasks
    for i in range(count):
        result = kit.submit_cluster_task(
            task_type="image_processing",
            payload={
                "task_id": f"img-{i+1}",
                "file_type": "jpg",
                "dimensions": [1920, 1080],
                "processing": ["resize", "optimize", "watermark"]
            }
        )
        task_results.append(result)
        logger.info(f"Submitted image task {i+1}: {result.get('success', False)}")
        
    # Submit data analysis tasks
    for i in range(count):
        result = kit.submit_cluster_task(
            task_type="data_analysis",
            payload={
                "task_id": f"data-{i+1}",
                "record_count": 10000 * (i + 1),
                "dimensions": 15,
                "analysis_type": "statistical"
            }
        )
        task_results.append(result)
        logger.info(f"Submitted data analysis task {i+1}: {result.get('success', False)}")
    
    return task_results

def monitor_task_progress(kit, task_ids, interval=5, max_time=60):
    """Monitor the progress of specific tasks."""
    logger.info(f"Monitoring progress of {len(task_ids)} tasks...")
    
    start_time = time.time()
    completed = set()
    
    while time.time() - start_time < max_time and len(completed) < len(task_ids):
        for task_id in task_ids:
            if task_id in completed:
                continue
                
            status = kit.get_task_status(task_id)
            if status.get("status") == "completed":
                logger.info(f"Task {task_id} completed")
                completed.add(task_id)
            elif status.get("status") == "failed":
                logger.error(f"Task {task_id} failed: {status.get('error', 'Unknown error')}")
                completed.add(task_id)
            else:
                logger.info(f"Task {task_id} status: {status.get('status', 'unknown')}")
        
        # Print completion percentage
        completion = len(completed) / len(task_ids) * 100
        logger.info(f"Overall completion: {completion:.1f}%")
        
        # Sleep before checking again
        time.sleep(interval)
    
    # Final completion stats
    completion = len(completed) / len(task_ids) * 100
    logger.info(f"Final completion: {completion:.1f}% ({len(completed)}/{len(task_ids)} tasks)")
    
    return completed

def main():
    """Run the advanced cluster example."""
    parser = argparse.ArgumentParser(
        description="Advanced IPFS Kit Cluster Management Example"
    )
    parser.add_argument(
        "--role",
        choices=["master", "worker", "client"],
        default="master",
        help="Role of this node in the cluster"
    )
    parser.add_argument(
        "--master-address",
        help="Address of the master node (required for worker and client)"
    )
    parser.add_argument(
        "--node-id",
        help="Unique identifier for this node (generated if not provided)"
    )
    parser.add_argument(
        "--submit-tasks",
        type=int,
        default=0,
        help="Number of example tasks to submit to the cluster"
    )
    args = parser.parse_args()
    
    if args.role == "master":
        # Run as master node
        kit = run_master_node()
        
        # Submit example tasks if requested
        if args.submit_tasks > 0:
            task_results = submit_example_tasks(kit, count=args.submit_tasks)
            task_ids = [r.get("task_id") for r in task_results if r.get("task_id")]
            monitor_task_progress(kit, task_ids)
        
        # Keep running until interrupted
        try:
            logger.info("Master node running. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down master node...")
            
    elif args.role == "worker":
        # Check required arguments
        if not args.master_address:
            parser.error("--master-address is required for worker nodes")
        
        # Run as worker node
        kit = run_worker_node(args.master_address, args.node_id)
        
        # Keep running until interrupted
        try:
            logger.info("Worker node running. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down worker node...")
            
    elif args.role == "client":
        # Check required arguments
        if not args.master_address:
            parser.error("--master-address is required for client nodes")
        if args.submit_tasks <= 0:
            parser.error("--submit-tasks must be > 0 for client role")
            
        # Initialize client
        logger.info("Initializing client node...")
        kit = ipfs_kit(
            role="leecher",  # Clients use leecher role
            metadata={
                "enable_cluster_management": True,
                "master_address": args.master_address,
                "node_id": args.node_id or "client-node"
            }
        )
        
        # Submit tasks
        task_results = submit_example_tasks(kit, count=args.submit_tasks)
        task_ids = [r.get("task_id") for r in task_results if r.get("task_id")]
        
        # Monitor task progress
        completed_tasks = monitor_task_progress(kit, task_ids)
        
        # Get cluster metrics
        logger.info("Getting cluster metrics...")
        metrics = kit.get_cluster_metrics()
        logger.info(f"Cluster consists of {len(metrics.get('member_metrics', {})) + 1} nodes")
        
        if 'task_statistics' in metrics:
            task_stats = metrics['task_statistics']
            logger.info(f"Task statistics: {json.dumps(task_stats, indent=2)}")
        
        logger.info("Client operations completed.")

if __name__ == "__main__":
    main()