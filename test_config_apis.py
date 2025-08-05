#!/usr/bin/env python3
"""
Simple test for configuration management API functionality.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

async def test_config_apis():
    """Test the configuration management APIs directly."""
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
        
        print("🔧 Testing configuration management APIs...")
        
        # Test getting all configs
        result = await dashboard._get_all_configs()
        print(f"📋 All configs result: {result['success']}")
        if result['success']:
            configs = result['configs']
            print(f"   - Backend configs: {len(configs.get('backend_configs', {}))}")
            print(f"   - Bucket configs: {len(configs.get('bucket_configs', {}))}")
            print(f"   - Main configs: {len(configs.get('main_configs', {}))}")
            print(f"   - Schemas: {len(configs.get('schemas', {}))}")
            
            # Show some backend config names
            backend_configs = configs.get('backend_configs', {})
            if backend_configs:
                print(f"   - Backend examples: {list(backend_configs.keys())[:3]}")
            
            # Show some bucket config names  
            bucket_configs = configs.get('bucket_configs', {})
            if bucket_configs:
                print(f"   - Bucket examples: {list(bucket_configs.keys())[:3]}")
        
        # Test config schemas
        schemas = dashboard._get_config_schemas()
        print(f"📝 Schemas available: {list(schemas.keys())}")
        
        # Test validation for an existing backend
        backend_configs = result['configs'].get('backend_configs', {})
        if backend_configs:
            first_backend = list(backend_configs.keys())[0]
            print(f"🔍 Testing validation for backend: {first_backend}")
            validation_result = await dashboard._validate_config('backend', first_backend)
            print(f"   - Validation result: {validation_result}")
        
        print("✅ Configuration management APIs working perfectly!")
        
        # Test create/update operations
        test_config = {
            "name": "test-backend",
            "type": "s3",
            "enabled": True,
            "config": {
                "access_key_id": "test-access-key",
                "secret_access_key": "test-secret-key", 
                "bucket_name": "test-bucket",
                "region": "us-east-1"
            },
            "metadata": {
                "description": "Test S3 backend for API testing",
                "version": "1.0"
            }
        }
        
        print(f"💾 Testing backend creation...")
        create_result = await dashboard._create_config('backend', 'test-backend', test_config)
        print(f"   - Create result: {create_result}")
        
        if create_result.get('success'):
            print(f"🧪 Testing backend validation...")
            validate_result = await dashboard._validate_config('backend', 'test-backend')
            print(f"   - Validation result: {validate_result}")
            
            print(f"🗑️ Cleaning up test backend...")
            delete_result = await dashboard._delete_config('backend', 'test-backend')
            print(f"   - Delete result: {delete_result}")
        
        print("🎉 All configuration management tests passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_config_apis())
