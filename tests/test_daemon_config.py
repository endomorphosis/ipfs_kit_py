#!/usr/bin/env python3
"""Test daemon configuration manager functionality"""

import os
import sys

sys.path.insert(0, ".")

print("🧪 Testing daemon configuration manager...")

try:
    print("📦 Importing daemon config manager...")
    from daemon_config_manager import DaemonConfigManager

    print("✅ Successfully imported DaemonConfigManager")

    print("📦 Creating manager instance...")
    manager = DaemonConfigManager()
    print("✅ Manager created successfully")

    print("📦 Getting default configurations...")
    ipfs_config = manager.get_default_ipfs_config()
    print(f"✅ Default IPFS config: {ipfs_config}")

    lotus_config = manager.get_default_lotus_config()
    print(f"✅ Default Lotus config: {lotus_config}")

    lassie_config = manager.get_default_lassie_config()
    print(f"✅ Default Lassie config: {lassie_config}")

    print("🎉 All tests passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
