#!/usr/bin/env python3
"""
Test script for the comprehensive configuration management dashboard.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

async def test_dashboard():
    """Test the dashboard configuration management functionality."""
    try:
        from ipfs_kit_py.dashboard.comprehensive_mcp_dashboard import ComprehensiveMCPDashboard
        
        # Create dashboard with minimal config
        config = {
            'host': '127.0.0.1',
            'port': 8085,
            'mcp_server_url': 'http://localhost:8004',
            'data_dir': '~/.ipfs_kit',
            'debug': True,
            'update_interval': 5
        }
        
        dashboard = ComprehensiveMCPDashboard(config)
        
        # Test configuration API methods
        print("🔧 Testing configuration management APIs...")
        
        # Test getting all configs
        result = await dashboard._get_all_configs()
        print(f"📋 All configs result: {result['success']}")
        if result['success']:
            print(f"   - Backend configs: {len(result['configs'].get('backend_configs', {}))}")
            print(f"   - Bucket configs: {len(result['configs'].get('bucket_configs', {}))}")
            print(f"   - Main configs: {len(result['configs'].get('main_configs', {}))}")
        
        # Test schemas
        schemas = dashboard._get_config_schemas()
        print(f"📝 Schemas available: {list(schemas.keys())}")
        
        print("✅ Configuration management APIs working!")
        
        # Start the dashboard
        print(f"🚀 Starting dashboard on {config['host']}:{config['port']}")
        await dashboard.start()
        
    except KeyboardInterrupt:
        print("\n⏹️  Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dashboard())
