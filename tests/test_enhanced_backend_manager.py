#!/usr/bin/env python3
"""
Test script for Enhanced Backend Manager with Dirty State Tracking

This script tests:
1. All new backend adapters
2. Dirty state tracking and marking
3. Pin synchronization for dirty backends
4. Bulk sync operations
"""

# This file is a manual integration harness, not a unit test module.
# The async helpers below require real adapters and/or external services and can
# be slow or flaky in CI. The project has dedicated unit tests for the backend
# manager elsewhere.
import pytest

pytestmark = pytest.mark.anyio

pytest.skip("Integration harness; skipped in automated test runs", allow_module_level=True)

import anyio
import json
import logging
import tempfile
import time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_backend_adapters():
    """Test all backend adapters creation and availability."""
    logger.info("Testing backend adapter creation...")
    
    try:
        from ipfs_kit_py.backend_manager import BackendManager, list_supported_backends
        
        # Test supported backends
        supported_backends = list_supported_backends()
        logger.info(f"Supported backend types: {supported_backends}")
        
        # Test backend manager initialization
        backend_manager = BackendManager()
        logger.info(f"✓ Backend manager initialized successfully")
        
        # Test adapter creation for each supported type
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
            },
            'huggingface': {
                'token': 'test-token',
                'repo': 'test-user/test-repo'
            },
            'storacha': {
                'api_key': 'test-api-key'
            },
            'ftp': {
                'host': 'ftp.example.com',
                'username': 'testuser',
                'password': 'testpass',
                'port': 21
            },
            'github': {
                'token': 'test-github-token',
                'repo': 'test-user/test-repo'
            }
        }
        
        successful_adapters = 0
        total_adapters = len(test_configs)
        
        for backend_type, config in test_configs.items():
            try:
                adapter = backend_manager.get_backend_adapter(backend_type)
                if adapter is None:
                    # Try to create config first
                    await backend_manager.create_backend_config(
                        f'test_{backend_type}',
                        backend_type,
                        config
                    )
                    adapter = backend_manager.get_backend_adapter(f'test_{backend_type}')
                
                if adapter:
                    logger.info(f"✓ Successfully tested {backend_type} adapter")
                    successful_adapters += 1
                    
                    # Test dirty state functionality
                    logger.info(f"  Testing dirty state for {backend_type}...")
                    is_dirty_before = adapter.is_dirty()
                    adapter.mark_dirty("test_reason")
                    is_dirty_after = adapter.is_dirty()
                    adapter.clear_dirty_state()
                    is_dirty_cleared = adapter.is_dirty()
                    
                    logger.info(f"  Dirty state test: {is_dirty_before} -> {is_dirty_after} -> {is_dirty_cleared}")
                    
                else:
                    logger.warning(f"⚠ Could not create {backend_type} adapter")
                
            except Exception as e:
                logger.error(f"✗ Failed to test {backend_type} adapter: {e}")
        
        logger.info(f"Adapter creation test: {successful_adapters}/{total_adapters} successful")
        return backend_manager, successful_adapters == total_adapters
        
    except Exception as e:
        logger.error(f"Backend adapter test failed: {e}")
        return None, False


async def test_dirty_state_management(backend_manager):
    """Test dirty state management and tracking."""
    logger.info("Testing dirty state management...")
    
    try:
        # Get initial state
        initial_status = backend_manager.get_backend_sync_status()
        logger.info(f"Initial sync status: {len(initial_status)} backends")
        
        # Mark some backends as dirty
        backends = list(backend_manager.discover_backends().keys())
        if backends:
            test_backend = backends[0]
            
            # Test individual backend marking
            backend_manager.mark_backend_dirty(test_backend, "test_individual_mark")
            dirty_backends = backend_manager.get_dirty_backends()
            logger.info(f"After marking {test_backend}: {len(dirty_backends)} dirty backends")
            
            # Test bulk marking
            backend_manager.mark_all_backends_dirty("test_bulk_mark")
            dirty_backends_bulk = backend_manager.get_dirty_backends()
            logger.info(f"After bulk marking: {len(dirty_backends_bulk)} dirty backends")
            
            # Test sync status retrieval
            sync_status = backend_manager.get_backend_sync_status()
            dirty_count = sum(1 for status in sync_status.values() if status.get('is_dirty', False))
            logger.info(f"Sync status shows {dirty_count} dirty backends")
            
            return True
        else:
            logger.warning("No backends available for dirty state testing")
            return False
            
    except Exception as e:
        logger.error(f"Dirty state management test failed: {e}")
        return False


async def test_pin_sync_operations(backend_manager):
    """Test pin synchronization operations."""
    logger.info("Testing pin synchronization operations...")
    
    try:
        # Test dirty backend sync
        dirty_backends = backend_manager.get_dirty_backends()
        if dirty_backends:
            logger.info(f"Testing sync for {len(dirty_backends)} dirty backends...")
            sync_results = await backend_manager.sync_dirty_backends()
            successful_syncs = sum(1 for result in sync_results.values() if result)
            logger.info(f"Dirty sync results: {successful_syncs}/{len(sync_results)} successful")
        else:
            logger.info("No dirty backends to sync")
        
        # Test force sync (this will mark all backends dirty first)
        logger.info("Testing force sync for all backends...")
        force_sync_results = await backend_manager.force_sync_all_backends()
        successful_force_syncs = sum(1 for result in force_sync_results.values() if result)
        logger.info(f"Force sync results: {successful_force_syncs}/{len(force_sync_results)} successful")
        
        return len(sync_results) > 0 or len(force_sync_results) > 0
        
    except Exception as e:
        logger.error(f"Pin sync operations test failed: {e}")
        return False


async def test_health_checks_all_backends(backend_manager):
    """Test health checks for all backend types."""
    logger.info("Testing health checks for all backends...")
    
    try:
        # Test health check for all backends
        health_results = await backend_manager.health_check_all_backends()
        
        total_backends = len(health_results)
        healthy_backends = sum(1 for result in health_results.values() 
                              if result.get('healthy', False))
        
        logger.info(f"Health check results: {healthy_backends}/{total_backends} healthy")
        
        # Log detailed results
        for backend_name, health_result in health_results.items():
            status = "✓ HEALTHY" if health_result.get('healthy', False) else "✗ UNHEALTHY"
            error = health_result.get('error', 'No error')
            response_time = health_result.get('response_time_ms', 0)
            logger.info(f"  {backend_name}: {status} ({response_time:.1f}ms) - {error}")
        
        return True
        
    except Exception as e:
        logger.error(f"Health checks test failed: {e}")
        return False


async def test_backend_cleanup(backend_manager):
    """Test backend state cleanup."""
    logger.info("Testing backend state cleanup...")
    
    try:
        # Clean up backend state
        await backend_manager.cleanup_backend_state()
        
        # Verify no backends are dirty after cleanup
        dirty_backends_after = backend_manager.get_dirty_backends()
        logger.info(f"After cleanup: {len(dirty_backends_after)} dirty backends")
        
        return len(dirty_backends_after) == 0
        
    except Exception as e:
        logger.error(f"Backend cleanup test failed: {e}")
        return False


async def main():
    """Run all tests for enhanced backend manager."""
    logger.info("Starting Enhanced Backend Manager Tests")
    logger.info("=" * 70)
    
    tests = [
        ("Backend Adapters", test_backend_adapters),
        ("Dirty State Management", lambda: test_dirty_state_management(backend_manager)),
        ("Pin Sync Operations", lambda: test_pin_sync_operations(backend_manager)),
        ("Health Checks", lambda: test_health_checks_all_backends(backend_manager)),
        ("Backend Cleanup", lambda: test_backend_cleanup(backend_manager)),
    ]
    
    backend_manager = None
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "Backend Adapters":
                backend_manager, result = await test_func()
            else:
                result = await test_func()
            
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
        logger.info("🎉 All tests passed! Enhanced backend manager working perfectly.")
    else:
        logger.warning(f"⚠ {total - passed} test(s) failed. Check logs for details.")
    
    # Additional information
    if backend_manager:
        logger.info(f"\n{'='*70}")
        logger.info("SYSTEM INFORMATION")
        logger.info(f"{'='*70}")
        
        from ipfs_kit_py.backend_manager import list_supported_backends
        supported = list_supported_backends()
        logger.info(f"Total supported backend types: {len(supported)}")
        for backend_type in supported:
            logger.info(f"  - {backend_type}")
        
        # Backend status summary
        try:
            backends = backend_manager.discover_backends()
            sync_status = backend_manager.get_backend_sync_status()
            dirty_count = sum(1 for status in sync_status.values() if status.get('is_dirty', False))
            
            logger.info(f"\nBackend Status Summary:")
            logger.info(f"  Total configured backends: {len(backends)}")
            logger.info(f"  Dirty backends: {dirty_count}")
            logger.info(f"  Clean backends: {len(backends) - dirty_count}")
            
        except Exception as e:
            logger.error(f"Error getting backend status: {e}")
    
    return passed == total


if __name__ == "__main__":
    success = anyio.run(main)
    exit(0 if success else 1)
