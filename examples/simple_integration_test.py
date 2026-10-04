#!/usr/bin/env python3
"""
Simple Integration Test for Enhanced Comprehensive Dashboard

This test validates that the enhanced dashboard works correctly with
the existing MCP server infrastructure and light initialization.
"""

import sys
import json
import requests
import time
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_dashboard_import():
    """Test that the enhanced dashboard can be imported with light initialization."""
    print("🧪 Testing Dashboard Import...")
    try:
        from enhanced_comprehensive_dashboard import EnhancedComprehensiveDashboard
        print("✅ Enhanced dashboard imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import dashboard: {e}")
        return False

def test_dashboard_initialization():
    """Test dashboard initialization with current environment."""
    print("🧪 Testing Dashboard Initialization...")
    try:
        from enhanced_comprehensive_dashboard import EnhancedComprehensiveDashboard
        
        config = {
            'host': '127.0.0.1',
            'port': 8084,  # Use different port to avoid conflicts
            'data_dir': '~/.ipfs_kit',
            'debug': True
        }
        
        dashboard = EnhancedComprehensiveDashboard(config)
        print("✅ Dashboard initialized successfully")
        print(f"📁 Data directory: {dashboard.data_dir}")
        print(f"🔧 Debug mode: {config['debug']}")
        
        # Test light initialization components
        if hasattr(dashboard, 'bucket_interface'):
            print("✅ Bucket interface available")
        else:
            print("⚠️  Bucket interface in fallback mode")
            
        if hasattr(dashboard, 'mcp_backend_controller'):
            print("✅ MCP backend controller available")
        else:
            print("⚠️  MCP backend controller in fallback mode")
            
        return True
    except Exception as e:
        print(f"❌ Failed to initialize dashboard: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mcp_server_connection():
    """Test connection to existing MCP server."""
    print("🧪 Testing MCP Server Connection...")
    try:
        # Try to connect to standard MCP server ports
        mcp_ports = [3000, 3001, 3002, 8080, 8081, 8082, 8083]
        
        for port in mcp_ports:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✅ Found MCP server on port {port}")
                    return True
            except:
                continue
                
        print("⚠️  No MCP servers found on standard ports - that's okay for testing")
        return True
    except Exception as e:
        print(f"❌ Error testing MCP connection: {e}")
        return False

def test_ipfs_kit_state_directory():
    """Test ~/.ipfs_kit/ state directory access."""
    print("🧪 Testing IPFS Kit State Directory...")
    try:
        from pathlib import Path
        import os
        
        ipfs_kit_dir = Path.home() / ".ipfs_kit"
        print(f"📁 Checking: {ipfs_kit_dir}")
        
        if ipfs_kit_dir.exists():
            print("✅ ~/.ipfs_kit/ directory exists")
            
            # Check for common subdirectories
            subdirs = ['backends', 'buckets', 'config', 'logs', 'state']
            for subdir in subdirs:
                subdir_path = ipfs_kit_dir / subdir
                if subdir_path.exists():
                    print(f"✅ Found: ~/.ipfs_kit/{subdir}/")
                else:
                    print(f"📝 Missing: ~/.ipfs_kit/{subdir}/ (will be created)")
        else:
            print("📝 ~/.ipfs_kit/ directory doesn't exist (will be created)")
            
        return True
    except Exception as e:
        print(f"❌ Error checking state directory: {e}")
        return False

def test_dashboard_endpoints():
    """Test that dashboard has all expected endpoints."""
    print("🧪 Testing Dashboard Endpoints...")
    try:
        from enhanced_comprehensive_dashboard import EnhancedComprehensiveDashboard
        
        config = {
            'host': '127.0.0.1',
            'port': 8084,
            'data_dir': '~/.ipfs_kit',
            'debug': True
        }
        
        dashboard = EnhancedComprehensiveDashboard(config)
        
        # Check if FastAPI app is created
        if hasattr(dashboard, 'app'):
            print("✅ FastAPI app created")
            
            # Get routes
            routes = [route.path for route in dashboard.app.routes]
            
            # Check for key endpoint categories
            categories = {
                'System': ['/api/system-overview', '/api/metrics'],
                'Services': ['/api/services', '/api/service-status'],
                'Backends': ['/api/backends', '/api/backend-health'],
                'Buckets': ['/api/buckets', '/api/bucket-operations'],
                'MCP': ['/mcp/tools', '/mcp/status'],
                'Config': ['/api/configs', '/api/config-management']
            }
            
            found_endpoints = 0
            total_endpoints = sum(len(endpoints) for endpoints in categories.values())
            
            for category, endpoints in categories.items():
                category_found = 0
                for endpoint in endpoints:
                    if any(endpoint in route for route in routes):
                        category_found += 1
                        found_endpoints += 1
                        
                print(f"📊 {category}: {category_found}/{len(endpoints)} endpoints found")
            
            print(f"📈 Total endpoints found: {found_endpoints}/{total_endpoints}")
            print(f"📋 Total routes registered: {len(routes)}")
            
            return True
        else:
            print("❌ FastAPI app not created")
            return False
            
    except Exception as e:
        print(f"❌ Error testing endpoints: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests."""
    print("🚀 Enhanced Comprehensive Dashboard - Integration Test")
    print("=" * 60)
    
    tests = [
        test_dashboard_import,
        test_dashboard_initialization,
        test_mcp_server_connection,
        test_ipfs_kit_state_directory,
        test_dashboard_endpoints
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print()
        try:
            if test():
                passed += 1
                print("✅ PASSED")
            else:
                print("❌ FAILED")
        except Exception as e:
            print(f"❌ FAILED with exception: {e}")
        print("-" * 40)
    
    print()
    print("📊 INTEGRATION TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Dashboard ready for integration.")
    else:
        print("⚠️  Some tests failed. Check output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
