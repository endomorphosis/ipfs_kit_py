"""
Tests for DHT operations in the MCP Server with AnyIO support.

This module tests the DHT operations (dht_findpeer, dht_findprovs) 
in the IPFS Model of the MCP server using AnyIO for async support.
"""

import json
import os
import sys
import time
import pytest
from unittest.mock import patch, MagicMock, call, AsyncMock

# Add the parent directory to the path so we can import the ipfs_kit_py module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

# Keep original unittest class for backward compatibility
from test_mcp_dht_operations import TestMCPDHTOperations

@pytest.mark.anyio
class TestMCPDHTOperationsAnyIO:
    """Test case for DHT operations in the MCP Server using AnyIO."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up the test environment with AnyIO support."""
        # Create a mock IPFS Kit instance with async methods
        self.mock_ipfs_kit = MagicMock()
        self.mock_ipfs_kit.dht_findpeer_async = AsyncMock()
        self.mock_ipfs_kit.dht_findprovs_async = AsyncMock()
        
        self.mock_cache_manager = MagicMock()
        
        # Create an instance of the IPFS Model with the mock IPFS Kit
        self.ipfs_model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.mock_cache_manager
        )
        
        # Add async methods to the model
        self.ipfs_model.dht_findpeer_async = AsyncMock()
        self.ipfs_model.dht_findprovs_async = AsyncMock()
        
        yield
        
        # Cleanup if needed
    
    @pytest.mark.anyio
    async def test_dht_findpeer_async_success(self):
        """Test that dht_findpeer_async correctly finds a peer."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"
        
        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {
                    "ID": "QmFoundPeer1",
                    "Addrs": [
                        "/ip4/127.0.0.1/tcp/4001",
                        "/ip6/::1/tcp/4001"
                    ]
                }
            ],
            "Extra": "Some additional info"
        }
        
        # Mock the dht_findpeer_async method
        self.mock_ipfs_kit.dht_findpeer_async.return_value = expected_response
        
        # Configure model mock to delegate to kit
        async def async_dht_findpeer(peer_id, **kwargs):
            return {
                "success": True,
                "operation": "dht_findpeer",
                "peer_id": peer_id,
                "timestamp": time.time(),
                "responses": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in (await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs))["Responses"]
                ],
                "peers_found": len((await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs))["Responses"])
            }
        
        self.ipfs_model.dht_findpeer_async.side_effect = async_dht_findpeer
        
        # Call the method
        result = await self.ipfs_model.dht_findpeer_async(test_peer_id)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dht_findpeer"
        assert result["peer_id"] == test_peer_id
        assert "responses" in result
        assert len(result["responses"]) == 1
        assert result["responses"][0]["id"] == "QmFoundPeer1"
        assert len(result["responses"][0]["addrs"]) == 2
        
        # Verify the mock was called correctly
        self.mock_ipfs_kit.dht_findpeer_async.assert_called_once_with(test_peer_id)
    
    @pytest.mark.anyio
    async def test_dht_findpeer_async_empty_response(self):
        """Test handling of empty response from dht_findpeer_async."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"
        
        # Empty response
        empty_response = {
            "Responses": []
        }
        
        # Mock the dht_findpeer_async method
        self.mock_ipfs_kit.dht_findpeer_async.return_value = empty_response
        
        # Configure model mock to delegate to kit
        async def async_dht_findpeer(peer_id, **kwargs):
            response = await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs)
            return {
                "success": True,
                "operation": "dht_findpeer",
                "peer_id": peer_id,
                "timestamp": time.time(),
                "responses": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "peers_found": len(response["Responses"])
            }
        
        self.ipfs_model.dht_findpeer_async.side_effect = async_dht_findpeer
        
        # Call the method
        result = await self.ipfs_model.dht_findpeer_async(test_peer_id)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dht_findpeer"
        assert result["peer_id"] == test_peer_id
        assert "responses" in result
        assert len(result["responses"]) == 0
        assert result["peers_found"] == 0
    
    @pytest.mark.anyio
    async def test_dht_findpeer_async_error(self):
        """Test error handling in dht_findpeer_async."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"
        
        # Mock the dht_findpeer_async method to raise an exception
        error_msg = "DHT error"
        self.mock_ipfs_kit.dht_findpeer_async.side_effect = Exception(error_msg)
        
        # Configure model mock to handle errors
        async def async_dht_findpeer(peer_id, **kwargs):
            try:
                response = await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs)
                return {
                    "success": True,
                    "operation": "dht_findpeer",
                    "peer_id": peer_id,
                    "timestamp": time.time(),
                    "responses": [
                        {
                            "id": resp["ID"],
                            "addrs": resp["Addrs"]
                        } for resp in response["Responses"]
                    ],
                    "peers_found": len(response["Responses"])
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dht_findpeer",
                    "peer_id": peer_id,
                    "timestamp": time.time(),
                    "error": f"Error: {str(e)}",
                    "error_type": "dht_error"
                }
        
        self.ipfs_model.dht_findpeer_async.side_effect = async_dht_findpeer
        
        # Call the method
        result = await self.ipfs_model.dht_findpeer_async(test_peer_id)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "dht_findpeer"
        assert result["peer_id"] == test_peer_id
        assert "error" in result
        assert error_msg in result["error"]
        assert result["error_type"] == "dht_error"
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_success(self):
        """Test that dht_findprovs_async correctly finds providers for a CID."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"
        
        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {
                    "ID": "QmProvider1",
                    "Addrs": [
                        "/ip4/192.168.1.1/tcp/4001",
                        "/ip6/2001:db8::1/tcp/4001"
                    ]
                },
                {
                    "ID": "QmProvider2",
                    "Addrs": [
                        "/ip4/192.168.1.2/tcp/4001"
                    ]
                }
            ],
            "Extra": "Additional information"
        }
        
        # Mock the dht_findprovs_async method
        self.mock_ipfs_kit.dht_findprovs_async.return_value = expected_response
        
        # Configure model mock to delegate to kit
        async def async_dht_findprovs(cid, **kwargs):
            response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
            result = {
                "success": True,
                "operation": "dht_findprovs",
                "cid": cid,
                "timestamp": time.time(),
                "providers": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "count": len(response["Responses"])
            }
            if "num_providers" in kwargs:
                result["num_providers"] = kwargs["num_providers"]
            return result
        
        self.ipfs_model.dht_findprovs_async.side_effect = async_dht_findprovs
        
        # Call the method
        result = await self.ipfs_model.dht_findprovs_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dht_findprovs"
        assert result["cid"] == test_cid
        assert "providers" in result
        assert len(result["providers"]) == 2
        assert result["providers"][0]["id"] == "QmProvider1"
        assert len(result["providers"][0]["addrs"]) == 2
        assert result["providers"][1]["id"] == "QmProvider2"
        assert len(result["providers"][1]["addrs"]) == 1
        assert result["count"] == 2
        
        # Verify the mock was called correctly
        self.mock_ipfs_kit.dht_findprovs_async.assert_called_once_with(test_cid)
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_with_num_providers(self):
        """Test that dht_findprovs_async respects the num_providers parameter."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"
        test_num_providers = 5
        
        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {"ID": "QmProvider1", "Addrs": ["/ip4/192.168.1.1/tcp/4001"]},
                {"ID": "QmProvider2", "Addrs": ["/ip4/192.168.1.2/tcp/4001"]}
            ]
        }
        
        # Mock the dht_findprovs_async method
        self.mock_ipfs_kit.dht_findprovs_async.return_value = expected_response
        
        # Configure model mock to delegate to kit and include num_providers
        async def async_dht_findprovs(cid, **kwargs):
            response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
            result = {
                "success": True,
                "operation": "dht_findprovs",
                "cid": cid,
                "timestamp": time.time(),
                "providers": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "count": len(response["Responses"])
            }
            if "num_providers" in kwargs:
                result["num_providers"] = kwargs["num_providers"]
            return result
        
        self.ipfs_model.dht_findprovs_async.side_effect = async_dht_findprovs
        
        # Call the method with num_providers parameter
        result = await self.ipfs_model.dht_findprovs_async(test_cid, num_providers=test_num_providers)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dht_findprovs"
        assert result["cid"] == test_cid
        assert result["num_providers"] == test_num_providers
        
        # Verify the mock was called correctly with num_providers
        self.mock_ipfs_kit.dht_findprovs_async.assert_called_once_with(
            test_cid, num_providers=test_num_providers
        )
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_empty_response(self):
        """Test handling of empty response from dht_findprovs_async."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"
        
        # Empty response
        empty_response = {
            "Responses": []
        }
        
        # Mock the dht_findprovs_async method
        self.mock_ipfs_kit.dht_findprovs_async.return_value = empty_response
        
        # Configure model mock to delegate to kit
        async def async_dht_findprovs(cid, **kwargs):
            response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
            return {
                "success": True,
                "operation": "dht_findprovs",
                "cid": cid,
                "timestamp": time.time(),
                "providers": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "count": len(response["Responses"])
            }
        
        self.ipfs_model.dht_findprovs_async.side_effect = async_dht_findprovs
        
        # Call the method
        result = await self.ipfs_model.dht_findprovs_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dht_findprovs"
        assert result["cid"] == test_cid
        assert "providers" in result
        assert len(result["providers"]) == 0
        assert result["count"] == 0
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_error(self):
        """Test error handling in dht_findprovs_async."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"
        
        # Mock the dht_findprovs_async method to raise an exception
        error_msg = "DHT error"
        self.mock_ipfs_kit.dht_findprovs_async.side_effect = Exception(error_msg)
        
        # Configure model mock to handle errors
        async def async_dht_findprovs(cid, **kwargs):
            try:
                response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
                return {
                    "success": True,
                    "operation": "dht_findprovs",
                    "cid": cid,
                    "timestamp": time.time(),
                    "providers": [
                        {
                            "id": resp["ID"],
                            "addrs": resp["Addrs"]
                        } for resp in response["Responses"]
                    ],
                    "count": len(response["Responses"])
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dht_findprovs",
                    "cid": cid,
                    "timestamp": time.time(),
                    "error": f"Error: {str(e)}",
                    "error_type": "dht_error"
                }
        
        self.ipfs_model.dht_findprovs_async.side_effect = async_dht_findprovs
        
        # Call the method
        result = await self.ipfs_model.dht_findprovs_async(test_cid)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "dht_findprovs"
        assert result["cid"] == test_cid
        assert "error" in result
        assert error_msg in result["error"]
        assert result["error_type"] == "dht_error"
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test explicit anyio.sleep integration with DHT operations."""
        import anyio
        
        # Test parameters
        test_peer_id = "QmTestPeerID"
        test_cid = "QmTestContentID"
        
        # Define async functions with delays
        async def findpeer_with_delay_async(peer_id, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage
            return {
                "Responses": [
                    {
                        "ID": "QmFoundPeer1",
                        "Addrs": ["/ip4/127.0.0.1/tcp/4001", "/ip6/::1/tcp/4001"]
                    }
                ]
            }
        
        async def findprovs_with_delay_async(cid, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage
            return {
                "Responses": [
                    {
                        "ID": "QmProvider1",
                        "Addrs": ["/ip4/192.168.1.1/tcp/4001"]
                    }
                ]
            }
        
        # Set side effects for async methods
        self.mock_ipfs_kit.dht_findpeer_async.side_effect = findpeer_with_delay_async
        self.mock_ipfs_kit.dht_findprovs_async.side_effect = findprovs_with_delay_async
        
        # Configure model mocks
        async def model_findpeer_async(peer_id, **kwargs):
            response = await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs)
            return {
                "success": True,
                "operation": "dht_findpeer",
                "peer_id": peer_id,
                "timestamp": time.time(),
                "responses": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "peers_found": len(response["Responses"])
            }
        
        async def model_findprovs_async(cid, **kwargs):
            response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
            result = {
                "success": True,
                "operation": "dht_findprovs",
                "cid": cid,
                "timestamp": time.time(),
                "providers": [
                    {
                        "id": resp["ID"],
                        "addrs": resp["Addrs"]
                    } for resp in response["Responses"]
                ],
                "count": len(response["Responses"])
            }
            return result
        
        self.ipfs_model.dht_findpeer_async.side_effect = model_findpeer_async
        self.ipfs_model.dht_findprovs_async.side_effect = model_findprovs_async
        
        # Test operations with delay
        start_time = time.time()
        
        # Run operations in sequence
        findpeer_result = await self.ipfs_model.dht_findpeer_async(test_peer_id)
        findprovs_result = await self.ipfs_model.dht_findprovs_async(test_cid)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Verify results
        assert findpeer_result["success"] is True
        assert findpeer_result["peers_found"] == 1
        
        assert findprovs_result["success"] is True
        assert findprovs_result["count"] == 1
        
        # Verify timing - should be at least 0.2s (0.1s delay × 2 operations)
        assert elapsed_time >= 0.2, f"Expected delay of at least 0.2s but got {elapsed_time}s"