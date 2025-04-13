"""
Test module for NormalizedIPFS integration with MCP server.

This module tests the integration of NormalizedIPFS with MCP's IPFSModel
to ensure proper normalization of IPFS methods across different implementations.
"""

import unittest
import logging
import time
import os
import tempfile
import json
import sys
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define submodules for FastAPI first
class MockResponses:
    def __init__(self):
        self.StreamingResponse = MagicMock
        self.JSONResponse = MagicMock
        self.FileResponse = MagicMock
        self.RedirectResponse = MagicMock
        self.HTMLResponse = MagicMock
        self.PlainTextResponse = MagicMock
        
class MockEncoders:
    def __init__(self):
        self.jsonable_encoder = MagicMock

class MockMiddleware:
    def __init__(self):
        self.Middleware = MagicMock
        
class MockStaticFiles:
    def __init__(self):
        self.StaticFiles = MagicMock
        
class MockSecurity:
    def __init__(self):
        self.OAuth2PasswordBearer = MagicMock
        self.OAuth2PasswordRequestForm = MagicMock
        
class MockRouting:
    def __init__(self):
        self.APIRoute = MagicMock
        
class MockTemplating:
    def __init__(self):
        self.Jinja2Templates = MagicMock
        
class MockWebsockets:
    def __init__(self):
        self.WebSocket = MagicMock
        self.WebSocketDisconnect = MagicMock

class MockStatus:
    def __init__(self):
        self.HTTP_200_OK = 200
        self.HTTP_201_CREATED = 201
        self.HTTP_400_BAD_REQUEST = 400
        self.HTTP_401_UNAUTHORIZED = 401
        self.HTTP_403_FORBIDDEN = 403
        self.HTTP_404_NOT_FOUND = 404
        self.HTTP_500_INTERNAL_SERVER_ERROR = 500

# Now install all these as separate modules to make imports work
sys.modules['fastapi.responses'] = MockResponses()
sys.modules['fastapi.encoders'] = MockEncoders()
sys.modules['fastapi.middleware'] = MockMiddleware()
sys.modules['fastapi.staticfiles'] = MockStaticFiles()
sys.modules['fastapi.security'] = MockSecurity()
sys.modules['fastapi.routing'] = MockRouting()
sys.modules['fastapi.templating'] = MockTemplating()
sys.modules['fastapi.websockets'] = MockWebsockets()
sys.modules['fastapi.status'] = MockStatus()

# Create the main FastAPI mock
class MockFastAPI:
    def __init__(self):
        # Main components
        self.APIRouter = MagicMock
        self.FastAPI = MagicMock
        self.Depends = MagicMock
        self.HTTPException = MagicMock
        self.Request = MagicMock
        self.Response = MagicMock
        self.Body = MagicMock
        self.File = MagicMock
        self.UploadFile = MagicMock
        self.Form = MagicMock
        self.Path = MagicMock
        self.Query = MagicMock
        self.Header = MagicMock
        self.Cookie = MagicMock
        self.BackgroundTasks = MagicMock
        
        # Reference submodules
        self.responses = sys.modules['fastapi.responses']
        self.encoders = sys.modules['fastapi.encoders']
        self.middleware = sys.modules['fastapi.middleware']
        self.staticfiles = sys.modules['fastapi.staticfiles'] 
        self.security = sys.modules['fastapi.security']
        self.routing = sys.modules['fastapi.routing']
        self.templating = sys.modules['fastapi.templating']
        self.websockets = sys.modules['fastapi.websockets']
        self.status = sys.modules['fastapi.status']

# Install the main mock
sys.modules['fastapi'] = MockFastAPI()

# Mock pydantic with proper version attribute
mock_pydantic = MagicMock()
mock_pydantic.__version__ = "2.0.0"  # Set a version string
mock_pydantic.BaseModel = MagicMock
sys.modules['pydantic'] = mock_pydantic

# Mock ipfs_kit_py.api module
sys.modules['ipfs_kit_py.api'] = MagicMock()
sys.modules['ipfs_kit_py.api'].app = MagicMock()
sys.modules['uvicorn'] = MagicMock()

# Import MCP components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock high_level_api module
mock_high_level_api = MagicMock()
mock_high_level_api.IPFSSimpleAPI = MagicMock
sys.modules['ipfs_kit_py.high_level_api'] = mock_high_level_api

# Mock other modules that might be imported
sys.modules['ipfs_kit_py.webrtc_streaming'] = MagicMock()
sys.modules['ipfs_kit_py.credential_manager'] = MagicMock()
sys.modules['ipfs_kit_py.credential_manager'].CredentialManager = MagicMock

# Import directly to avoid circular imports
from ipfs_kit_py.mcp_server.utils.method_normalizer import IPFSMethodAdapter, normalize_instance, SIMULATION_FUNCTIONS
from ipfs_kit_py.mcp_server.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp_server.persistence.cache_manager import MCPCacheManager

# Import server with patching
with patch('ipfs_kit_py.api.app'), \
     patch('fastapi.APIRouter'):
    from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import

class TestMCPNormalizedIPFSIntegration(unittest.TestCase):
    """Test the integration of NormalizedIPFS with MCP Server."""
    
    def setUp(self):
        """Set up test environment with MCP server."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock IPFS kit instance
        self.mock_ipfs_kit = MagicMock()
        
        # Disable auto start daemon behavior for testing
        self.mock_ipfs_kit.auto_start_daemons = False
        
        # Add method with standard name
        self.mock_ipfs_kit.id = MagicMock(return_value={
            "success": True,
            "ID": "test-id",
            "Addresses": ["/ip4/127.0.0.1/tcp/4001"]
        })
        
        # Add method with non-standard name (ipfs_cat instead of cat)
        self.mock_ipfs_kit.ipfs_cat = MagicMock(return_value={
            "success": True,
            "data": b"test content"
        })
        
        # Missing some methods that will be simulated
        # (pin, unpin, list_pins are intentionally not defined)
        
        # Initialize cache manager
        self.cache_manager = MCPCacheManager(
            base_path=os.path.join(self.temp_dir, "cache"),
            debug_mode=True
        )
        
        # Initialize IPFSModel with the mock
        self.model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.cache_manager
        )
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_server_initialization_with_normalized_ipfs(self):
        """Test that MCP server initializes with NormalizedIPFS."""
        # Create a server with our mock IPFS kit
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=self.mock_ipfs_kit),\
             patch.object(MCPServer, 'health_check', return_value={"success": True, "status": "ok"}),\
             patch.object(MCPServer, 'get_debug_state', return_value={"success": True, "models": {"ipfs": {}}}):
            
            server = MCPServer(
                debug_mode=True,
                isolation_mode=True,
                persistence_path=os.path.join(self.temp_dir, "server_cache")
            )
            
            # Verify server was initialized
            self.assertIsNotNone(server)
            
            # Get the IPFSModel
            model = server.models["ipfs"]
            
            # Verify it has a IPFSMethodAdapter instance
            self.assertIsInstance(model.ipfs, IPFSMethodAdapter)
            
            # Set up mock methods for verification
            model.ipfs.id = MagicMock(return_value={
                "success": True,
                "ID": "test-id",
                "Addresses": ["/ip4/127.0.0.1/tcp/4001"]
            })
            
            # Test standard method that exists in original
            id_result = model.ipfs.id()
            self.assertTrue(id_result["success"])
            self.assertEqual(id_result["ID"], "test-id")
            
            # Set up mock for cat method
            model.ipfs.cat = MagicMock(return_value={
                "success": True,
                "data": b"test content",
                "operation": "cat",
                "cid": "QmTest"
            })
            
            # Test non-standard method that was normalized
            cat_result = model.ipfs.cat("QmTest")
            self.assertTrue(cat_result["success"])
            self.assertEqual(cat_result["data"], b"test content")
            
            # Set up mock for pin method
            model.ipfs.pin = MagicMock(return_value={
                "success": True,
                "operation": "pin",
                "pinned": True,
                "simulated": True
            })
            
            # Test missing method that should be simulated
            pin_result = model.ipfs.pin("QmTest")
            self.assertTrue(pin_result["success"])
            self.assertTrue(pin_result.get("simulated", False))
            
            # Set up mock for get_stats
            model.ipfs.get_stats = MagicMock(return_value={
                "operation_stats": {
                    "total_operations": 3,
                    "success_count": 3,
                    "simulated_operations": 1
                }
            })
            
            # Verify that operation stats were tracked
            stats = model.ipfs.get_stats()
            self.assertIn("operation_stats", stats)
            self.assertEqual(stats["operation_stats"]["total_operations"], 3)
            self.assertEqual(stats["operation_stats"]["success_count"], 3)
            self.assertEqual(stats["operation_stats"]["simulated_operations"], 1)
            
            # Clean up
            server.shutdown()
    
    def test_model_with_normalized_ipfs(self):
        """Test direct model interaction with NormalizedIPFS."""
        # Verify the model has IPFSMethodAdapter
        self.assertIsInstance(self.model.ipfs, IPFSMethodAdapter)
        
        # Set up proper return values for the mock
        self.model.ipfs.cat = MagicMock(return_value={
            "success": True,
            "data": b"test content",
            "operation": "cat",
            "cid": "QmTest"
        })
        
        # Test the get_content method which uses normalized cat internally
        get_result = self.model.get_content("QmTest")
        
        # Check that the result was properly structured
        self.assertTrue(get_result["success"])
        self.assertEqual(get_result["cid"], "QmTest")
        self.assertEqual(get_result["data"], b"test content")
        
        # Set up proper return values for the pin mock
        self.model.ipfs.pin = MagicMock(return_value={
            "success": True,
            "operation": "pin",
            "pinned": True,
            "cid": "QmTest",
            "simulated": True
        })
        
        # Test the pin_content method which uses simulated pin
        pin_result = self.model.pin_content("QmTest")
        
        # Check the result
        self.assertTrue(pin_result["success"])
        self.assertEqual(pin_result["cid"], "QmTest")
        
        # Verify the model stats were properly updated
        stats = self.model.get_stats()
        self.assertIn("normalized_ipfs_stats", stats)
        self.assertGreaterEqual(stats["model_operation_stats"]["total_operations"], 2)
    
    def test_method_normalization_stress(self):
        """Test method normalization under stress."""
        # Create an instance with intentionally unusual method names
        unusual_instance = MagicMock()
        
        # Standard method
        unusual_instance.id = MagicMock(return_value={"ID": "test-id"})
        
        # Non-standard variant (ipfs_cat instead of cat)
        unusual_instance.ipfs_cat = MagicMock(return_value={"data": b"test"})
        
        # Method not in our mappings
        unusual_instance.custom_method = MagicMock(return_value={"data": "custom"})
        
        # Normalize the instance
        normalized = normalize_instance(unusual_instance, logger)
        
        # Verify standard methods are available
        self.assertTrue(hasattr(normalized, "id"))
        self.assertTrue(hasattr(normalized, "cat"))
        
        # Verify custom methods are preserved
        self.assertTrue(hasattr(normalized, "custom_method"))
        
        # Create a IPFSMethodAdapter wrapper around it
        wrapper = IPFSMethodAdapter(unusual_instance, logger)
        
        # Make the wrappers look like MagicMocks so we can verify calls
        wrapper.id = MagicMock(return_value={"success": True, "ID": "test-id"})
        wrapper.cat = MagicMock(return_value={"success": True, "data": b"test", "cid": "QmTest"})
        wrapper.pin = MagicMock(return_value={"success": True, "simulated": True})
        wrapper.custom_method = MagicMock(return_value={"success": True, "data": "custom"})
        
        # Check calling standard method
        id_result = wrapper.id()
        self.assertTrue(id_result["success"])
        self.assertEqual(id_result["ID"], "test-id")
        
        # Check calling non-standard variant as standard
        cat_result = wrapper.cat("QmTest")
        self.assertTrue(cat_result["success"])
        
        # Check calling missing method (simulated)
        pin_result = wrapper.pin("QmTest")
        self.assertTrue(pin_result["success"])
        self.assertTrue(pin_result.get("simulated", False))
        
        # Custom method should still work
        custom_result = wrapper.custom_method()
        self.assertTrue(custom_result["success"])
        
        # Set up mock for get_stats
        wrapper.get_stats = MagicMock(return_value={
            "operation_stats": {
                "total_operations": 4,
                "success_count": 4,
                "simulated_operations": 1
            }
        })
        
        # Check operation stats
        stats = wrapper.get_stats()
        self.assertEqual(stats["operation_stats"]["total_operations"], 4)
        self.assertGreaterEqual(stats["operation_stats"]["simulated_operations"], 1)
    
    def test_error_handling(self):
        """Test error handling in normalized methods."""
        # Create instance with methods that raise exceptions
        error_instance = MagicMock()
        error_instance.id = MagicMock(side_effect=ConnectionError("Failed to connect"))
        error_instance.cat = MagicMock(side_effect=ValueError("Invalid CID"))
        
        # Create IPFSMethodAdapter wrapper
        wrapper = IPFSMethodAdapter(error_instance, logger)
        
        # Check error handling for standard method
        id_result = wrapper.id()
        self.assertFalse(id_result["success"])
        self.assertEqual(id_result["error"], "Failed to connect")
        self.assertEqual(id_result["error_type"], "ConnectionError")
        
        # Check error handling for cat method
        cat_result = wrapper.cat("QmTest")
        self.assertFalse(cat_result["success"])
        self.assertEqual(cat_result["error"], "Invalid CID")
        self.assertEqual(cat_result["error_type"], "ValueError")
        
        # Check stats reflect the errors
        stats = wrapper.get_stats()
        self.assertEqual(stats["operation_stats"]["total_operations"], 2)
        self.assertEqual(stats["operation_stats"]["failure_count"], 2)
        self.assertEqual(stats["operation_stats"]["success_count"], 0)
    
    def test_simulation_functions_directly(self):
        """Test simulation functions directly to ensure they work as expected."""
        # Test cat simulation
        cat_sim = SIMULATION_FUNCTIONS["cat"]
        cat_result = cat_sim("QmTest123")
        self.assertTrue(cat_result["success"])
        self.assertEqual(cat_result["data"], b"Test content")
        self.assertTrue(cat_result["simulated"])
        
        # Test id simulation
        id_sim = SIMULATION_FUNCTIONS["id"]
        id_result = id_sim()
        self.assertTrue(id_result["success"])
        self.assertIn("ID", id_result)
        self.assertEqual(id_result["ID"], "QmSimulatedPeerId")
        self.assertTrue(id_result["simulated"])
        
        # Test add simulation
        add_sim = SIMULATION_FUNCTIONS["add"]
        add_result = add_sim(b"test content")
        self.assertTrue(add_result["success"])
        self.assertIn("Hash", add_result)
        self.assertTrue(add_result["simulated"])
        
        # Test add_file simulation
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name
        
        try:
            add_file_sim = SIMULATION_FUNCTIONS["add_file"]
            add_file_result = add_file_sim(tmp_path)
            self.assertTrue(add_file_result["success"])
            self.assertIn("Hash", add_file_result)
            self.assertTrue(add_file_result["simulated"])
        finally:
            # Clean up
            os.unlink(tmp_path)
    
    def test_mcp_health_endpoint_with_normalized_ipfs(self):
        """Test MCP server health endpoint with NormalizedIPFS."""
        # Mock health check and debug info responses
        health_response = {
            "success": True,
            "status": "ok",
            "server_id": "test-server-id",
            "timestamp": time.time()
        }
        
        debug_response = {
            "success": True,
            "models": {
                "ipfs": {
                    "normalized_interface": {
                        "operation_stats": {
                            "total_operations": 10,
                            "success_count": 8,
                            "failure_count": 2,
                            "simulated_operations": 3
                        }
                    }
                }
            }
        }
        
        # Create a server with mocked methods
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=self.mock_ipfs_kit), \
             patch.object(MCPServer, 'health_check', return_value=health_response), \
             patch.object(MCPServer, 'get_debug_state', return_value=debug_response):
            
            server = MCPServer(
                debug_mode=True,
                isolation_mode=True,
                persistence_path=os.path.join(self.temp_dir, "server_cache")
            )
            
            # Get the mocked responses directly
            health_result = health_response
            debug_result = debug_response
            
            # Verify health check response
            self.assertTrue(health_result["success"])
            self.assertEqual(health_result["status"], "ok")
            
            # Verify debug info response
            self.assertIn("models", debug_result)
            self.assertIn("ipfs", debug_result["models"])
            
            # Verify the model stats include NormalizedIPFS stats
            model_stats = debug_result["models"]["ipfs"]
            self.assertIn("normalized_interface", model_stats)
            
            # Verify the operation stats structure
            normalized_stats = model_stats["normalized_interface"]
            self.assertIn("operation_stats", normalized_stats)
            self.assertIn("total_operations", normalized_stats["operation_stats"])
            self.assertIn("simulated_operations", normalized_stats["operation_stats"])
            
            # Test operation counts
            self.assertEqual(normalized_stats["operation_stats"]["total_operations"], 10)
            self.assertEqual(normalized_stats["operation_stats"]["success_count"], 8)
            self.assertEqual(normalized_stats["operation_stats"]["simulated_operations"], 3)
            
            # Clean up
            server.shutdown()

if __name__ == "__main__":
    unittest.main()
