#!/usr/bin/env python3
"""
Test script for the corrected Intelligent Daemon Manager and Backend System

This script tests the integration with existing backend files:
1. Backend manager with S3 and SSHFS adapters
2. Intelligent daemon management with metadata-driven operations
3. Health monitoring using existing backend implementations
"""

import anyio
import json
import logging
import tempfile
import time
from pathlib import Path
import pytest

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio


def test_backend_manager():
    """Test the enhanced backend manager with existing backend integrations."""
    logger.info("Testing enhanced backend manager...")
    
    try:
        from ipfs_kit_py.backend_manager import BackendManager, get_backend_adapter, list_supported_backends
        
        # Test supported backends
        supported_backends = list_supported_backends()
        logger.info(f"Supported backend types: {supported_backends}")
        
        # Test backend manager initialization
        backend_manager = BackendManager()
        logger.info(f"✓ Backend manager initialized successfully")
        
        # Test backend discovery
        backends = backend_manager.discover_backends()
        logger.info(f"Discovered {len(backends)} backends: {list(backends.keys())}")
        
        # Test adapter creation for supported types
        test_configs = {
            's3': {
                'bucket_name': 'test-bucket',
                'region': 'us-east-1',
                'access_key_id': 'test-key',
                'secret_access_key': 'test-secret'
            },
            'sshfs': {
                'hostname': 'example.com',
                'username': 'testuser',
                'remote_base_path': '/tmp/test'
            }
        }
        
        for backend_type, config in test_configs.items():
            try:
                adapter = get_backend_adapter(backend_type, f'test_{backend_type}', config)
                logger.info(f"✓ Successfully created {backend_type} adapter: {adapter.__class__.__name__}")
                
                # Test that isomorphic methods exist
                required_methods = [
                    'health_check', 'sync_pins', 'backup_buckets', 'backup_metadata'
                ]
                
                for method_name in required_methods:
                    if hasattr(adapter, method_name):
                        logger.debug(f"  ✓ {method_name} method exists")
                    else:
                        logger.error(f"  ✗ {method_name} method missing")
                
            except Exception as e:
                logger.error(f"✗ Failed to create {backend_type} adapter: {e}")
        
        logger.info("✓ Backend manager tests completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Backend manager test failed: {e}")
        return False


async def test_s3_adapter_health():
    """Test S3 adapter health check (will likely fail without real credentials)."""
    logger.info("Testing S3 adapter health check...")
    
    try:
        from ipfs_kit_py.backend_manager import S3BackendAdapter
        
        # Create test configuration
        test_config = {
            'bucket_name': 'test-bucket',
            'region': 'us-east-1',
            'access_key_id': 'test-key',
            'secret_access_key': 'test-secret'
        }
        
        # Create adapter
        adapter = S3BackendAdapter('test_s3', test_config)
        
        # Test health check (expected to fail gracefully)
        logger.info("Testing S3 health check (expected to fail without valid credentials)...")
        health_result = await adapter.health_check()
        logger.info(f"S3 health check result: {health_result}")
        
        # Should have proper structure even on failure
        required_fields = ['healthy', 'response_time_ms', 'error', 'pin_count', 'storage_usage']
        for field in required_fields:
            if field in health_result:
                logger.debug(f"  ✓ {field} field present")
            else:
                logger.error(f"  ✗ {field} field missing")
        
        logger.info("✓ S3 adapter health check test completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ S3 adapter health check test failed: {e}")
        return False


async def test_backend_manager_operations():
    """Test backend manager health check operations."""
    logger.info("Testing backend manager operations...")
    
    try:
        from ipfs_kit_py.backend_manager import BackendManager
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create backend manager
            backend_manager = BackendManager(str(temp_path))
            
            # Create test backend configuration
            test_backend_config = {
                'type': 's3',
                'config': {
                    'bucket_name': 'test-bucket',
                    'region': 'us-east-1'
                },
                'enabled': True
            }
            
            # Create backend config
            result = await backend_manager.create_backend_config(
                'test_s3_backend',
                's3',
                test_backend_config['config']
            )
            logger.info(f"Backend config creation result: {result}")
            
            # Test health check (will fail but should handle gracefully)
            health_result = await backend_manager.health_check_backend('test_s3_backend')
            logger.info(f"Backend health check result: {health_result}")
            
            # Test health check for all backends
            all_health = await backend_manager.health_check_all_backends()
            logger.info(f"All backends health check: {all_health}")
            
            logger.info("✓ Backend manager operations test completed")
            return True
            
    except Exception as e:
        logger.error(f"✗ Backend manager operations test failed: {e}")
        return False


def test_intelligent_daemon_integration():
    """Test intelligent daemon manager integration with backend manager."""
    logger.info("Testing intelligent daemon manager integration...")
    
    try:
        from ipfs_kit_py.intelligent_daemon_manager import IntelligentDaemonManager
        
        # Create daemon manager
        daemon = IntelligentDaemonManager()
        
        # Test daemon status
        status = daemon.get_status()
        logger.info(f"Initial daemon status: {status}")
        
        # Test backend index
        backend_index = daemon.get_backend_index()
        logger.info(f"Backend index shape: {backend_index.shape}")
        logger.info(f"Backend index columns: {list(backend_index.columns)}")
        
        # Test unhealthy backends
        unhealthy = daemon.get_unhealthy_backends()
        logger.info(f"Unhealthy backends: {unhealthy}")
        
        # Test sync needs
        sync_needs = daemon.get_backends_needing_sync()
        logger.info(f"Backends needing sync: {sync_needs}")
        
        logger.info("✓ Intelligent daemon integration test completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Intelligent daemon integration test failed: {e}")
        return False


def main():
    """Run all tests for the corrected intelligent daemon system."""
    logger.info("Starting Corrected Intelligent Daemon System Tests")
    logger.info("=" * 70)
    
    tests = [
        ("Backend Manager", test_backend_manager),
        ("S3 Adapter Health", lambda: anyio.run(test_s3_adapter_health)),
        ("Backend Manager Operations", lambda: anyio.run(test_backend_manager_operations)),
        ("Intelligent Daemon Integration", test_intelligent_daemon_integration),
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
        logger.info("🎉 All tests passed! Corrected intelligent daemon system working.")
    else:
        logger.warning(f"⚠ {total - passed} test(s) failed. Check logs for details.")
    
    # Additional information
    logger.info(f"\n{'='*70}")
    logger.info("SYSTEM INFORMATION")
    logger.info(f"{'='*70}")
    
    try:
        from ipfs_kit_py.backend_manager import list_supported_backends
        supported = list_supported_backends()
        logger.info(f"Supported backend types: {supported}")
        
        # Check availability of backend implementations
        try:
            from ipfs_kit_py.s3_kit import s3_kit
            logger.info("✓ s3_kit backend available")
        except ImportError:
            logger.warning("✗ s3_kit backend not available")
        
        try:
            from ipfs_kit_py.sshfs_backend import SSHFSBackend
            logger.info("✓ SSHFSBackend available")
        except ImportError:
            logger.warning("✗ SSHFSBackend not available")
            
    except Exception as e:
        logger.error(f"Error getting system information: {e}")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
