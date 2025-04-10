"""
Test module for FilecoinModel in MCP server.

This module tests the FilecoinModel class that provides business logic for Filecoin (Lotus) operations.
"""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel


class TestFilecoinModel(unittest.TestCase):
    """Test cases for FilecoinModel."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_lotus_kit = MagicMock()
        self.mock_ipfs_model = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()
        
        # Configure credential manager to return test credentials
        self.mock_credential_manager.get_credentials.return_value = {
            "token": "test-token",
            "address": "f1test123"
        }
        
        # Create FilecoinModel instance with mock dependencies
        self.filecoin_model = FilecoinModel(
            lotus_kit_instance=self.mock_lotus_kit,
            ipfs_model=self.mock_ipfs_model,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a test file
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for Filecoin import")
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test FilecoinModel initialization."""
        # Check that dependencies are properly stored
        self.assertEqual(self.filecoin_model.kit, self.mock_lotus_kit)
        self.assertEqual(self.filecoin_model.ipfs_model, self.mock_ipfs_model)
        self.assertEqual(self.filecoin_model.cache_manager, self.mock_cache_manager)
        self.assertEqual(self.filecoin_model.credential_manager, self.mock_credential_manager)
        
        # Check that backend name is correct
        self.assertEqual(self.filecoin_model.backend_name, "Filecoin")
        
        # Check that operation_stats is initialized
        self.assertIsNotNone(self.filecoin_model.operation_stats)
        self.assertEqual(self.filecoin_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["download_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["delete_count"], 0)
    
    def test_check_connection_success(self):
        """Test successful connection check."""
        # Configure mock response
        self.mock_lotus_kit.check_connection.return_value = {
            "success": True,
            "result": "1.19.1+calibnet"
        }
        
        # Check connection
        result = self.filecoin_model.check_connection()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["version"], "1.19.1+calibnet")
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called
        self.mock_lotus_kit.check_connection.assert_called_once()
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_check_connection_error(self):
        """Test connection check with error."""
        # Configure mock response with error
        self.mock_lotus_kit.check_connection.return_value = {
            "success": False,
            "error": "Failed to connect to Lotus daemon",
            "error_type": "ConnectionError"
        }
        
        # Check connection
        result = self.filecoin_model.check_connection()
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ConnectionError")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["failure_count"], 1)
    
    def test_list_wallets_success(self):
        """Test successful listing of wallets."""
        # Configure mock response
        self.mock_lotus_kit.list_wallets.return_value = {
            "success": True,
            "result": [
                "f1test123",
                "f1test456"
            ]
        }
        
        # List wallets
        result = self.filecoin_model.list_wallets()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["wallets"]), 2)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called
        self.mock_lotus_kit.list_wallets.assert_called_once()
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_list_wallets_error(self):
        """Test listing wallets with error."""
        # Configure mock response with error
        self.mock_lotus_kit.list_wallets.return_value = {
            "success": False,
            "error": "Failed to list wallets",
            "error_type": "WalletListError"
        }
        
        # List wallets
        result = self.filecoin_model.list_wallets()
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "WalletListError")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["failure_count"], 1)
    
    def test_get_wallet_balance_success(self):
        """Test successful wallet balance check."""
        # Configure mock response
        self.mock_lotus_kit.wallet_balance.return_value = {
            "success": True,
            "result": "10000000000000000000"
        }
        
        # Get wallet balance
        result = self.filecoin_model.get_wallet_balance("f1test123")
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["address"], "f1test123")
        self.assertEqual(result["balance"], "10000000000000000000")
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.wallet_balance.assert_called_once_with("f1test123")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_get_wallet_balance_validation_error(self):
        """Test wallet balance check with validation error."""
        # Test with empty address
        result = self.filecoin_model.get_wallet_balance("")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_create_wallet_success(self):
        """Test successful wallet creation."""
        # Configure mock response
        self.mock_lotus_kit.create_wallet.return_value = {
            "success": True,
            "result": "f1test789"
        }
        
        # Create wallet
        result = self.filecoin_model.create_wallet(wallet_type="bls")
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["address"], "f1test789")
        self.assertEqual(result["wallet_type"], "bls")
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.create_wallet.assert_called_once_with("bls")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["create_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_create_wallet_validation_error(self):
        """Test wallet creation with validation error."""
        # Test with invalid wallet type
        result = self.filecoin_model.create_wallet(wallet_type="invalid_type")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_import_file_success(self):
        """Test successful file import."""
        # Configure mock response
        self.mock_lotus_kit.client_import.return_value = {
            "success": True,
            "result": {
                "Root": {
                    "/": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
                },
                "ImportID": 12345,
                "Size": 100,
                "Status": "Importing"
            }
        }
        
        # Import file
        result = self.filecoin_model.import_file(self.test_file_path)
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["root"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(result["file_path"], self.test_file_path)
        self.assertEqual(result["importid"], 12345)
        self.assertEqual(result["status"], "Importing")
        self.assertIn("size_bytes", result)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.client_import.assert_called_once_with(self.test_file_path)
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_import_file_validation_error(self):
        """Test file import with validation error."""
        # Test with non-existent file
        result = self.filecoin_model.import_file("/non/existent/file.txt")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "FileNotFoundError")
    
    def test_list_imports_success(self):
        """Test successful listing of imports."""
        # Configure mock response
        self.mock_lotus_kit.client_list_imports.return_value = {
            "success": True,
            "result": [
                {
                    "Key": 1,
                    "Root": {
                        "/": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"
                    },
                    "Source": "import1.txt",
                    "FilePath": "/path/to/import1.txt",
                    "Size": 100
                },
                {
                    "Key": 2,
                    "Root": {
                        "/": "bafk2bzaceduagzgkqswfl32ycl7yofkweru2a63jvkkszp3xuinhna6l3dq2"
                    },
                    "Source": "import2.txt",
                    "FilePath": "/path/to/import2.txt",
                    "Size": 200
                }
            ]
        }
        
        # List imports
        result = self.filecoin_model.list_imports()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["imports"]), 2)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called
        self.mock_lotus_kit.client_list_imports.assert_called_once()
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_find_data_success(self):
        """Test successful data location lookup."""
        # Configure mock response
        self.mock_lotus_kit.client_find_data.return_value = {
            "success": True,
            "result": [
                {
                    "Miner": "f01000",
                    "Status": "Active",
                    "PieceCid": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                },
                {
                    "Miner": "f01001",
                    "Status": "Active",
                    "PieceCid": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                }
            ]
        }
        
        # Find data
        result = self.filecoin_model.find_data("bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["locations"]), 2)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.client_find_data.assert_called_once_with("bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_find_data_validation_error(self):
        """Test data location lookup with validation error."""
        # Test with empty CID
        result = self.filecoin_model.find_data("")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_list_deals_success(self):
        """Test successful listing of deals."""
        # Configure mock response
        self.mock_lotus_kit.client_list_deals.return_value = {
            "success": True,
            "result": [
                {
                    "DealID": 1,
                    "Provider": "f01000",
                    "State": 7,
                    "ClientDealProposal": {
                        "Proposal": {
                            "PieceCID": {
                                "/": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                            },
                            "Client": "f1test123",
                            "Provider": "f01000",
                            "StartEpoch": 100000,
                            "EndEpoch": 200000,
                            "StoragePricePerEpoch": "1000000000",
                            "ProviderCollateral": "1000000000000",
                            "ClientCollateral": "1000000000000"
                        }
                    }
                },
                {
                    "DealID": 2,
                    "Provider": "f01001",
                    "State": 5,
                    "ClientDealProposal": {
                        "Proposal": {
                            "PieceCID": {
                                "/": "baga6ea4seaqas5frgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                            },
                            "Client": "f1test123",
                            "Provider": "f01001",
                            "StartEpoch": 100000,
                            "EndEpoch": 200000,
                            "StoragePricePerEpoch": "1000000000",
                            "ProviderCollateral": "1000000000000",
                            "ClientCollateral": "1000000000000"
                        }
                    }
                }
            ]
        }
        
        # List deals
        result = self.filecoin_model.list_deals()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["deals"]), 2)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called
        self.mock_lotus_kit.client_list_deals.assert_called_once()
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_get_deal_info_success(self):
        """Test successful deal info retrieval."""
        # Configure mock response
        self.mock_lotus_kit.client_deal_info.return_value = {
            "success": True,
            "result": {
                "DealID": 1,
                "Provider": "f01000",
                "State": 7,
                "ClientDealProposal": {
                    "Proposal": {
                        "PieceCID": {
                            "/": "baga6ea4seaqntdmgrqcgbaanqpdf2kzfrgyunikuwh6ccnwlkdnfk7yzvv7sgni"
                        },
                        "Client": "f1test123",
                        "Provider": "f01000",
                        "StartEpoch": 100000,
                        "EndEpoch": 200000,
                        "StoragePricePerEpoch": "1000000000",
                        "ProviderCollateral": "1000000000000",
                        "ClientCollateral": "1000000000000"
                    }
                }
            }
        }
        
        # Get deal info
        result = self.filecoin_model.get_deal_info(1)
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["deal_id"], 1)
        self.assertIn("deal_info", result)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.client_deal_info.assert_called_once_with(1)
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_get_deal_info_validation_error(self):
        """Test deal info retrieval with validation error."""
        # Test with non-integer deal ID
        result = self.filecoin_model.get_deal_info("not-an-integer")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_start_deal_success(self):
        """Test successful deal creation."""
        # Configure mock response
        self.mock_lotus_kit.client_start_deal.return_value = {
            "success": True,
            "result": {
                "/": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4"
            }
        }
        
        # Start deal
        result = self.filecoin_model.start_deal(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True
        )
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["deal_cid"], "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4")
        self.assertEqual(result["data_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(result["miner"], "f01000")
        self.assertEqual(result["price"], "1000000000")
        self.assertEqual(result["duration"], 100000)
        self.assertEqual(result["wallet"], "f1test123")
        self.assertTrue(result["verified"])
        self.assertTrue(result["fast_retrieval"])
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.client_start_deal.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True
        )
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["create_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_start_deal_validation_error(self):
        """Test deal creation with validation error."""
        # Test with missing required parameters
        result = self.filecoin_model.start_deal(
            data_cid="",
            miner="f01000",
            price="1000000000",
            duration=100000
        )
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_retrieve_data_success(self):
        """Test successful data retrieval."""
        # Configure mock response
        self.mock_lotus_kit.client_retrieve.return_value = {
            "success": True,
            "result": {
                "DealID": 1,
                "Size": 1000,
                "Status": "Retrieved"
            }
        }
        
        # Set up mock for os.path.getsize
        with patch('os.path.getsize', return_value=1000):
            # Retrieve data
            result = self.filecoin_model.retrieve_data(
                data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                out_file="/tmp/test_output.txt"
            )
            
            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
            self.assertEqual(result["file_path"], "/tmp/test_output.txt")
            self.assertEqual(result["size_bytes"], 1000)
            self.assertIn("duration_ms", result)
            
            # Check that lotus_kit was called with correct parameters
            self.mock_lotus_kit.client_retrieve.assert_called_once_with(
                "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                "/tmp/test_output.txt"
            )
            
            # Check that operation stats were updated
            self.assertEqual(self.filecoin_model.operation_stats["download_count"], 1)
            self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_retrieve_data_validation_error(self):
        """Test data retrieval with validation error."""
        # Test with missing required parameters
        result = self.filecoin_model.retrieve_data(
            data_cid="",
            out_file="/tmp/test_output.txt"
        )
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_list_miners_success(self):
        """Test successful miner listing."""
        # Configure mock response
        self.mock_lotus_kit.list_miners.return_value = {
            "success": True,
            "result": [
                "f01000",
                "f01001",
                "f01002"
            ]
        }
        
        # List miners
        result = self.filecoin_model.list_miners()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["miners"]), 3)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called
        self.mock_lotus_kit.list_miners.assert_called_once()
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_get_miner_info_success(self):
        """Test successful miner info retrieval."""
        # Configure mock response
        self.mock_lotus_kit.miner_get_info.return_value = {
            "success": True,
            "result": {
                "MinerAddress": "f01000",
                "SectorSize": 34359738368,
                "Multiaddrs": [
                    "/ip4/10.0.0.1/tcp/1234"
                ],
                "PeerID": "12D3KooWJvW4tVa7A1huRyuLivLzS64KndQgYYEir233uJrExHTF"
            }
        }
        
        # Get miner info
        result = self.filecoin_model.get_miner_info("f01000")
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["miner_address"], "f01000")
        self.assertIn("miner_info", result)
        self.assertIn("duration_ms", result)
        
        # Check that lotus_kit was called with correct parameters
        self.mock_lotus_kit.miner_get_info.assert_called_once_with("f01000")
        
        # Check that operation stats were updated
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 1)
        self.assertEqual(self.filecoin_model.operation_stats["success_count"], 1)
    
    def test_get_miner_info_validation_error(self):
        """Test miner info retrieval with validation error."""
        # Test with empty miner address
        result = self.filecoin_model.get_miner_info("")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_filecoin_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from IPFS to Filecoin."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file
        
        # Configure mock IPFS model
        self.mock_ipfs_model.get_content.return_value = {
            "success": True,
            "data": b"Test content from IPFS",
            "cid": "QmTestCid"
        }
        self.mock_ipfs_model.pin_content.return_value = {
            "success": True,
            "cid": "QmTestCid"
        }
        
        # Mock the import_file and start_deal methods
        with patch.object(self.filecoin_model, "import_file") as mock_import:
            mock_import.return_value = {
                "success": True,
                "root": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                "size_bytes": 100
            }
            
            with patch.object(self.filecoin_model, "start_deal") as mock_start_deal:
                mock_start_deal.return_value = {
                    "success": True,
                    "deal_cid": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4"
                }
                
                # Transfer from IPFS to Filecoin
                result = self.filecoin_model.ipfs_to_filecoin(
                    cid="QmTestCid",
                    miner="f01000",
                    price="1000000000",
                    duration=100000,
                    wallet="f1test123",
                    verified=True,
                    fast_retrieval=True,
                    pin=True
                )
                
                # Check result
                self.assertTrue(result["success"])
                self.assertEqual(result["ipfs_cid"], "QmTestCid")
                self.assertEqual(result["filecoin_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
                self.assertEqual(result["deal_cid"], "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4")
                self.assertEqual(result["miner"], "f01000")
                self.assertEqual(result["price"], "1000000000")
                self.assertEqual(result["duration"], 100000)
                self.assertIn("size_bytes", result)
                self.assertIn("duration_ms", result)
                
                # Check that IPFS model was called
                self.mock_ipfs_model.get_content.assert_called_once_with("QmTestCid")
                self.mock_ipfs_model.pin_content.assert_called_once_with("QmTestCid")
                
                # Check that import_file was called with correct parameters
                mock_import.assert_called_once_with(mock_temp_file.name)
                
                # Check that start_deal was called with correct parameters
                mock_start_deal.assert_called_once_with(
                    data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                    miner="f01000",
                    price="1000000000",
                    duration=100000,
                    wallet="f1test123",
                    verified=True,
                    fast_retrieval=True
                )
                
                # Check that temporary file was cleaned up
                mock_unlink.assert_called_once_with(mock_temp_file.name)
    
    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_filecoin_ipfs_error(self, mock_unlink, mock_named_temp_file):
        """Test IPFS to Filecoin transfer with IPFS error."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file
        
        # Configure mock IPFS model to return error
        self.mock_ipfs_model.get_content.return_value = {
            "success": False,
            "error": "IPFS get failed",
            "error_type": "IPFSGetError"
        }
        
        # Transfer from IPFS to Filecoin
        result = self.filecoin_model.ipfs_to_filecoin(
            cid="QmTestCid",
            miner="f01000",
            price="1000000000",
            duration=100000
        )
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "IPFSGetError")
        self.assertIn("ipfs_result", result)
        
        # Check that temporary file was cleaned up
        mock_unlink.assert_called_once_with(mock_temp_file.name)
    
    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_filecoin_to_ipfs_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from Filecoin to IPFS."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file
        
        # Mock the retrieve_data method
        with patch.object(self.filecoin_model, "retrieve_data") as mock_retrieve:
            mock_retrieve.return_value = {
                "success": True,
                "cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                "file_path": mock_temp_file.name,
                "size_bytes": 100
            }
            
            # Mock file open and read
            mock_file_content = b"Test content from Filecoin"
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = mock_file_content
            mock_open = MagicMock(return_value=mock_file)
            
            # Configure mock IPFS model
            self.mock_ipfs_model.add_content.return_value = {
                "success": True,
                "cid": "QmNewTestCid"
            }
            self.mock_ipfs_model.pin_content.return_value = {
                "success": True,
                "cid": "QmNewTestCid"
            }
            
            with patch("builtins.open", mock_open):
                # Transfer from Filecoin to IPFS
                result = self.filecoin_model.filecoin_to_ipfs(
                    data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                    pin=True
                )
                
                # Check result
                self.assertTrue(result["success"])
                self.assertEqual(result["filecoin_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
                self.assertEqual(result["ipfs_cid"], "QmNewTestCid")
                self.assertIn("size_bytes", result)
                self.assertIn("duration_ms", result)
                
                # Check that retrieve_data was called with correct parameters
                mock_retrieve.assert_called_once_with(
                    "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
                    mock_temp_file.name
                )
                
                # Check that IPFS model was called with correct parameters
                self.mock_ipfs_model.add_content.assert_called_once_with(mock_file_content)
                self.mock_ipfs_model.pin_content.assert_called_once_with("QmNewTestCid")
                
                # Check that file was read and temporary file was cleaned up
                mock_open.assert_called_once_with(mock_temp_file.name, "rb")
                mock_unlink.assert_called_once_with(mock_temp_file.name)
    
    def test_filecoin_to_ipfs_validation_error(self):
        """Test Filecoin to IPFS transfer with validation error."""
        # Test with empty CID
        result = self.filecoin_model.filecoin_to_ipfs("")
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")
    
    def test_get_stats(self):
        """Test getting operation statistics."""
        # Perform some operations to update stats
        self.filecoin_model.operation_stats["upload_count"] = 5
        self.filecoin_model.operation_stats["download_count"] = 3
        self.filecoin_model.operation_stats["list_count"] = 2
        self.filecoin_model.operation_stats["delete_count"] = 1
        self.filecoin_model.operation_stats["success_count"] = 10
        self.filecoin_model.operation_stats["failure_count"] = 1
        self.filecoin_model.operation_stats["bytes_uploaded"] = 5000
        self.filecoin_model.operation_stats["bytes_downloaded"] = 3000
        
        # Get stats
        stats = self.filecoin_model.get_stats()
        
        # Check stats
        self.assertEqual(stats["backend_name"], "Filecoin")
        self.assertEqual(stats["operation_stats"]["upload_count"], 5)
        self.assertEqual(stats["operation_stats"]["download_count"], 3)
        self.assertEqual(stats["operation_stats"]["list_count"], 2)
        self.assertEqual(stats["operation_stats"]["delete_count"], 1)
        self.assertEqual(stats["operation_stats"]["success_count"], 10)
        self.assertEqual(stats["operation_stats"]["failure_count"], 1)
        self.assertEqual(stats["operation_stats"]["bytes_uploaded"], 5000)
        self.assertEqual(stats["operation_stats"]["bytes_downloaded"], 3000)
        self.assertIn("timestamp", stats)
        self.assertIn("uptime_seconds", stats)
    
    def test_reset_stats(self):
        """Test resetting operation statistics."""
        # Perform some operations to update stats
        self.filecoin_model.operation_stats["upload_count"] = 5
        self.filecoin_model.operation_stats["download_count"] = 3
        self.filecoin_model.operation_stats["list_count"] = 2
        self.filecoin_model.operation_stats["delete_count"] = 1
        
        # Reset stats
        result = self.filecoin_model.reset()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "reset_stats")
        self.assertEqual(result["backend_name"], "Filecoin")
        
        # Check that previous stats are included
        self.assertEqual(result["previous_stats"]["upload_count"], 5)
        self.assertEqual(result["previous_stats"]["download_count"], 3)
        self.assertEqual(result["previous_stats"]["list_count"], 2)
        self.assertEqual(result["previous_stats"]["delete_count"], 1)
        
        # Check that stats were reset
        self.assertEqual(self.filecoin_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["download_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["list_count"], 0)
        self.assertEqual(self.filecoin_model.operation_stats["delete_count"], 0)
    
    def test_health_check(self):
        """Test health check functionality."""
        # Run health check
        result = self.filecoin_model.health_check()
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "Filecoin")
        self.assertTrue(result["kit_available"])
        self.assertTrue(result["cache_available"])
        self.assertTrue(result["credential_available"])
        self.assertIn("duration_ms", result)
    
    def test_health_check_no_dependencies(self):
        """Test health check with missing dependencies."""
        # Create model with no dependencies
        model = FilecoinModel()
        
        # Run health check
        result = model.health_check()
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "Filecoin")
        self.assertFalse(result["kit_available"])
        self.assertFalse(result["cache_available"])
        self.assertFalse(result["credential_available"])


if __name__ == "__main__":
    unittest.main()