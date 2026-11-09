#!/usr/bin/env python3
"""
Quick Test Script for Columnar IPLD Implementation

This script performs basic import and initialization tests to validate
the core implementation is working correctly.
"""

import sys
import os
import traceback
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_import(module_name, import_statement):
    """Test importing a specific module with error handling."""
    try:
        exec(import_statement)
        logger.info(f"✓ {module_name} imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ {module_name} import failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run basic import and initialization tests."""
    logger.info("Starting Columnar IPLD Implementation Tests")
    logger.info("=" * 50)
    
    # Add project root to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Test core imports
    tests = [
        ("ParquetCARBridge", "from ipfs_kit_py.parquet_car_bridge import ParquetCARBridge"),
        ("Enhanced VFS APIs", "from ipfs_kit_py.dashboard.enhanced_vfs_apis import VFSMetadataAPI, VectorIndexAPI, KnowledgeGraphAPI, PinsetAPI"),
        ("Enhanced Frontend", "from ipfs_kit_py.dashboard.enhanced_frontend import EnhancedDashboardFrontend"),
        ("Dashboard Integration", "from ipfs_kit_py.dashboard.dashboard_integration import enhance_existing_dashboard"),
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    for module_name, import_statement in tests:
        if test_import(module_name, import_statement):
            success_count += 1
    
    logger.info("=" * 50)
    logger.info(f"Test Results: {success_count}/{total_tests} imports successful")
    
    if success_count == total_tests:
        logger.info("🎉 All core imports working correctly!")
        
        # Test basic class instantiation
        logger.info("Testing basic class instantiation...")
        try:
            # Test mock managers
            class MockIPFSClient:
                async def add_data(self, data): return "mock_cid"
                async def get_data(self, cid): return b"mock_data"
            
            # Test ParquetCARBridge instantiation with correct parameters
            from ipfs_kit_py.parquet_car_bridge import ParquetCARBridge
            
            # Create ParquetIPLDBridge for VFS APIs
            from ipfs_kit_py.parquet_ipld_bridge import ParquetIPLDBridge
            parquet_bridge = ParquetIPLDBridge(
                ipfs_client=MockIPFSClient(),
                storage_path=os.path.expanduser("~/.ipfs_parquet_storage")
            )
            
            # Create TieredCacheManager for VFS APIs
            from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
            cache_manager = TieredCacheManager()
            
            car_bridge = ParquetCARBridge(
                ipfs_client=MockIPFSClient(),
                storage_path="/tmp/test_car_storage"
            )
            logger.info("✓ ParquetCARBridge instantiated successfully")
            
            # Test API instantiation with all required parameters
            from ipfs_kit_py.dashboard.enhanced_vfs_apis import VFSMetadataAPI
            vfs_api = VFSMetadataAPI(
                parquet_bridge=parquet_bridge,
                car_bridge=car_bridge,
                cache_manager=cache_manager
            )
            logger.info("✓ VFSMetadataAPI instantiated successfully")
            
            logger.info("🎉 All basic instantiation tests passed!")
            return True
            
        except Exception as e:
            logger.error(f"✗ Instantiation test failed: {e}")
            traceback.print_exc()
            return False
    else:
        logger.error("❌ Some imports failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
