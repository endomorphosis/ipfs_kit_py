#!/usr/bin/env python3
"""
Simplified test script for MCP Discovery integration.

This script checks if the MCP Discovery controller is registered correctly in the MCP server.
"""

import sys
import os
import importlib.util

print("Testing MCP Discovery Controller Integration")
print("-------------------------------------------")

# First check if the MCP Discovery model and controller modules exist
mcp_discovery_model_path = os.path.join(
    os.path.dirname(__file__),
    "ipfs_kit_py",
    "mcp",
    "models",
    "mcp_discovery_model.py"
)

mcp_discovery_controller_path = os.path.join(
    os.path.dirname(__file__),
    "ipfs_kit_py",
    "mcp",
    "controllers",
    "mcp_discovery_controller.py"
)

print("Checking if required files exist...")
print(f"MCP Discovery Model: {'EXISTS' if os.path.exists(mcp_discovery_model_path) else 'MISSING'}")
print(f"MCP Discovery Controller: {'EXISTS' if os.path.exists(mcp_discovery_controller_path) else 'MISSING'}")

print("\nChecking server.py for discovery integration...")
server_path = os.path.join(
    os.path.dirname(__file__),
    "ipfs_kit_py",
    "mcp",
    "server.py"
)

# Check if server.py contains the necessary references
with open(server_path, 'r') as f:
    server_content = f.read()

# Check for necessary imports
has_imports = "from ipfs_kit_py.mcp.controllers.mcp_discovery_controller import MCPDiscoveryController" in server_content
has_model_import = "from ipfs_kit_py.mcp.models.mcp_discovery_model import MCPDiscoveryModel" in server_content
has_flag = "HAS_MCP_DISCOVERY_CONTROLLER = True" in server_content

# Check for model initialization
has_model_init = 'self.models["mcp_discovery"] = MCPDiscoveryModel(' in server_content

# Check for controller initialization
has_controller_init = 'self.controllers["mcp_discovery"] = MCPDiscoveryController(' in server_content

# Check for route registration
has_route_registration = 'if "mcp_discovery" in self.controllers:' in server_content and 'self.controllers["mcp_discovery"].register_routes(' in server_content

print(f"Import statements: {'FOUND' if has_imports and has_model_import and has_flag else 'MISSING'}")
print(f"Model initialization: {'FOUND' if has_model_init else 'MISSING'}")
print(f"Controller initialization: {'FOUND' if has_controller_init else 'MISSING'}")
print(f"Route registration: {'FOUND' if has_route_registration else 'MISSING'}")

# Overall result
success = has_imports and has_model_import and has_flag and has_model_init and has_controller_init and has_route_registration
print("\nTEST RESULT:", "SUCCESS" if success else "FAILURE")
print("-------------------------------------------")

sys.exit(0 if success else 1)