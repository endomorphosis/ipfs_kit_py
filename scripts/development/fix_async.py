#!/usr/bin/env python3
"""
Fix async methods in modern_mcp_feature_bridge.py
"""
import re

def fix_async_methods():
    with open('/home/devel/ipfs_kit_py/modern_mcp_feature_bridge.py', 'r') as f:
        content = f.read()
    
    # Replace async def with def for specific methods
    methods_to_fix = [
        'get_system_status', 'get_system_health', 'get_system_metrics',
        'get_mcp_status', 'get_buckets', 'get_bucket_details', 
        'get_backends', 'get_backend_health', 'get_all_configs'
    ]
    
    for method in methods_to_fix:
        # Replace async def with def
        pattern = f'async def {method}'
        replacement = f'def {method}'
        content = content.replace(pattern, replacement)
        
        # Replace await calls inside these methods (except for bucket manager calls)
        # This is a simple approach - might need refinement
        content = re.sub(
            f'(def {method}.*?)await ((?!self\\.bucket_manager).*?)(\n.*?def )',
            r'\1\2\3',
            content,
            flags=re.DOTALL
        )
    
    with open('/home/devel/ipfs_kit_py/modern_mcp_feature_bridge.py', 'w') as f:
        f.write(content)
    
    print("Fixed async methods")

if __name__ == "__main__":
    fix_async_methods()
