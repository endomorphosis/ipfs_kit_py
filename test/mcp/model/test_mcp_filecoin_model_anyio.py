"""
Test module for FilecoinModelAnyIO.

This module contains tests for the FilecoinModelAnyIO class, which provides
asynchronous versions of the Filecoin operations for the MCP server.
"""

import unittest
import os
import tempfile
import anyio
import anyio
import warnings
from unittest.mock import patch, MagicMock, AsyncMock, call

from ipfs_kit_py.mcp.models.storage.filecoin_model_anyio import FilecoinModelAnyIO


class TestFilecoinModelAnyIO(unittest.TestCase):
    """Test class for FilecoinModelAnyIO."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_lotus_kit = MagicMock()
        self.mock_ipfs_model = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()
        
        # Create test instance
        self.filecoin_model = FilecoinModelAnyIO(
            lotus_kit_instance=self.mock_lotus_kit,
            ipfs_model=self.mock_ipfs_model,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )
        
        # Create a test file
        self.test_file_fd, self.test_file_path = tempfile.mkstemp()
        with os.fdopen(self.test_file_fd, 'w') as f:
            f.write("Test content")
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove test file
        try:
            os.unlink(self.test_file_path)
        except:
            pass
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.filecoin_model.kit, self.mock_lotus_kit)
        self.assertEqual(self.filecoin_model.ipfs_model, self.mock_ipfs_model)
        self.assertEqual(self.filecoin_model.cache_manager, self.mock_cache_manager)
        self.assertEqual(self.filecoin_model.credential_manager, self.mock_credential_manager)
    
    def test_get_backend(self):
        """Test get_backend method."""
        # Should return None when not in async context
        self.assertIsNone(self.filecoin_model.get_backend())
    
    def test_warn_if_async_context(self):
        """Test warning in sync methods from async context."""
        # Mock get_backend to simulate async context
        with patch.object(FilecoinModelAnyIO, 'get_backend', return_value='asyncio'):
            with warnings.catch_warnings(record=True) as w:
                # Call a sync method
                self.filecoin_model.check_connection()
                
                # Verify warning was issued
                self.assertEqual(len(w), 1)
                self.assertTrue(issubclass(w[0].category, Warning))
                self.assertIn('check_connection', str(w[0].message))
                self.assertIn('check_connection_async', str(w[0].message))
    
    async def _async_test_helper(self, coroutine, expected_result):
        """Helper to run async tests."""
        result = await coroutine
        # Only check the specific fields in expected_result, ignoring additional fields
        for key, value in expected_result.items():
            if key == "duration_ms":
                # Duration is variable, just check it exists
                self.assertIn(key, result)
                self.assertIsInstance(result[key], (int, float))
            else:
                self.assertIn(key, result)
                self.assertEqual(result[key], value)
    
    def test_async_check_connection(self):
        """Test check_connection_async method."""
        # Set up mock response
        self.mock_lotus_kit.check_connection.return_value = {
            "success": True,
            "result": "Lotus version 1.2.3"
        }
        
        # Run async test
        expected_result = {
            "success": True,
            "connected": True,
            "version": "Lotus version 1.2.3",
            "operation": "check_connection_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test using asyncio
        anyio.run(self._async_test_helper(
            self.filecoin_model.check_connection_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.check_connection.assert_called_once()
    
    def test_async_list_wallets(self):
        """Test list_wallets_async method."""
        # Set up mock response
        self.mock_lotus_kit.list_wallets.return_value = {
            "success": True,
            "result": ["wallet1", "wallet2"]
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "wallets": ["wallet1", "wallet2"],
            "count": 2,
            "operation": "list_wallets_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.list_wallets_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.list_wallets.assert_called_once()
    
    def test_async_get_wallet_balance(self):
        """Test get_wallet_balance_async method."""
        # Set up mock response
        self.mock_lotus_kit.wallet_balance.return_value = {
            "success": True,
            "result": "1000000000"
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "address": "wallet1",
            "balance": "1000000000",
            "operation": "get_wallet_balance_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.get_wallet_balance_async("wallet1"),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.wallet_balance.assert_called_once_with("wallet1")
    
    def test_async_create_wallet(self):
        """Test create_wallet_async method."""
        # Set up mock response
        self.mock_lotus_kit.create_wallet.return_value = {
            "success": True,
            "result": "new_wallet_address"
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "address": "new_wallet_address",
            "wallet_type": "bls",
            "operation": "create_wallet_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.create_wallet_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.create_wallet.assert_called_once_with("bls")
    
    def test_async_import_file(self):
        """Test import_file_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_import.return_value = {
            "success": True,
            "result": {
                "Root": {"/": "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2"},
                "ImportID": 12345,
                "Size": 100,
                "Status": "Importing"
            }
        }
        
        # Run the async test
        result = anyio.run(self.filecoin_model.import_file_async(self.test_file_path))
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["root"], "bafk2bzacecmhmnrk4v2tpspgp2fyryahqadek4k4fbfiupftkfv65yz7o5si2")
        self.assertEqual(result["importid"], 12345)
        self.assertEqual(result["status"], "Importing")
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.client_import.assert_called_once_with(self.test_file_path)
    
    def test_async_list_imports(self):
        """Test list_imports_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_list_imports.return_value = {
            "success": True,
            "result": [
                {"ImportID": 1, "Status": "Complete"},
                {"ImportID": 2, "Status": "Importing"}
            ]
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "imports": [
                {"ImportID": 1, "Status": "Complete"},
                {"ImportID": 2, "Status": "Importing"}
            ],
            "count": 2,
            "operation": "list_imports_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.list_imports_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.client_list_imports.assert_called_once()
    
    def test_async_find_data(self):
        """Test find_data_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_find_data.return_value = {
            "success": True,
            "result": [
                {"Location": "local", "Status": "Active"},
                {"Location": "miner1", "Status": "Sealed"}
            ]
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "cid": "testcid",
            "locations": [
                {"Location": "local", "Status": "Active"},
                {"Location": "miner1", "Status": "Sealed"}
            ],
            "count": 2,
            "operation": "find_data_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.find_data_async("testcid"),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.client_find_data.assert_called_once_with("testcid")
    
    def test_async_list_deals(self):
        """Test list_deals_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_list_deals.return_value = {
            "success": True,
            "result": [
                {"DealID": 1, "State": "Active"},
                {"DealID": 2, "State": "Proposed"}
            ]
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "deals": [
                {"DealID": 1, "State": "Active"},
                {"DealID": 2, "State": "Proposed"}
            ],
            "count": 2,
            "operation": "list_deals_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.list_deals_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.client_list_deals.assert_called_once()
    
    def test_async_get_deal_info(self):
        """Test get_deal_info_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_deal_info.return_value = {
            "success": True,
            "result": {
                "State": "Active",
                "Provider": "miner1",
                "Size": 1024
            }
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "deal_id": 123,
            "deal_info": {
                "State": "Active",
                "Provider": "miner1",
                "Size": 1024
            },
            "operation": "get_deal_info_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.get_deal_info_async(123),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.client_deal_info.assert_called_once_with(123)
    
    def test_async_start_deal(self):
        """Test start_deal_async method."""
        # Set up mock responses
        self.mock_lotus_kit.client_start_deal.return_value = {
            "success": True,
            "result": {"/": "deal_cid_123"}
        }
        
        # Run the async test
        result = anyio.run(self.filecoin_model.start_deal_async(
            data_cid="test_data_cid",
            miner="miner1",
            price="100",
            duration=1000,
            wallet="wallet1",
            verified=True,
            fast_retrieval=True
        ))
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["deal_cid"], "deal_cid_123")
        self.assertEqual(result["data_cid"], "test_data_cid")
        self.assertEqual(result["miner"], "miner1")
        self.assertEqual(result["price"], "100")
        self.assertEqual(result["duration"], 1000)
        self.assertEqual(result["wallet"], "wallet1")
        self.assertTrue(result["verified"])
        self.assertTrue(result["fast_retrieval"])
        
        # Verify lotus_kit method was called with correct parameters
        self.mock_lotus_kit.client_start_deal.assert_called_once_with(
            data_cid="test_data_cid",
            miner="miner1",
            price="100",
            duration=1000,
            wallet="wallet1",
            verified=True,
            fast_retrieval=True
        )
    
    def test_async_retrieve_data(self):
        """Test retrieve_data_async method."""
        # Set up mock response
        self.mock_lotus_kit.client_retrieve.return_value = {
            "success": True,
            "result": "Retrieval complete"
        }
        
        # Create a temporary output file
        out_fd, out_path = tempfile.mkstemp()
        os.close(out_fd)
        
        try:
            # Run the async test
            result = anyio.run(self.filecoin_model.retrieve_data_async(
                data_cid="test_data_cid",
                out_file=out_path
            ))
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["cid"], "test_data_cid")
            self.assertEqual(result["file_path"], out_path)
            
            # Verify lotus_kit method was called
            self.mock_lotus_kit.client_retrieve.assert_called_once_with(
                "test_data_cid", out_path
            )
            
        finally:
            # Clean up
            try:
                os.unlink(out_path)
            except:
                pass
    
    def test_async_list_miners(self):
        """Test list_miners_async method."""
        # Set up mock response
        self.mock_lotus_kit.list_miners.return_value = {
            "success": True,
            "result": ["miner1", "miner2", "miner3"]
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "miners": ["miner1", "miner2", "miner3"],
            "count": 3,
            "operation": "list_miners_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.list_miners_async(),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.list_miners.assert_called_once()
    
    def test_async_get_miner_info(self):
        """Test get_miner_info_async method."""
        # Set up mock response
        self.mock_lotus_kit.miner_get_info.return_value = {
            "success": True,
            "result": {
                "Owner": "owner1",
                "Worker": "worker1",
                "PeerId": "peer1"
            }
        }
        
        # Expected result
        expected_result = {
            "success": True,
            "miner_address": "miner1",
            "miner_info": {
                "Owner": "owner1",
                "Worker": "worker1",
                "PeerId": "peer1"
            },
            "operation": "get_miner_info_async",
            "duration_ms": unittest.mock.ANY
        }
        
        # Run the async test
        anyio.run(self._async_test_helper(
            self.filecoin_model.get_miner_info_async("miner1"),
            expected_result
        ))
        
        # Verify lotus_kit method was called
        self.mock_lotus_kit.miner_get_info.assert_called_once_with("miner1")
    
    def test_async_ipfs_to_filecoin(self):
        """Test ipfs_to_filecoin_async method."""
        # Set up mock responses
        self.mock_ipfs_model.get_content_async = AsyncMock(return_value={
            "success": True,
            "data": b"Test content"
        })
        self.mock_ipfs_model.pin_content_async = AsyncMock(return_value={
            "success": True
        })
        
        # Mock import_file_async and start_deal_async methods
        self.filecoin_model.import_file_async = AsyncMock(return_value={
            "success": True,
            "root": "data_cid_123",
            "size_bytes": 100
        })
        self.filecoin_model.start_deal_async = AsyncMock(return_value={
            "success": True,
            "deal_cid": "deal_cid_123"
        })
        
        # Run the async test
        result = anyio.run(self.filecoin_model.ipfs_to_filecoin_async(
            cid="ipfs_cid_123",
            miner="miner1",
            price="100",
            duration=1000,
            wallet="wallet1",
            verified=True,
            fast_retrieval=True,
            pin=True
        ))
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["ipfs_cid"], "ipfs_cid_123")
        self.assertEqual(result["filecoin_cid"], "data_cid_123")
        self.assertEqual(result["deal_cid"], "deal_cid_123")
        self.assertEqual(result["miner"], "miner1")
        self.assertEqual(result["price"], "100")
        self.assertEqual(result["duration"], 1000)
        
        # Verify methods were called with correct parameters
        self.mock_ipfs_model.get_content_async.assert_called_once_with("ipfs_cid_123")
        self.mock_ipfs_model.pin_content_async.assert_called_once_with("ipfs_cid_123")
        self.filecoin_model.start_deal_async.assert_called_once_with(
            data_cid="data_cid_123",
            miner="miner1",
            price="100",
            duration=1000,
            wallet="wallet1",
            verified=True,
            fast_retrieval=True
        )
    
    def test_async_filecoin_to_ipfs(self):
        """Test filecoin_to_ipfs_async method."""
        # Set up mock responses
        self.mock_ipfs_model.add_content_async = AsyncMock(return_value={
            "success": True,
            "cid": "ipfs_cid_123"
        })
        self.mock_ipfs_model.pin_content_async = AsyncMock(return_value={
            "success": True
        })
        
        # Mock retrieve_data_async method
        self.filecoin_model.retrieve_data_async = AsyncMock(return_value={
            "success": True,
            "file_path": self.test_file_path
        })
        
        # Run the async test
        result = anyio.run(self.filecoin_model.filecoin_to_ipfs_async(
            data_cid="data_cid_123",
            pin=True
        ))
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["filecoin_cid"], "data_cid_123")
        self.assertEqual(result["ipfs_cid"], "ipfs_cid_123")
        
        # Verify methods were called with correct parameters
        self.filecoin_model.retrieve_data_async.assert_called_once_with("data_cid_123", unittest.mock.ANY)
        self.mock_ipfs_model.pin_content_async.assert_called_once_with("ipfs_cid_123")
    
    def test_async_error_handling(self):
        """Test error handling in async methods."""
        # Set up mock to raise exception
        self.mock_lotus_kit.check_connection.side_effect = Exception("Test error")
        
        # Run the async test
        result = anyio.run(self.filecoin_model.check_connection_async())
        
        # Verify error handling
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["error_type"], "Exception")
        self.assertIn("Test error", result["error"])


if __name__ == "__main__":
    unittest.main()