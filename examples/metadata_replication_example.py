#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Metadata Replication Example

This example demonstrates how to use the metadata replication system in ipfs_kit_py.
It shows how to configure different replication factors, perform replication operations,
and verify the replication status.
"""

import os
import time
import uuid
import json
import logging
from typing import Dict, Any, List

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("metadata_replication_example")

def setup_test_environment(base_path: str = "/tmp/ipfs_kit_py_replication_example"):
    """
    Set up a test environment with multiple nodes for replication testing.
    
    Args:
        base_path: Base directory for test environment
        
    Returns:
        Dictionary with master and worker API instances
    """
    # Create directories for nodes
    os.makedirs(f"{base_path}/master", exist_ok=True)
    os.makedirs(f"{base_path}/worker1", exist_ok=True)
    os.makedirs(f"{base_path}/worker2", exist_ok=True)
    os.makedirs(f"{base_path}/worker3", exist_ok=True)
    os.makedirs(f"{base_path}/worker4", exist_ok=True)
    
    # Create configuration for master node with replication settings
    master_config = {
        "role": "master",
        "ipfs_path": f"{base_path}/master",
        "metadata_replication": {
            "enabled": True,
            "min_replication_factor": 3,  # Minimum for fault tolerance
            "target_replication_factor": 4,  # Target for optimal performance
            "max_replication_factor": 5,   # Maximum to limit resource usage
            "replication_level": "QUORUM",  # Ensure quorum consistency
            "progressive_replication": True  # Enable tiered replication
        }
    }
    
    # Create configuration for worker nodes
    worker_configs = [
        {
            "role": "worker",
            "ipfs_path": f"{base_path}/worker1",
            "metadata_replication": {"enabled": True}
        },
        {
            "role": "worker",
            "ipfs_path": f"{base_path}/worker2",
            "metadata_replication": {"enabled": True}
        },
        {
            "role": "worker",
            "ipfs_path": f"{base_path}/worker3",
            "metadata_replication": {"enabled": True}
        },
        {
            "role": "worker",
            "ipfs_path": f"{base_path}/worker4",
            "metadata_replication": {"enabled": True}
        }
    ]
    
    # Initialize master node
    logger.info("Initializing master node...")
    master_api = IPFSSimpleAPI(config=master_config)
    
    # Initialize worker nodes
    logger.info("Initializing worker nodes...")
    worker_apis = []
    for config in worker_configs:
        worker_api = IPFSSimpleAPI(config=config)
        worker_apis.append(worker_api)
        
    # Register workers with master
    # In a real deployment, this would happen through peer discovery
    # Here we manually register the workers for demonstration purposes
    for i, worker_api in enumerate(worker_apis):
        worker_id = f"worker{i+1}"
        logger.info(f"Registering {worker_id} with master...")
        master_api.register_peer(peer_id=worker_id, 
                              peer_address=f"127.0.0.1:500{i+1}", 
                              capabilities=["metadata_replication"])
    
    return {
        "master": master_api,
        "workers": worker_apis
    }

def create_test_metadata(count: int = 5) -> List[Dict[str, Any]]:
    """
    Create test metadata entries for replication testing.
    
    Args:
        count: Number of metadata entries to create
        
    Returns:
        List of metadata dictionaries
    """
    metadata_entries = []
    
    for i in range(count):
        metadata = {
            "id": str(uuid.uuid4()),
            "name": f"test_file_{i}.txt",
            "content_type": "text/plain",
            "size": 1024 * (i + 1),  # Varying sizes
            "created_at": time.time(),
            "checksum": f"sha256:{uuid.uuid4().hex}",
            "tags": ["test", f"file{i}", "example"],
            "custom_metadata": {
                "importance": i % 3,  # 0, 1, 2 - for demonstrating prioritization
                "category": ["document", "image", "data"][i % 3],
                "retention": ["short", "medium", "long"][i % 3]
            }
        }
        metadata_entries.append(metadata)
        
    return metadata_entries

def demonstrate_basic_replication(apis: Dict[str, Any], metadata_entries: List[Dict[str, Any]]):
    """
    Demonstrate basic metadata replication with status checking.
    
    Args:
        apis: Dictionary containing master and worker API instances
        metadata_entries: List of metadata entries to replicate
    """
    master_api = apis["master"]
    
    logger.info("\n=== Basic Metadata Replication ===\n")
    
    # Store and replicate each metadata entry
    for i, metadata in enumerate(metadata_entries):
        logger.info(f"Storing and replicating metadata entry {i+1}...")
        
        # Store metadata with replication
        result = master_api.store_metadata(
            metadata=metadata,
            replicate=True,  # Enable replication
            replication_level="QUORUM"  # Ensure quorum consistency
        )
        
        logger.info(f"Replication result: {json.dumps(result, indent=2)}")
        
        # Print replication status
        logger.info(f"Replication status: {result['replication_status']}")
        logger.info(f"Replication success level: {result.get('success_level', 'N/A')}")
        logger.info(f"Replication factor achieved: {result.get('successful_replications', 0)}/{result.get('target_nodes_count', 0)}")
        logger.info("-" * 60)

def demonstrate_query_replicated_metadata(apis: Dict[str, Any], metadata_entries: List[Dict[str, Any]]):
    """
    Demonstrate querying replicated metadata across the cluster.
    
    Args:
        apis: Dictionary containing master and worker API instances
        metadata_entries: List of metadata entries that were replicated
    """
    master_api = apis["master"]
    worker_apis = apis["workers"]
    
    logger.info("\n=== Querying Replicated Metadata ===\n")
    
    # Choose one metadata entry to query
    metadata = metadata_entries[0]
    metadata_id = metadata["id"]
    
    # Query from master
    logger.info(f"Querying metadata {metadata_id} from master...")
    master_result = master_api.get_metadata(metadata_id)
    logger.info(f"Master query result: {json.dumps(master_result, indent=2)}")
    
    # Query from each worker
    for i, worker_api in enumerate(worker_apis):
        try:
            logger.info(f"Querying metadata {metadata_id} from worker {i+1}...")
            worker_result = worker_api.get_metadata(metadata_id)
            logger.info(f"Worker {i+1} has metadata: {worker_result is not None}")
        except Exception as e:
            logger.info(f"Worker {i+1} does not have metadata: {str(e)}")
            
    logger.info("-" * 60)

def demonstrate_progressive_replication(apis: Dict[str, Any], metadata_entries: List[Dict[str, Any]]):
    """
    Demonstrate progressive replication with different importance levels.
    
    Args:
        apis: Dictionary containing master and worker API instances
        metadata_entries: List of metadata entries to replicate
    """
    master_api = apis["master"]
    
    logger.info("\n=== Progressive Metadata Replication ===\n")
    
    # Choose metadata entries with different importance levels
    important_metadata = next(m for m in metadata_entries if m["custom_metadata"]["importance"] == 2)
    normal_metadata = next(m for m in metadata_entries if m["custom_metadata"]["importance"] == 1)
    low_metadata = next(m for m in metadata_entries if m["custom_metadata"]["importance"] == 0)
    
    # Store with progressive replication
    for level, metadata in [("High", important_metadata), 
                           ("Normal", normal_metadata), 
                           ("Low", low_metadata)]:
        logger.info(f"Replicating {level} importance metadata...")
        
        # Store with progressive replication strategy
        result = master_api.store_metadata(
            metadata=metadata,
            replicate=True,
            replication_level="PROGRESSIVE",  # Use progressive strategy
            importance_level=metadata["custom_metadata"]["importance"]
        )
        
        logger.info(f"{level} importance replication result: {json.dumps(result, indent=2)}")
        logger.info(f"Replicated to {result.get('successful_replications', 0)} nodes")
        logger.info("-" * 60)

def demonstrate_fault_tolerance(apis: Dict[str, Any], metadata_entries: List[Dict[str, Any]]):
    """
    Demonstrate fault tolerance of the replication system.
    
    Args:
        apis: Dictionary containing master and worker API instances
        metadata_entries: List of metadata entries that were replicated
    """
    master_api = apis["master"]
    worker_apis = apis["workers"]
    
    logger.info("\n=== Fault Tolerance Demonstration ===\n")
    
    # Choose one metadata entry to test with
    metadata = metadata_entries[-1]
    metadata_id = metadata["id"]
    
    # First, verify it's replicated
    logger.info(f"Verifying metadata {metadata_id} is replicated...")
    verification = master_api.verify_metadata_replication(metadata_id)
    logger.info(f"Initial verification: {json.dumps(verification, indent=2)}")
    
    # Now simulate failure of a worker node
    logger.info("Simulating failure of worker node 1...")
    # In a real environment, we would stop the node
    # Here we just simulate by unregistering it
    master_api.unregister_peer(peer_id="worker1")
    
    # Verify metadata is still available despite node failure
    logger.info("Verifying metadata availability after node failure...")
    verification = master_api.verify_metadata_replication(metadata_id)
    logger.info(f"Verification after failure: {json.dumps(verification, indent=2)}")
    
    # Test if we can still get the metadata
    master_result = master_api.get_metadata(metadata_id)
    logger.info(f"Can still access metadata: {master_result is not None}")
    
    logger.info("-" * 60)

def main():
    """
    Main function to run the metadata replication example.
    """
    logger.info("Starting metadata replication example...")
    
    # Set up test environment
    apis = setup_test_environment()
    
    # Create test metadata
    metadata_entries = create_test_metadata()
    
    # Run demonstrations
    try:
        demonstrate_basic_replication(apis, metadata_entries)
        demonstrate_query_replicated_metadata(apis, metadata_entries)
        demonstrate_progressive_replication(apis, metadata_entries)
        demonstrate_fault_tolerance(apis, metadata_entries)
    except Exception as e:
        logger.error(f"Error in demonstration: {str(e)}")
    finally:
        # Clean up (optional - in real usage you'd keep the nodes running)
        logger.info("Example complete.")

if __name__ == "__main__":
    main()
