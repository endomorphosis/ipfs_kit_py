"""
Extended tests for the DHT operations in the MCP server with AnyIO support.

This test file provides more comprehensive testing for DHT operations
(findpeer and findprovs) with the AnyIO implementation, focusing on
async/await patterns and compatibility with different async backends.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import anyio
import sniffio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller_anyio import IPFSControllerAnyIO
from ipfs_kit_py.mcp.server import MCPServer

@pytest.mark.anyio
class TestMCPDHTOperationsAnyIOExtended:
    """Extended tests for DHT operations with AnyIO support."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up the test environment with mocked components."""
        # Create mock IPFS kit
        self.mock_ipfs_kit = MagicMock()
        
        # Add async methods for DHT operations
        self.mock_ipfs_kit.dht_findpeer_async = AsyncMock()
        self.mock_ipfs_kit.dht_findprovs_async = AsyncMock()
        
        # Create IPFS model with mock kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Add async methods to model
        self.ipfs_model.dht_findpeer_async = AsyncMock()
        self.ipfs_model.dht_findprovs_async = AsyncMock()
        
        # Create AnyIO controller
        self.controller = IPFSControllerAnyIO(self.ipfs_model)
        
        # Create FastAPI app with router
        self.app = FastAPI()
        self.router = self.app.router
        self.controller.register_routes(self.router)
        
        # Create test client
        self.client = TestClient(self.app)
        
        # Configure mock successful responses
        self.mock_ipfs_kit.dht_findpeer_async.return_value = {
            "Responses": [
                {
                    "ID": "QmPeerID1",
                    "Addrs": [
                        "/ip4/192.168.1.1/tcp/4001",
                        "/ip6/::1/tcp/4001"
                    ]
                }
            ],
            "Extra": "test-peer-data"
        }
        
        self.mock_ipfs_kit.dht_findprovs_async.return_value = {
            "Responses": [
                {
                    "ID": "QmProviderID1",
                    "Addrs": [
                        "/ip4/192.168.1.2/tcp/4001",
                        "/ip6/::2/tcp/4001"
                    ]
                },
                {
                    "ID": "QmProviderID2",
                    "Addrs": [
                        "/ip4/192.168.1.3/tcp/4001"
                    ]
                }
            ],
            "Extra": "test-provider-data"
        }
        
        # Configure model methods to use kit methods
        async def model_dht_findpeer_async(peer_id, **kwargs):
            result = {
                "success": True,
                "operation": "dht_findpeer",
                "peer_id": peer_id,
                "timestamp": time.time()
            }
            
            try:
                # Call mock kit method
                response = await self.mock_ipfs_kit.dht_findpeer_async(peer_id, **kwargs)
                result["responses"] = response.get("Responses", [])
                result["extra"] = response.get("Extra", "")
                return result
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)
                return result
                
        async def model_dht_findprovs_async(cid, **kwargs):
            result = {
                "success": True,
                "operation": "dht_findprovs",
                "cid": cid,
                "timestamp": time.time()
            }
            
            try:
                # Call mock kit method
                response = await self.mock_ipfs_kit.dht_findprovs_async(cid, **kwargs)
                result["responses"] = response.get("Responses", [])
                result["extra"] = response.get("Extra", "")
                return result
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)
                return result
        
        self.ipfs_model.dht_findpeer_async.side_effect = model_dht_findpeer_async
        self.ipfs_model.dht_findprovs_async.side_effect = model_dht_findprovs_async
        
        yield
        
        # Cleanup after tests
    
    @pytest.mark.anyio
    async def test_dht_findpeer_async_success(self):
        """Test successful DHT findpeer operation with AnyIO."""
        # Make request to find peer endpoint
        response = self.client.get("/ipfs/dht/findpeer?peer_id=QmTestPeer")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["operation"] == "dht_findpeer"
        assert data["peer_id"] == "QmTestPeer"
        assert "responses" in data
        assert len(data["responses"]) == 1
        assert data["responses"][0]["ID"] == "QmPeerID1"
        assert len(data["responses"][0]["Addrs"]) == 2
        assert data["extra"] == "test-peer-data"
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.dht_findpeer_async.assert_called_once_with("QmTestPeer")
    
    @pytest.mark.anyio
    async def test_dht_findpeer_async_error(self):
        """Test error handling in DHT findpeer operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.dht_findpeer_async.side_effect = Exception("Test error finding peer")
        
        # Make request to find peer endpoint
        response = self.client.get("/ipfs/dht/findpeer?peer_id=QmTestPeer")
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert data["operation"] == "dht_findpeer"
        assert data["peer_id"] == "QmTestPeer"
        assert "error" in data
        assert "Test error finding peer" in data["error"]
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_success(self):
        """Test successful DHT findprovs operation with AnyIO."""
        # Make request to find providers endpoint
        response = self.client.get("/ipfs/dht/findprovs?cid=QmTestCID")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["operation"] == "dht_findprovs"
        assert data["cid"] == "QmTestCID"
        assert "responses" in data
        assert len(data["responses"]) == 2
        assert data["responses"][0]["ID"] == "QmProviderID1"
        assert data["responses"][1]["ID"] == "QmProviderID2"
        assert data["extra"] == "test-provider-data"
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.dht_findprovs_async.assert_called_once_with("QmTestCID")
    
    @pytest.mark.anyio
    async def test_dht_findprovs_async_error(self):
        """Test error handling in DHT findprovs operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.dht_findprovs_async.side_effect = Exception("Test error finding providers")
        
        # Make request to find providers endpoint
        response = self.client.get("/ipfs/dht/findprovs?cid=QmTestCID")
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert data["operation"] == "dht_findprovs"
        assert data["cid"] == "QmTestCID"
        assert "error" in data
        assert "Test error finding providers" in data["error"]
    
    @pytest.mark.anyio
    async def test_dht_findpeer_with_timeout_parameter(self):
        """Test DHT findpeer with timeout parameter."""
        # Make request with timeout parameter
        response = self.client.get("/ipfs/dht/findpeer?peer_id=QmTestPeer&timeout=5")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        
        # Verify the mock was called with correct arguments including timeout
        # Note: The controller should convert timeout from seconds to milliseconds
        kwargs = self.mock_ipfs_kit.dht_findpeer_async.call_args[1]
        assert "timeout" in kwargs or "Timeout" in kwargs
    
    @pytest.mark.anyio
    async def test_dht_findprovs_with_num_providers_parameter(self):
        """Test DHT findprovs with num_providers parameter."""
        # Make request with num_providers parameter
        response = self.client.get("/ipfs/dht/findprovs?cid=QmTestCID&num_providers=5")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        
        # Verify the mock was called with correct arguments
        kwargs = self.mock_ipfs_kit.dht_findprovs_async.call_args[1]
        assert "num_providers" in kwargs or "NumProviders" in kwargs
    
    @pytest.mark.anyio
    async def test_dht_operations_with_sniffio_detection(self):
        """Test DHT operations with sniffio backend detection."""
        # Get the current async backend
        backend = self.controller.get_backend()
        assert backend == "asyncio" or backend == "trio"
        
        # Make request with backend logging
        async def test_with_backend():
            # This task runs in the current async backend
            current_backend = sniffio.current_async_library()
            
            # Execute DHT findpeer operation
            response = await self.ipfs_model.dht_findpeer_async("QmTestPeer")
            
            return {
                "backend": current_backend,
                "response": response
            }
        
        # Run the test
        result = await test_with_backend()
        
        # Verify backend detection worked
        assert result["backend"] == "asyncio" or result["backend"] == "trio"
        assert result["response"]["success"] is True
    
    @pytest.mark.anyio
    async def test_concurrent_dht_operations(self):
        """Test running multiple DHT operations concurrently."""
        # Configure mocks with delayed responses
        async def delayed_findpeer(peer_id, delay=0.1, **kwargs):
            await anyio.sleep(delay)
            return {
                "Responses": [{"ID": f"{peer_id}_response", "Addrs": ["/ip4/127.0.0.1/tcp/4001"]}],
                "Extra": f"delayed_{delay}"
            }
            
        async def delayed_findprovs(cid, delay=0.1, **kwargs):
            await anyio.sleep(delay)
            return {
                "Responses": [{"ID": f"{cid}_provider", "Addrs": ["/ip4/127.0.0.1/tcp/4001"]}],
                "Extra": f"delayed_{delay}"
            }
        
        self.mock_ipfs_kit.dht_findpeer_async.side_effect = delayed_findpeer
        self.mock_ipfs_kit.dht_findprovs_async.side_effect = delayed_findprovs
        
        # Run multiple operations concurrently
        async def run_concurrent_operations():
            async with anyio.create_task_group() as tg:
                # Start multiple peer lookups with different delays
                peer_results = []
                provider_results = []
                
                for i in range(3):
                    peer_id = f"QmPeer{i}"
                    cid = f"QmCID{i}"
                    
                    # Find peer task
                    async def find_peer_task(p_id, delay, results):
                        model_response = await self.ipfs_model.dht_findpeer_async(p_id, delay=delay)
                        results.append(model_response)
                    
                    # Find providers task
                    async def find_provs_task(c_id, delay, results):
                        model_response = await self.ipfs_model.dht_findprovs_async(c_id, delay=delay)
                        results.append(model_response)
                    
                    # Start tasks with different delays
                    tg.start_soon(find_peer_task, peer_id, 0.1 * (i + 1), peer_results)
                    tg.start_soon(find_provs_task, cid, 0.1 * (i + 1), provider_results)
                
                # Wait for all tasks to complete (handled by context manager)
                
            # Return combined results
            return {
                "peer_results": peer_results,
                "provider_results": provider_results
            }
        
        # Execute concurrent operations
        start_time = time.time()
        results = await run_concurrent_operations()
        end_time = time.time()
        
        # Verify results
        assert len(results["peer_results"]) == 3
        assert len(results["provider_results"]) == 3
        
        # Tasks should have completed concurrently, not serially
        # If run serially, would take 0.1+0.2+0.3 + 0.1+0.2+0.3 = 1.2 seconds
        # Concurrently should take ~0.3 seconds plus overhead
        execution_time = end_time - start_time
        assert execution_time < 0.6, f"Execution time {execution_time} suggests operations ran serially, not concurrently"
        
        # Verify all operations completed successfully
        for result in results["peer_results"] + results["provider_results"]:
            assert result["success"] is True
    
    @pytest.mark.anyio
    async def test_dht_operations_with_anyio_timeouts(self):
        """Test DHT operations with AnyIO timeouts."""
        # Configure mocks with very slow responses
        async def very_slow_operation(*args, **kwargs):
            await anyio.sleep(2.0)  # Too slow - should timeout
            return {"Responses": []}
        
        self.mock_ipfs_kit.dht_findpeer_async.side_effect = very_slow_operation
        
        # Run operation with timeout
        async def run_with_timeout():
            try:
                async with anyio.move_on_after(0.5):  # 500ms timeout
                    # This should timeout
                    result = await self.ipfs_model.dht_findpeer_async("QmTestPeer")
                    return {"completed": True, "result": result}
                
                # If we get here, the operation timed out
                return {"completed": False, "timeout": True}
            except Exception as e:
                return {"completed": False, "error": str(e)}
        
        # Execute with timeout
        result = await run_with_timeout()
        
        # Verify timeout behavior
        assert result["completed"] is False
        assert "timeout" in result
        assert result["timeout"] is True
    
    @pytest.mark.anyio
    async def test_dht_operations_with_sync_fallback(self):
        """Test DHT operations falling back to sync methods."""
        # Create a model with only sync methods (no async DHT methods)
        sync_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Remove any async methods that might be there
        if hasattr(sync_model, "dht_findpeer_async"):
            delattr(sync_model, "dht_findpeer_async")
            
        if hasattr(sync_model, "dht_findprovs_async"):
            delattr(sync_model, "dht_findprovs_async")
        
        # Add sync versions that will be used as fallbacks
        sync_model.dht_findpeer = MagicMock(return_value={
            "success": True,
            "operation": "dht_findpeer",
            "peer_id": "QmTestPeer",
            "responses": [{"ID": "QmSyncPeerID", "Addrs": ["/ip4/127.0.0.1/tcp/4001"]}]
        })
        
        # Create controller with the sync model
        sync_controller = IPFSControllerAnyIO(sync_model)
        
        # Create FastAPI app with router
        app = FastAPI()
        router = app.router
        sync_controller.register_routes(router)
        
        # Create test client
        client = TestClient(app)
        
        # Test that AnyIO controller correctly handles sync methods
        response = client.get("/ipfs/dht/findpeer?peer_id=QmTestPeer")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        # Even though we're using sync methods, the response should be formatted
        # as if it came from an async method
        assert data["success"] is True
        assert data["operation"] == "dht_findpeer"
        assert data["peer_id"] == "QmTestPeer"
        
        # Verify the sync method was called
        sync_model.dht_findpeer.assert_called_once()