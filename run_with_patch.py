#!/usr/bin/env python3
"""
Wrapper script to run the final MCP server with asyncio patch
"""
import os
import sys
import importlib.util

# First import and execute the patch
patch_path = os.path.join(os.getcwd(), "asyncio_patch.py")
spec = importlib.util.spec_from_file_location("asyncio_patch", patch_path)
patch_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_module)

# Now import and run the actual server module
server_path = os.path.join(os.getcwd(), "final_mcp_server.py")
spec = importlib.util.spec_from_file_location("final_mcp_server", server_path)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

# Run the main function
sys.exit(server_module.main())
