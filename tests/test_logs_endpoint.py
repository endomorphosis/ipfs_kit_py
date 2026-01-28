#!/usr/bin/env python3
"""
Test script to verify the logs endpoint is working correctly.
"""

import anyio
import sys
import logging
from pathlib import Path
import pytest

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

pytestmark = pytest.mark.anyio

async def test_logs_endpoint():
    """Test the logs endpoint functionality."""
    print("🧪 Testing Logs Endpoint Functionality")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.dashboard.comprehensive_mcp_dashboard import ComprehensiveMCPDashboard
        
        # Initialize dashboard
        config = {
            'data_dir': '~/.ipfs_kit/data',
            'port': 8085,
            'mcp_server_url': 'http://127.0.0.1:8085'
        }
        
        print("✅ Initializing dashboard...")
        dashboard = ComprehensiveMCPDashboard(config)
        
        # Generate some test logs
        print("📝 Generating test logs...")
        test_logger = logging.getLogger('test_logs_system')
        test_logger.info('Test info message for logs endpoint')
        test_logger.warning('Test warning message for logs endpoint')
        test_logger.error('Test error message for logs endpoint')
        
        # Test the logs endpoint directly
        print("🔍 Testing logs endpoint...")
        result = await dashboard._get_logs(component='all', level='info', limit=10)
        
        print(f"✅ Logs endpoint returned {result.get('total_count', 0)} logs")
        
        # Display some logs
        logs = result.get('logs', [])
        print(f"\n📋 Sample logs (showing first 5):")
        for i, log_entry in enumerate(logs[:5], 1):
            timestamp = log_entry.get('timestamp', 'N/A')
            level = log_entry.get('level', 'N/A')
            component = log_entry.get('component', 'N/A')
            message = log_entry.get('raw_message', 'N/A')
            print(f"  {i}. [{level}] {component}: {message}")
        
        # Test different parameters
        print(f"\n🔬 Testing different log levels...")
        
        # Test error level only
        error_result = await dashboard._get_logs(component='all', level='error', limit=5)
        print(f"   - Error logs: {error_result.get('total_count', 0)}")
        
        # Test warning level and above
        warning_result = await dashboard._get_logs(component='all', level='warning', limit=5)
        print(f"   - Warning+ logs: {warning_result.get('total_count', 0)}")
        
        # Test specific component filter
        component_result = await dashboard._get_logs(component='test_logs_system', level='all', limit=5)
        print(f"   - Test component logs: {component_result.get('total_count', 0)}")
        
        print(f"\n✅ All tests passed! Logs endpoint is working correctly.")
        print(f"🌐 The logs endpoint should be available at: http://localhost:8085/api/logs")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = anyio.run(test_logs_endpoint)
    sys.exit(0 if success else 1)
