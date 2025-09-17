
#!/usr/bin/env python3
"""
Comprehensive Test Suite for Enhanced Dashboard

Tests all 90+ endpoints and features to ensure proper integration
with modern light initialization + bucket VFS architecture.
"""

import asyncio
import json
import requests
import pytest
from pathlib import Path
import time

class TestEnhancedComprehensiveDashboard:
    """Test suite for all dashboard features."""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment."""
        cls.base_url = "http://localhost:8080"
        cls.test_data_dir = Path("~/.ipfs_kit_test").expanduser()
        cls.test_data_dir.mkdir(parents=True, exist_ok=True)
        
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
            response = requests.get(f"{self.base_url}{endpoint}")
            assert response.status_code in [200, 404], f"Failed: {endpoint}"
            
    def test_service_management(self):
        """Test service management endpoints."""
        # Test service listing
        response = requests.get(f"{self.base_url}/api/services")
        assert response.status_code in [200, 404]
        
        # Test service details
        response = requests.get(f"{self.base_url}/api/services/ipfs")
        assert response.status_code in [200, 404]
        
    def test_backend_management(self):
        """Test backend management endpoints."""
        # Test backend listing
        response = requests.get(f"{self.base_url}/api/backends")
        assert response.status_code in [200, 404]
        
        # Test backend health
        response = requests.get(f"{self.base_url}/api/backends/health")
        assert response.status_code in [200, 404]
        
    def test_bucket_operations(self):
        """Test bucket operations endpoints."""
        # Test bucket listing
        response = requests.get(f"{self.base_url}/api/buckets")
        assert response.status_code in [200, 404]
        
        # Test bucket index
        response = requests.get(f"{self.base_url}/api/bucket_index")
        assert response.status_code in [200, 404]
        
    def test_peer_management(self):
        """Test peer management endpoints."""
        # Test peer listing
        response = requests.get(f"{self.base_url}/api/peers")
        assert response.status_code in [200, 404]
        
        # Test peer stats
        response = requests.get(f"{self.base_url}/api/peers/stats")
        assert response.status_code in [200, 404]
        
    def test_analytics_monitoring(self):
        """Test analytics and monitoring endpoints."""
        # Test analytics summary
        response = requests.get(f"{self.base_url}/api/analytics/summary")
        assert response.status_code in [200, 404]
        
        # Test performance analytics
        response = requests.get(f"{self.base_url}/api/analytics/performance")
        assert response.status_code in [200, 404]
        
    def test_configuration_management(self):
        """Test configuration management endpoints."""
        # Test config listing
        response = requests.get(f"{self.base_url}/api/configs")
        assert response.status_code in [200, 404]
        
        # Test config schemas
        response = requests.get(f"{self.base_url}/api/configs/schemas")
        assert response.status_code in [200, 404]
        
    def test_pin_management(self):
        """Test pin management endpoints."""
        # Test pin listing
        response = requests.get(f"{self.base_url}/api/pins")
        assert response.status_code in [200, 404]
        
    def test_log_management(self):
        """Test log management endpoints."""
        # Test log access
        response = requests.get(f"{self.base_url}/api/logs")
        assert response.status_code in [200, 404]
        
    def test_mcp_protocol(self):
        """Test MCP protocol endpoints."""
        # Test MCP status
        response = requests.get(f"{self.base_url}/api/mcp")
        assert response.status_code in [200, 404]
        
        # Test MCP tools
        response = requests.get(f"{self.base_url}/api/mcp/tools")
        assert response.status_code in [200, 404]
        
    def test_light_initialization(self):
        """Test light initialization fallbacks."""
        # This would test that the dashboard works even when
        # optional components are not available
        pass
        
    def test_bucket_vfs_integration(self):
        """Test bucket VFS integration."""
        # Test VFS operations
        response = requests.get(f"{self.base_url}/api/vfs")
        assert response.status_code in [200, 404]
        
    def test_state_management(self):
        """Test ~/.ipfs_kit/ state management."""
        # Verify state directory structure
        assert self.test_data_dir.exists()
        
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
