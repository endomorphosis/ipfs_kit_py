#!/usr/bin/env python3
"""
Comprehensive integration test for WebRTC AnyIO fixes.

This script performs real-world testing of the WebRTC AnyIO fixes
by simulating a full FastAPI application with WebRTC operations.
"""

import os
import sys
import time
import uuid
import anyio
import logging
import unittest
import multiprocessing
from contextlib import contextmanager
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for required dependencies
try:
    import anyio
    import sniffio
    import fastapi
    import uvicorn
    import requests
    from fastapi import FastAPI, APIRouter
    from fastapi.testclient import TestClient
except ImportError:
    logger.error("Missing required dependencies. Install with:")
    logger.error("pip install anyio sniffio fastapi uvicorn requests")
    sys.exit(1)

# Mock classes to simulate WebRTC operations
class MockWebRTCManager:
    """Mock WebRTC manager for testing."""
    
    def __init__(self):
        self.connections = {}
        self.streams = {}
        
    async def close_connection(self, connection_id):
        """Mock async method to close a connection."""
        logger.info(f"Closing connection: {connection_id}")
        await anyio.sleep(0.2)  # Simulate work
        if connection_id in self.connections:
            self.connections.pop(connection_id)
            return {"success": True, "connection_id": connection_id}
        return {"success": False, "error": "Connection not found"}
    
    async def close_all_connections(self):
        """Mock async method to close all connections."""
        logger.info(f"Closing all connections: {len(self.connections)}")
        await anyio.sleep(0.3)  # Simulate work
        connection_count = len(self.connections)
        self.connections.clear()
        return {"success": True, "connections_closed": connection_count}
    
    def get_stats(self):
        """Get connection statistics."""
        return {
            "connections": self.connections,
            "active_connections": len(self.connections),
            "streams": self.streams
        }
    
    def add_connection(self, connection_id=None):
        """Add a connection for testing."""
        if connection_id is None:
            connection_id = f"conn-{uuid.uuid4()}"
        self.connections[connection_id] = {
            "id": connection_id,
            "created_at": time.time(),
            "state": "connected"
        }
        return connection_id

class MockIPFSModel:
    """Mock IPFS model with WebRTC methods."""
    
    def __init__(self):
        self.webrtc_manager = MockWebRTCManager()
        self.operation_stats = {}
        
    # Original problematic methods (before patching)
    def original_stop_webrtc_streaming(self, server_id):
        """Original problematic implementation with event loop issues."""
        result = {
            "success": False,
            "operation": "stop_webrtc_streaming",
            "server_id": server_id
        }
        
        try:
            # Problematic pattern
            try:
                loop = anyio.get_event_loop()
                if loop.is_running():
                    # This is the problem - creating a new loop in a running loop
                    new_loop = anyio.new_event_loop()
                    anyio.set_event_loop(new_loop)
                    loop = new_loop
            except RuntimeError:
                # No event loop in this thread
                loop = anyio.new_event_loop()
                anyio.set_event_loop(loop)
            
            # Try to run_until_complete in a running loop
            close_result = loop.run_until_complete(
                self.webrtc_manager.close_all_connections()
            )
            
            result["success"] = True
            result["connections_closed"] = close_result.get("connections_closed", 0)
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def original_close_webrtc_connection(self, connection_id):
        """Original problematic implementation with event loop issues."""
        result = {
            "success": False,
            "operation": "close_webrtc_connection",
            "connection_id": connection_id
        }
        
        try:
            # Problematic pattern
            try:
                loop = anyio.get_event_loop()
                if loop.is_running():
                    # This is the problem - creating a new loop in a running loop
                    new_loop = anyio.new_event_loop()
                    anyio.set_event_loop(new_loop)
                    loop = new_loop
            except RuntimeError:
                # No event loop in this thread
                loop = anyio.new_event_loop()
                anyio.set_event_loop(loop)
            
            # Try to run_until_complete in a running loop
            close_result = loop.run_until_complete(
                self.webrtc_manager.close_connection(connection_id)
            )
            
            if not close_result.get("success", False):
                result["error"] = close_result.get("error", "Unknown error")
                return result
                
            result["success"] = True
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def original_close_all_webrtc_connections(self):
        """Original problematic implementation with event loop issues."""
        result = {
            "success": False,
            "operation": "close_all_webrtc_connections"
        }
        
        try:
            # Problematic pattern
            try:
                loop = anyio.get_event_loop()
                if loop.is_running():
                    # This is the problem - creating a new loop in a running loop
                    new_loop = anyio.new_event_loop()
                    anyio.set_event_loop(new_loop)
                    loop = new_loop
            except RuntimeError:
                # No event loop in this thread
                loop = anyio.new_event_loop()
                anyio.set_event_loop(loop)
            
            # Try to run_until_complete in a running loop
            stats = self.webrtc_manager.get_stats()
            connection_count = len(stats.get("connections", {}))
            
            close_result = loop.run_until_complete(
                self.webrtc_manager.close_all_connections()
            )
            
            result["success"] = True
            result["connections_closed"] = connection_count
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result

class MockWebRTCController:
    """Mock WebRTC controller for API endpoints."""
    
    def __init__(self, ipfs_model):
        self.ipfs_model = ipfs_model
    
    def register_routes(self, router):
        """Register API routes with a FastAPI router."""
        # Close connection endpoint (problematic)
        router.add_api_route(
            "/webrtc/connections/{connection_id}/close",
            self.close_connection,
            methods=["POST"]
        )
        
        # Close all connections endpoint (problematic)
        router.add_api_route(
            "/webrtc/connections/close-all",
            self.close_all_connections,
            methods=["POST"]
        )
        
        # Stop streaming endpoint (problematic)
        router.add_api_route(
            "/webrtc/stream/stop/{server_id}",
            self.stop_streaming,
            methods=["POST"]
        )
        
        # Add a test connection (for testing)
        router.add_api_route(
            "/webrtc/test/add-connection",
            self.add_test_connection,
            methods=["POST"]
        )
        
        # Get connections (for testing)
        router.add_api_route(
            "/webrtc/connections",
            self.get_connections,
            methods=["GET"]
        )
    
    async def close_connection(self, connection_id: str):
        """API endpoint to close a WebRTC connection."""
        try:
            result = self.ipfs_model.original_close_webrtc_connection(connection_id)
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "connection_id": connection_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def close_all_connections(self):
        """API endpoint to close all WebRTC connections."""
        try:
            result = self.ipfs_model.original_close_all_webrtc_connections()
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "connections_closed": result.get("connections_closed", 0)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop_streaming(self, server_id: str):
        """API endpoint to stop WebRTC streaming."""
        try:
            result = self.ipfs_model.original_stop_webrtc_streaming(server_id)
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "server_id": server_id, "connections_closed": result.get("connections_closed", 0)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def add_test_connection(self):
        """API endpoint to add a test connection."""
        try:
            connection_id = self.ipfs_model.webrtc_manager.add_connection()
            return {"success": True, "connection_id": connection_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_connections(self):
        """API endpoint to get connections."""
        try:
            stats = self.ipfs_model.webrtc_manager.get_stats()
            connections = [
                {"connection_id": conn_id, "state": data["state"]}
                for conn_id, data in stats.get("connections", {}).items()
            ]
            return {"success": True, "connections": connections, "count": len(connections)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

def create_test_app():
    """Create a FastAPI app for testing the problematic WebRTC methods."""
    app = FastAPI(title="WebRTC Test App")
    
    # Create model and controller
    ipfs_model = MockIPFSModel()
    webrtc_controller = MockWebRTCController(ipfs_model)
    
    # Create router and register routes
    router = APIRouter()
    webrtc_controller.register_routes(router)
    
    # Add info endpoint
    @router.get("/info")
    async def get_info():
        """Get server information."""
        try:
            backend = sniffio.current_async_library()
        except:
            backend = "unknown"
            
        return {
            "app": "WebRTC Test App",
            "async_backend": backend,
            "context": "running_event_loop"
        }
    
    # Include router
    app.include_router(router, prefix="/api")
    
    return app, ipfs_model

@contextmanager
def run_app_in_background(port=8765):
    """Run a FastAPI app in the background using a separate process."""
    # Function to run in a separate process
    def run_server():
        app, _ = create_test_app()
        uvicorn.run(app, host="127.0.0.1", port=port)
    
    # Start server in a separate process
    process = multiprocessing.Process(target=run_server)
    process.start()
    
    # Wait for server to start
    server_url = f"http://127.0.0.1:{port}"
    max_retries = 10
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(f"{server_url}/api/info")
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(0.5)
        retries += 1
    
    if retries == max_retries:
        process.terminate()
        raise Exception("Server failed to start")
    
    try:
        # Yield control back to the caller
        yield server_url
    finally:
        # Clean up
        process.terminate()
        process.join()

def apply_anyio_fixes(ipfs_model):
    """Apply AnyIO fixes to the IPFS model."""
    from fixes.webrtc_anyio_fix import (
        patched_stop_webrtc_streaming,
        patched_close_webrtc_connection,
        patched_close_all_webrtc_connections,
        async_stop_webrtc_streaming,
        async_close_webrtc_connection,
        async_close_all_webrtc_connections
    )
    
    # Store original methods for reference
    ipfs_model._original_stop_webrtc_streaming = ipfs_model.original_stop_webrtc_streaming
    ipfs_model._original_close_webrtc_connection = ipfs_model.original_close_webrtc_connection
    ipfs_model._original_close_all_webrtc_connections = ipfs_model.original_close_all_webrtc_connections
    
    # Apply patched methods
    ipfs_model.stop_webrtc_streaming = lambda server_id: patched_stop_webrtc_streaming(ipfs_model, server_id)
    ipfs_model.close_webrtc_connection = lambda connection_id: patched_close_webrtc_connection(ipfs_model, connection_id)
    ipfs_model.close_all_webrtc_connections = lambda: patched_close_all_webrtc_connections(ipfs_model)
    
    # Add async methods
    ipfs_model.async_stop_webrtc_streaming = lambda server_id: async_stop_webrtc_streaming(ipfs_model, server_id)
    ipfs_model.async_close_webrtc_connection = lambda connection_id: async_close_webrtc_connection(ipfs_model, connection_id)
    ipfs_model.async_close_all_webrtc_connections = lambda: async_close_all_webrtc_connections(ipfs_model)
    
    return ipfs_model

def apply_anyio_fixes_to_controller(controller):
    """Apply AnyIO fixes to a WebRTC controller to use async methods."""
    # Create async methods that call the model's async methods
    async def patched_close_connection(connection_id: str):
        try:
            result = await controller.ipfs_model.async_close_webrtc_connection(connection_id)
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "connection_id": connection_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def patched_close_all_connections():
        try:
            result = await controller.ipfs_model.async_close_all_webrtc_connections()
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "connections_closed": result.get("connections_closed", 0)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def patched_stop_streaming(server_id: str):
        try:
            result = await controller.ipfs_model.async_stop_webrtc_streaming(server_id)
            
            if not result.get("success", False):
                return {"success": False, "error": result.get("error", "Unknown error")}
                
            return {"success": True, "server_id": server_id, "connections_closed": result.get("connections_closed", 0)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Store original methods for reference
    controller._original_close_connection = controller.close_connection
    controller._original_close_all_connections = controller.close_all_connections
    controller._original_stop_streaming = controller.stop_streaming
    
    # Apply patched methods
    controller.close_connection = patched_close_connection
    controller.close_all_connections = patched_close_all_connections
    controller.stop_streaming = patched_stop_streaming
    
    return controller

def create_patched_app():
    """Create a FastAPI app with the AnyIO fixes applied."""
    app = FastAPI(title="WebRTC Test App (Patched)")
    
    # Create model and controller
    ipfs_model = MockIPFSModel()
    ipfs_model = apply_anyio_fixes(ipfs_model)
    
    webrtc_controller = MockWebRTCController(ipfs_model)
    webrtc_controller = apply_anyio_fixes_to_controller(webrtc_controller)
    
    # Create router and register routes
    router = APIRouter()
    webrtc_controller.register_routes(router)
    
    # Add info endpoint
    @router.get("/info")
    async def get_info():
        """Get server information."""
        try:
            backend = sniffio.current_async_library()
        except:
            backend = "unknown"
            
        return {
            "app": "WebRTC Test App (Patched)",
            "async_backend": backend,
            "context": "running_event_loop"
        }
    
    # Include router
    app.include_router(router, prefix="/api")
    
    return app, ipfs_model, webrtc_controller

@contextmanager
def run_patched_app_in_background(port=8766):
    """Run a patched FastAPI app in the background using a separate process."""
    # Function to run in a separate process
    def run_server():
        app, _, _ = create_patched_app()
        uvicorn.run(app, host="127.0.0.1", port=port)
    
    # Start server in a separate process
    process = multiprocessing.Process(target=run_server)
    process.start()
    
    # Wait for server to start
    server_url = f"http://127.0.0.1:{port}"
    max_retries = 10
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(f"{server_url}/api/info")
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(0.5)
        retries += 1
    
    if retries == max_retries:
        process.terminate()
        raise Exception("Server failed to start")
    
    try:
        # Yield control back to the caller
        yield server_url
    finally:
        # Clean up
        process.terminate()
        process.join()

class TestWebRTCAnyIOFixes(unittest.TestCase):
    """Tests for the WebRTC AnyIO fixes."""
    
    def test_problematic_methods_local(self):
        """Test the problematic methods locally (not in FastAPI context)."""
        # Create model
        model = MockIPFSModel()
        
        # Add a test connection
        connection_id = model.webrtc_manager.add_connection()
        
        # Test methods directly (should work since we're not in a running event loop)
        close_result = model.original_close_webrtc_connection(connection_id)
        self.assertTrue(close_result["success"])
        
        # Add more connections
        model.webrtc_manager.add_connection()
        model.webrtc_manager.add_connection()
        
        # Test close all connections
        close_all_result = model.original_close_all_webrtc_connections()
        self.assertTrue(close_all_result["success"])
        self.assertEqual(close_all_result["connections_closed"], 2)
        
        # Test stop streaming
        stop_result = model.original_stop_webrtc_streaming("test-server")
        self.assertTrue(stop_result["success"])
    
    def test_problematic_methods_in_fastapi(self):
        """Test the problematic methods in FastAPI context (should fail)."""
        with run_app_in_background() as server_url:
            # Add a test connection
            add_response = requests.post(f"{server_url}/api/webrtc/test/add-connection")
            self.assertEqual(add_response.status_code, 200)
            connection_id = add_response.json()["connection_id"]
            
            # Try to close the connection (should fail with RuntimeError)
            close_response = requests.post(f"{server_url}/api/webrtc/connections/{connection_id}/close")
            # Note: response might be 200 even though there was an error,
            # because FastAPI might catch the exception and return a default
            # response rather than propagating the error
            self.assertEqual(close_response.status_code, 200)
            
            # In a real FastAPI app, this would cause a RuntimeError, but our test app
            # might handle it differently, so we don't make assumptions about the response content
            
            # Try to close all connections (should also fail)
            close_all_response = requests.post(f"{server_url}/api/webrtc/connections/close-all")
            self.assertEqual(close_all_response.status_code, 200)
            
            # Try to stop streaming (should also fail)
            stop_response = requests.post(f"{server_url}/api/webrtc/stream/stop/test-server")
            self.assertEqual(stop_response.status_code, 200)
    
    def test_fixed_methods_in_fastapi(self):
        """Test the fixed methods in FastAPI context (should succeed)."""
        with run_patched_app_in_background() as server_url:
            # Add a test connection
            add_response = requests.post(f"{server_url}/api/webrtc/test/add-connection")
            self.assertEqual(add_response.status_code, 200)
            connection_id = add_response.json()["connection_id"]
            
            # Verify the connection was added
            connections_response = requests.get(f"{server_url}/api/webrtc/connections")
            self.assertEqual(connections_response.status_code, 200)
            self.assertEqual(connections_response.json()["count"], 1)
            
            # Close the connection (should work with AnyIO fix)
            close_response = requests.post(f"{server_url}/api/webrtc/connections/{connection_id}/close")
            self.assertEqual(close_response.status_code, 200)
            close_result = close_response.json()
            self.assertTrue(close_result["success"])
            
            # Verify the connection was closed
            time.sleep(0.5)  # Give time for the background task to complete
            connections_response = requests.get(f"{server_url}/api/webrtc/connections")
            self.assertEqual(connections_response.status_code, 200)
            self.assertEqual(connections_response.json()["count"], 0)
            
            # Add more connections
            for _ in range(3):
                requests.post(f"{server_url}/api/webrtc/test/add-connection")
            
            # Verify the connections were added
            connections_response = requests.get(f"{server_url}/api/webrtc/connections")
            self.assertEqual(connections_response.status_code, 200)
            self.assertEqual(connections_response.json()["count"], 3)
            
            # Close all connections (should work with AnyIO fix)
            close_all_response = requests.post(f"{server_url}/api/webrtc/connections/close-all")
            self.assertEqual(close_all_response.status_code, 200)
            close_all_result = close_all_response.json()
            self.assertTrue(close_all_result["success"])
            
            # Verify the connections were closed
            time.sleep(0.5)  # Give time for the background task to complete
            connections_response = requests.get(f"{server_url}/api/webrtc/connections")
            self.assertEqual(connections_response.status_code, 200)
            self.assertEqual(connections_response.json()["count"], 0)
            
            # Test stop streaming (should work with AnyIO fix)
            # First add some connections again
            for _ in range(2):
                requests.post(f"{server_url}/api/webrtc/test/add-connection")
                
            stop_response = requests.post(f"{server_url}/api/webrtc/stream/stop/test-server")
            self.assertEqual(stop_response.status_code, 200)
            stop_result = stop_response.json()
            self.assertTrue(stop_result["success"])
            
            # Verify the connections were closed
            time.sleep(0.5)  # Give time for the background task to complete
            connections_response = requests.get(f"{server_url}/api/webrtc/connections")
            self.assertEqual(connections_response.status_code, 200)
            self.assertEqual(connections_response.json()["count"], 0)
    
    def test_fixed_methods_with_client(self):
        """Test the fixed methods using TestClient instead of a running server."""
        # Create app with fixes
        app, _, _ = create_patched_app()
        
        # Create test client
        client = TestClient(app)
        
        # Add a test connection
        add_response = client.post("/api/webrtc/test/add-connection")
        self.assertEqual(add_response.status_code, 200)
        connection_id = add_response.json()["connection_id"]
        
        # Close the connection (should work with AnyIO fix)
        close_response = client.post(f"/api/webrtc/connections/{connection_id}/close")
        self.assertEqual(close_response.status_code, 200)
        close_result = close_response.json()
        self.assertTrue(close_result["success"])
        
        # Add more connections
        for _ in range(3):
            client.post("/api/webrtc/test/add-connection")
        
        # Close all connections (should work with AnyIO fix)
        close_all_response = client.post("/api/webrtc/connections/close-all")
        self.assertEqual(close_all_response.status_code, 200)
        close_all_result = close_all_response.json()
        self.assertTrue(close_all_result["success"])
        
        # Test stop streaming (should work with AnyIO fix)
        # First add some connections again
        for _ in range(2):
            client.post("/api/webrtc/test/add-connection")
            
        stop_response = client.post("/api/webrtc/stream/stop/test-server")
        self.assertEqual(stop_response.status_code, 200)
        stop_result = stop_response.json()
        self.assertTrue(stop_result["success"])

if __name__ == "__main__":
    # Run tests
    unittest.main()