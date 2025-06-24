#!/usr/bin/env python3
"""
Load Enhanced Tools into MCP Server

This script loads the enhanced tools directly into the MCP server.
"""

import os
import sys
import json
import logging
import importlib.util
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def import_module_from_file(file_path, module_name=None):
    """Import a module from a file path"""
    if not os.path.exists(file_path):
        raise ImportError(f"File not found: {file_path}")

    if module_name is None:
        module_name = os.path.basename(file_path).split('.')[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {file_path}")

    if spec.loader is None:
        raise ImportError(f"Could not get loader for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_tools_from_json():
    """Load tools from the JSON file"""
    try:
        if not os.path.exists("mcp_registered_tools.json"):
            logger.error("mcp_registered_tools.json not found")
            return None

        with open("mcp_registered_tools.json", "r") as f:
            tools = json.load(f)

        logger.info(f"Loaded {len(tools)} tools from JSON file")
        return tools

    except Exception as e:
        logger.error(f"Error loading tools from JSON: {e}")
        return None

def patch_mcp_server():
    """Create a patched version of the MCP server to load tools"""
    try:
        patch_content = """
import json
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_tools_into_server(server_file, tools_file):
    """Load tools into an MCP server"""
    try:
        # Load tools from JSON file
        with open(tools_file, "r") as f:
            tools = json.load(f)

        # Create a simple patch to add tools to the server file
        patch = f'''
# Add tools to MCP server
def register_mcp_tools():
    """Register tools with MCP server"""
    tools = {tools}
    return tools

# Add to server
if __name__ == "__main__":
    # Existing server code would be above this line
    try:
        registered_tools = register_mcp_tools()
        if registered_tools:
            print(f"Registered {{len(registered_tools)}} tools with MCP server")
    except Exception as e:
        print(f"Error registering tools: {{e}}")
'''

        # Write the patch to a file
        with open("patched_mcp_server.py", "w") as f:
            # First, copy the original server file
            with open(server_file, "r") as original:
                f.write(original.read())

            # Then append the patch
            f.write(patch)

        logger.info(f"✅ Successfully created patched MCP server")
        return True

    except Exception as e:
        logger.error(f"Error patching MCP server: {e}")
        return False

def create_direct_loader():
    """Create a script that directly loads tools into the MCP tools registry"""
    try:
        with open("direct_mcp_loader.py", "w") as f:
            f.write('''
#!/usr/bin/env python3
"""
Direct MCP Loader

This script directly loads tools into the MCP server.
"""

import os
import sys
import json
import importlib.util

def import_module_from_file(file_path, module_name=None):
    """Import a module from a file path"""
    if not os.path.exists(file_path):
        raise ImportError(f"File not found: {file_path}")

    if module_name is None:
        module_name = os.path.basename(file_path).split('.')[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    """Main function"""
    # Load the tools from JSON
    with open("mcp_registered_tools.json", "r") as f:
        tools = json.load(f)

    print(f"Loaded {len(tools)} tools from JSON file")

    # Import the direct_mcp_server module
    if not os.path.exists("direct_mcp_server.py"):
        print("direct_mcp_server.py not found")
        return 1

    direct_mcp = import_module_from_file("direct_mcp_server.py")

    # Check if the module has a tools attribute
    if hasattr(direct_mcp, "tools"):
        # Add the tools to the module's tools attribute
        direct_mcp.tools.extend(tools)
        print(f"Added {len(tools)} tools to direct_mcp_server.tools")
        return 0

    # If the module doesn't have a tools attribute, create a tools registry
    # and inject it into the module
    direct_mcp.tools = tools
    print(f"Created tools registry in direct_mcp_server with {len(tools)} tools")
    return 0

if __name__ == "__main__":
    sys.exit(main())
''')

        # Make the script executable
        os.chmod("direct_mcp_loader.py", 0o755)

        logger.info(f"✅ Created direct loader script at direct_mcp_loader.py")
        return True

    except Exception as e:
        logger.error(f"Error creating direct loader: {e}")
        return False
"""
    Append tools to the MCP server file
    """
    try:
        # Read the original server file
        if not os.path.exists("direct_mcp_server.py"):
            logger.error("direct_mcp_server.py not found")
            return False

        # Load tools
        tools = load_tools_from_json()
        if not tools:
            return False

        # Create a modified version of the server file that includes the tools
        with open("direct_mcp_server_with_tools.py", "w") as f:
            # First, read the original content
            with open("direct_mcp_server.py", "r") as original:
                server_content = original.read()

            # Look for the existing tools section
            if "tools = [" in server_content:
                # If tools section exists, replace it
                lines = server_content.split("\n")
                tools_start = None
                tools_end = None

                for i, line in enumerate(lines):
                    if line.strip().startswith("tools = ["):
                        tools_start = i
                    elif tools_start is not None and line.strip() == "]":
                        tools_end = i
                        break

                if tools_start is not None and tools_end is not None:
                    # Replace the existing tools with new tools
                    new_lines = lines[:tools_start]
                    new_lines.append("tools = ")
                    new_lines.append(json.dumps(tools, indent=4))
                    new_lines.extend(lines[tools_end+1:])

                    f.write("\n".join(new_lines))
                    logger.info("✅ Replaced existing tools section in server file")
                else:
                    # Could not find the end of the tools section, append the tools
                    f.write(server_content)
                    f.write("\n\n# Enhanced tools\n")
                    f.write("tools = ")
                    f.write(json.dumps(tools, indent=4))
                    logger.info("✅ Appended tools to server file (could not find end of existing tools section)")
            else:
                # No existing tools section, append the tools
                f.write(server_content)
                f.write("\n\n# Enhanced tools\n")
                f.write("tools = ")
                f.write(json.dumps(tools, indent=4))
                logger.info("✅ Appended tools to server file (no existing tools section)")

        logger.info(f"✅ Created modified MCP server file at direct_mcp_server_with_tools.py")
        return True

    except Exception as e:
        logger.error(f"Error appending tools to server file: {e}")
        return False

def create_restart_script():
    """Create a script to restart the MCP server with the new tools"""
    try:
        with open("restart_mcp_with_tools.sh", "w") as f:
            f.write("""#!/bin/bash
# Restart MCP server with the new tools

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server" || true
sleep 2

echo "Starting MCP server with enhanced tools..."
python direct_mcp_server_with_tools.py &

echo "MCP server started with PID $!"
echo "Waiting for server to initialize..."
sleep 3

echo "✅ MCP server is now running with enhanced tools"
echo "You can use the new tools through the JSON-RPC interface"
""")

        # Make the script executable
        os.chmod("restart_mcp_with_tools.sh", 0o755)

        logger.info(f"✅ Created restart script at restart_mcp_with_tools.sh")
        return True

    except Exception as e:
        logger.error(f"Error creating restart script: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting enhanced tools loader...")

    # Load tools
    tools = load_tools_from_json()
    if not tools:
        logger.error("❌ Failed to load tools from JSON")
        return 1

    # Append tools to the MCP server file
    if not patch_mcp_server():
        logger.error("❌ Failed to create patched MCP server file")
        return 1

    # Create direct loader
    if not create_direct_loader():
        logger.error("❌ Failed to create direct loader")
        return 1

    # Create restart script
    if not create_restart_script():
        logger.error("❌ Failed to create restart script")
        return 1

    logger.info("\n✅ Enhanced tools loader completed successfully")
    logger.info("To use the enhanced tools:")
    logger.info("  1. Run ./restart_mcp_with_tools.sh to restart the MCP server with enhanced tools")
    logger.info("  2. The MCP server will now have access to the enhanced tools")
    return 0

if __name__ == "__main__":
    sys.exit(main())
