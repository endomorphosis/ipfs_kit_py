"""
Test suite for MCP Aria2 Controller AnyIO version.

This module tests the functionality of the Aria2ControllerAnyIO class
which provides asynchronous HTTP endpoints for Aria2 download manager operations
with AnyIO support.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

# Import the controller and models
from ipfs_kit_py.mcp_server.controllers.aria2_controller_anyio import (
    Aria2ControllerAnyIO, URIListModel, DownloadIDModel, DaemonOptionsModel, 
    MetalinkFileModel
)

# Mock implementation for testing
class MockAria2ControllerAnyIO(Aria2ControllerAnyIO):
    """Mock version of Aria2ControllerAnyIO for testing."""
    
    def __init__(self, aria2_model=None):
        """Initialize with a mock model if not provided."""
        if aria2_model is None:
            aria2_model = MagicMock()
            
            # Set up mock return values for model methods
            aria2_model.get_version.return_value = {
                "success": True,
                "version": {
                    "version": "1.36.0",
                    "enabledFeatures": ["BitTorrent", "Metalink", "WebSocket"]
                }
            }
            
            aria2_model.add_uri.return_value = {
                "success": True,
                "gid": "test-gid-123",
                "status": "active"
            }
            
            aria2_model.add_torrent.return_value = {
                "success": True,
                "gid": "test-gid-124",
                "status": "active"
            }
            
            aria2_model.add_metalink.return_value = {
                "success": True,
                "gid": "test-gid-125",
                "status": "active"
            }
            
            aria2_model.remove_download.return_value = {
                "success": True,
                "gid": "test-gid-123",
                "message": "Download removed successfully"
            }
            
            aria2_model.pause_download.return_value = {
                "success": True,
                "gid": "test-gid-123",
                "message": "Download paused successfully"
            }
            
            aria2_model.resume_download.return_value = {
                "success": True,
                "gid": "test-gid-123",
                "message": "Download resumed successfully"
            }
            
            aria2_model.get_status.return_value = {
                "success": True,
                "gid": "test-gid-123",
                "status": "active",
                "total_length": 1000000,
                "completed_length": 500000,
                "download_speed": 1024
            }
            
            aria2_model.list_downloads.return_value = {
                "success": True,
                "downloads": [
                    {
                        "gid": "test-gid-123",
                        "status": "active",
                        "total_length": 1000000,
                        "completed_length": 500000
                    },
                    {
                        "gid": "test-gid-124",
                        "status": "paused",
                        "total_length": 2000000,
                        "completed_length": 1000000
                    }
                ]
            }
            
            aria2_model.purge_downloads.return_value = {
                "success": True,
                "purged_count": 3,
                "message": "Purged 3 downloads"
            }
            
            aria2_model.get_global_status.return_value = {
                "success": True,
                "download_speed": 5120,
                "upload_speed": 1024,
                "active_downloads": 2
            }
            
            aria2_model.start_daemon.return_value = {
                "success": True,
                "message": "Daemon started successfully",
                "pid": 12345
            }
            
            aria2_model.stop_daemon.return_value = {
                "success": True,
                "message": "Daemon stopped successfully"
            }
            
            # Mock aria2_kit for create_metalink
            aria2_model.aria2_kit = MagicMock()
            aria2_model.aria2_kit.create_metalink.return_value = {
                "success": True,
                "metalink_content": "<metalink version=\"3.0\">...</metalink>"
            }
            
            # Set operation stats
            aria2_model.operation_stats = {
                "operations": {
                    "add_uri": 5,
                    "add_torrent": 2,
                    "add_metalink": 1,
                    "remove_download": 3
                },
                "total_downloads": 8,
                "active_downloads": 2
            }
            
            # Set daemon status
            aria2_model.aria2_kit.daemon_running = True
            
        # Initialize with the model
        super().__init__(aria2_model)


class TestAria2ControllerAnyIOInitialization:
    """Test initialization and basic setup of Aria2ControllerAnyIO."""
    
    def test_init(self):
        """Test controller initialization."""
        # Create mock model
        mock_model = MagicMock()
        
        # Create controller
        controller = Aria2ControllerAnyIO(mock_model)
        
        # Verify initialization
        assert controller.aria2_model == mock_model
        assert isinstance(controller.initialized_endpoints, set)
        
    def test_register_routes(self):
        """Test route registration."""
        # Create mock router and model
        mock_router = MagicMock(spec=APIRouter)
        mock_model = MagicMock()
        
        # Create controller and register routes
        controller = Aria2ControllerAnyIO(mock_model)
        controller.register_routes(mock_router)
        
        # Verify routes were registered
        expected_routes = [
            "/aria2/health",
            "/aria2/version",
            "/aria2/add",
            "/aria2/add-torrent",
            "/aria2/add-metalink",
            "/aria2/create-metalink",
            "/aria2/remove",
            "/aria2/pause",
            "/aria2/resume",
            "/aria2/status/{gid}",
            "/aria2/list",
            "/aria2/purge",
            "/aria2/global-stats",
            "/aria2/daemon/start",
            "/aria2/daemon/stop"
        ]
        
        # Check that all expected routes were registered
        call_args_list = mock_router.add_api_route.call_args_list
        registered_paths = [args[0][0] for args in call_args_list]
        
        for route in expected_routes:
            assert route in registered_paths, f"Route {route} was not registered"
    
    def test_get_backend(self):
        """Test get_backend method."""
        # Create controller with mock model
        controller = MockAria2ControllerAnyIO()
        
        # Test outside of async context
        assert controller.get_backend() is None
        
        # Can't easily test in async context here, will test in the TestAria2ControllerAnyIO class


@pytest.mark.anyio
class TestAria2ControllerAnyIO:
    """Test AnyIO-specific functionality of Aria2ControllerAnyIO."""
    
    @pytest.fixture
    def mock_aria2_model(self):
        """Create a mock Aria2 model with async methods."""
        model = MagicMock()
        
        # Set up mock responses
        model.get_version = MagicMock(return_value={
            "success": True,
            "version": {
                "version": "1.36.0",
                "enabledFeatures": ["BitTorrent", "Metalink", "WebSocket"]
            }
        })
        
        model.add_uri = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-123",
            "status": "active"
        })
        
        model.add_torrent = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-124",
            "status": "active"
        })
        
        model.add_metalink = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-125",
            "status": "active"
        })
        
        model.remove_download = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-123",
            "message": "Download removed successfully"
        })
        
        model.pause_download = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-123",
            "message": "Download paused successfully"
        })
        
        model.resume_download = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-123",
            "message": "Download resumed successfully"
        })
        
        model.get_status = MagicMock(return_value={
            "success": True,
            "gid": "test-gid-123",
            "status": "active",
            "total_length": 1000000,
            "completed_length": 500000,
            "download_speed": 1024
        })
        
        model.list_downloads = MagicMock(return_value={
            "success": True,
            "downloads": [
                {
                    "gid": "test-gid-123",
                    "status": "active",
                    "total_length": 1000000,
                    "completed_length": 500000
                },
                {
                    "gid": "test-gid-124",
                    "status": "paused",
                    "total_length": 2000000,
                    "completed_length": 1000000
                }
            ]
        })
        
        model.purge_downloads = MagicMock(return_value={
            "success": True,
            "purged_count": 3,
            "message": "Purged 3 downloads"
        })
        
        model.get_global_status = MagicMock(return_value={
            "success": True,
            "download_speed": 5120,
            "upload_speed": 1024,
            "active_downloads": 2
        })
        
        model.start_daemon = MagicMock(return_value={
            "success": True,
            "message": "Daemon started successfully",
            "pid": 12345
        })
        
        model.stop_daemon = MagicMock(return_value={
            "success": True,
            "message": "Daemon stopped successfully"
        })
        
        # Mock aria2_kit for create_metalink
        model.aria2_kit = MagicMock()
        model.aria2_kit.create_metalink = MagicMock(return_value={
            "success": True,
            "metalink_content": "<metalink version=\"3.0\">...</metalink>"
        })
        
        # Set operation stats
        model.operation_stats = {
            "operations": {
                "add_uri": 5,
                "add_torrent": 2,
                "add_metalink": 1,
                "remove_download": 3
            },
            "total_downloads": 8,
            "active_downloads": 2
        }
        
        # Set daemon status
        model.aria2_kit.daemon_running = True
        
        return model
    
    @pytest.fixture
    def controller(self, mock_aria2_model):
        """Create Aria2ControllerAnyIO with mock model."""
        return Aria2ControllerAnyIO(mock_aria2_model)
    
    @pytest.fixture
    def app_client(self, controller):
        """Create FastAPI test client with controller routes."""
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        return TestClient(app)
    
    @pytest.mark.anyio
    async def test_health_check_async(self, controller, mock_aria2_model):
        """Test health_check_async method."""
        result = await controller.health_check_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.get_version.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["status"] == "healthy"
        assert result["version"] == "1.36.0"
        assert "features" in result
        assert result["features"]["bittorrent"] is True
        assert result["features"]["metalink"] is True
        assert result["features"]["websocket"] is True
        assert result["daemon_running"] is True
        assert "stats" in result
    
    @pytest.mark.anyio
    async def test_get_version_async(self, controller, mock_aria2_model):
        """Test get_version_async method."""
        result = await controller.get_version_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.get_version.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert "version" in result
        assert result["version"]["version"] == "1.36.0"
    
    @pytest.mark.anyio
    async def test_add_uri_async(self, controller, mock_aria2_model):
        """Test add_uri_async method."""
        # Create request data
        uri_data = URIListModel(
            uris=["http://example.com/file.zip"],
            filename="file.zip",
            options={"dir": "/downloads"}
        )
        
        # Call method
        result = await controller.add_uri_async(uri_data)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.add_uri.assert_called_once_with(
            uris=["http://example.com/file.zip"],
            filename="file.zip",
            options={"dir": "/downloads"}
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-123"
        assert result["status"] == "active"
    
    @pytest.mark.anyio
    async def test_add_torrent_async(self, controller, mock_aria2_model):
        """Test add_torrent_async method."""
        # Create mock torrent file
        class MockUploadFile:
            async def read(self):
                return b"mock torrent content"
        
        # Call method
        result = await controller.add_torrent_async(
            torrent_file=MockUploadFile(),
            options='{"dir": "/downloads"}'
        )
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.add_torrent.assert_called_once_with(
            torrent=b"mock torrent content",
            options={"dir": "/downloads"}
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-124"
        assert result["status"] == "active"
    
    @pytest.mark.anyio
    async def test_add_metalink_async(self, controller, mock_aria2_model):
        """Test add_metalink_async method."""
        # Create mock metalink file
        class MockUploadFile:
            async def read(self):
                return b"mock metalink content"
        
        # Call method
        result = await controller.add_metalink_async(
            metalink_file=MockUploadFile(),
            options='{"dir": "/downloads"}'
        )
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.add_metalink.assert_called_once_with(
            metalink=b"mock metalink content",
            options={"dir": "/downloads"}
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-125"
        assert result["status"] == "active"
    
    @pytest.mark.anyio
    async def test_create_metalink_async(self, controller, mock_aria2_model):
        """Test create_metalink_async method."""
        # Create request data
        files_data = MetalinkFileModel(
            files=[
                {
                    "filename": "example.iso",
                    "urls": ["http://example.com/file.iso", "http://mirror.example.com/file.iso"],
                    "size": 1073741824,
                    "hash": {"type": "sha-256", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
                }
            ]
        )
        
        # Call method
        result = await controller.create_metalink_async(files_data)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.aria2_kit.create_metalink.assert_called_once_with(
            file_data=files_data.files
        )
        
        # Verify result
        assert result["success"] is True
        assert "metalink_content" in result
        assert result["metalink_content"] == "<metalink version=\"3.0\">...</metalink>"
    
    @pytest.mark.anyio
    async def test_remove_download_async(self, controller, mock_aria2_model):
        """Test remove_download_async method."""
        # Create request data
        download = DownloadIDModel(
            gid="test-gid-123",
            force=True
        )
        
        # Call method
        result = await controller.remove_download_async(download)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.remove_download.assert_called_once_with(
            gid="test-gid-123",
            force=True
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-123"
        assert "message" in result
    
    @pytest.mark.anyio
    async def test_pause_download_async(self, controller, mock_aria2_model):
        """Test pause_download_async method."""
        # Create request data
        download = DownloadIDModel(
            gid="test-gid-123",
            force=False
        )
        
        # Call method
        result = await controller.pause_download_async(download)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.pause_download.assert_called_once_with(
            gid="test-gid-123",
            force=False
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-123"
        assert "message" in result
    
    @pytest.mark.anyio
    async def test_resume_download_async(self, controller, mock_aria2_model):
        """Test resume_download_async method."""
        # Create request data
        download = DownloadIDModel(
            gid="test-gid-123"
        )
        
        # Call method
        result = await controller.resume_download_async(download)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.resume_download.assert_called_once_with(
            gid="test-gid-123"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-123"
        assert "message" in result
    
    @pytest.mark.anyio
    async def test_get_status_async(self, controller, mock_aria2_model):
        """Test get_status_async method."""
        # Call method
        result = await controller.get_status_async("test-gid-123")
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.get_status.assert_called_once_with(
            gid="test-gid-123"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["gid"] == "test-gid-123"
        assert result["status"] == "active"
        assert "total_length" in result
        assert "completed_length" in result
        assert "download_speed" in result
    
    @pytest.mark.anyio
    async def test_list_downloads_async(self, controller, mock_aria2_model):
        """Test list_downloads_async method."""
        # Call method
        result = await controller.list_downloads_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.list_downloads.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert "downloads" in result
        assert len(result["downloads"]) == 2
        assert result["downloads"][0]["gid"] == "test-gid-123"
        assert result["downloads"][1]["gid"] == "test-gid-124"
    
    @pytest.mark.anyio
    async def test_purge_downloads_async(self, controller, mock_aria2_model):
        """Test purge_downloads_async method."""
        # Call method
        result = await controller.purge_downloads_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.purge_downloads.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["purged_count"] == 3
        assert "message" in result
    
    @pytest.mark.anyio
    async def test_get_global_status_async(self, controller, mock_aria2_model):
        """Test get_global_status_async method."""
        # Call method
        result = await controller.get_global_status_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.get_global_status.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["download_speed"] == 5120
        assert result["upload_speed"] == 1024
        assert result["active_downloads"] == 2
    
    @pytest.mark.anyio
    async def test_start_daemon_async(self, controller, mock_aria2_model):
        """Test start_daemon_async method."""
        # Create request data
        options = DaemonOptionsModel(
            options={
                "dir": "/downloads",
                "max-concurrent-downloads": 5
            }
        )
        
        # Call method
        result = await controller.start_daemon_async(options)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.start_daemon.assert_called_once_with(
            options=options.options
        )
        
        # Verify result
        assert result["success"] is True
        assert "message" in result
        assert result["pid"] == 12345
    
    @pytest.mark.anyio
    async def test_stop_daemon_async(self, controller, mock_aria2_model):
        """Test stop_daemon_async method."""
        # Call method
        result = await controller.stop_daemon_async()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_aria2_model.stop_daemon.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert "message" in result
    
    @pytest.mark.anyio
    async def test_error_handling(self, controller, mock_aria2_model):
        """Test error handling in async methods."""
        # Set up model to return an error
        mock_aria2_model.get_status.return_value = {
            "success": False,
            "error": "Download not found",
            "error_type": "not_found"
        }
        
        # Test method that should raise HTTPException
        with pytest.raises(Exception) as excinfo:
            await controller.get_status_async("nonexistent-gid")
        
        # Verify the exception details
        assert "Download not found" in str(excinfo.value)
    
    @pytest.mark.anyio
    async def test_warn_if_async_context(self, controller):
        """Test _warn_if_async_context method in async context."""
        # Override get_backend to simulate async context
        with patch.object(controller, "get_backend", return_value="asyncio"):
            with pytest.warns(UserWarning, match="Synchronous method health_check called from async context"):
                controller.health_check()


@pytest.mark.skip("HTTP endpoint tests requiring complex setup")
class TestAria2ControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints of Aria2ControllerAnyIO."""
    
    @pytest.fixture
    def mock_aria2_model(self):
        """Create a mock Aria2 model."""
        model = MagicMock()
        
        # Set up mock responses
        model.get_version.return_value = {
            "success": True,
            "version": {
                "version": "1.36.0",
                "enabledFeatures": ["BitTorrent", "Metalink", "WebSocket"]
            }
        }
        
        model.add_uri.return_value = {
            "success": True,
            "gid": "test-gid-123",
            "status": "active"
        }
        
        model.add_torrent.return_value = {
            "success": True,
            "gid": "test-gid-124",
            "status": "active"
        }
        
        model.add_metalink.return_value = {
            "success": True,
            "gid": "test-gid-125",
            "status": "active"
        }
        
        model.remove_download.return_value = {
            "success": True,
            "gid": "test-gid-123",
            "message": "Download removed successfully"
        }
        
        model.pause_download.return_value = {
            "success": True,
            "gid": "test-gid-123",
            "message": "Download paused successfully"
        }
        
        model.resume_download.return_value = {
            "success": True,
            "gid": "test-gid-123",
            "message": "Download resumed successfully"
        }
        
        model.get_status.return_value = {
            "success": True,
            "gid": "test-gid-123",
            "status": "active",
            "total_length": 1000000,
            "completed_length": 500000,
            "download_speed": 1024
        }
        
        model.list_downloads.return_value = {
            "success": True,
            "downloads": [
                {
                    "gid": "test-gid-123",
                    "status": "active",
                    "total_length": 1000000,
                    "completed_length": 500000
                },
                {
                    "gid": "test-gid-124",
                    "status": "paused",
                    "total_length": 2000000,
                    "completed_length": 1000000
                }
            ]
        }
        
        model.purge_downloads.return_value = {
            "success": True,
            "purged_count": 3,
            "message": "Purged 3 downloads"
        }
        
        model.get_global_status.return_value = {
            "success": True,
            "download_speed": 5120,
            "upload_speed": 1024,
            "active_downloads": 2
        }
        
        model.start_daemon.return_value = {
            "success": True,
            "message": "Daemon started successfully",
            "pid": 12345
        }
        
        model.stop_daemon.return_value = {
            "success": True,
            "message": "Daemon stopped successfully"
        }
        
        # Mock aria2_kit for create_metalink
        model.aria2_kit = MagicMock()
        model.aria2_kit.create_metalink.return_value = {
            "success": True,
            "metalink_content": "<metalink version=\"3.0\">...</metalink>"
        }
        
        # Set operation stats
        model.operation_stats = {
            "operations": {
                "add_uri": 5,
                "add_torrent": 2,
                "add_metalink": 1,
                "remove_download": 3
            },
            "total_downloads": 8,
            "active_downloads": 2
        }
        
        # Set daemon status
        model.aria2_kit.daemon_running = True
        
        return model
    
    @pytest.fixture
    def app_client(self, mock_aria2_model):
        """Create FastAPI test client with controller routes."""
        app = FastAPI()
        router = APIRouter()
        
        # Create controller
        controller = Aria2ControllerAnyIO(mock_aria2_model)
        controller.register_routes(router)
        
        app.include_router(router)
        return TestClient(app)
    
    def test_health_check_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/health endpoint."""
        response = app_client.get("/aria2/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert "version" in data
        assert "features" in data
        assert "stats" in data
        
        # Verify model method was called
        mock_aria2_model.get_version.assert_called_once()
    
    def test_version_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/version endpoint."""
        response = app_client.get("/aria2/version")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "version" in data
        assert data["version"]["version"] == "1.36.0"
        
        # Verify model method was called
        mock_aria2_model.get_version.assert_called_once()
    
    def test_add_uri_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/add endpoint."""
        response = app_client.post(
            "/aria2/add",
            json={
                "uris": ["http://example.com/file.zip"],
                "filename": "file.zip",
                "options": {"dir": "/downloads"}
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["gid"] == "test-gid-123"
        
        # Verify model method was called
        mock_aria2_model.add_uri.assert_called_once()
    
    def test_remove_download_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/remove endpoint."""
        response = app_client.post(
            "/aria2/remove",
            json={
                "gid": "test-gid-123",
                "force": True
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["gid"] == "test-gid-123"
        
        # Verify model method was called
        mock_aria2_model.remove_download.assert_called_once()
    
    def test_pause_download_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/pause endpoint."""
        response = app_client.post(
            "/aria2/pause",
            json={
                "gid": "test-gid-123",
                "force": False
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["gid"] == "test-gid-123"
        
        # Verify model method was called
        mock_aria2_model.pause_download.assert_called_once()
    
    def test_resume_download_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/resume endpoint."""
        response = app_client.post(
            "/aria2/resume",
            json={
                "gid": "test-gid-123"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["gid"] == "test-gid-123"
        
        # Verify model method was called
        mock_aria2_model.resume_download.assert_called_once()
    
    def test_get_status_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/status/{gid} endpoint."""
        response = app_client.get("/aria2/status/test-gid-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["gid"] == "test-gid-123"
        assert data["status"] == "active"
        
        # Verify model method was called
        mock_aria2_model.get_status.assert_called_once()
    
    def test_list_downloads_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/list endpoint."""
        response = app_client.get("/aria2/list")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "downloads" in data
        assert len(data["downloads"]) == 2
        
        # Verify model method was called
        mock_aria2_model.list_downloads.assert_called_once()
    
    def test_purge_downloads_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/purge endpoint."""
        response = app_client.post("/aria2/purge")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["purged_count"] == 3
        
        # Verify model method was called
        mock_aria2_model.purge_downloads.assert_called_once()
    
    def test_get_global_status_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/global-stats endpoint."""
        response = app_client.get("/aria2/global-stats")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["download_speed"] == 5120
        assert data["upload_speed"] == 1024
        
        # Verify model method was called
        mock_aria2_model.get_global_status.assert_called_once()
    
    def test_start_daemon_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/daemon/start endpoint."""
        response = app_client.post(
            "/aria2/daemon/start",
            json={
                "options": {
                    "dir": "/downloads",
                    "max-concurrent-downloads": 5
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert data["pid"] == 12345
        
        # Verify model method was called
        mock_aria2_model.start_daemon.assert_called_once()
    
    def test_stop_daemon_endpoint(self, app_client, mock_aria2_model):
        """Test /aria2/daemon/stop endpoint."""
        response = app_client.post("/aria2/daemon/stop")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        
        # Verify model method was called
        mock_aria2_model.stop_daemon.assert_called_once()
    
    def test_error_handling(self, app_client, mock_aria2_model):
        """Test error handling in endpoints."""
        # Set up model to return an error
        mock_aria2_model.get_status.return_value = {
            "success": False,
            "error": "Download not found",
            "error_type": "not_found"
        }
        
        # Test endpoint that should return a 404
        response = app_client.get("/aria2/status/nonexistent-gid")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Download not found" in data["detail"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])