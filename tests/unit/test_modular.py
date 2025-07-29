#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

print("Testing modular server components...")

try:
    from mcp.ipfs_kit.backends.backend_clients import IPFSClient
    print("✓ Backend clients imported")
except Exception as e:
    print(f"✗ Backend clients import failed: {e}")
    sys.exit(1)

try:
    from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    print("✓ Health monitor imported")
except Exception as e:
    print(f"✗ Health monitor import failed: {e}")
    sys.exit(1)

try:
    monitor = BackendHealthMonitor()
    print("✓ Health monitor created")
    print(f"Available backends: {list(monitor.backends.keys())}")
except Exception as e:
    print(f"✗ Health monitor creation failed: {e}")
    sys.exit(1)

try:
    from mcp.ipfs_kit.dashboard.template_manager import DashboardTemplateManager
    print("✓ Template manager imported")
except Exception as e:
    print(f"✗ Template manager import failed: {e}")
    sys.exit(1)

try:
    from mcp.ipfs_kit.api.routes import APIRoutes
    print("✓ API routes imported")
except Exception as e:
    print(f"✗ API routes import failed: {e}")
    sys.exit(1)

try:
    from mcp.ipfs_kit.mcp_tools.tool_manager import MCPToolManager
    print("✓ MCP tools imported")
except Exception as e:
    print(f"✗ MCP tools import failed: {e}")
    sys.exit(1)

print("\nAll components imported successfully!")
print("Ready to start modular server...")
