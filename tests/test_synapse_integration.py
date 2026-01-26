#!/usr/bin/env python3
"""
Comprehensive tests for Synapse SDK integration with IPFS Kit.

This test suite covers:
- Installation and configuration processes
- Storage backend wrapper functionality
- MCP server integration
- FSSpec integration
- End-to-end workflows

Run with: python -m pytest tests/test_synapse_integration.py -v
"""

import os
import sys
import json
import anyio
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import modules to test
try:
    from ipfs_kit_py.install_synapse_sdk import install_synapse_sdk
    from ipfs_kit_py.config_synapse_sdk import config_synapse_sdk
    from ipfs_kit_py.synapse_storage import synapse_storage, JavaScriptBridge
    SYNAPSE_MODULES_AVAILABLE = True
except ImportError as e:
    SYNAPSE_MODULES_AVAILABLE = False
    IMPORT_ERROR = str(e)


class TestSynapseInstallation:
    """Test Synapse SDK installation processes."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_installer_initialization(self):
        """Test that the installer can be initialized."""
        metadata = {
            "force": False,
            "verbose": True,
            "skip_node_check": True  # Skip Node.js check for testing
        }
        
        installer = install_synapse_sdk(metadata=metadata)
        
        assert installer is not None
        assert installer.metadata == metadata
        assert installer.force == False
        assert installer.verbose == True
        assert installer.skip_node_check == True
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_architecture_detection(self):
        """Test architecture detection for Node.js downloads."""
        installer = install_synapse_sdk()
        arch = installer._detect_architecture()
        
        assert arch in ['x64', 'arm64', 'armv7l']
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_node_version_comparison(self):
        """Test version comparison functionality."""
        installer = install_synapse_sdk()
        
        # Test version comparisons
        assert installer._compare_versions("16.0.0", "15.0.0") == 1
        assert installer._compare_versions("16.0.0", "16.0.0") == 0
        assert installer._compare_versions("15.0.0", "16.0.0") == -1
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_js_wrapper_creation(self):
        """Test JavaScript wrapper file creation."""
        installer = install_synapse_sdk(metadata={"skip_node_check": True})
        
        # Create JS wrapper files
        success = installer.create_js_wrapper_files()
        assert success == True
        
        # Check that files were created
        js_dir = os.path.join(installer.this_dir, "js")
        assert os.path.exists(js_dir)
        assert os.path.exists(os.path.join(js_dir, "synapse_wrapper.js"))
        assert os.path.exists(os.path.join(js_dir, "package.json"))
        
        # Verify package.json content
        with open(os.path.join(js_dir, "package.json"), 'r') as f:
            package_json = json.load(f)
        
        assert "@filoz/synapse-sdk" in package_json["dependencies"]
        assert "ethers" in package_json["dependencies"]
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    @patch('subprocess.run')
    def test_node_version_check(self, mock_subprocess):
        """Test Node.js version checking."""
        installer = install_synapse_sdk()
        
        # Mock successful Node.js check
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "v18.17.0\n"
        
        installed, version = installer._check_node_installed()
        
        assert installed == True
        assert version == "18.17.0"
        
        # Mock failed Node.js check
        mock_subprocess.side_effect = FileNotFoundError()
        
        installed, version = installer._check_node_installed()
        
        assert installed == False
        assert version is None


class TestSynapseConfiguration:
    """Test Synapse SDK configuration management."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_config_initialization(self):
        """Test configuration manager initialization."""
        metadata = {
            "network": "calibration",
            "auto_approve": True,
            "with_cdn": False
        }
        
        config_mgr = config_synapse_sdk(metadata=metadata)
        
        assert config_mgr is not None
        assert config_mgr.config["network"] == "calibration"
        assert config_mgr.config["payment"]["auto_approve"] == True
        assert config_mgr.config["storage"]["with_cdn"] == False
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_environment_variable_override(self):
        """Test environment variable configuration override."""
        # Set environment variables
        os.environ["SYNAPSE_NETWORK"] = "mainnet"
        os.environ["SYNAPSE_WITH_CDN"] = "true"
        os.environ["SYNAPSE_MAX_FILE_SIZE"] = "1000000"
        
        try:
            config_mgr = config_synapse_sdk()
            
            assert config_mgr.config["network"] == "mainnet"
            assert config_mgr.config["storage"]["with_cdn"] == True
            assert config_mgr.config["storage"]["max_file_size"] == 1000000
        finally:
            # Clean up environment
            for key in ["SYNAPSE_NETWORK", "SYNAPSE_WITH_CDN", "SYNAPSE_MAX_FILE_SIZE"]:
                os.environ.pop(key, None)
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_network_configuration(self):
        """Test network-specific configuration."""
        # Test calibration network
        config_mgr = config_synapse_sdk(metadata={"network": "calibration"})
        network_config = config_mgr.get_network_config()
        
        assert network_config["network"] == "calibration"
        assert network_config["chain_id"] == 314159
        assert "calibration" in network_config["rpc_url"]
        
        # Test mainnet network
        config_mgr = config_synapse_sdk(metadata={"network": "mainnet"})
        network_config = config_mgr.get_network_config()
        
        assert network_config["network"] == "mainnet"
        assert network_config["chain_id"] == 314
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid configuration
        config_mgr = config_synapse_sdk(metadata={"network": "calibration"})
        assert config_mgr.validate_configuration() == True
        
        # Invalid network
        config_mgr = config_synapse_sdk(metadata={"network": "invalid_network"})
        # Should default to calibration and still be valid
        assert config_mgr.validate_configuration() == True
        assert config_mgr.config["network"] == "calibration"
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_js_bridge_config_format(self):
        """Test JavaScript bridge configuration formatting."""
        os.environ["SYNAPSE_PRIVATE_KEY"] = "0x1234567890abcdef"
        
        try:
            config_mgr = config_synapse_sdk(metadata={
                "network": "calibration",
                "authorization": "Bearer test_token"
            })
            
            js_config = config_mgr.get_js_bridge_config()
            
            assert js_config["network"] == "calibration"
            assert js_config["chainId"] == 314159
            assert js_config["privateKey"] == "0x1234567890abcdef"
            assert js_config["authorization"] == "Bearer test_token"
            assert "payment" in js_config
            assert "storage" in js_config
        finally:
            os.environ.pop("SYNAPSE_PRIVATE_KEY", None)


class TestSynapseStorage:
    """Test Synapse storage backend wrapper."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create mock JavaScript wrapper
        js_dir = os.path.join(self.temp_dir, "js")
        os.makedirs(js_dir, exist_ok=True)
        
        mock_wrapper = """
console.log(JSON.stringify({
    success: true,
    method: "test",
    message: "Mock JavaScript wrapper"
}));
"""
        with open(os.path.join(js_dir, "synapse_wrapper.js"), 'w') as f:
            f.write(mock_wrapper)
        
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_javascript_bridge_initialization(self):
        """Test JavaScript bridge initialization."""
        wrapper_path = os.path.join(self.temp_dir, "js", "synapse_wrapper.js")
        
        bridge = JavaScriptBridge(wrapper_path)
        assert bridge.wrapper_script_path == wrapper_path
        assert bridge.initialized == False
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_javascript_bridge_missing_script(self):
        """Test JavaScript bridge with missing script."""
        with pytest.raises(Exception):  # Should raise SynapseConfigurationError
            JavaScriptBridge("/nonexistent/path/script.js")
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    @patch('ipfs_kit_py.synapse_storage.config_synapse_sdk')
    def test_storage_initialization(self, mock_config_class):
        """Test storage interface initialization."""
        # Mock configuration
        mock_config = Mock()
        mock_config.setup_configuration.return_value = True
        mock_config.get_configuration.return_value = {"network": "calibration"}
        mock_config.get_network_config.return_value = {"network": "calibration", "chain_id": 314159}
        mock_config.get_payment_config.return_value = {"auto_approve": True}
        mock_config.get_storage_config.return_value = {"with_cdn": False, "max_file_size": 209715200}
        mock_config.get_js_bridge_config.return_value = {"network": "calibration"}
        mock_config.validate_configuration.return_value = True
        
        mock_config_class.return_value = mock_config
        
        # Mock JavaScript wrapper finding
        with patch.object(synapse_storage, '_find_wrapper_script') as mock_find:
            mock_find.return_value = os.path.join(self.temp_dir, "js", "synapse_wrapper.js")
            
            storage = synapse_storage(metadata={"network": "calibration"})
            
            assert storage is not None
            assert storage.synapse_initialized == False
            assert storage.storage_service_created == False
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_storage_status(self):
        """Test storage status reporting."""
        with patch('ipfs_kit_py.synapse_storage.config_synapse_sdk'), \
             patch.object(synapse_storage, '_find_wrapper_script') as mock_find:
            
            mock_find.return_value = os.path.join(self.temp_dir, "js", "synapse_wrapper.js")
            
            storage = synapse_storage(metadata={"network": "calibration"})
            status = storage.get_status()
            
            assert "synapse_initialized" in status
            assert "storage_service_created" in status
            assert "network" in status
            assert "configuration_valid" in status


class MockJavaScriptBridge:
    """Mock JavaScript bridge for testing storage operations."""
    
    def __init__(self, wrapper_script_path):
        self.wrapper_script_path = wrapper_script_path
        self.initialized = False
        self.storage_created = False
    
    async def initialize(self, config):
        self.initialized = True
        return {"success": True, "network": config.get("network", "calibration")}
    
    async def call_method(self, method, params=None):
        params = params or {}
        
        if method == "createStorage":
            self.storage_created = True
            return {
                "success": True,
                "proofSetId": 42,
                "storageProvider": "0x1234567890abcdef"
            }
        
        elif method == "storeData":
            return {
                "success": True,
                "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq",
                "size": len(params.get("data", "")),
                "rootId": 1
            }
        
        elif method == "retrieveData":
            # Return base64 encoded test data
            import base64
            test_data = b"Hello, Synapse SDK!"
            return {
                "success": True,
                "data": base64.b64encode(test_data).decode()
            }
        
        elif method == "getBalance":
            return {
                "success": True,
                "walletBalance": "1000000000000000000",  # 1 USDFC
                "contractBalance": "500000000000000000"   # 0.5 USDFC
            }
        
        elif method == "getStorageInfo":
            return {
                "success": True,
                "info": {
                    "providers": [
                        {
                            "owner": "0x1234567890abcdef",
                            "pdpUrl": "https://test-provider.example.com",
                            "pieceRetrievalUrl": "https://test-provider.example.com/retrieve"
                        }
                    ],
                    "pricing": {
                        "noCDN": {"perTiBPerMonth": "1000000000000000000"},
                        "withCDN": {"perTiBPerMonth": "1500000000000000000"}
                    }
                }
            }
        
        elif method == "getPieceStatus":
            return {
                "success": True,
                "status": {
                    "exists": True,
                    "proofSetLastProven": 1234567890,
                    "proofSetNextProofDue": 1234567890 + 3600,
                    "inChallengeWindow": False
                }
            }
        
        else:
            return {"success": False, "error": f"Unknown method: {method}"}


class TestSynapseStorageOperations:
    """Test Synapse storage operations with mocked JavaScript bridge."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_storage(self):
        """Create a mocked storage instance."""
        if not SYNAPSE_MODULES_AVAILABLE:
            pytest.skip(f"Synapse modules not available: {IMPORT_ERROR}")
        
        with patch('ipfs_kit_py.synapse_storage.config_synapse_sdk'), \
             patch.object(synapse_storage, '_find_wrapper_script') as mock_find, \
             patch.object(synapse_storage, 'JavaScriptBridge', MockJavaScriptBridge):
            
            mock_find.return_value = os.path.join(self.temp_dir, "synapse_wrapper.js")
            
            storage = synapse_storage(metadata={"network": "calibration"})
            return storage
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_store_data(self, mock_storage):
        """Test data storage operation."""
        test_data = b"Hello, Synapse SDK!"
        
        result = await mock_storage.synapse_store_data(test_data, filename="test.txt")
        
        assert result["success"] == True
        assert "commp" in result
        assert result["size"] == len(test_data)
        assert result["filename"] == "test.txt"
        assert "proof_set_id" in result
        assert "storage_provider" in result
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_retrieve_data(self, mock_storage):
        """Test data retrieval operation."""
        test_commp = "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
        
        data = await mock_storage.synapse_retrieve_data(test_commp)
        
        assert isinstance(data, bytes)
        assert data == b"Hello, Synapse SDK!"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_store_file(self, mock_storage):
        """Test file storage operation."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        test_content = b"Hello, file storage!"
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        result = await mock_storage.synapse_store_file(test_file)
        
        assert result["success"] == True
        assert "commp" in result
        assert result["file_path"] == test_file
        assert result["filename"] == "test.txt"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_retrieve_file(self, mock_storage):
        """Test file retrieval operation."""
        test_commp = "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
        output_file = os.path.join(self.temp_dir, "retrieved.txt")
        
        result = await mock_storage.synapse_retrieve_file(test_commp, output_file)
        
        assert result["success"] == True
        assert result["output_path"] == output_file
        assert os.path.exists(output_file)
        
        # Check file content
        with open(output_file, 'rb') as f:
            content = f.read()
        assert content == b"Hello, Synapse SDK!"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_get_balance(self, mock_storage):
        """Test balance checking operation."""
        result = await mock_storage.synapse_get_balance()
        
        assert result["success"] == True
        assert "wallet_balance" in result
        assert "contract_balance" in result
        assert result["token"] == "USDFC"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_get_provider_recommendations(self, mock_storage):
        """Test provider recommendation operation."""
        result = await mock_storage.synapse_recommend_providers()
        
        assert result["success"] == True
        assert "providers" in result
        assert len(result["providers"]) > 0
        assert "pricing" in result
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_get_piece_status(self, mock_storage):
        """Test piece status checking operation."""
        test_commp = "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
        
        result = await mock_storage.synapse_get_piece_status(test_commp)
        
        assert result["success"] == True
        assert result["exists"] == True
        assert "proof_set_last_proven" in result
        assert "proof_set_next_proof_due" in result
        assert "in_challenge_window" in result
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_data_size_validation(self, mock_storage):
        """Test data size validation."""
        # Test data too small
        small_data = b"x" * 10  # Below minimum size
        result = await mock_storage.synapse_store_data(small_data)
        assert result["success"] == False
        assert "below minimum" in result["error"]
        
        # Test data too large (mock large data)
        with patch.object(mock_storage.storage_config, '__getitem__') as mock_config:
            mock_config.return_value = 100  # Very small max size for testing
            
            large_data = b"x" * 200
            result = await mock_storage.synapse_store_data(large_data)
            assert result["success"] == False
            assert "exceeds maximum" in result["error"]


def create_mock_mcp_server():
    """Create a mock MCP server for testing."""
    class MockMCPServer:
        def __init__(self):
            self.synapse_storage = None
            self.tools = []
        
        def _should_initialize_synapse(self):
            return True
        
        async def handle_synapse_store_data(self, arguments):
            if not self.synapse_storage:
                return {"error": "Synapse storage not initialized"}
            
            import base64
            data = base64.b64decode(arguments["data"])
            result = await self.synapse_storage.synapse_store_data(
                data=data,
                filename=arguments.get("filename")
            )
            return result
        
        async def handle_synapse_retrieve_data(self, arguments):
            if not self.synapse_storage:
                return {"error": "Synapse storage not initialized"}
            
            import base64
            data = await self.synapse_storage.synapse_retrieve_data(
                commp=arguments["commp"]
            )
            return {
                "success": True,
                "data": base64.b64encode(data).decode(),
                "size": len(data)
            }
    
    return MockMCPServer()


class TestMCPServerIntegration:
    """Test MCP server integration with Synapse storage."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_mcp_server_synapse_initialization(self):
        """Test MCP server Synapse storage initialization."""
        server = create_mock_mcp_server()
        
        # Mock storage initialization
        with patch('ipfs_kit_py.synapse_storage.config_synapse_sdk'), \
             patch.object(synapse_storage, '_find_wrapper_script') as mock_find, \
             patch.object(synapse_storage, 'JavaScriptBridge', MockJavaScriptBridge):
            
            mock_find.return_value = os.path.join(self.temp_dir, "synapse_wrapper.js")
            
            server.synapse_storage = synapse_storage(metadata={"network": "calibration"})
            
            assert server.synapse_storage is not None
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_mcp_server_store_data_tool(self):
        """Test MCP server store data tool."""
        server = create_mock_mcp_server()
        
        # Mock storage initialization
        with patch('ipfs_kit_py.synapse_storage.config_synapse_sdk'), \
             patch.object(synapse_storage, '_find_wrapper_script') as mock_find, \
             patch.object(synapse_storage, 'JavaScriptBridge', MockJavaScriptBridge):
            
            mock_find.return_value = os.path.join(self.temp_dir, "synapse_wrapper.js")
            
            server.synapse_storage = synapse_storage(metadata={"network": "calibration"})
            
            # Test store data tool
            import base64
            test_data = b"Hello, MCP server!"
            arguments = {
                "data": base64.b64encode(test_data).decode(),
                "filename": "mcp_test.txt"
            }
            
            result = await server.handle_synapse_store_data(arguments)
            
            assert result["success"] == True
            assert "commp" in result
            assert result["filename"] == "mcp_test.txt"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {IMPORT_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_mcp_server_retrieve_data_tool(self):
        """Test MCP server retrieve data tool."""
        server = create_mock_mcp_server()
        
        # Mock storage initialization
        with patch('ipfs_kit_py.synapse_storage.config_synapse_sdk'), \
             patch.object(synapse_storage, '_find_wrapper_script') as mock_find, \
             patch.object(synapse_storage, 'JavaScriptBridge', MockJavaScriptBridge):
            
            mock_find.return_value = os.path.join(self.temp_dir, "synapse_wrapper.js")
            
            server.synapse_storage = synapse_storage(metadata={"network": "calibration"})
            
            # Test retrieve data tool
            arguments = {
                "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
            }
            
            result = await server.handle_synapse_retrieve_data(arguments)
            
            assert result["success"] == True
            assert "data" in result
            assert "size" in result
            
            # Decode and verify data
            import base64
            decoded_data = base64.b64decode(result["data"])
            assert decoded_data == b"Hello, Synapse SDK!"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
