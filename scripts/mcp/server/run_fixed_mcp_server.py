#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_server_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by server_runner.py

This file is kept for backward compatibility. Please use the unified server runner instead,
which provides comprehensive server capabilities with all fixes applied:

    python server_runner.py --server-type=anyio --debug

The server runner supports all configurations with additional options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run the fixed MCP server using the new server_runner."""
    # Show deprecation warning
    warnings.warn(
        "run_fixed_mcp_server.py is deprecated and will be removed in a future version. "
        "Please use server_runner.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Starting fixed MCP server using the new server_runner module...")

    # Check if server_runner.py exists
    server_runner_path = os.path.join(os.path.dirname(__file__), "server_runner.py")
    if not os.path.exists(server_runner_path):
        print("ERROR: server_runner.py not found. Please make sure it's in the same directory.")
        return 1

    # Build command for server_runner.py with equivalent parameters
    cmd = [
        sys.executable,
        server_runner_path,
        "--server-type=anyio",
        "--debug",
        "--port=9991",
        "--host=127.0.0.1",
        "--api-prefix=/api/v0/mcp"
    ]

    # Run server_runner
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping fixed MCP server...")
        return 0
    except Exception as e:
        print(f"Error running server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
