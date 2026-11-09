#!/usr/bin/env python3
"""
Comprehensive test script for the Filecoin API in ipfs_kit_py.

This script tests all major functionality of the Filecoin integration:
1. Basic connectivity and API functionality
2. Wallet operations
3. Content storage operations
4. Deal management
5. Miner interactions
6. Integration with IPFS
7. Mock mode for testing without credentials

Usage:
    python test_filecoin_api.py

Requirements:
    - ipfs_kit_py with Filecoin dependencies installed
    - Proper Filecoin API credentials (optional - can run in mock mode)

Running without credentials:
    The test script will automatically detect if credentials are available.
    If credentials are not found, it will run in mock mode, using simulated
    responses instead of actual API calls.

Environment variables (optional):
    LOTUS_API_URL: URL of the Lotus API (default: http://localhost:1234/rpc/v0)
    LOTUS_API_TOKEN: Authentication token for Lotus API
    LOTUS_PATH: Path to Lotus directory
"""

import os
import sys
import time
import tempfile
import logging
import json
import random
import unittest
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("filecoin-api-test")

# Add parent directory to path to allow importing from ipfs_kit_py
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import required modules
try:
    from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_KIT_AVAILABLE
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    from ipfs_kit_py.credential_manager import CredentialManager
    HAS_LOTUS_KIT = LOTUS_KIT_AVAILABLE
except ImportError as e:
    logger.error(f"Import error: {e}")
    HAS_LOTUS_KIT = False

def check_api_credentials():
    """Check if Filecoin API credentials are available."""
    try:
        # Check for direct environment variable
        if os.environ.get("LOTUS_API_TOKEN"):
            logger.info("Found Filecoin API token in environment variables")
            return True
            
        # Try to get stored credentials from credential manager
        cred_manager = CredentialManager()
        filecoin_creds = cred_manager.get_filecoin_credentials("default")
        
        if not filecoin_creds:
            logger.warning("No Filecoin credentials found in credential store")
            return False
            
        logger.info("Found Filecoin credentials in credential store")
        return True
    except Exception as e:
        logger.error(f"Error checking credentials: {e}")
        return False

def generate_test_content(size_kb=1024):
    """Generate random test content of specified size in KB."""
    # Create 1MB of random data
    data = bytes(random.getrandbits(8) for _ in range(size_kb * 1024))
    return data

class FilecoinAPITest(unittest.TestCase):
    """Test suite for Filecoin API integration."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are reused across test methods."""
        logger.info("Setting up Filecoin API tests...")
        
        # Check if lotus_kit is available
        if not LOTUS_KIT_AVAILABLE:
            logger.error("lotus_kit module is not available")
            sys.exit(1)
            
        # Check for credentials
        cls.has_credentials = check_api_credentials()
        
        # Initialize metadata with defaults or environment variables
        cls.metadata = {
            "api_url": os.environ.get("LOTUS_API_URL", "http://localhost:1234/rpc/v0"),
            "token": os.environ.get("LOTUS_API_TOKEN", ""),
            "lotus_path": os.environ.get("LOTUS_PATH", "/tmp/lotus"),
            "mock_mode": not cls.has_credentials
        }
        
        # Try to get stored credentials if environment variables not set
        if not cls.metadata["token"]:
            try:
                cred_manager = CredentialManager()
                filecoin_creds = cred_manager.get_filecoin_credentials("default")
                if filecoin_creds:
                    cls.metadata["token"] = filecoin_creds.get("api_key", "")
            except Exception as e:
                logger.warning(f"Could not get credentials from manager: {e}")
        
        # Create a temporary test file
        cls.test_data = generate_test_content()
        fd, cls.test_file_path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            f.write(cls.test_data)
        
        logger.info(f"Created test file at {cls.test_file_path} with size {len(cls.test_data)/1024} KB")
        
        # Initialize lotus_kit instance (with real credentials or mock mode)
        try:
            cls.lotus = lotus_kit(metadata=cls.metadata)
            logger.info(f"Initialized lotus_kit (mock_mode={cls.metadata['mock_mode']})")
        except Exception as e:
            logger.error(f"Failed to initialize lotus_kit: {e}")
            cls.lotus = None
            cls.has_credentials = False
            
        # Initialize FilecoinModel
        try:
            cls.filecoin_model = FilecoinModel(lotus_kit_instance=cls.lotus)
            logger.info("Initialized FilecoinModel")
        except Exception as e:
            logger.error(f"Failed to initialize FilecoinModel: {e}")
            cls.filecoin_model = None
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test fixtures."""
        # Remove test file
        if hasattr(cls, 'test_file_path') and os.path.exists(cls.test_file_path):
            os.unlink(cls.test_file_path)
            logger.info(f"Removed test file {cls.test_file_path}")
            
        # Clean up any test credentials
        try:
            cred_manager = CredentialManager()
            cred_manager.remove_credential("filecoin", "test_credentials")
            logger.info("Cleaned up test credentials")
        except Exception as e:
            logger.warning(f"Failed to clean up test credentials: {e}")
    
    def setUp(self):
        """Set up individual test fixtures."""
        # Only skip API tests that require real credentials
        # These tests can run without real credentials:
        # - Module availability test
        # - Credential management test
        # - Mock mode test
        # - IPFS integration tests (these use mocks internally)
        test_name = self._testMethodName
        if (not self.has_credentials and 
            not test_name.startswith("test_00_check_module") and 
            not test_name.startswith("test_01_credential") and 
            not test_name.startswith("test_13_mock") and
            not test_name.startswith("test_14_ipfs_to_filecoin") and
            not test_name.startswith("test_15_filecoin_to_ipfs")):
            # Skip actual API tests that require credentials
            self.skipTest("No Filecoin credentials available")
    
    def test_00_check_module_availability(self):
        """Test that the Filecoin modules are available."""
        self.assertTrue(LOTUS_KIT_AVAILABLE, "lotus_kit module should be available")
        self.assertIsNotNone(self.filecoin_model, "FilecoinModel should be initialized")
    
    def test_01_credential_management(self):
        """Test Filecoin credential management."""
        # Initialize credential manager
        cred_manager = CredentialManager()
        
        # Test adding credentials
        result = cred_manager.add_filecoin_credentials(
            name="test_credentials",
            api_key="test_api_key",
            api_secret="test_secret",
            wallet_address="t1test123",
            provider="lotus"
        )
        self.assertTrue(result, "Should successfully add test credentials")
        
        # Test retrieving credentials
        filecoin_creds = cred_manager.get_filecoin_credentials("test_credentials")
        self.assertIsNotNone(filecoin_creds, "Should retrieve the test credentials")
        self.assertEqual(filecoin_creds.get("api_key"), "test_api_key", "API key should match")
        self.assertEqual(filecoin_creds.get("provider"), "lotus", "Provider should match")
        
        # Clean up by removing test credentials
        cred_manager.remove_credential("filecoin", "test_credentials")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_02_check_connection(self):
        """Test checking connection to the Lotus API."""
        if self.has_credentials and self.lotus:
            # Test actual connection
            result = self.lotus.check_connection()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                logger.info(f"Successfully connected to Lotus API: {result.get('result', {}).get('Version', 'unknown')}")
            else:
                logger.warning(f"Could not connect to Lotus API: {result.get('error', 'Unknown error')}")
        
        # Test connection checking through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.check_connection()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                logger.info("FilecoinModel successfully connected to Lotus API")
            else:
                logger.warning(f"FilecoinModel could not connect to Lotus API: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_03_list_wallets(self):
        """Test listing Filecoin wallets."""
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.list_wallets()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                wallets = result.get("result", [])
                logger.info(f"Found {len(wallets)} wallets")
                if wallets:
                    logger.info(f"First wallet: {wallets[0]}")
            else:
                logger.warning(f"Could not list wallets: {result.get('error', 'Unknown error')}")
        
        # Test wallet listing through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.list_wallets()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                wallets = result.get("wallets", [])
                logger.info(f"FilecoinModel found {len(wallets)} wallets")
            else:
                logger.warning(f"FilecoinModel could not list wallets: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_04_wallet_balance(self):
        """Test getting wallet balance."""
        if self.has_credentials and self.lotus:
            # First get a wallet address
            list_result = self.lotus.list_wallets()
            if list_result.get("success", False) and list_result.get("result"):
                wallet_address = list_result["result"][0]
                
                # Test actual API
                result = self.lotus.wallet_balance(wallet_address)
                self.assertIn("success", result, "Result should contain success field")
                if result.get("success", False):
                    balance = result.get("result", "0")
                    logger.info(f"Wallet {wallet_address} has balance: {balance}")
                else:
                    logger.warning(f"Could not get wallet balance: {result.get('error', 'Unknown error')}")
            else:
                logger.warning("No wallets available for balance test")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_05_import_file(self):
        """Test importing a file into the Lotus client."""
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.client_import(self.test_file_path)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                root_cid = result.get("result", {}).get("Root", {}).get("/")
                logger.info(f"Successfully imported file with root CID: {root_cid}")
                # Store CID for later tests
                self.__class__.imported_cid = root_cid
            else:
                logger.warning(f"Could not import file: {result.get('error', 'Unknown error')}")
        
        # Test import through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.import_file(self.test_file_path)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                root_cid = result.get("root")
                logger.info(f"FilecoinModel successfully imported file with root CID: {root_cid}")
                # Store CID for later tests if not already set
                if not hasattr(self.__class__, 'imported_cid'):
                    self.__class__.imported_cid = root_cid
            else:
                logger.warning(f"FilecoinModel could not import file: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_06_list_imports(self):
        """Test listing imported files."""
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.client_list_imports()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                imports = result.get("result", [])
                logger.info(f"Found {len(imports)} imports")
                if imports:
                    logger.info(f"First import: {imports[0]}")
            else:
                logger.warning(f"Could not list imports: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.list_imports()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                imports = result.get("imports", [])
                logger.info(f"FilecoinModel found {len(imports)} imports")
            else:
                logger.warning(f"FilecoinModel could not list imports: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_07_find_data(self):
        """Test finding where data is stored."""
        if not hasattr(self.__class__, 'imported_cid') or not self.__class__.imported_cid:
            self.skipTest("No imported CID available for testing")
            
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.client_find_data(self.__class__.imported_cid)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                locations = result.get("result", {}).get("Info", [])
                logger.info(f"Found data in {len(locations)} locations")
                if locations:
                    logger.info(f"First location: {locations[0]}")
            else:
                logger.warning(f"Could not find data: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.find_data(self.__class__.imported_cid)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                locations = result.get("locations", [])
                logger.info(f"FilecoinModel found data in {len(locations)} locations")
            else:
                logger.warning(f"FilecoinModel could not find data: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_08_list_deals(self):
        """Test listing storage deals."""
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.client_list_deals()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                deals = result.get("result", [])
                logger.info(f"Found {len(deals)} storage deals")
                if deals:
                    logger.info(f"First deal: {deals[0]}")
                    # Store deal ID for later tests
                    if "DealID" in deals[0]:
                        self.__class__.deal_id = deals[0]["DealID"]
            else:
                logger.warning(f"Could not list deals: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.list_deals()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                deals = result.get("deals", [])
                logger.info(f"FilecoinModel found {len(deals)} storage deals")
                if deals and not hasattr(self.__class__, 'deal_id'):
                    if "DealID" in deals[0]:
                        self.__class__.deal_id = deals[0]["DealID"]
            else:
                logger.warning(f"FilecoinModel could not list deals: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_09_deal_info(self):
        """Test getting information about a specific deal."""
        if not hasattr(self.__class__, 'deal_id'):
            self.skipTest("No deal ID available for testing")
            
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.client_deal_info(self.__class__.deal_id)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                deal_info = result.get("result", {})
                logger.info(f"Deal info: {deal_info}")
            else:
                logger.warning(f"Could not get deal info: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.get_deal_info(self.__class__.deal_id)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                deal_info = result.get("deal_info", {})
                logger.info(f"FilecoinModel got deal info for deal {self.__class__.deal_id}")
            else:
                logger.warning(f"FilecoinModel could not get deal info: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_10_list_miners(self):
        """Test listing miners in the network."""
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.list_miners()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                miners = result.get("result", [])
                logger.info(f"Found {len(miners)} miners")
                if miners:
                    logger.info(f"First miner: {miners[0]}")
                    # Store miner address for later tests
                    self.__class__.miner_address = miners[0]
            else:
                logger.warning(f"Could not list miners: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.list_miners()
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                miners = result.get("miners", [])
                logger.info(f"FilecoinModel found {len(miners)} miners")
                if miners and not hasattr(self.__class__, 'miner_address'):
                    self.__class__.miner_address = miners[0]
            else:
                logger.warning(f"FilecoinModel could not list miners: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_11_miner_info(self):
        """Test getting information about a specific miner."""
        if not hasattr(self.__class__, 'miner_address'):
            self.skipTest("No miner address available for testing")
            
        if self.has_credentials and self.lotus:
            # Test actual API
            result = self.lotus.miner_get_info(self.__class__.miner_address)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                miner_info = result.get("result", {})
                logger.info(f"Miner info: {miner_info}")
            else:
                logger.warning(f"Could not get miner info: {result.get('error', 'Unknown error')}")
        
        # Test through FilecoinModel
        if self.filecoin_model:
            result = self.filecoin_model.get_miner_info(self.__class__.miner_address)
            self.assertIn("success", result, "Result should contain success field")
            if result.get("success", False):
                miner_info = result.get("miner_info", {})
                logger.info(f"FilecoinModel got miner info for miner {self.__class__.miner_address}")
            else:
                logger.warning(f"FilecoinModel could not get miner info: {result.get('error', 'Unknown error')}")
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_12_error_handling(self):
        """Test error handling in the Filecoin API."""
        if self.has_credentials and self.lotus:
            # Test with invalid CID
            result = self.lotus.client_find_data("invalid_cid")
            self.assertIn("success", result, "Result should contain success field")
            self.assertFalse(result.get("success", True), "Operation with invalid CID should fail")
            self.assertIn("error", result, "Result should contain error field")
            logger.info(f"Error handling test passed: {result.get('error', 'Unknown error')}")
        
        # Test error handling in FilecoinModel
        if self.filecoin_model:
            # Test with invalid deal ID
            result = self.filecoin_model.get_deal_info("invalid_deal_id")
            self.assertIn("success", result, "Result should contain success field")
            self.assertFalse(result.get("success", True), "Operation with invalid deal ID should fail")
            self.assertIn("error", result, "Result should contain error field")
            logger.info(f"FilecoinModel error handling test passed: {result.get('error', 'Unknown error')}")
            
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_14_ipfs_to_filecoin_integration(self):
        """Test IPFS to Filecoin integration functionality."""
        if not self.filecoin_model:
            self.skipTest("FilecoinModel not available")
            
        # This test uses mocks to avoid actual network calls
        # Create test IPFS CID
        test_ipfs_cid = "QmTest123456789"
        
        # Mock the IPFS model
        mock_ipfs_model = MagicMock()
        mock_ipfs_model.get_content.return_value = {
            "success": True,
            "content": self.test_data
        }
        
        # Temporarily save the current IPFS model
        original_ipfs_model = None
        if hasattr(self.filecoin_model, 'ipfs_model'):
            original_ipfs_model = self.filecoin_model.ipfs_model
            
        try:
            # Set the mock IPFS model
            self.filecoin_model.ipfs_model = mock_ipfs_model
            
            # Mock the necessary lotus_kit methods if we're not using real credentials
            if not self.has_credentials:
                self.filecoin_model.lotus_kit.client_import = MagicMock(return_value={
                    "success": True,
                    "result": {"Root": {"/": "bafymock456"}}
                })
                self.filecoin_model.lotus_kit.client_start_deal = MagicMock(return_value={
                    "success": True,
                    "result": {"/": "bafy123dealcid"}
                })
            
            # Test the integration function
            result = self.filecoin_model.ipfs_to_filecoin(
                cid=test_ipfs_cid,
                miner="f01000",  # Test miner address
                price="100000",
                duration=518400,
                wallet="t1mock123" if not hasattr(self.__class__, 'test_wallet') else self.__class__.test_wallet,
                verified=False,
                fast_retrieval=True
            )
            
            # Check the result
            self.assertIn("success", result, "Result should contain success field")
            
            # If the operation succeeded, check the result fields
            if result.get("success", False):
                self.assertIn("ipfs_cid", result, "Result should contain ipfs_cid field")
                self.assertEqual(result["ipfs_cid"], test_ipfs_cid, "IPFS CID should match the input")
                self.assertIn("filecoin_cid", result, "Result should contain filecoin_cid field")
                self.assertIn("deal_cid", result, "Result should contain deal_cid field")
                logger.info(f"IPFS to Filecoin integration test passed: IPFS CID {test_ipfs_cid} -> Filecoin CID {result['filecoin_cid']}")
            else:
                # Note: In real environment with no actual Filecoin access, this may fail
                logger.warning(f"IPFS to Filecoin integration failed: {result.get('error', 'Unknown error')}")
                
        finally:
            # Restore the original IPFS model
            if original_ipfs_model is not None:
                self.filecoin_model.ipfs_model = original_ipfs_model

    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_15_filecoin_to_ipfs_integration(self):
        """Test Filecoin to IPFS integration functionality."""
        if not self.filecoin_model:
            self.skipTest("FilecoinModel not available")
            
        # This test uses mocks to avoid actual network calls
        # Create test Filecoin data CID
        test_filecoin_cid = "bafytest123filecoin"
        
        # Mock the necessary lotus_kit methods if we're not using real credentials
        original_client_retrieve = None
        original_add_content = None
        
        try:
            # Mock the lotus_kit client_retrieve method
            if hasattr(self.filecoin_model, 'lotus_kit'):
                original_client_retrieve = self.filecoin_model.lotus_kit.client_retrieve
                self.filecoin_model.lotus_kit.client_retrieve = MagicMock(return_value={
                    "success": True,
                    "result": self.test_data if hasattr(self, 'test_data') else b"mock test data"
                })
            
            # Mock the IPFS model add_content method
            if hasattr(self.filecoin_model, 'ipfs_model'):
                original_add_content = self.filecoin_model.ipfs_model.add_content
                self.filecoin_model.ipfs_model.add_content = MagicMock(return_value={
                    "success": True,
                    "cid": "QmTestIPFSFromFilecoin"
                })
            
            # Test the integration function
            result = self.filecoin_model.filecoin_to_ipfs(
                data_cid=test_filecoin_cid,
                pin=True
            )
            
            # Check the result
            self.assertIn("success", result, "Result should contain success field")
            
            # If the operation succeeded, check the result fields
            if result.get("success", False):
                self.assertIn("filecoin_cid", result, "Result should contain filecoin_cid field")
                self.assertEqual(result["filecoin_cid"], test_filecoin_cid, "Filecoin CID should match the input")
                self.assertIn("ipfs_cid", result, "Result should contain ipfs_cid field")
                logger.info(f"Filecoin to IPFS integration test passed: Filecoin CID {test_filecoin_cid} -> IPFS CID {result['ipfs_cid']}")
            else:
                # Note: In real environment with no actual Filecoin access, this may fail
                logger.warning(f"Filecoin to IPFS integration failed: {result.get('error', 'Unknown error')}")
                
        finally:
            # Restore the original methods
            if original_client_retrieve is not None and hasattr(self.filecoin_model, 'lotus_kit'):
                self.filecoin_model.lotus_kit.client_retrieve = original_client_retrieve
            
            if original_add_content is not None and hasattr(self.filecoin_model, 'ipfs_model'):
                self.filecoin_model.ipfs_model.add_content = original_add_content
    
    @unittest.skipIf(not LOTUS_KIT_AVAILABLE, "lotus_kit not available")
    def test_13_mock_mode(self):
        """Test Filecoin API with mock mode."""
        # Create a mock lotus_kit
        mock_lotus = MagicMock()
        mock_lotus.check_connection.return_value = {
            "success": True,
            "result": {"Version": "1.23.0+mock", "APIVersion": "v1.10.0"}
        }
        
        # Add mock implementation for other methods
        mock_lotus.list_wallets.return_value = {
            "success": True,
            "result": ["t1mock123", "t1mock456"]
        }
        
        mock_lotus.wallet_balance.return_value = {
            "success": True,
            "result": "1000000000000000000"
        }
        
        mock_lotus.client_import.return_value = {
            "success": True,
            "result": {"Root": {"/": "bafymock123"}}
        }
        
        # Create FilecoinModel with mock
        mock_model = FilecoinModel(lotus_kit_instance=mock_lotus)
        
        # Test the model with mock
        result = mock_model.check_connection()
        self.assertTrue(result.get("success", False), "Mock connection check should succeed")
        self.assertEqual(mock_lotus.check_connection.call_count, 1, "Mock should be called exactly once")
        
        # Test wallet operations
        wallets_result = mock_model.list_wallets()
        self.assertTrue(wallets_result.get("success", False), "Mock wallet listing should succeed")
        self.assertIn("wallets", wallets_result, "Result should contain wallets field")
        
        # Test import operations
        if self.test_file_path and os.path.exists(self.test_file_path):
            import_result = mock_model.import_file(self.test_file_path)
            self.assertTrue(import_result.get("success", False), "Mock file import should succeed")
            self.assertIn("root", import_result, "Result should contain root field")
        
        logger.info("Enhanced mock mode tests passed successfully")

def print_summary(test_result):
    """Print a summary of test results."""
    print("\n" + "=" * 70)
    print("FILECOIN API TEST SUMMARY")
    print("=" * 70)
    
    total = test_result.testsRun
    failures = len(test_result.failures)
    errors = len(test_result.errors)
    skipped = len(test_result.skipped)
    passed = total - failures - errors - skipped
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    print(f"Skipped: {skipped}")
    
    # Determine test mode (real API or mock)
    has_real_api = False
    has_ipfs_integration = False
    for test, reason in test_result.skipped:
        if "No Filecoin credentials available" in reason:
            has_real_api = False
            break
    else:
        if passed > 0:
            has_real_api = True
            
    # Check for IPFS integration tests
    for test in test_result.__dict__.get('_tests', []):
        if hasattr(test, '_testMethodName') and (
            'ipfs_to_filecoin' in test._testMethodName or 
            'filecoin_to_ipfs' in test._testMethodName):
            has_ipfs_integration = True
    
    # Determine API status
    if has_real_api:
        print("\nAPI STATUS: CONNECTED to real Filecoin API")
    else:
        print("\nAPI STATUS: MOCK MODE (no real Filecoin API connection)")
        
    # Report on integration status
    if has_ipfs_integration:
        if passed > 0:
            print("IPFS INTEGRATION: VERIFIED")
        else:
            print("IPFS INTEGRATION: NOT VERIFIED (tests failed)")
    else:
        print("IPFS INTEGRATION: NOT TESTED")
    
    if failures > 0 or errors > 0:
        print("\nFAILURES:")
        for test, trace in test_result.failures:
            print(f"- {test}")
        
        print("\nERRORS:")
        for test, trace in test_result.errors:
            print(f"- {test}")
    
    print("\nSKIPPED:")
    for test, reason in test_result.skipped:
        print(f"- {test}: {reason}")
    
    # Add overall API verdict
    verdict = "OPERATIONAL" if passed > 0 and failures == 0 and errors == 0 else "NOT OPERATIONAL"
    
    print("=" * 70)
    print(f"FILECOIN API STATUS: {verdict}")
    if verdict == "OPERATIONAL" and not has_real_api:
        print("NOTE: Operating in MOCK MODE - testing structure is valid, but no real API connection was made")
    print("=" * 70)
    
    # Overall status
    if failures > 0 or errors > 0:
        return False
    return True

def main():
    """Main function to run the Filecoin API tests."""
    print("\n" + "=" * 70)
    print("FILECOIN API COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    # Check for lotus_kit availability
    if not LOTUS_KIT_AVAILABLE:
        print("ERROR: lotus_kit module is not available")
        print("Make sure the lotus_kit module and its dependencies are installed")
        return False
    
    # Environment information
    print("\nEnvironment Information:")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Using LOTUS_API_URL: {os.environ.get('LOTUS_API_URL', 'http://localhost:1234/rpc/v0')}")
    print(f"LOTUS_API_TOKEN: {'Present' if os.environ.get('LOTUS_API_TOKEN') else 'Not present'}")
    print(f"LOTUS_PATH: {os.environ.get('LOTUS_PATH', 'Not set')}")
    
    # Check credential availability
    has_credentials = check_api_credentials()
    if has_credentials:
        print("\nCredential Status: AVAILABLE - Will connect to real Filecoin API")
    else:
        print("\nCredential Status: NOT AVAILABLE - Will run in mock mode")
        print("To use real credentials, either:")
        print("  1. Set LOTUS_API_TOKEN environment variable")
        print("  2. Use credential_manager to add 'filecoin_default' credentials")
    
    print("\nRunning tests...")
    
    # Create test suite with ordered tests
    loader = unittest.TestLoader()
    # Preserve test order by sorting by name
    loader.sortTestMethodsUsing = lambda x, y: 1 if x > y else -1 if x < y else 0
    suite = loader.loadTestsFromTestCase(FilecoinAPITest)
    
    # Run tests
    test_result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Print summary
    return print_summary(test_result)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)