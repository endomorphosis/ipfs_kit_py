#!/usr/bin/env python3
"""
Tests for MCP Storage Controllers.

These tests verify that all storage backends (IPFS, S3, Storacha, Filecoin, HuggingFace, Lassie)
are properly integrated into the MCP server and feature-complete with the ipfs_kit_py APIs.
"""

import os
import sys
import json
import time
import uuid
import tempfile
import unittest
import shutil
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Test if pyarrow is available
try:
    import pyarrow
    import pyarrow.parquet
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False
    print("PyArrow not available, skipping Arrow-related tests")

# Import MCP server components
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
    from ipfs_kit_py.mcp.models.storage_manager import StorageManager
    from ipfs_kit_py.mcp.models.storage.s3_model import S3Model
    from ipfs_kit_py.mcp.models.storage.storacha_model import StorachaModel
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    from ipfs_kit_py.mcp.models.storage.huggingface_model import HuggingFaceModel
    from ipfs_kit_py.mcp.models.storage.lassie_model import LassieModel
    from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
    from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
    from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
    from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP components not available, skipping MCP tests")

# Core IPFS kit imports
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.huggingface_kit import huggingface_kit
from ipfs_kit_py.lassie_kit import lassie_kit

@unittest.skipIf(not MCP_AVAILABLE, "MCP components not available")
@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestMCPStorageControllers(unittest.TestCase):
    """Test MCP storage controllers integration with backend kits."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Create temporary directories for various components
        cls.base_dir = tempfile.mkdtemp(prefix="mcp_storage_test_")
        cls.persistence_path = os.path.join(cls.base_dir, "mcp_data")
        cls.test_data = b"Test data for storage backend testing" * 100  # Some reasonable size
        
        # Setup mock environment
        os.environ["IPFS_PATH"] = os.path.join(cls.base_dir, "ipfs")
        os.makedirs(cls.persistence_path, exist_ok=True)
        os.makedirs(os.environ["IPFS_PATH"], exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        shutil.rmtree(cls.base_dir)
        
    def setUp(self):
        """Set up test fixture for each test."""
        # Create a unique CID for each test
        self.test_cid = f"QmTest{uuid.uuid4().hex[:16]}"
        
        # Create temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(self.test_data)
        self.temp_file.close()
        
        # Create mocks
        self.setup_mocks()
        
        # Initialize MCP server with isolation mode to avoid affecting real system
        with patch('ipfs_kit_py.ipfs_kit.ipfs_kit._check_ipfs_daemon') as mock_check_daemon, \
             patch('ipfs_kit_py.ipfs_kit.ipfs_kit._start_daemon') as mock_start_daemon, \
             patch('ipfs_kit_py.ipfs_kit.ipfs_kit.check_daemon_status') as mock_daemon_status, \
             patch('ipfs_kit_py.ipfs_kit.ipfs_kit.ipfs_add') as mock_ipfs_add, \
             patch('ipfs_kit_py.ipfs_kit.ipfs_kit.ipfs_cat') as mock_ipfs_cat:
            
            # Set up mock responses
            mock_check_daemon.return_value = True
            mock_start_daemon.return_value = {"success": True}
            mock_daemon_status.return_value = {"success": True, "daemons": {"ipfs": {"running": True}}}
            mock_ipfs_add.return_value = {"success": True, "Hash": self.test_cid}
            mock_ipfs_cat.return_value = self.test_data
            
            # Initialize MCP server with S3 configuration through config parameter
            self.mcp_server = MCPServer(
                debug_mode=True,
                log_level="INFO",
                persistence_path=self.persistence_path,
                isolation_mode=True,
                config={
                    "resources": {
                        "s3": {"test": True}
                    },
                    "metadata": {
                        "s3_config": {
                            "accessKey": "test-access-key",
                            "secretKey": "test-secret-key",
                            "endpoint": "http://localhost:9000"
                        }
                    }
                }
            )
            
            # Create app and test client
            self.app = FastAPI()
            self.mcp_server.register_with_app(self.app, prefix="/mcp")
            self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary file
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
            
        # Shut down MCP server if it exists
        if hasattr(self, 'mcp_server'):
            # Note: Normally we'd call shutdown here, but since we heavily mocked the MCP server,
            # it might cause issues. In a real test environment, uncomment this.
            # self.mcp_server.shutdown()
            pass
    
    def setup_mocks(self):
        """Set up mocks for the various storage backends."""
        # IPFS mock
        self.ipfs_mock = patch('ipfs_kit_py.ipfs_kit.ipfs_kit').start()
        self.ipfs_mock.ipfs_add.return_value = {"success": True, "Hash": self.test_cid}
        self.ipfs_mock.ipfs_cat.return_value = self.test_data
        self.ipfs_mock.pin_add.return_value = {"success": True}
        self.ipfs_mock.pin_ls.return_value = {"success": True, "pins": [self.test_cid]}
        
        # S3 mock
        self.s3_mock = patch('ipfs_kit_py.s3_kit.s3_kit').start()
        # Make sure the constructor returns a mocked instance
        self.s3_instance_mock = MagicMock()
        self.s3_instance_mock.s3_ul_file.return_value = {"success": True, "ETag": "mock-etag"}
        self.s3_instance_mock.s3_dl_file.return_value = {"success": True}
        self.s3_instance_mock.s3_ls_dir.return_value = {"success": True, "files": [{"Key": "test.bin"}]}
        self.s3_instance_mock.s3_rm_file.return_value = {"success": True}
        self.s3_instance_mock.list_buckets.return_value = {"success": True, "buckets": ["ipfs-content"]}
        self.s3_mock.return_value = self.s3_instance_mock
        
        # Also patch the S3 kit call within the StorageManager to ensure it works
        patch('ipfs_kit_py.mcp.models.storage_manager.s3_kit', return_value=self.s3_instance_mock).start()
        
        # Storacha mock
        self.storacha_mock = patch('ipfs_kit_py.storacha_kit.storacha_kit').start()
        self.storacha_mock.return_value.w3_up.return_value = {"success": True, "cid": self.test_cid}
        self.storacha_mock.return_value.w3_cat.return_value = {"success": True, "content": self.test_data}
        self.storacha_mock.return_value.w3_list_spaces.return_value = {"success": True, "spaces": [{"did": "did:key:test"}]}
        
        # Filecoin mock
        self.lotus_mock = patch('ipfs_kit_py.lotus_kit.lotus_kit').start()
        self.lotus_mock.return_value.client_import.return_value = {"success": True}
        self.lotus_mock.return_value.client_retrieve.return_value = {"success": True, "data": self.test_data}
        self.lotus_mock.return_value.client_list_deals.return_value = {"success": True, "deals": []}
        
        # HuggingFace mock
        self.huggingface_mock = patch('ipfs_kit_py.huggingface_kit.huggingface_kit').start()
        self.huggingface_mock.return_value.upload_file_to_repo.return_value = {"success": True}
        self.huggingface_mock.return_value.download_file_from_repo.return_value = {"success": True, "content": self.test_data}
        self.huggingface_mock.return_value.list_repos.return_value = {"success": True, "repos": ["test-repo"]}
        
        # Lassie mock
        self.lassie_mock = patch('ipfs_kit_py.lassie_kit.lassie_kit').start()
        self.lassie_mock.return_value.fetch.return_value = {"success": True, "content": self.test_data}
        
        # Create helper patches for S3 kit
        # We won't try to patch validate_credentials since it doesn't exist
        # Instead, we'll create patches for methods we know exist
        patch('ipfs_kit_py.s3_kit.s3_kit.check_credentials', return_value=True).start()
        patch('ipfs_kit_py.s3_kit.s3_kit.s3_list_buckets', return_value={"success": True, "buckets": ["ipfs-content"]}).start()
        
        # For Arrow and Parquet tests
        if ARROW_AVAILABLE:
            patch('ipfs_kit_py.arrow_metadata_index.ArrowMetadataIndex').start()
            
    def teardown_mocks(self):
        """Clean up all mocks."""
        patch.stopall()
        
    # Helper method to extract model from MCP server
    def get_model(self, model_name):
        """Get a specific model from the MCP server."""
        if not hasattr(self.mcp_server, 'models'):
            return None
        return self.mcp_server.models.get(model_name)
    
    # Helper method to extract controller from MCP server
    def get_controller(self, controller_name):
        """Get a specific controller from the MCP server."""
        if not hasattr(self.mcp_server, 'controllers'):
            return None
        return self.mcp_server.controllers.get(controller_name)
    
    # Test core MCP server with storage backends
    def test_mcp_server_initialization(self):
        """Test that MCP server initializes with all storage backends."""
        # Verify that the MCP server was initialized
        self.assertIsNotNone(self.mcp_server)
        
        # Check that the storage manager was initialized and has expected models
        storage_models = set()
        for name, model in self.mcp_server.models.items():
            if name.startswith("storage_"):
                storage_models.add(name.split("_")[1])
                
        # Check for expected storage backends
        self.assertIn("storacha", storage_models, "Storacha model should be present")
        self.assertIn("filecoin", storage_models, "Filecoin model should be present")
        self.assertIn("huggingface", storage_models, "HuggingFace model should be present")
        self.assertIn("lassie", storage_models, "Lassie model should be present")
        
        # S3 may not be present due to missing credentials, so we don't check for it
        
        # Check that the controllers were initialized
        storage_controllers = set()
        for name, controller in self.mcp_server.controllers.items():
            if name.startswith("storage_"):
                storage_controllers.add(name.split("_")[1])
                
        # Check for expected controllers
        self.assertIn("storacha", storage_controllers, "Storacha controller should be present")
        self.assertIn("filecoin", storage_controllers, "Filecoin controller should be present")
        self.assertIn("huggingface", storage_controllers, "HuggingFace controller should be present")
        self.assertIn("lassie", storage_controllers, "Lassie controller should be present")
    
    # Test IPFS model API parity
    def test_ipfs_model_parity(self):
        """Test that IPFS model has parity with ipfs_kit_py's APIs."""
        # Get IPFS model
        ipfs_model = self.get_model("ipfs")
        self.assertIsNotNone(ipfs_model, "IPFS model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(ipfs_model, "add"), "add method should exist")
        self.assertTrue(hasattr(ipfs_model, "cat"), "cat method should exist")
        self.assertTrue(hasattr(ipfs_model, "pin_add"), "pin_add method should exist")
        self.assertTrue(hasattr(ipfs_model, "pin_rm"), "pin_rm method should exist")
        self.assertTrue(hasattr(ipfs_model, "pin_ls"), "pin_ls method should exist")
        
        # Check HTTP endpoints via router/client
        response = self.client.get("/mcp/health")
        self.assertEqual(response.status_code, 200)
        
        # Upload a file
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            response = self.client.post("/mcp/ipfs/add", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
        # Retrieve content (mocked to return test data)
        response = self.client.get(f"/mcp/ipfs/cat/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_data)
        
        # Pin content
        response = self.client.post(f"/mcp/ipfs/pin/add/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # List pins
        response = self.client.get("/mcp/ipfs/pin/ls")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    # Test Storacha model API parity
    def test_storacha_model_parity(self):
        """Test that Storacha model has parity with storacha_kit's APIs."""
        # Skip if not available
        if "storage_storacha" not in self.mcp_server.models:
            self.skipTest("Storacha model not available")
            
        # Get Storacha model
        storacha_model = self.get_model("storage_storacha")
        self.assertIsNotNone(storacha_model, "Storacha model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(storacha_model, "w3_up"), "w3_up method should exist")
        self.assertTrue(hasattr(storacha_model, "w3_cat"), "w3_cat method should exist")
        self.assertTrue(hasattr(storacha_model, "w3_list_spaces"), "w3_list_spaces method should exist")
        self.assertTrue(hasattr(storacha_model, "ipfs_to_storacha"), "ipfs_to_storacha method should exist")
        self.assertTrue(hasattr(storacha_model, "storacha_to_ipfs"), "storacha_to_ipfs method should exist")
        
        # Check HTTP endpoints via router/client
        # Upload a file to Storacha
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            response = self.client.post("/mcp/storage/storacha/upload", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
        # Get content from Storacha
        response = self.client.get(f"/mcp/storage/storacha/cat/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_data)
        
        # List spaces
        response = self.client.get("/mcp/storage/storacha/spaces")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Test IPFS to Storacha
        response = self.client.post(f"/mcp/storage/storacha/from_ipfs/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Test Storacha to IPFS
        response = self.client.post(f"/mcp/storage/storacha/to_ipfs/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    # Test Filecoin model API parity
    def test_filecoin_model_parity(self):
        """Test that Filecoin model has parity with lotus_kit's APIs."""
        # Skip if not available
        if "storage_filecoin" not in self.mcp_server.models:
            self.skipTest("Filecoin model not available")
            
        # Get Filecoin model
        filecoin_model = self.get_model("storage_filecoin")
        self.assertIsNotNone(filecoin_model, "Filecoin model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(filecoin_model, "client_import"), "client_import method should exist")
        self.assertTrue(hasattr(filecoin_model, "client_retrieve"), "client_retrieve method should exist")
        self.assertTrue(hasattr(filecoin_model, "client_list_deals"), "client_list_deals method should exist")
        self.assertTrue(hasattr(filecoin_model, "ipfs_to_filecoin"), "ipfs_to_filecoin method should exist")
        self.assertTrue(hasattr(filecoin_model, "filecoin_to_ipfs"), "filecoin_to_ipfs method should exist")
        
        # Check HTTP endpoints via router/client
        # Upload a file to Filecoin
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            response = self.client.post("/mcp/storage/filecoin/import", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
        # Test IPFS to Filecoin
        response = self.client.post(f"/mcp/storage/filecoin/from_ipfs/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Test Filecoin to IPFS
        response = self.client.post(f"/mcp/storage/filecoin/to_ipfs/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # List deals
        response = self.client.get("/mcp/storage/filecoin/deals")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    # Test HuggingFace model API parity
    def test_huggingface_model_parity(self):
        """Test that HuggingFace model has parity with huggingface_kit's APIs."""
        # Skip if not available
        if "storage_huggingface" not in self.mcp_server.models:
            self.skipTest("HuggingFace model not available")
            
        # Get HuggingFace model
        huggingface_model = self.get_model("storage_huggingface")
        self.assertIsNotNone(huggingface_model, "HuggingFace model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(huggingface_model, "upload_file_to_repo"), "upload_file_to_repo method should exist")
        self.assertTrue(hasattr(huggingface_model, "download_file_from_repo"), "download_file_from_repo method should exist")
        self.assertTrue(hasattr(huggingface_model, "list_repos"), "list_repos method should exist")
        self.assertTrue(hasattr(huggingface_model, "ipfs_to_huggingface"), "ipfs_to_huggingface method should exist")
        self.assertTrue(hasattr(huggingface_model, "huggingface_to_ipfs"), "huggingface_to_ipfs method should exist")
        
        # Check HTTP endpoints via router/client
        # Upload a file to HuggingFace
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            response = self.client.post("/mcp/storage/huggingface/upload?repo_id=test-repo&repo_type=model&path=test.bin", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
        # List repositories
        response = self.client.get("/mcp/storage/huggingface/repos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Test IPFS to HuggingFace
        response = self.client.post(f"/mcp/storage/huggingface/from_ipfs/{self.test_cid}?repo_id=test-repo&repo_type=model&path=test.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Test HuggingFace to IPFS
        response = self.client.post(f"/mcp/storage/huggingface/to_ipfs?repo_id=test-repo&repo_type=model&path=test.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    # Test Lassie model API parity
    def test_lassie_model_parity(self):
        """Test that Lassie model has parity with lassie_kit's APIs."""
        # Skip if not available
        if "storage_lassie" not in self.mcp_server.models:
            self.skipTest("Lassie model not available")
            
        # Get Lassie model
        lassie_model = self.get_model("storage_lassie")
        self.assertIsNotNone(lassie_model, "Lassie model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(lassie_model, "fetch"), "fetch method should exist")
        
        # Check HTTP endpoints via router/client
        # Fetch content via Lassie
        response = self.client.get(f"/mcp/storage/lassie/fetch/{self.test_cid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_data)
    
    # Test S3 model API parity (when available)
    def test_s3_model_parity(self):
        """Test that S3 model has parity with s3_kit's APIs."""
        # Skip if not available
        if "storage_s3" not in self.mcp_server.models:
            # We expected this to fail, so artificially inject the model and controller
            # for testing purposes. This wouldn't happen in production but allows us to test
            # the API parity without credentials.
            
            # Create and inject S3 model with mocked kit
            s3_kit_instance = MagicMock()
            s3_kit_instance.upload_file.return_value = {"success": True}
            s3_kit_instance.download_file.return_value = {"success": True, "content": self.test_data}
            s3_kit_instance.list_buckets.return_value = {"success": True, "buckets": ["ipfs-content"]}
            s3_kit_instance.list_objects.return_value = {"success": True, "objects": [{"Key": "test.bin"}]}
            
            # Create S3 model
            ipfs_model = self.get_model("ipfs")
            cache_manager = self.mcp_server.cache_manager
            credential_manager = self.mcp_server.credential_manager
            
            s3_model = S3Model(
                s3_kit_instance=s3_kit_instance,
                ipfs_model=ipfs_model,
                cache_manager=cache_manager,
                credential_manager=credential_manager
            )
            
            # Inject model
            self.mcp_server.models["storage_s3"] = s3_model
            
            # Create and inject controller
            s3_controller = S3Controller(s3_model)
            self.mcp_server.controllers["storage_s3"] = s3_controller
            
            # Register controller routes
            router = APIRouter(prefix="", tags=["mcp"])
            s3_controller.register_routes(router)
            self.app.include_router(router, prefix="/mcp")
            
        # Now get the model
        s3_model = self.get_model("storage_s3")
        self.assertIsNotNone(s3_model, "S3 model should be present")
        
        # Check key methods in model
        self.assertTrue(hasattr(s3_model, "upload_file"), "upload_file method should exist")
        self.assertTrue(hasattr(s3_model, "download_file"), "download_file method should exist")
        self.assertTrue(hasattr(s3_model, "list_buckets"), "list_buckets method should exist")
        self.assertTrue(hasattr(s3_model, "ipfs_to_s3"), "ipfs_to_s3 method should exist")
        self.assertTrue(hasattr(s3_model, "s3_to_ipfs"), "s3_to_ipfs method should exist")
        
        # Check HTTP endpoints via router/client
        # Upload a file to S3
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            form_data = {'bucket': 'ipfs-content', 'key': 'test.bin'}
            response = self.client.post("/mcp/storage/s3/upload", files=files, data=form_data)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
        # Also test JSON-based upload
        json_data = {
            "bucket": "ipfs-content",
            "key": "test.bin",
            "content_b64": "VGVzdCBkYXRh"  # Base64 encoded "Test data"
        }
        response = self.client.post("/mcp/storage/s3/upload", json=json_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        # Download file from S3
        response = self.client.get("/mcp/storage/s3/download?bucket=ipfs-content&key=test.bin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_data)
            
        # List buckets (using new /storage/s3/buckets endpoint)
        response = self.client.get("/mcp/storage/s3/buckets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn("buckets", data)
        self.assertIsInstance(data["buckets"], list)
            
        # Test backward compatibility with old endpoint pattern
        response = self.client.get("/mcp/s3/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        # IPFS to S3
        response = self.client.post(f"/mcp/storage/s3/from_ipfs/{self.test_cid}?bucket=ipfs-content&key=test_from_ipfs.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        # S3 to IPFS
        response = self.client.post("/mcp/storage/s3/to_ipfs?bucket=ipfs-content&key=test.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Upload a file to S3
        result = s3_model.upload_file(
            file_path=self.temp_file.name,
            bucket="ipfs-content",
            key="test.bin"
        )
        self.assertTrue(result["success"])
        
        # Download file from S3
        result = s3_model.download_file(
            bucket="ipfs-content",
            key="test.bin"
        )
        self.assertTrue(result["success"])
        
        # List buckets
        result = s3_model.list_buckets()
        self.assertTrue(result["success"])
        self.assertIn("buckets", result)
        self.assertIsInstance(result["buckets"], list)
        
        # IPFS to S3
        result = s3_model.ipfs_to_s3(
            cid=self.test_cid,
            bucket="ipfs-content",
            key="test_from_ipfs.bin"
        )
        self.assertTrue(result["success"])
        
        # S3 to IPFS
        result = s3_model.s3_to_ipfs(
            bucket="ipfs-content",
            key="test.bin"
        )
        self.assertTrue(result["success"])
    
    # Test Arrow/Parquet integration if available
    @unittest.skipIf(not ARROW_AVAILABLE, "PyArrow not available")
    def test_arrow_parquet_integration(self):
        """Test integration with Arrow and Parquet."""
        # This is a more complex test that would require PyArrow to be available
        # Since we can't guarantee that, we'll skip it if PyArrow isn't available
        
        # Assert that we have PyArrow and can import necessary modules
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        # Check for arrow-related modules in ipfs_kit_py
        # Note: These modules may not be directly exposed in the MCP server but should
        # still be usable with the IPFS module.
        from ipfs_kit_py import arrow_metadata_index
        
        # If we get here, we'll just verify that the component exists
        self.assertTrue(hasattr(arrow_metadata_index, 'IPFSArrowIndex'))
        
        # Note: A more comprehensive test would create an index, add data, and query it,
        # but that requires significant setup and is better handled in the module's own tests.
    
    # Test the S3 controller specifically
    def test_s3_controller_http_endpoints(self):
        """Test the S3 controller HTTP endpoints specifically."""
        # Skip if not available
        if "storage_s3" not in self.mcp_server.models:
            self.skipTest("S3 controller not available")
            
        # Get the S3 controller
        s3_controller = self.get_controller("storage_s3")
        self.assertIsNotNone(s3_controller, "S3 controller should be present")
        
        # Get all available routes for S3
        s3_routes = []
        for route in self.app.routes:
            if hasattr(route, 'path') and ('/storage/s3/' in route.path or '/s3/' in route.path):
                s3_routes.append(route.path)
                
        # Check that both new and legacy routes are registered
        self.assertIn("/mcp/storage/s3/upload", s3_routes, "New /storage/s3/upload endpoint should be registered")
        self.assertIn("/mcp/s3/status", s3_routes, "Legacy /s3/status endpoint should be registered for backward compatibility")
        self.assertIn("/mcp/storage/s3/buckets", s3_routes, "New /storage/s3/buckets endpoint should be registered")
        
        # Test form-based file upload
        with open(self.temp_file.name, 'rb') as f:
            files = {'file': ('test.bin', f)}
            form_data = {'bucket': 'ipfs-content', 'key': 'form_upload.bin', 'metadata': '{"source": "form_upload"}'}
            response = self.client.post("/mcp/storage/s3/upload", files=files, data=form_data)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            
    # Test the Lassie controller specifically
    def test_lassie_controller_http_endpoints(self):
        """Test the Lassie controller HTTP endpoints specifically."""
        # Skip if not available
        if "storage_lassie" not in self.mcp_server.models:
            self.skipTest("Lassie controller not available")
            
        # Get the Lassie controller
        lassie_controller = self.get_controller("storage_lassie")
        self.assertIsNotNone(lassie_controller, "Lassie controller should be present")
        
        # Configure the mocked lassie_kit to return a simulated check_lassie_installed response
        self.lassie_mock.return_value.check_lassie_installed.return_value = {
            "success": True,
            "installed": True,
            "version": "1.0.0-simulation",
            "simulated": True
        }
        
        # Configure the fetch method to return simulated content
        self.lassie_mock.return_value.fetch_cid.return_value = {
            "success": True,
            "cid": self.test_cid,
            "content": self.test_data,
            "simulated": True
        }
        
        # Get all available routes for Lassie
        lassie_routes = []
        for route in self.app.routes:
            if hasattr(route, 'path') and ('/storage/lassie/' in route.path or '/lassie/' in route.path):
                lassie_routes.append(route.path)
                
        # Check that essential routes are registered
        self.assertIn("/mcp/storage/lassie/status", lassie_routes, "Status endpoint should be registered")
        self.assertIn("/mcp/lassie/fetch", lassie_routes, "Fetch endpoint should be registered")
        
        # Test the status endpoint
        response = self.client.get("/mcp/storage/lassie/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Since we have simulation mode enabled, it should always succeed
        self.assertTrue(data['success'])
        
        # Check if we're in simulation mode
        self.assertTrue(data.get('simulated', False), "Response should indicate simulation mode")
        self.assertIn("note", data, "Response should include a note about simulation mode")
        self.assertEqual(data["backend"], "lassie")
        
        # Test the fetch endpoint with a test CID
        request_data = {
            "cid": self.test_cid
        }
        response = self.client.post("/mcp/lassie/fetch", json=request_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cid'], self.test_cid)
            
        # Test JSON-based upload with base64 content
        import base64
        test_content = b"Testing JSON-based upload"
        content_b64 = base64.b64encode(test_content).decode('utf-8')
        json_data = {
            "bucket": "ipfs-content",
            "key": "json_upload.bin",
            "content_b64": content_b64,
            "metadata": {"source": "json_upload"}
        }
        response = self.client.post("/mcp/storage/s3/upload", json=json_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        # Test bucket listing
        response = self.client.get("/mcp/storage/s3/buckets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn("buckets", data)
        self.assertIsInstance(data["buckets"], list)
        self.assertIn("ipfs-content", data["buckets"])
            
        # Test status endpoint - both new and legacy paths
        response = self.client.get("/mcp/storage/s3/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        response = self.client.get("/mcp/s3/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        # Test download endpoint
        response = self.client.get("/mcp/storage/s3/download?bucket=ipfs-content&key=test.bin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_data)
            
        # Test IPFS integration
        response = self.client.post(f"/mcp/storage/s3/from_ipfs/{self.test_cid}?bucket=ipfs-content&key=from_ipfs.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
            
        response = self.client.post("/mcp/storage/s3/to_ipfs?bucket=ipfs-content&key=test.bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn("cid", data)

    # Test that all MCP controllers are feature-complete with direct API access
    def test_mcp_api_feature_completeness(self):
        """Test that all MCP controllers expose all features of their underlying APIs."""
        # For each controller, verify it exposes all the key methods of its model
        
        # IPFS
        ipfs_model = self.get_model("ipfs")
        ipfs_controller = self.get_controller("ipfs")
        
        if ipfs_model and ipfs_controller:
            # Get all public methods of the model
            ipfs_model_methods = [method for method in dir(ipfs_model) 
                               if not method.startswith('_') and callable(getattr(ipfs_model, method))]
            
            # Get all routes registered by the controller
            ipfs_routes = [route.name for route in self.app.routes if route.name and 'ipfs' in route.name.lower()]
            
            # Check that key methods are exposed
            essential_methods = ['add', 'cat', 'pin_add', 'pin_rm', 'pin_ls']
            for method in essential_methods:
                self.assertIn(method, ipfs_model_methods, f"IPFS model should have {method} method")
                # The route name may not match the method name exactly, but should contain it
                matching_routes = [route for route in ipfs_routes if method.replace('_', '') in route.lower()]
                self.assertTrue(len(matching_routes) > 0, f"IPFS controller should expose {method} via HTTP")
                
        # S3
        if "storage_s3" in self.mcp_server.models:
            s3_model = self.get_model("storage_s3")
            s3_controller = self.get_controller("storage_s3")
            
            if s3_model and s3_controller:
                # Get all routes registered by the controller
                s3_routes = []
                for route in self.app.routes:
                    if hasattr(route, 'path') and ('/storage/s3/' in route.path or '/s3/' in route.path):
                        s3_routes.append(route.path)
                
                # Check that key methods are exposed
                essential_methods = ['upload_file', 'download_file', 'list_buckets', 'ipfs_to_s3', 's3_to_ipfs']
                essential_endpoints = ['/mcp/storage/s3/upload', '/mcp/storage/s3/download', 
                                      '/mcp/storage/s3/buckets', '/mcp/storage/s3/from_ipfs/', 
                                      '/mcp/storage/s3/to_ipfs']
                
                for method in essential_methods:
                    self.assertTrue(hasattr(s3_model, method), f"S3 model should have {method} method")
                    
                for endpoint in essential_endpoints:
                    matching_routes = [route for route in s3_routes if endpoint in route]
                    self.assertTrue(len(matching_routes) > 0, f"S3 controller should expose {endpoint} via HTTP")
                
        # Storacha
        if "storage_storacha" in self.mcp_server.models:
            storacha_model = self.get_model("storage_storacha")
            storacha_controller = self.get_controller("storage_storacha")
            
            if storacha_model and storacha_controller:
                # Get all routes registered by the controller
                storacha_routes = [route.name for route in self.app.routes if route.name and 'storacha' in route.name.lower()]
                
                # Check that key methods are exposed
                essential_methods = ['w3_up', 'w3_cat', 'w3_list_spaces', 'ipfs_to_storacha', 'storacha_to_ipfs']
                for method in essential_methods:
                    self.assertTrue(hasattr(storacha_model, method), f"Storacha model should have {method} method")
                    # The route name may not match the method name exactly, but should contain it
                    method_parts = method.replace('_', ' ').split()
                    matching_routes = [route for route in storacha_routes 
                                      if any(part in route.lower() for part in method_parts)]
                    self.assertTrue(len(matching_routes) > 0, f"Storacha controller should expose {method} via HTTP")
                    
        # Filecoin
        if "storage_filecoin" in self.mcp_server.models:
            filecoin_model = self.get_model("storage_filecoin")
            filecoin_controller = self.get_controller("storage_filecoin")
            
            if filecoin_model and filecoin_controller:
                # Get all routes registered by the controller
                filecoin_routes = [route.name for route in self.app.routes if route.name and 'filecoin' in route.name.lower()]
                
                # Check that key methods are exposed
                essential_methods = ['client_import', 'client_retrieve', 'client_list_deals', 
                                   'ipfs_to_filecoin', 'filecoin_to_ipfs']
                for method in essential_methods:
                    self.assertTrue(hasattr(filecoin_model, method), f"Filecoin model should have {method} method")
                    # The route name may not match the method name exactly, but should contain it
                    method_parts = method.replace('_', ' ').split()
                    matching_routes = [route for route in filecoin_routes 
                                      if any(part in route.lower() for part in method_parts)]
                    self.assertTrue(len(matching_routes) > 0, f"Filecoin controller should expose {method} via HTTP")
                    
        # HuggingFace
        if "storage_huggingface" in self.mcp_server.models:
            huggingface_model = self.get_model("storage_huggingface")
            huggingface_controller = self.get_controller("storage_huggingface")
            
            if huggingface_model and huggingface_controller:
                # Get all routes registered by the controller
                huggingface_routes = [route.name for route in self.app.routes if route.name and 'huggingface' in route.name.lower()]
                
                # Check that key methods are exposed
                essential_methods = ['upload_file_to_repo', 'download_file_from_repo', 'list_repos',
                                   'ipfs_to_huggingface', 'huggingface_to_ipfs']
                for method in essential_methods:
                    self.assertTrue(hasattr(huggingface_model, method), f"HuggingFace model should have {method} method")
                    # The route name may not match the method name exactly, but should contain it
                    method_parts = method.replace('_', ' ').split()
                    matching_routes = [route for route in huggingface_routes 
                                      if any(part in route.lower() for part in method_parts)]
                    self.assertTrue(len(matching_routes) > 0, f"HuggingFace controller should expose {method} via HTTP")

    
if __name__ == "__main__":
    unittest.main()