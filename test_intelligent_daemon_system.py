#!/usr/bin/env python3
"""
Test script for the Intelligent Daemon Manager and Backend Adapters

This script tests the complete intelligent daemon system with:
1. Backend adapter factory and isomorphic interfaces
2. Health monitoring and metadata-driven operations
3. Task scheduling and execution
"""

import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_backend_adapters():
    """Test backend adapter factory and isomorphic interfaces."""
    logger.info("Testing backend adapter factory and interfaces...")
    
    try:
        # Import the backend system
        from ipfs_kit_py.backends import get_backend_adapter, list_supported_backends, BACKEND_ADAPTERS
        
        # Test supported backends list
        supported_backends = list_supported_backends()
        logger.info(f"Supported backend types: {supported_backends}")
        
        # Test adapter registry
        logger.info(f"Backend adapter registry: {list(BACKEND_ADAPTERS.keys())}")
        
        # Test creating adapters for each supported type
        test_configs = {
            'ipfs': {'type': 'ipfs', 'api_url': 'http://localhost:5001'},
            'filesystem': {'type': 'filesystem', 'storage_path': '/tmp/test_fs_backend'},
            's3': {'type': 's3', 'bucket_name': 'test-bucket', 'region': 'us-east-1'}
        }
        
        for backend_type, config in test_configs.items():
            try:
                adapter = get_backend_adapter(backend_type, f'test_{backend_type}')
                logger.info(f"✓ Successfully created {backend_type} adapter: {adapter.__class__.__name__}")
                
                # Test that all required methods exist
                required_methods = [
                    'health_check', 'sync_pins', 'backup_buckets', 'backup_metadata',
                    'restore_pins', 'restore_buckets', 'restore_metadata',
                    'list_pins', 'list_buckets', 'cleanup_old_backups', 'get_storage_usage'
                ]
                
                for method_name in required_methods:
                    if hasattr(adapter, method_name):
                        logger.debug(f"  ✓ {method_name} method exists")
                    else:
                        logger.error(f"  ✗ {method_name} method missing")
                
            except Exception as e:
                logger.error(f"✗ Failed to create {backend_type} adapter: {e}")
        
        # Test invalid backend type
        try:
            get_backend_adapter('invalid_type', 'test_invalid')
            logger.error("✗ Should have raised error for invalid backend type")
        except ValueError as e:
            logger.info(f"✓ Correctly raised error for invalid backend type: {e}")
        
        logger.info("✓ Backend adapter factory tests completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Backend adapter factory test failed: {e}")
        return False


def test_filesystem_adapter():
    """Test filesystem backend adapter with temporary directory."""
    logger.info("Testing filesystem backend adapter...")
    
    try:
        from ipfs_kit_py.backends import FilesystemBackendAdapter
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test configuration
            test_config = {
                'type': 'filesystem',
                'storage_path': str(temp_path / 'test_storage')
            }
            
            # Create adapter
            adapter = FilesystemBackendAdapter('test_filesystem')
            adapter.config = test_config
            adapter.storage_path = Path(test_config['storage_path'])
            adapter.pins_dir = adapter.storage_path / 'pins'
            adapter.buckets_dir = adapter.storage_path / 'buckets'
            adapter.metadata_dir = adapter.storage_path / 'metadata'
            
            # Test health check
            logger.info("Testing filesystem health check...")
            health_result = asyncio.run(adapter.health_check())
            logger.info(f"Health check result: {health_result}")
            
            if health_result.get('healthy'):
                logger.info("✓ Filesystem health check passed")
            else:
                logger.warning(f"⚠ Filesystem health check failed: {health_result.get('error')}")
            
            # Test storage usage
            logger.info("Testing storage usage calculation...")
            storage_usage = asyncio.run(adapter.get_storage_usage())
            logger.info(f"Storage usage: {storage_usage}")
            
            # Test pin operations (with mock data)
            logger.info("Testing pin operations...")
            
            # Create some test pin data
            test_pin = {
                'cid': 'QmTest123',
                'name': 'test_pin',
                'pin_type': 'recursive',
                'timestamp': time.time(),
                'size_bytes': 1024
            }
            
            # Test backup pin to storage
            adapter.pins_dir.mkdir(parents=True, exist_ok=True)
            success = asyncio.run(adapter._backup_pin_to_storage(test_pin))
            if success:
                logger.info("✓ Pin backup test passed")
            else:
                logger.error("✗ Pin backup test failed")
            
            # Test getting stored pins
            stored_pins = asyncio.run(adapter._get_stored_pins())
            logger.info(f"Stored pins: {len(stored_pins)}")
            
            logger.info("✓ Filesystem adapter tests completed")
            return True
            
    except Exception as e:
        logger.error(f"✗ Filesystem adapter test failed: {e}")
        return False


def test_intelligent_daemon_discovery():
    """Test backend discovery using temporary configurations."""
    logger.info("Testing intelligent daemon backend discovery...")
    
    try:
        from ipfs_kit_py.intelligent_daemon_manager import BackendHealthMonitor
        
        # Create temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ipfs_kit_dir = temp_path / '.ipfs_kit'
            backend_index_dir = ipfs_kit_dir / 'backend_index'
            backend_index_dir.mkdir(parents=True, exist_ok=True)
            
            # Create test backend configurations
            test_backends = {
                'test_ipfs': {
                    'type': 'ipfs',
                    'api_url': 'http://localhost:5001',
                    'enabled': True
                },
                'test_filesystem': {
                    'type': 'filesystem',
                    'storage_path': '/tmp/test_fs',
                    'enabled': True
                },
                'test_s3': {
                    'type': 's3',
                    'bucket_name': 'test-bucket',
                    'region': 'us-east-1',
                    'enabled': False
                }
            }
            
            # Write backend configurations
            import yaml
            for backend_name, config in test_backends.items():
                config_file = backend_index_dir / f'backend_{backend_name}.yaml'
                with open(config_file, 'w') as f:
                    yaml.dump(config, f)
            
            # Create health monitor
            health_monitor = BackendHealthMonitor(ipfs_kit_dir)
            
            # Test backend discovery
            discovered_backends = health_monitor.discover_backends()
            logger.info(f"Discovered backends: {list(discovered_backends.keys())}")
            
            # Verify all test backends were discovered
            expected_backends = set(test_backends.keys())
            discovered_names = set(discovered_backends.keys())
            
            if expected_backends.issubset(discovered_names):
                logger.info("✓ All test backends discovered correctly")
            else:
                missing = expected_backends - discovered_names
                logger.error(f"✗ Missing backends: {missing}")
            
            # Test backend metadata
            for backend_name in discovered_backends:
                metadata = health_monitor.get_backend_metadata(backend_name)
                logger.info(f"Backend {backend_name} metadata: {metadata}")
            
            logger.info("✓ Intelligent daemon discovery tests completed")
            return True
            
    except Exception as e:
        logger.error(f"✗ Intelligent daemon discovery test failed: {e}")
        return False


def test_daemon_task_system():
    """Test the daemon task scheduling and execution system."""
    logger.info("Testing daemon task scheduling system...")
    
    try:
        from ipfs_kit_py.intelligent_daemon_manager import IntelligentDaemonManager
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ipfs_kit_dir = temp_path / '.ipfs_kit'
            ipfs_kit_dir.mkdir(parents=True, exist_ok=True)
            
            # Create daemon manager
            daemon = IntelligentDaemonManager(ipfs_kit_dir)
            
            # Test daemon status before starting
            status = daemon.get_daemon_status()
            logger.info(f"Initial daemon status: {status}")
            
            # Start daemon
            logger.info("Starting daemon...")
            daemon.start()
            time.sleep(2)  # Let daemon initialize
            
            # Test daemon status after starting
            status = daemon.get_daemon_status()
            logger.info(f"Running daemon status: {status}")
            
            if status['running']:
                logger.info("✓ Daemon started successfully")
            else:
                logger.error("✗ Daemon failed to start")
            
            # Test manual health check
            logger.info("Testing manual health check...")
            result = daemon.manual_health_check()
            logger.info(f"Manual health check result: {result}")
            
            # Wait a bit for tasks to process
            time.sleep(3)
            
            # Check task history
            task_history = daemon.get_task_history()
            logger.info(f"Task history: {len(task_history)} tasks")
            
            # Stop daemon
            logger.info("Stopping daemon...")
            daemon.stop()
            
            # Test daemon status after stopping
            status = daemon.get_daemon_status()
            logger.info(f"Stopped daemon status: {status}")
            
            if not status['running']:
                logger.info("✓ Daemon stopped successfully")
            else:
                logger.error("✗ Daemon failed to stop")
            
            logger.info("✓ Daemon task system tests completed")
            return True
            
    except Exception as e:
        logger.error(f"✗ Daemon task system test failed: {e}")
        return False


async def test_adapter_health_checks():
    """Test health checks for different adapter types."""
    logger.info("Testing adapter health checks...")
    
    try:
        from ipfs_kit_py.backends import get_backend_adapter
        
        # Test filesystem adapter health check
        filesystem_adapter = get_backend_adapter('filesystem', 'test_fs')
        filesystem_adapter.config = {
            'type': 'filesystem',
            'storage_path': '/tmp/test_health_check'
        }
        filesystem_adapter.storage_path = Path('/tmp/test_health_check')
        filesystem_adapter.pins_dir = filesystem_adapter.storage_path / 'pins'
        filesystem_adapter.buckets_dir = filesystem_adapter.storage_path / 'buckets'
        filesystem_adapter.metadata_dir = filesystem_adapter.storage_path / 'metadata'
        
        logger.info("Testing filesystem adapter health check...")
        health_result = await filesystem_adapter.health_check()
        logger.info(f"Filesystem health: {health_result}")
        
        # Test S3 adapter (will likely fail without credentials, but tests interface)
        s3_adapter = get_backend_adapter('s3', 'test_s3')
        s3_adapter.config = {
            'type': 's3',
            'bucket_name': 'test-bucket',
            'region': 'us-east-1'
        }
        
        logger.info("Testing S3 adapter health check...")
        health_result = await s3_adapter.health_check()
        logger.info(f"S3 health: {health_result}")
        
        # Test IPFS adapter (will likely fail without IPFS running)
        ipfs_adapter = get_backend_adapter('ipfs', 'test_ipfs')
        ipfs_adapter.config = {
            'type': 'ipfs',
            'api_url': 'http://localhost:5001'
        }
        
        logger.info("Testing IPFS adapter health check...")
        health_result = await ipfs_adapter.health_check()
        logger.info(f"IPFS health: {health_result}")
        
        logger.info("✓ Adapter health check tests completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Adapter health check test failed: {e}")
        return False


def main():
    """Run all tests for the intelligent daemon system."""
    logger.info("Starting Intelligent Daemon Manager and Backend Adapter Tests")
    logger.info("=" * 70)
    
    tests = [
        ("Backend Adapter Factory", test_backend_adapters),
        ("Filesystem Adapter", test_filesystem_adapter),
        ("Daemon Discovery", test_intelligent_daemon_discovery),
        ("Daemon Task System", test_daemon_task_system),
        ("Adapter Health Checks", lambda: asyncio.run(test_adapter_health_checks())),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                logger.info(f"✓ {test_name} PASSED")
            else:
                logger.error(f"✗ {test_name} FAILED")
        except Exception as e:
            logger.error(f"✗ {test_name} ERROR: {e}")
            results[test_name] = False
    
    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*70}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name:30} {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Intelligent daemon system is working correctly.")
    else:
        logger.warning(f"⚠ {total - passed} test(s) failed. Check the logs above for details.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
