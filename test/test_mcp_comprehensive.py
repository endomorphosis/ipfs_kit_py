"""
Comprehensive test suite for MCP server and tools.

This module contains tests for the Model-Controller-Persistence server
architecture and associated tools.
"""

import os
import sys
import pytest
import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our direct fixes before other imports if available
try:
    from direct_mcp_fix import apply_mcp_fixes
    logger.info("Loaded direct MCP fixes")
    apply_mcp_fixes()
except ImportError:
    logger.warning("MCP direct fixes not available, tests may fail")
except Exception as e:
    logger.error(f"Error applying MCP fixes: {e}")

# Try to import the modules we need
try:
    from ipfs_kit_py.mcp.server import MCPServer
    from ipfs_kit_py.mcp.controller import MCPController
    from ipfs_kit_py.mcp.model import MCPModel
    from ipfs_kit_py.mcp.tools import MCPTools, register_tool
    from ipfs_kit_py.mcp.storage_manager import BackendStorage
except ImportError as e:
    logger.error(f"Error importing MCP modules: {e}")
    # Create mock versions for testing
    class MCPServer:
        def __init__(self, config=None):
            self.config = config or {}
            self.controller = MagicMock()
            self.model = MagicMock()
        
        def start(self):
            return True
        
        def stop(self):
            return True
    
    class MCPController:
        def __init__(self, model=None):
            self.model = model or MagicMock()
    
    class MCPModel:
        def __init__(self):
            pass
    
    class MCPTools:
        @staticmethod
        def get_registered_tools():
            return {}
    
    def register_tool(func):
        return func
    
    class BackendStorage:
        def __init__(self, config=None):
            self.config = config or {}

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture
def mock_model():
    """Create a mocked MCP model."""
    return MagicMock(spec=MCPModel)

@pytest.fixture
def mock_controller():
    """Create a mocked MCP controller."""
    return MagicMock(spec=MCPController)

@pytest.fixture
def test_mcp_config(temp_dir):
    """Create a test configuration for MCP server."""
    config_path = temp_dir / "mcp_test_config.json"
    config = {
        "server": {
            "host": "localhost",
            "port": 8000,
            "debug": True,
            "log_level": "DEBUG"
        },
        "storage": {
            "backends": [
                {
                    "type": "ipfs",
                    "id": "local",
                    "api_url": "http://localhost:5001/api/v0",
                    "gateway_url": "http://localhost:8080/ipfs"
                }
            ],
            "default_backend": "local"
        },
        "tools": {
            "enabled": True,
            "register_all": True
        },
        "test_mode": True
    }
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    return config_path

# Test MCP Server
class TestMCPServer:
    
    @patch('ipfs_kit_py.mcp.server.MCPController')
    @patch('ipfs_kit_py.mcp.server.MCPModel')
    def test_server_init(self, mock_model_class, mock_controller_class, test_mcp_config):
        """Test MCP server initialization."""
        mock_model_instance = MagicMock()
        mock_controller_instance = MagicMock()
        
        mock_model_class.return_value = mock_model_instance
        mock_controller_class.return_value = mock_controller_instance
        
        server = MCPServer(config_path=test_mcp_config)
        
        assert server is not None
        assert server.model == mock_model_instance
        assert server.controller == mock_controller_instance
    
    @patch('ipfs_kit_py.mcp.server.uvicorn.run')
    def test_server_start(self, mock_uvicorn_run):
        """Test starting the MCP server."""
        server = MCPServer(config={"server": {"host": "localhost", "port": 8000}})
        server.start()
        
        mock_uvicorn_run.assert_called_once()
    
    def test_server_initialization_endpoint(self):
        """Test the server initialization endpoint."""
        server = MCPServer(config={"test_mode": True})
        
        # This should be mocked or we need a test client
        # For now, we'll just verify the server object has the expected attribute
        assert hasattr(server, "app")

# Test MCP Tools
class TestMCPTools:
    
    def test_tools_registration(self):
        """Test tool registration mechanism."""
        # Register a test tool
        @register_tool
        def test_tool(input_data: str) -> str:
            """Test tool that echoes input."""
            return f"Echo: {input_data}"
        
        # Get registered tools
        tools = MCPTools.get_registered_tools()
        
        # Check if our test tool is registered
        assert "test_tool" in tools
        
        # Check if the tool works
        result = tools["test_tool"]("hello")
        assert result == "Echo: hello"
    
    def test_tools_documentation(self):
        """Test tool documentation."""
        # Register a test tool with documentation
        @register_tool
        def documented_tool(input_data: str) -> dict:
            """
            A documented test tool.
            
            Args:
                input_data: The input string to process
                
            Returns:
                dict: A dictionary with the processed result
            """
            return {"result": f"Processed: {input_data}"}
        
        # Get registered tools
        tools = MCPTools.get_registered_tools()
        
        # Check if our test tool is registered
        assert "documented_tool" in tools
        
        # Check if documentation is preserved
        import inspect
        doc = inspect.getdoc(tools["documented_tool"])
        assert "A documented test tool" in doc
        assert "Args:" in doc
        assert "Returns:" in doc

# Test MCP Storage Backends
class TestMCPStorage:
    
    def test_backend_registration(self):
        """Test storage backend registration."""
        config = {
            "storage": {
                "backends": [
                    {
                        "type": "ipfs",
                        "id": "local",
                        "api_url": "http://localhost:5001/api/v0"
                    },
                    {
                        "type": "s3",
                        "id": "test-s3",
                        "endpoint_url": "http://localhost:9000",
                        "access_key": "test",
                        "secret_key": "test"
                    }
                ],
                "default_backend": "local"
            }
        }
        
        with patch('ipfs_kit_py.mcp.storage_manager.backend_registry.get_backend') as mock_get_backend:
            mock_backend = MagicMock()
            mock_get_backend.return_value = mock_backend
            
            storage = BackendStorage(config)
            
            assert storage is not None
            assert "local" in storage.backends
            assert "test-s3" in storage.backends
            assert storage.default_backend == "local"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
