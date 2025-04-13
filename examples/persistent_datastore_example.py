#!/usr/bin/env python3
"""
Persistent DHT Datastore Example

This example demonstrates the usage of the PersistentDHTDatastore class,
which provides disk persistence for the libp2p Kademlia DHT. The datastore
is used to store key-value pairs and provider records, with automatic
synchronization between memory and disk.

Key features demonstrated:
1. Basic operations (put/get/delete)
2. Provider registration and lookup
3. Persistence across restarts
4. Synchronization and transaction safety
5. Async operations for non-blocking usage
6. Performance metrics and statistics
7. Integration with KademliaNode for full DHT functionality

This example can be run in four modes:
1. Basic operations (default)
2. Performance benchmark mode (-b flag)
3. Persistence test mode (-p flag)
4. KademliaNode integration mode (-k flag)

Usage:
    python persistent_datastore_example.py
    python persistent_datastore_example.py -b
    python persistent_datastore_example.py -p
    python persistent_datastore_example.py -k
"""

import os
import sys
import time
import random
import anyio
import argparse
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our datastore implementation
try:
    from ipfs_kit_py.libp2p.datastore import PersistentDHTDatastore
except ImportError:
    # If running from the example directory directly, adjust path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.libp2p.datastore import PersistentDHTDatastore

def run_basic_operations():
    """Demonstrate basic datastore operations."""
    print("\n=== Basic Datastore Operations ===\n")
    
    # Create a test directory for the datastore
    test_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit_test", "datastore")
    os.makedirs(test_dir, exist_ok=True)
    
    # Create the datastore with a small flush threshold for demonstration
    datastore = PersistentDHTDatastore(
        path=test_dir,
        max_items=100,
        flush_threshold=5,  # Flush after 5 changes
        sync_interval=10    # Background sync every 10 seconds
    )
    
    try:
        # Store some test values
        print("Storing test values...")
        datastore.put("key1", b"Simple text value", publisher="peer1")
        datastore.put("key2", b"Another simple value", publisher="peer2")
        datastore.put("binary_key", os.urandom(100), publisher="peer1")  # Binary data
        
        # Register additional providers
        print("Registering additional providers...")
        datastore.add_provider("key1", "peer3")
        datastore.add_provider("key2", "peer1")
        
        # Retrieve values
        print("\nRetrieving values:")
        for key in ["key1", "key2", "binary_key", "nonexistent_key"]:
            value = datastore.get(key)
            if value is not None:
                if len(value) > 50:
                    print(f"  {key}: {value[:20]}... (binary data, {len(value)} bytes)")
                else:
                    print(f"  {key}: {value}")
            else:
                print(f"  {key}: Not found")
        
        # Get providers
        print("\nLooking up providers:")
        for key in ["key1", "key2", "binary_key", "nonexistent_key"]:
            providers = datastore.get_providers(key)
            print(f"  {key}: {providers}")
        
        # Delete a key
        print("\nDeleting key1...")
        datastore.delete("key1")
        
        # Verify deletion
        print("Checking if key1 exists:", datastore.has("key1"))
        
        # Get statistics
        print("\nDatastore statistics:")
        stats = datastore.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Explicitly flush changes to disk
        print("\nManually flushing changes...")
        datastore.stop()
        
        # Create a new instance to demonstrate persistence
        print("\nCreating new datastore instance to verify persistence...")
        datastore2 = PersistentDHTDatastore(path=test_dir)
        
        # Check if data was persisted
        print("\nChecking persisted data:")
        value = datastore2.get("key2")
        print(f"  key2: {value}")
        
        providers = datastore2.get_providers("key2")
        print(f"  key2 providers: {providers}")
        
        # Verify deleted data is still deleted
        print(f"  key1 exists: {datastore2.has('key1')}")
        
        # Clean up
        datastore2.stop()
        
    except Exception as e:
        print(f"Error during basic operations: {e}")
    finally:
        # Make sure to stop the datastore
        if 'datastore' in locals() and datastore:
            datastore.stop()
        if 'datastore2' in locals() and datastore2:
            datastore2.stop()
    
    print("\nBasic operations complete!")

async def run_async_operations():
    """Demonstrate asynchronous datastore operations."""
    print("\n=== Asynchronous Datastore Operations ===\n")
    
    # Create a test directory for the datastore
    test_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit_test", "async_datastore")
    os.makedirs(test_dir, exist_ok=True)
    
    # Create the datastore
    datastore = PersistentDHTDatastore(
        path=test_dir,
        max_items=1000,
        flush_threshold=10
    )
    
    try:
        # Store a large batch of data asynchronously
        print("Storing data with async operations...")
        tasks = []
        
        for i in range(100):
            key = f"async_key_{i}"
            value = f"Async value {i}".encode()
            # Use anyio.create_task to avoid blocking
            tasks.append(
                anyio.create_task(
                    datastore.async_put(key, value, publisher=f"peer{i % 5}")
                )
            )
        
        # Wait for all tasks to complete
        results = await anyio.gather(*tasks)
        print(f"Put operations completed: {sum(results)} successful")
        
        # Read back values asynchronously
        print("\nReading data with async operations...")
        read_tasks = []
        
        for i in range(100):
            key = f"async_key_{i}"
            read_tasks.append(
                anyio.create_task(datastore.async_get(key))
            )
        
        # Wait for all tasks to complete
        values = await anyio.gather(*read_tasks)
        successful_reads = sum(1 for v in values if v is not None)
        print(f"Get operations completed: {successful_reads} successful")
        
        # Flush data
        print("\nFlushing data asynchronously...")
        flush_success = await datastore.async_flush()
        print(f"Flush successful: {flush_success}")
        
        # Get statistics
        print("\nDatastore statistics:")
        stats = datastore.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"Error during async operations: {e}")
    finally:
        # Make sure to stop the datastore
        datastore.stop()
    
    print("\nAsync operations complete!")

def run_performance_benchmark():
    """Benchmark datastore performance."""
    print("\n=== Performance Benchmark ===\n")
    
    # Create a test directory for the datastore
    test_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit_test", "benchmark_datastore")
    os.makedirs(test_dir, exist_ok=True)
    
    # Create the datastore with larger capacity
    datastore = PersistentDHTDatastore(
        path=test_dir,
        max_items=10000,       # 10k items in memory
        flush_threshold=1000,  # Flush after 1000 changes
        sync_interval=30       # Longer interval for benchmark
    )
    
    # Test data sizes
    small_data = b"Small data value" * 5  # ~80 bytes
    medium_data = os.urandom(10 * 1024)   # 10 KB
    large_data = os.urandom(100 * 1024)   # 100 KB
    
    try:
        # 1. Benchmark write performance
        print("Benchmarking write performance...")
        
        # Functions to test different sized writes
        def test_small_writes():
            for i in range(1000):
                key = f"small_{i}"
                datastore.put(key, small_data, publisher=f"peer{i % 10}")
        
        def test_medium_writes():
            for i in range(100):
                key = f"medium_{i}"
                datastore.put(key, medium_data, publisher=f"peer{i % 10}")
        
        def test_large_writes():
            for i in range(10):
                key = f"large_{i}"
                datastore.put(key, large_data, publisher=f"peer{i % 10}")
        
        # Run with timing
        for name, func in [
            ("Small writes (1000 x 80B)", test_small_writes),
            ("Medium writes (100 x 10KB)", test_medium_writes),
            ("Large writes (10 x 100KB)", test_large_writes)
        ]:
            start_time = time.time()
            func()
            elapsed = time.time() - start_time
            print(f"  {name}: {elapsed:.4f} seconds ({func.__name__})")
        
        # 2. Benchmark read performance
        print("\nBenchmarking read performance...")
        
        # Functions to test different access patterns
        def test_sequential_reads():
            for i in range(1000):
                key = f"small_{i}"
                datastore.get(key)
        
        def test_random_reads():
            for _ in range(1000):
                i = random.randint(0, 999)
                key = f"small_{i}"
                datastore.get(key)
        
        def test_repeated_reads():
            for _ in range(1000):
                i = random.randint(0, 50)  # Read from a smaller set repeatedly
                key = f"small_{i}"
                datastore.get(key)
        
        # Run with timing
        for name, func in [
            ("Sequential reads (1000)", test_sequential_reads),
            ("Random reads (1000)", test_random_reads),
            ("Repeated reads (1000)", test_repeated_reads)
        ]:
            start_time = time.time()
            func()
            elapsed = time.time() - start_time
            print(f"  {name}: {elapsed:.4f} seconds ({func.__name__})")
        
        # 3. Benchmark provider operations
        print("\nBenchmarking provider operations...")
        
        def test_add_providers():
            for i in range(1000):
                key = f"small_{i % 100}"  # Use 100 keys with multiple providers
                datastore.add_provider(key, f"peer{i % 50}")
        
        def test_get_providers():
            for i in range(1000):
                key = f"small_{i % 100}"
                datastore.get_providers(key)
        
        # Run with timing
        for name, func in [
            ("Add providers (1000)", test_add_providers),
            ("Get providers (1000)", test_get_providers)
        ]:
            start_time = time.time()
            func()
            elapsed = time.time() - start_time
            print(f"  {name}: {elapsed:.4f} seconds ({func.__name__})")
        
        # 4. Benchmark disk operations
        print("\nBenchmarking disk operations...")
        
        start_time = time.time()
        datastore._flush_to_disk()
        elapsed = time.time() - start_time
        print(f"  Full flush to disk: {elapsed:.4f} seconds")
        
        # Get statistics
        print("\nDatastore statistics after benchmark:")
        stats = datastore.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"Error during benchmark: {e}")
    finally:
        # Make sure to stop the datastore
        datastore.stop()
    
    print("\nBenchmark complete!")

def run_persistence_test():
    """Test persistence across restarts with simulated crashes."""
    print("\n=== Persistence Test ===\n")
    
    # Create a test directory for the datastore
    test_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit_test", "persistence_datastore")
    os.makedirs(test_dir, exist_ok=True)
    
    # Phase 1: Create datastore and add data
    print("Phase 1: Creating datastore and adding data...")
    datastore = PersistentDHTDatastore(
        path=test_dir,
        max_items=1000,
        flush_threshold=20
    )
    
    try:
        # Add test data
        data_map = {}
        for i in range(100):
            key = f"persist_key_{i}"
            value = f"Persistence test value {i} with extra data for uniqueness".encode()
            data_map[key] = value
            datastore.put(key, value, publisher=f"peer{i % 5}")
            
            # Add providers to some keys
            if i % 3 == 0:
                for p in range(3):
                    datastore.add_provider(key, f"provider{p}")
        
        # Force sync to disk
        datastore.stop()
        print("  Added 100 items and forced sync to disk")
        
        # Phase 2: Create a new instance and verify persistence
        print("\nPhase 2: Creating new instance to verify persistence...")
        datastore2 = PersistentDHTDatastore(path=test_dir)
        
        # Verify data
        success_count = 0
        for key, expected_value in data_map.items():
            actual_value = datastore2.get(key)
            if actual_value == expected_value:
                success_count += 1
            else:
                print(f"  Mismatch on {key}: expected length {len(expected_value)}, got {len(actual_value) if actual_value else 'None'}")
        
        print(f"  Data verification: {success_count}/{len(data_map)} items match")
        
        # Verify providers
        provider_success = 0
        for i in range(100):
            if i % 3 == 0:
                key = f"persist_key_{i}"
                providers = datastore2.get_providers(key)
                if len(providers) == 3 and all(f"provider{p}" in providers for p in range(3)):
                    provider_success += 1
        
        print(f"  Provider verification: {provider_success}/{100//3} keys correct")
        
        # Phase 3: Simulate crash during updates
        print("\nPhase 3: Simulating crash during updates...")
        
        # Update some data without proper stopping
        for i in range(50):
            key = f"persist_key_{i}"
            new_value = f"Updated value for crash test {i}".encode()
            data_map[key] = new_value
            datastore2.put(key, new_value)
        
        # Don't call stop() to simulate crash
        print("  Simulated crash after 50 updates (without proper shutdown)")
        
        # Force Python garbage collection to ensure resources are released
        import gc
        datastore2 = None
        gc.collect()
        
        # Phase 4: Recovery after crash
        print("\nPhase 4: Testing recovery after crash...")
        datastore3 = PersistentDHTDatastore(path=test_dir)
        
        # Check how many updates were actually persisted
        recovered_count = 0
        for i in range(50):
            key = f"persist_key_{i}"
            new_value = f"Updated value for crash test {i}".encode()
            actual_value = datastore3.get(key)
            if actual_value == new_value:
                recovered_count += 1
        
        print(f"  Recovery after crash: {recovered_count}/50 updates recovered")
        
        # Clean up
        datastore3.stop()
        
        print("\nPersistence test complete!")
    
    except Exception as e:
        print(f"Error during persistence test: {e}")
    finally:
        # Make sure all datastores are stopped
        for ds in ['datastore', 'datastore2', 'datastore3']:
            if ds in locals() and locals()[ds]:
                try:
                    locals()[ds].stop()
                except:
                    pass

async def run_kademlia_integration():
    """Demonstrate integration with KademliaNode."""
    print("\n=== KademliaNode Integration ===\n")
    
    # Create a test directory for the datastore
    test_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit_test", "kademlia_datastore")
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        # Import KademliaNode
        try:
            from ipfs_kit_py.libp2p.kademlia import KademliaNode
        except ImportError:
            # If running from the example directory directly, adjust path
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            from ipfs_kit_py.libp2p.kademlia import KademliaNode
        
        # Create the persistent datastore
        print("Creating persistent datastore...")
        datastore = PersistentDHTDatastore(
            path=test_dir,
            max_items=100,
            flush_threshold=5,  # Flush after 5 changes
            sync_interval=10    # Background sync every 10 seconds
        )
        
        # First store some test data directly in the datastore
        print("Storing test data directly in datastore...")
        test_keys = []
        for i in range(10):
            key = f"test_key_{i}"
            test_keys.append(key)
            value = f"Test value {i} from datastore".encode()
            datastore.put(key, value, publisher=f"peer{i % 3}")
        
        # Create a KademliaNode instance with the persistent datastore
        print("\nCreating KademliaNode with persistent datastore...")
        node = KademliaNode(
            peer_id="test_peer_id",
            bucket_size=20,
            alpha=3,
            datastore=datastore  # Use our persistent datastore
        )
        
        # Start the node
        print("Starting KademliaNode...")
        await node.start()
        
        # Store some data through the KademliaNode
        print("\nStoring test data through KademliaNode...")
        for i in range(5):
            key = f"kad_key_{i}"
            value = f"Test value {i} from KademliaNode".encode()
            success = await node.put_value(key, value)
            print(f"  Stored key '{key}': {success}")
        
        # Register as a provider for some content
        print("\nRegistering as provider for test content...")
        for i in range(3):
            key = f"kad_content_{i}"
            success = await node.provide(key)
            print(f"  Registered as provider for '{key}': {success}")
        
        # Retrieve values
        print("\nRetrieving values from KademliaNode:")
        # Test retrieving datastore values through KademliaNode
        for key in test_keys[:5]:  # Check a few of the datastore keys
            value = await node.get_value(key)
            if value:
                print(f"  {key}: {value.decode()}")
            else:
                print(f"  {key}: Not found")
        
        # Test retrieving KademliaNode values
        for i in range(5):
            key = f"kad_key_{i}"
            value = await node.get_value(key)
            if value:
                print(f"  {key}: {value.decode()}")
            else:
                print(f"  {key}: Not found")
        
        # Find providers
        print("\nLooking up providers:")
        for i in range(3):
            key = f"kad_content_{i}"
            providers = await node.find_providers(key)
            print(f"  {key}: {providers}")
        
        # Stop the node
        print("\nStopping KademliaNode...")
        await node.stop()
        
        # Create a new node instance to verify persistence
        print("\nCreating new KademliaNode to verify persistence...")
        datastore2 = PersistentDHTDatastore(path=test_dir)
        node2 = KademliaNode(
            peer_id="test_peer_id_2",
            datastore=datastore2
        )
        
        # Start the new node
        await node2.start()
        
        # Verify that data persists
        print("\nVerifying persisted data:")
        for i in range(5):
            key = f"kad_key_{i}"
            value = await node2.get_value(key)
            if value:
                print(f"  {key}: {value.decode()}")
            else:
                print(f"  {key}: Not found")
        
        # Verify provider records persistence
        print("\nVerifying persisted provider records:")
        for i in range(3):
            key = f"kad_content_{i}"
            providers = datastore2.get_providers(key)
            print(f"  {key}: {providers}")
        
        # Stop the second node
        await node2.stop()
        
        # Check statistics from both datastores
        print("\nDatastore statistics after KademliaNode usage:")
        stats1 = datastore.get_stats()
        for key, value in stats1.items():
            print(f"  {key}: {value}")
            
        print("\nSecond datastore statistics:")
        stats2 = datastore2.get_stats()
        for key, value in stats2.items():
            print(f"  {key}: {value}")
        
        # Clean up
        datastore.stop()
        datastore2.stop()
        
    except Exception as e:
        print(f"Error during KademliaNode integration: {e}")
    finally:
        # Make sure all resources are cleaned up
        if 'datastore' in locals() and datastore:
            datastore.stop()
        if 'datastore2' in locals() and datastore2:
            datastore2.stop()
    
    print("\nKademliaNode integration test complete!")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Persistent DHT Datastore Example")
    parser.add_argument("-b", "--benchmark", action="store_true", help="Run performance benchmark")
    parser.add_argument("-p", "--persistence", action="store_true", help="Run persistence test")
    parser.add_argument("-a", "--async", action="store_true", help="Run async operations test")
    parser.add_argument("-k", "--kademlia", action="store_true", help="Run KademliaNode integration test")
    args = parser.parse_args()
    
    # Run the selected mode
    if args.benchmark:
        run_performance_benchmark()
    elif args.persistence:
        run_persistence_test()
    elif getattr(args, 'async'):
        anyio.run(run_async_operations())
    elif args.kademlia:
        anyio.run(run_kademlia_integration())
    else:
        # Default: run basic operations
        run_basic_operations()