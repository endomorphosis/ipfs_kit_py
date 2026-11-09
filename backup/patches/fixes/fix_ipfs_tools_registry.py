#!/usr/bin/env python3
"""
Fix the formatting issues in the IPFS tools registry file.
"""

import json
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_registry():
    """Fix the IPFS tools registry file"""
    registry_path = "ipfs_tools_registry.py"

    try:
        # Read the current registry
        with open(registry_path, 'r') as f:
            content = f.read()

        # Extract all tool entries from the file - look for all dictionary entries
        tools = []
        current_tool = ""
        depth = 0
        in_tool = False

        for line in content.split("\n"):
            stripped = line.strip()

            if stripped.startswith("{") and not in_tool:
                in_tool = True
                current_tool = line + "\n"
                if "{" in stripped:
                    depth += stripped.count("{")
                continue

            if in_tool:
                current_tool += line + "\n"

                if "{" in stripped:
                    depth += stripped.count("{")

                if "}" in stripped:
                    depth -= stripped.count("}")

                if depth == 0 and stripped.endswith("},"):
                    # We've reached the end of a tool entry
                    tools.append(current_tool.strip())
                    current_tool = ""
                    in_tool = False

        # Filter out any invalid entries
        valid_tools = []
        for tool in tools:
            if '"name":' in tool and '"description":' in tool and '"schema":' in tool:
                valid_tools.append(tool)

        # Create a new registry file
        new_content = '''"""IPFS MCP Tools Registry - Fixed by fix_ipfs_tools_registry.py"""

IPFS_TOOLS = [
{}
]

def get_ipfs_tools():
    """Get all IPFS tool definitions"""
    return IPFS_TOOLS'''.format("\n".join(valid_tools))

        # Write the fixed registry
        with open(registry_path, 'w') as f:
            f.write(new_content)

        logger.info(f"✅ Fixed IPFS tools registry with {len(valid_tools)} valid tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing registry: {e}")
        return False

if __name__ == "__main__":
    fix_registry()
