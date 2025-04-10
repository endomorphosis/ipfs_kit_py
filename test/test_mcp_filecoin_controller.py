"""
Test module for FilecoinController in MCP server.

This module tests the FilecoinController class that handles HTTP endpoints for Filecoin operations.
"""

import os
import tempfile
import json
import unittest
from unittest.mock import MagicMock, patch
from io import BytesIO

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient


class TestFilecoinController(unittest.TestCase):
    """Test cases for FilecoinController."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock Filecoin model
        self.mock_filecoin_model = MagicMock()
        
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
        
        # Create FilecoinController with mock model
        self.controller = FilecoinController(self.mock_filecoin_model)
        
        # Create FastAPI router and register routes
        self.router = APIRouter()
        self.controller.register_routes(self.router)
        
        # Create test app with router
        from fastapi import FastAPI
        self.app = FastAPI()
        self.app.include_router(self.router)
        
        # Create test client
        self.client = TestClient(self.app)
        
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
        """Test FilecoinController initialization."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
        
        # Create a new controller with mock model
        controller = FilecoinController(self.mock_filecoin_model)
        
        # Check that model is properly stored
        self.assertEqual(controller.filecoin_model, self.mock_filecoin_model)
    
    def test_route_registration(self):
        """Test that routes are registered correctly."""
        # Check that routes are registered
        route_paths = [route.path for route in self.router.routes]
        
        # Check core routes
        self.assertIn("/filecoin/status", route_paths)
        self.assertIn("/filecoin/wallets", route_paths)
        self.assertIn("/filecoin/wallet/balance/{address}", route_paths)
        self.assertIn("/filecoin/wallet/create", route_paths)
        self.assertIn("/filecoin/import", route_paths)
        self.assertIn("/filecoin/imports", route_paths)
        self.assertIn("/filecoin/deals", route_paths)
        self.assertIn("/filecoin/deal/{deal_id}", route_paths)
        self.assertIn("/filecoin/deal/start", route_paths)
        self.assertIn("/filecoin/retrieve", route_paths)
        self.assertIn("/filecoin/miners", route_paths)
        self.assertIn("/filecoin/miner/info", route_paths)
        self.assertIn("/filecoin/from_ipfs", route_paths)
        self.assertIn("/filecoin/to_ipfs", route_paths)
    
    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_filecoin_model.check_connection.return_value = {
            "success": True,
            "connected": True,
            "version": "1.19.1+calibnet",
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["backend"], "filecoin")
        self.assertTrue(response_data["is_available"])
        self.assertTrue(response_data["connected"])
        self.assertEqual(response_data["version"], "1.19.1+calibnet")
        
        # Check that model was called
        self.mock_filecoin_model.check_connection.assert_called_once()
    
    def test_handle_status_request_error(self):
        """Test handling status request with error."""
        # Configure mock response
        self.mock_filecoin_model.check_connection.return_value = {
            "success": False,
            "error": "Failed to connect to Lotus API",
            "error_type": "ConnectionError",
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])  # Overall operation success
        self.assertEqual(response_data["backend"], "filecoin")
        self.assertFalse(response_data["is_available"])
        self.assertEqual(response_data["error"], "Failed to connect to Lotus API")
        
        # Check that model was called
        self.mock_filecoin_model.check_connection.assert_called_once()
    
    def test_handle_list_wallets_request(self):
        """Test handling list wallets request."""
        # Configure mock response
        self.mock_filecoin_model.list_wallets.return_value = {
            "success": True,
            "wallets": ["f1test123", "f1test456"],
            "count": 2,
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/wallets")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["wallets"], ["f1test123", "f1test456"])
        self.assertEqual(response_data["count"], 2)
        
        # Check that model was called
        self.mock_filecoin_model.list_wallets.assert_called_once()
    
    def test_handle_wallet_balance_request(self):
        """Test handling wallet balance request."""
        # Configure mock response
        self.mock_filecoin_model.get_wallet_balance.return_value = {
            "success": True,
            "address": "f1test123",
            "balance": "10000000000000000000",
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/wallet/balance/f1test123")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["address"], "f1test123")
        self.assertEqual(response_data["balance"], "10000000000000000000")
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.get_wallet_balance.assert_called_once_with("f1test123")
    
    def test_handle_create_wallet_request(self):
        """Test handling create wallet request."""
        # Configure mock response
        self.mock_filecoin_model.create_wallet.return_value = {
            "success": True,
            "address": "f1test789",
            "wallet_type": "bls",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "wallet_type": "bls"
        }
        
        # Send request
        response = self.client.post("/filecoin/wallet/create", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["address"], "f1test789")
        self.assertEqual(response_data["wallet_type"], "bls")
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.create_wallet.assert_called_once_with(wallet_type="bls")
    
    def test_handle_import_file_request(self):
        """Test handling import file request."""
        # Configure mock response
        self.mock_filecoin_model.import_file.return_value = {
            "success": True,
            "root": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "file_path": self.test_file_path,
            "importid": 12345,
            "status": "Importing",
            "size_bytes": 100,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "file_path": self.test_file_path
        }
        
        # Send request
        response = self.client.post("/filecoin/import", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["root"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(response_data["file_path"], self.test_file_path)
        self.assertEqual(response_data["size_bytes"], 100)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.import_file.assert_called_once_with(file_path=self.test_file_path)
    
    def test_handle_list_imports_request(self):
        """Test handling list imports request."""
        # Configure mock response
        mock_imports = [
            {
                "Key": 1,
                "Root": {"/" : "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"},
                "Source": "import1.txt",
                "FilePath": "/path/to/import1.txt",
                "Size": 100
            },
            {
                "Key": 2,
                "Root": {"/" : "bafk2bzaceduagzgkqswfl32ycl7yofkweru2a63jvkkszp3xuinhna6l3dq2"},
                "Source": "import2.txt",
                "FilePath": "/path/to/import2.txt",
                "Size": 200
            }
        ]
        self.mock_filecoin_model.list_imports.return_value = {
            "success": True,
            "imports": mock_imports,
            "count": 2,
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/imports")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["count"], 2)
        self.assertEqual(len(response_data["imports"]), 2)
        
        # Check that model was called
        self.mock_filecoin_model.list_imports.assert_called_once()
    
    def test_handle_list_deals_request(self):
        """Test handling list deals request."""
        # Configure mock response
        mock_deals = [
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
        self.mock_filecoin_model.list_deals.return_value = {
            "success": True,
            "deals": mock_deals,
            "count": 2,
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/deals")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["count"], 2)
        self.assertEqual(len(response_data["deals"]), 2)
        
        # Check that model was called
        self.mock_filecoin_model.list_deals.assert_called_once()
    
    def test_handle_deal_info_request(self):
        """Test handling deal info request."""
        # Configure mock response
        mock_deal_info = {
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
        self.mock_filecoin_model.get_deal_info.return_value = {
            "success": True,
            "deal_id": 1,
            "deal_info": mock_deal_info,
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/deal/1")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["deal_id"], 1)
        self.assertEqual(response_data["deal_info"], mock_deal_info)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.get_deal_info.assert_called_once_with(1)
    
    def test_handle_start_deal_request(self):
        """Test handling start deal request."""
        # Configure mock response
        self.mock_filecoin_model.start_deal.return_value = {
            "success": True,
            "deal_cid": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4",
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True
        }
        
        # Send request
        response = self.client.post("/filecoin/deal/start", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["deal_cid"], "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4")
        self.assertEqual(response_data["data_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(response_data["miner"], "f01000")
        self.assertEqual(response_data["price"], "1000000000")
        self.assertEqual(response_data["duration"], 100000)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.start_deal.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True
        )
    
    def test_handle_retrieve_data_request(self):
        """Test handling retrieve data request."""
        # Configure mock response
        self.mock_filecoin_model.retrieve_data.return_value = {
            "success": True,
            "cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "file_path": "/tmp/test_output.txt",
            "size_bytes": 1000,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "out_file": "/tmp/test_output.txt"
        }
        
        # Send request
        response = self.client.post("/filecoin/retrieve", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(response_data["file_path"], "/tmp/test_output.txt")
        self.assertEqual(response_data["size_bytes"], 1000)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.retrieve_data.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            out_file="/tmp/test_output.txt"
        )
    
    def test_handle_list_miners_request(self):
        """Test handling list miners request."""
        # Configure mock response
        self.mock_filecoin_model.list_miners.return_value = {
            "success": True,
            "miners": ["f01000", "f01001", "f01002"],
            "count": 3,
            "duration_ms": 50.5
        }
        
        # Send request
        response = self.client.get("/filecoin/miners")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["miners"], ["f01000", "f01001", "f01002"])
        self.assertEqual(response_data["count"], 3)
        
        # Check that model was called
        self.mock_filecoin_model.list_miners.assert_called_once()
    
    def test_handle_miner_info_request(self):
        """Test handling miner info request."""
        # Configure mock response
        mock_miner_info = {
            "MinerAddress": "f01000",
            "SectorSize": 34359738368,
            "Multiaddrs": ["/ip4/10.0.0.1/tcp/1234"],
            "PeerID": "12D3KooWJvW4tVa7A1huRyuLivLzS64KndQgYYEir233uJrExHTF"
        }
        self.mock_filecoin_model.get_miner_info.return_value = {
            "success": True,
            "miner_address": "f01000",
            "miner_info": mock_miner_info,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "miner_address": "f01000"
        }
        
        # Send request
        response = self.client.post("/filecoin/miner/info", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["miner_address"], "f01000")
        self.assertEqual(response_data["miner_info"], mock_miner_info)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.get_miner_info.assert_called_once_with(miner_address="f01000")
    
    def test_handle_ipfs_to_filecoin_request(self):
        """Test handling IPFS to Filecoin request."""
        # Configure mock response
        self.mock_filecoin_model.ipfs_to_filecoin.return_value = {
            "success": True,
            "ipfs_cid": "QmTestCid",
            "filecoin_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "deal_cid": "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "size_bytes": 100,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "cid": "QmTestCid",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000,
            "wallet": "f1test123",
            "verified": True,
            "fast_retrieval": True,
            "pin": True
        }
        
        # Send request
        response = self.client.post("/filecoin/from_ipfs", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["ipfs_cid"], "QmTestCid")
        self.assertEqual(response_data["filecoin_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(response_data["deal_cid"], "bafy2bzacea3wsdh6y3a36tb3skempjoxqpuyompjbmfeyf34fi3uy6uue42v4")
        self.assertEqual(response_data["miner"], "f01000")
        self.assertEqual(response_data["price"], "1000000000")
        self.assertEqual(response_data["duration"], 100000)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.ipfs_to_filecoin.assert_called_once_with(
            cid="QmTestCid",
            miner="f01000",
            price="1000000000",
            duration=100000,
            wallet="f1test123",
            verified=True,
            fast_retrieval=True,
            pin=True
        )
    
    def test_handle_filecoin_to_ipfs_request(self):
        """Test handling Filecoin to IPFS request."""
        # Configure mock response
        self.mock_filecoin_model.filecoin_to_ipfs.return_value = {
            "success": True,
            "filecoin_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "ipfs_cid": "QmNewTestCid",
            "size_bytes": 100,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "pin": True
        }
        
        # Send request
        response = self.client.post("/filecoin/to_ipfs", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["filecoin_cid"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(response_data["ipfs_cid"], "QmNewTestCid")
        self.assertEqual(response_data["size_bytes"], 100)
        
        # Check that model was called with correct parameters
        self.mock_filecoin_model.filecoin_to_ipfs.assert_called_once_with(
            data_cid="bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            pin=True
        )
    
    def test_handle_request_with_error(self):
        """Test handling a request that results in an error response."""
        # Configure mock to return error
        self.mock_filecoin_model.start_deal.return_value = {
            "success": False,
            "error": "Failed to start deal",
            "error_type": "StartDealError"
        }
        
        # Create request
        request_data = {
            "data_cid": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2",
            "miner": "f01000",
            "price": "1000000000",
            "duration": 100000
        }
        
        # Send request
        response = self.client.post("/filecoin/deal/start", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Failed to start deal")
        self.assertEqual(response_data["detail"]["error_type"], "StartDealError")
    
    def test_handle_validation_error(self):
        """Test handling a request that fails validation."""
        # Send request with missing required fields
        response = self.client.post("/filecoin/deal/start", json={})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        # Validation errors return detailed information about missing fields
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main()