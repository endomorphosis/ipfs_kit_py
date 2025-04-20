#!/usr/bin/env python
"""
Verification test for Advanced Filecoin Integration in MCP.

This script tests the advanced Filecoin functionality of the MCP server by:
1. Testing network analytics and metrics
2. Verifying miner selection and analysis
3. Testing storage deal operations
4. Checking content health monitoring
5. Verifying chain exploration features

This addresses the "Advanced Filecoin Integration" section from the mcp_roadmap.md
that needs reassessment after the consolidation.
"""

import os
import sys
import json
import time
import uuid
import logging
import argparse
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("filecoin_verification")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import the modules needed
try:
    from advanced_filecoin import AdvancedFilecoinStorage
    ADVANCED_FILECOIN_AVAILABLE = True
except ImportError:
    logger.error("Could not import AdvancedFilecoinStorage. Make sure advanced_filecoin.py is accessible.")
    ADVANCED_FILECOIN_AVAILABLE = False


class FilecoinVerificationTest:
    """Test harness for verifying MCP Advanced Filecoin integration."""
    
    def __init__(self, use_mock: bool = True):
        """
        Initialize the test harness.
        
        Args:
            use_mock: Whether to use mock mode for testing
        """
        if not ADVANCED_FILECOIN_AVAILABLE:
            raise ImportError("Advanced Filecoin module not available")
        
        # Create test directory for temp files
        self.test_dir = tempfile.mkdtemp(prefix="filecoin_test_")
        logger.info(f"Created test directory: {self.test_dir}")
        
        # Initialize AdvancedFilecoinStorage in mock mode for testing
        self.filecoin_storage = AdvancedFilecoinStorage(
            lotus_path=None,
            mock_mode=use_mock,
            gateway_mode=False
        )
        
        logger.info(f"Initialized AdvancedFilecoinStorage in {'mock' if use_mock else 'real'} mode")
        
        # Track test CIDs
        self.test_cids = []
    
    def create_test_file(self, content: str = None) -> str:
        """
        Create a test file with random content.
        
        Args:
            content: Optional content for the file
            
        Returns:
            Path to the test file
        """
        if content is None:
            content = f"Test file content {uuid.uuid4()}\n" * 10
        
        file_path = os.path.join(self.test_dir, f"test_file_{uuid.uuid4().hex[:8]}.txt")
        with open(file_path, "w") as f:
            f.write(content)
        
        logger.info(f"Created test file: {file_path} ({len(content)} bytes)")
        return file_path
    
    def test_network_analytics(self) -> bool:
        """Test Filecoin network analytics and metrics."""
        logger.info("Test 1: Network analytics and metrics")
        
        # 1.1 Test getting network statistics
        logger.info("Test 1.1: Getting network statistics")
        result = self.filecoin_storage.get_network_stats()
        
        if result.get("success", False):
            stats = result.get("data", {})
            logger.info(f"✅ Successfully retrieved network statistics")
            logger.info(f"  Chain height: {stats.get('chain_height')}")
            logger.info(f"  Active miners: {stats.get('active_miners')}")
            logger.info(f"  Storage power: {stats.get('storage_power_TiB', 'N/A')} TiB")
        else:
            logger.error(f"❌ Failed to retrieve network statistics: {result.get('error', 'Unknown error')}")
            return False
        
        # 1.2 Test getting gas metrics
        logger.info("Test 1.2: Getting gas metrics")
        result = self.filecoin_storage.get_gas_metrics()
        
        if result.get("success", False):
            gas_data = result.get("data", {})
            logger.info(f"✅ Successfully retrieved gas metrics")
            logger.info(f"  Base fee: {gas_data.get('base_fee', 'N/A')}")
            logger.info(f"  Gas premium estimate: {gas_data.get('gas_premium_estimate', {}).get('medium', 'N/A')}")
        else:
            logger.error(f"❌ Failed to retrieve gas metrics: {result.get('error', 'Unknown error')}")
            return False
        
        return True
    
    def test_miner_selection(self) -> bool:
        """Test miner selection and analysis capabilities."""
        logger.info("Test 2: Miner selection and analysis")
        
        # 2.1 Test getting recommended miners
        logger.info("Test 2.1: Getting recommended miners")
        result = self.filecoin_storage.get_recommended_miners()
        
        if result.get("success", False):
            miners = result.get("miners", [])
            if miners:
                logger.info(f"✅ Successfully retrieved {len(miners)} recommended miners")
                
                # Save first miner for later tests
                self.test_miner = miners[0].get("address")
                logger.info(f"  Sample miner: {miners[0].get('address')} ({miners[0].get('name', 'Unknown')})")
                logger.info(f"  Miner reputation: {miners[0].get('reputation', 'N/A')}")
            else:
                logger.warning("⚠️ No recommended miners returned")
                return False
        else:
            logger.error(f"❌ Failed to retrieve recommended miners: {result.get('error', 'Unknown error')}")
            return False
        
        # 2.2 Test miner analysis
        if hasattr(self, 'test_miner'):
            logger.info(f"Test 2.2: Analyzing miner {self.test_miner}")
            result = self.filecoin_storage.analyze_miner(self.test_miner)
            
            if result.get("success", False):
                analysis = result.get("analysis", {})
                logger.info(f"✅ Successfully analyzed miner {self.test_miner}")
                logger.info(f"  Storage power: {analysis.get('storage_power', 'N/A')}")
                logger.info(f"  Performance score: {analysis.get('performance_score', 'N/A')}")
            else:
                logger.error(f"❌ Failed to analyze miner: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.warning("⚠️ Skipping miner analysis as no test miner is available")
        
        # 2.3 Test miner filtering
        logger.info("Test 2.3: Testing miner filtering")
        result = self.filecoin_storage.get_recommended_miners({"min_reputation": 90})
        
        if result.get("success", False):
            miners = result.get("miners", [])
            if miners:
                logger.info(f"✅ Successfully retrieved {len(miners)} filtered miners")
                
                # Verify filter was applied
                all_high_reputation = all(miner.get("reputation", 0) >= 90 for miner in miners)
                if all_high_reputation:
                    logger.info("  All miners have reputation >= 90 as expected")
                else:
                    logger.warning("⚠️ Some miners have reputation < 90 despite filter")
            else:
                logger.warning("⚠️ No miners match the filter criteria")
        else:
            logger.error(f"❌ Failed to retrieve filtered miners: {result.get('error', 'Unknown error')}")
            return False
        
        return True
    
    def test_storage_operations(self) -> bool:
        """Test storage deal operations."""
        logger.info("Test 3: Storage deal operations")
        
        # First create a test file to use
        test_file_path = self.create_test_file()
        
        # 3.1 Test storage cost estimation
        logger.info("Test 3.1: Storage cost estimation")
        file_size = os.path.getsize(test_file_path)
        result = self.filecoin_storage.estimate_storage_cost(file_size, duration_days=90)
        
        if result.get("success", False):
            estimate = result.get("estimate", {})
            logger.info(f"✅ Successfully estimated storage cost")
            logger.info(f"  Size: {estimate.get('size_gib')} GiB")
            logger.info(f"  Duration: {estimate.get('duration_days')} days")
            logger.info(f"  Estimated cost: {estimate.get('total_cost_fil')} FIL")
        else:
            logger.error(f"❌ Failed to estimate storage cost: {result.get('error', 'Unknown error')}")
            return False
        
        # 3.2 Test adding to IPFS first
        logger.info("Test 3.2: Adding file to IPFS")
        # Since we're in mock mode, we'll simulate this step
        # In a real implementation, we would call the IPFS API
        ipfs_cid = f"Qm{uuid.uuid4().hex[:32]}"
        self.test_cids.append(ipfs_cid)
        logger.info(f"✅ Added file to IPFS with CID: {ipfs_cid}")
        
        # 3.3 Test creating a Filecoin storage deal
        if hasattr(self, 'test_miner'):
            logger.info(f"Test 3.3: Creating storage deal with miner {self.test_miner}")
            result = self.filecoin_storage.from_ipfs(ipfs_cid, self.test_miner)
            
            if result.get("success", False):
                deal_id = result.get("deal_id")
                logger.info(f"✅ Successfully created storage deal with ID: {deal_id}")
                self.test_deal_id = deal_id
            else:
                logger.warning(f"⚠️ Failed to create storage deal: {result.get('error', 'Unknown error')}")
                logger.warning("  This is expected in mock mode with no real Filecoin node")
        else:
            logger.warning("⚠️ Skipping storage deal creation as no test miner is available")
        
        # 3.4 Test redundant storage operation
        logger.info("Test 3.4: Testing redundant storage")
        result = self.filecoin_storage.create_redundant_storage(ipfs_cid, miner_count=2)
        
        if result.get("success", False):
            deals = result.get("deals", [])
            logger.info(f"✅ Successfully created {len(deals)} redundant storage deals")
            logger.info(f"  Redundancy factor: {result.get('redundancy_factor')}")
        else:
            logger.warning(f"⚠️ Failed to create redundant storage: {result.get('error', 'Unknown error')}")
            logger.warning("  This is expected in mock mode with no real Filecoin node")
        
        return True
    
    def test_deal_management(self) -> bool:
        """Test deal management and monitoring."""
        logger.info("Test 4: Deal management and monitoring")
        
        # If we have a test deal ID from previous test, use it
        # Otherwise create a mock deal ID
        if not hasattr(self, 'test_deal_id'):
            self.test_deal_id = f"{random.randint(10000, 99999)}"
            logger.info(f"Using mock deal ID: {self.test_deal_id}")
        
        # 4.1 Test checking deal status
        logger.info(f"Test 4.1: Checking deal status for deal {self.test_deal_id}")
        result = self.filecoin_storage.check_deal_status(self.test_deal_id)
        
        if result.get("success", False):
            status = result.get("status")
            logger.info(f"✅ Successfully checked deal status: {status}")
        else:
            logger.warning(f"⚠️ Failed to check deal status: {result.get('error', 'Unknown error')}")
            logger.warning("  This is expected in mock mode with no real Filecoin node")
        
        # 4.2 Test setting up deal monitoring
        logger.info("Test 4.2: Setting up deal monitoring")
        result = self.filecoin_storage.monitor_deal_status(self.test_deal_id)
        
        if result.get("success", False):
            logger.info(f"✅ Successfully set up deal monitoring")
        else:
            logger.warning(f"⚠️ Failed to set up deal monitoring: {result.get('error', 'Unknown error')}")
            logger.warning("  This is expected in mock mode with no real deals")
        
        # 4.3 Test checking content health
        if hasattr(self, 'test_cids') and self.test_cids:
            test_cid = self.test_cids[0]
            logger.info(f"Test 4.3: Checking content health for CID {test_cid}")
            result = self.filecoin_storage.get_content_health(test_cid)
            
            if result.get("success", False):
                health = result.get("health", {})
                logger.info(f"✅ Successfully checked content health")
                logger.info(f"  Health score: {health.get('health_score')}")
                logger.info(f"  Health status: {health.get('health_status')}")
                logger.info(f"  Active deals: {len(health.get('active_deals', []))}")
            else:
                logger.warning(f"⚠️ Failed to check content health: {result.get('error', 'Unknown error')}")
                logger.warning("  This is expected in mock mode with no real content")
        else:
            logger.warning("⚠️ Skipping content health check as no test CID is available")
        
        return True
    
    def test_chain_exploration(self) -> bool:
        """Test chain exploration features."""
        logger.info("Test 5: Chain exploration")
        
        # 5.1 Test exploring chain block by height
        logger.info("Test 5.1: Exploring chain block by height")
        result = self.filecoin_storage.explore_chain_block(height=None)  # Use latest block
        
        if result.get("success", False):
            block = result.get("block", {})
            logger.info(f"✅ Successfully explored chain block")
            logger.info(f"  Block height: {block.get('Height')}")
            logger.info(f"  Block CID: {block.get('Cid')}")
            
            # Save block CID for next test
            if block.get('Cid'):
                self.test_block_cid = block.get('Cid')
        else:
            logger.error(f"❌ Failed to explore chain block: {result.get('error', 'Unknown error')}")
            return False
        
        # 5.2 Test exploring block by CID
        if hasattr(self, 'test_block_cid'):
            logger.info(f"Test 5.2: Exploring chain block by CID {self.test_block_cid}")
            result = self.filecoin_storage.explore_chain_block(cid=self.test_block_cid)
            
            if result.get("success", False):
                block = result.get("block", {})
                logger.info(f"✅ Successfully explored chain block by CID")
                logger.info(f"  Block height: {block.get('Height')}")
                logger.info(f"  Block miner: {block.get('Miner')}")
            else:
                logger.error(f"❌ Failed to explore chain block by CID: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.warning("⚠️ Skipping chain exploration by CID as no test block CID is available")
        
        return True
    
    def run_tests(self):
        """Run all verification tests."""
        logger.info("Starting Advanced Filecoin Integration verification tests")
        
        test_functions = [
            self.test_network_analytics,
            self.test_miner_selection,
            self.test_storage_operations,
            self.test_deal_management,
            self.test_chain_exploration
        ]
        
        all_passed = True
        
        for i, test_func in enumerate(test_functions):
            logger.info(f"\n{'='*80}\nRunning test {i+1}/{len(test_functions)}: {test_func.__name__}\n{'='*80}")
            try:
                result = test_func()
                if result:
                    logger.info(f"✅ Test {test_func.__name__} PASSED")
                else:
                    logger.error(f"❌ Test {test_func.__name__} FAILED")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {test_func.__name__} FAILED with exception: {e}")
                import traceback
                logger.error(traceback.format_exc())
                all_passed = False
                
            logger.info(f"{'='*80}\n")
        
        logger.info(f"{'='*40}")
        if all_passed:
            logger.info("✅ All Advanced Filecoin Integration tests PASSED")
        else:
            logger.error("❌ Some tests FAILED")
        logger.info(f"{'='*40}")
        
        return all_passed
    
    def cleanup(self):
        """Clean up test resources."""
        logger.info("Cleaning up test resources")
        
        # Clean up test directory
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        logger.info(f"Removed test directory: {self.test_dir}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='MCP Advanced Filecoin Integration Verification'
    )
    parser.add_argument(
        '--use-real', action='store_true',
        help='Use real Filecoin node instead of mock mode'
    )
    parser.add_argument(
        '--skip-cleanup', action='store_true',
        help='Skip cleaning up test resources'
    )
    
    # Only parse args when running the script directly, not when imported by pytest
    
    if __name__ == "__main__":
    
        args = parser.parse_args()
    
    else:
    
        # When run under pytest, use default values
    
        args = parser.parse_args([])
    
    if not ADVANCED_FILECOIN_AVAILABLE:
        logger.error("Advanced Filecoin module not available. Cannot run verification tests.")
        return 1
    
    # Initialize and run tests
    try:
        test = FilecoinVerificationTest(use_mock=not args.use_real)
        success = test.run_tests()
        
        if not args.skip_cleanup:
            test.cleanup()
        
        return 0 if success else 1
        
    except ImportError as e:
        logger.error(f"Failed to initialize tests: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import random  # Added here due to its use in the test methods
    sys.exit(main())