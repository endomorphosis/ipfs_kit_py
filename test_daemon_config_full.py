#!/usr/bin/env python3
"""Test daemon configuration functionality"""

import os
import sys
sys.path.insert(0, '.')

print("🧪 Testing daemon configuration functionality...")

try:
    print("📦 Importing daemon config manager...")
    from daemon_config_manager import DaemonConfigManager
    print("✅ Successfully imported DaemonConfigManager")
    
    print("📦 Creating manager instance...")
    manager = DaemonConfigManager()
    print("✅ Manager created successfully")
    
    print("📦 Testing IPFS configuration...")
    ipfs_result = manager.check_and_configure_ipfs()
    print(f"✅ IPFS config result: {ipfs_result}")
    
    print("📦 Testing Lassie configuration...")
    lassie_result = manager.check_and_configure_lassie()
    print(f"✅ Lassie config result: {lassie_result}")
    
    print("📦 Testing overall configuration...")
    overall_result = manager.check_and_configure_all_daemons()
    print(f"✅ Overall config result: {overall_result}")
    
    print("🎉 All configuration tests completed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
