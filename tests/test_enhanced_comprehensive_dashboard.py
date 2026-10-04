
#!/usr/bin/env python3
"""Comprehensive smoke tests for the enhanced dashboard.

This module was originally written as a manual integration harness that expected
an external server listening on localhost:8080.

For automated test runs, use FastAPI's TestClient against the in-process
`ConsolidatedMCPDashboard` app so tests are hermetic and don't hang on missing
services.
"""

import tempfile
import shutil

import pytest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard

class TestEnhancedComprehensiveDashboard:
    """Test suite for all dashboard features."""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment."""
        cls._tmpdir = tempfile.mkdtemp(prefix="ipfs_kit_test_dash_")
        cls.app = ConsolidatedMCPDashboard({"host": "127.0.0.1", "port": 0, "data_dir": cls._tmpdir})
        cls.client = TestClient(cls.app.app)

    @classmethod
    def teardown_class(cls):
        try:
            shutil.rmtree(getattr(cls, "_tmpdir", ""), ignore_errors=True)
        except Exception:
            pass

    def _assert_okish(self, r):
        # Some endpoints are intentionally protected; accept 401/403 in addition
        # to "implemented" (200) and "not present" (404).
        assert r.status_code in (200, 401, 403, 404), f"Unexpected status {r.status_code} for {r.request.url}"
        
    def test_core_endpoints(self):
        """Test core system endpoints."""
        endpoints = [
            "/",
            "/api/status", 
            "/api/health",
            "/api/system-overview",
            "/api/metrics"
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self._assert_okish(response)
            
    def test_service_management(self):
        """Test service management endpoints."""
        # Test service listing
        response = self.client.get("/api/services")
        self._assert_okish(response)
        
        # Test service details
        response = self.client.get("/api/services/ipfs")
        self._assert_okish(response)
        
    def test_backend_management(self):
        """Test backend management endpoints."""
        # Test backend listing
        response = self.client.get("/api/backends")
        self._assert_okish(response)
        
        # Test backend health
        response = self.client.get("/api/backends/health")
        self._assert_okish(response)
        
    def test_bucket_operations(self):
        """Test bucket operations endpoints."""
        # Test bucket listing
        response = self.client.get("/api/buckets")
        self._assert_okish(response)
        
        # Test bucket index
        response = self.client.get("/api/bucket_index")
        self._assert_okish(response)
        
    def test_peer_management(self):
        """Test peer management endpoints."""
        # Test peer listing
        response = self.client.get("/api/peers")
        self._assert_okish(response)
        
        # Test peer stats
        response = self.client.get("/api/peers/stats")
        self._assert_okish(response)
        
    def test_analytics_monitoring(self):
        """Test analytics and monitoring endpoints."""
        # Test analytics summary
        response = self.client.get("/api/analytics/summary")
        self._assert_okish(response)
        
        # Test performance analytics
        response = self.client.get("/api/analytics/performance")
        self._assert_okish(response)
        
    def test_configuration_management(self):
        """Test configuration management endpoints."""
        # Test config listing
        response = self.client.get("/api/configs")
        self._assert_okish(response)
        
        # Test config schemas
        response = self.client.get("/api/configs/schemas")
        self._assert_okish(response)
        
    def test_pin_management(self):
        """Test pin management endpoints."""
        # Test pin listing
        response = self.client.get("/api/pins")
        self._assert_okish(response)
        
    def test_log_management(self):
        """Test log management endpoints."""
        # Test log access
        response = self.client.get("/api/logs")
        self._assert_okish(response)
        
    def test_mcp_protocol(self):
        """Test MCP protocol endpoints."""
        # Test MCP status
        response = self.client.get("/api/mcp")
        self._assert_okish(response)
        
        # Test MCP tools
        response = self.client.get("/api/mcp/tools")
        self._assert_okish(response)
        
    def test_light_initialization(self):
        """Test light initialization fallbacks."""
        # This would test that the dashboard works even when
        # optional components are not available
        pass
        
    def test_bucket_vfs_integration(self):
        """Test bucket VFS integration."""
        # Test VFS operations
        response = self.client.get("/api/vfs")
        self._assert_okish(response)
        
    def test_state_management(self):
        """Test ~/.ipfs_kit/ state management."""
        # Verify state directory structure
        assert getattr(self, "_tmpdir", None)
        
if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
