#!/usr/bin/env python3
"""
Patch script for adding AI/ML functionality to direct_mcp_server.py
"""

import os
import sys
import re
import shutil
from pathlib import Path

def patch_mcp_server(server_path):
    """
    Patch the direct_mcp_server.py file to add AI/ML functionality.

    Args:
        server_path: Path to the direct_mcp_server.py file

    Returns:
        True if successful, False otherwise
    """
    # Verify the file exists
    if not os.path.exists(server_path):
        print(f"Error: {server_path} does not exist")
        return False

    # Create a backup
    backup_path = f"{server_path}.bak"
    shutil.copy2(server_path, backup_path)
    print(f"Created backup at {backup_path}")

    # Read the server file
    with open(server_path, "r") as f:
        content = f.read()

    # Add import for AI/ML integrator
    import_pattern = r"import uvicorn"
    import_replacement = r"import uvicorn\n\n# Import AI/ML integrator\ntry:\n    from ipfs_kit_py.mcp.integrator import integrate_ai_ml_with_mcp_server\n    HAS_AI_ML_INTEGRATOR = True\nexcept ImportError:\n    print(\"AI/ML integrator not available\")\n    HAS_AI_ML_INTEGRATOR = False"
    content = re.sub(import_pattern, import_replacement, content)

    # Add AI/ML integration code to app initialization
    app_pattern = r"# Run with uvicorn"
    app_replacement = r"# Integrate AI/ML components if available\n    if HAS_AI_ML_INTEGRATOR:\n        try:\n            logger.info(\"Integrating AI/ML components with MCP server...\")\n            success = integrate_ai_ml_with_mcp_server(app)\n            if success:\n                logger.info(\"AI/ML integration successful\")\n            else:\n                logger.warning(\"AI/ML integration failed\")\n        except Exception as e:\n            logger.error(f\"Error integrating AI/ML components: {e}\")\n    \n    # Run with uvicorn"
    content = re.sub(app_pattern, app_replacement, content)

    # Write the modified content back to the file
    with open(server_path, "w") as f:
        f.write(content)

    print(f"Successfully patched {server_path} with AI/ML functionality")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    else:
        server_path = Path(__file__).parent.parent / "direct_mcp_server.py"

    success = patch_mcp_server(str(server_path))
    sys.exit(0 if success else 1)
