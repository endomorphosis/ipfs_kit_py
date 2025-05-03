#!/usr/bin/env python3
"""
MCP Integration Patch

This script patches the direct_mcp_server.py file to integrate our
virtual filesystem features and multiple storage backends at server startup.
"""

import os
import sys
import re
import logging
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def backup_file(file_path: str) -> bool:
    """Create a backup of the specified file"""
    backup_path = f"{file_path}.bak"
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def patch_mcp_server():
    """Patch direct_mcp_server.py to add our tools at startup"""
    mcp_server_path = "direct_mcp_server.py"
    
    # Check if file exists
    if not os.path.exists(mcp_server_path):
        logger.error(f"File not found: {mcp_server_path}")
        return False
    
    # Create backup
    if not backup_file(mcp_server_path):
        return False
    
    try:
        # Read the file
        with open(mcp_server_path, 'r') as f:
            content = f.read()
        
        # Import statements to add
        imports_to_add = """
# FS Journal and Multi-Backend imports
try:
    from fs_journal_tools import register_fs_journal_tools
    from ipfs_mcp_fs_integration import register_all_tools
    from multi_backend_fs_integration import register_multi_backend_tools, MultiBackendFS
    FS_JOURNAL_AVAILABLE = True
except ImportError:
    logger.warning("FS Journal or Multi-Backend integration not available")
    FS_JOURNAL_AVAILABLE = False
"""
        
        # Add imports after existing imports
        import_section_end = "from mcp_error_handling import format_error_response"
        if import_section_end in content:
            content = content.replace(
                import_section_end,
                f"{import_section_end}\n{imports_to_add}"
            )
        else:
            logger.warning("Import section not found, adding imports at the beginning")
            content = imports_to_add + content
        
        # Add initialization code in the initialize_server method
        init_code = """
        # Initialize FS Journal and Multi-Backend integration
        if FS_JOURNAL_AVAILABLE:
            try:
                logger.info("Initializing FS Journal tools...")
                register_fs_journal_tools(self)
                
                logger.info("Initializing extended FS Journal tools...")
                register_all_tools(self)
                
                logger.info("Initializing Multi-Backend filesystem...")
                self.multi_backend_fs = MultiBackendFS(os.getcwd())
                
                logger.info("Registering Multi-Backend tools...")
                register_multi_backend_tools(self)
                
                logger.info("✅ Successfully registered FS Journal and Multi-Backend tools")
            except Exception as e:
                logger.error(f"Failed to initialize FS Journal and Multi-Backend tools: {e}")
        
"""
        
        # Find the initialize_server method
        initialize_pattern = r"def initialize_server\(self.*?\):"
        initialize_match = re.search(initialize_pattern, content)
        
        if initialize_match:
            # Find the end of the method's first block (indented code)
            method_start = initialize_match.end()
            next_line_start = content.find('\n', method_start) + 1
            
            # Look for the first indented line
            indented_line_match = re.search(r"\n( +)", content[next_line_start:])
            if indented_line_match:
                indentation = indented_line_match.group(1)
                
                # Format the init code with the proper indentation
                formatted_init_code = init_code.replace('\n        ', f'\n{indentation}')
                
                # Find a good position to insert the code (after controllers are initialized)
                insert_marker = "# Initialize controllers"
                marker_pos = content.find(insert_marker, next_line_start)
                
                if marker_pos > 0:
                    # Find the end of the controllers initialization section
                    controllers_section_end = content.find('\n\n', marker_pos)
                    if controllers_section_end > 0:
                        # Insert the initialization code after the controllers section
                        content = (
                            content[:controllers_section_end] + 
                            "\n\n" + indentation + "# Initialize FS Journal and Multi-Backend integration" +
                            formatted_init_code +
                            content[controllers_section_end:]
                        )
                    else:
                        logger.warning("Could not find end of controllers section, adding at the end of the method")
                        # Find the end of the method
                        method_end = content.find('\n\n', next_line_start)
                        if method_end > 0:
                            content = (
                                content[:method_end] + 
                                "\n\n" + indentation + "# Initialize FS Journal and Multi-Backend integration" +
                                formatted_init_code +
                                content[method_end:]
                            )
                else:
                    logger.warning("Controllers initialization marker not found, adding at the beginning of the method")
                    content = (
                        content[:next_line_start] + 
                        indentation + "# Initialize FS Journal and Multi-Backend integration" +
                        formatted_init_code +
                        content[next_line_start:]
                    )
            else:
                logger.error("Could not determine indentation in initialize_server method")
                return False
        else:
            logger.error("initialize_server method not found")
            return False
        
        # Write the modified content back to the file
        with open(mcp_server_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Successfully patched {mcp_server_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error patching MCP server: {e}")
        
        # Restore from backup
        backup_path = f"{mcp_server_path}.bak"
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, mcp_server_path)
                logger.info(f"Restored {mcp_server_path} from backup")
            except Exception as restore_err:
                logger.error(f"Failed to restore from backup: {restore_err}")
        
        return False

def create_updated_startup_script():
    """Create an updated startup script that uses the patched server"""
    script_path = "start_ipfs_mcp_complete.sh"
    
    try:
        with open(script_path, 'w') as f:
            f.write("""#!/bin/bash
# Start the MCP server with full IPFS Kit, FS Journal and Multi-Backend integration

# Stop any running server
if [ -f "direct_mcp_server_active.txt" ]; then
  PID=$(cat direct_mcp_server_active.txt)
  if [ -n "$PID" ] && ps -p $PID > /dev/null; then
    echo "Stopping running MCP server (PID: $PID)..."
    kill $PID
    sleep 1
  fi
  rm -f direct_mcp_server_active.txt
fi

echo "Starting MCP server with full integration..."

# Start the server in the background
python direct_mcp_server.py > mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > direct_mcp_server_active.txt

# Wait for server to start
echo "Waiting for server to start..."
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
  echo "✅ MCP server started successfully with full integration"
  echo "ℹ️ Server is running at http://127.0.0.1:3000"
  echo ""
  echo "To verify the integration, you can:"
  echo "- Test the tools using: python verify_integration_tools.py"
  echo "- Run the example: python example_ipfs_fs_usage.py"
  echo "- Check the MCP server logs: tail -f mcp_server.log"
else
  echo "❌ Failed to start MCP server. Check mcp_server.log for details."
  exit 1
fi
""")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        logger.info(f"Created startup script: {script_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create startup script: {e}")
        return False

def create_example_usage_script():
    """Create an example script to demonstrate the usage of our integration"""
    script_path = "example_ipfs_fs_usage.py"
    
    try:
        with open(script_path, 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Example IPFS FS Usage

This script demonstrates how to use the IPFS Kit Virtual Filesystem
and Multi-Backend Storage integration.
\"\"\"

import os
import sys
import json
import logging
import asyncio
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://127.0.0.1:3000"

async def main():
    \"\"\"Main function to demonstrate usage\"\"\"
    logger.info("IPFS Kit Virtual Filesystem and Multi-Backend Storage Demo")
    
    # Step 1: Check server health
    try:
        response = requests.get(f"{MCP_URL}/api/v0/health")
        response.raise_for_status()
        health_data = response.json()
        logger.info(f"Server health: {health_data.get('status')}")
    except Exception as e:
        logger.error(f"Server health check failed: {e}")
        logger.error("Make sure the MCP server is running using start_ipfs_mcp_complete.sh")
        return 1
    
    # Step 2: Use JSON-RPC to get available tools
    try:
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0", 
            "method": "get_tools",
            "params": {},
            "id": 1
        })
        response.raise_for_status()
        tools_data = response.json()
        
        if "result" in tools_data and "tools" in tools_data["result"]:
            tools = tools_data["result"]["tools"]
            logger.info(f"Found {len(tools)} registered tools")
            
            # List FS Journal and Multi-Backend tools
            fs_tools = [tool for tool in tools if tool.get("name", "").startswith(("fs_", "ipfs_fs_", "multi_backend_"))]
            logger.info(f"Found {len(fs_tools)} FS Journal and Multi-Backend tools:")
            for tool in fs_tools:
                logger.info(f"  - {tool.get('name')}: {tool.get('description')}")
        else:
            logger.warning("No tools found or unexpected response format")
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
    
    # Step 3: Demonstrate using some tools
    # This is a simplified demonstration - in a real scenario, you would use
    # the API to call these tools with appropriate parameters
    logger.info("\\nTool Usage Examples:")
    
    try:
        # Example usage outline (actual implementation would call the MCP API)
        examples = [
            "1. Initialize backends:",
            "   - init_huggingface_backend: Create a HuggingFace backend at /hf",
            "   - init_s3_backend: Create an S3 backend at /s3",
            "",
            "2. Map paths:",
            "   - multi_backend_map: Map /hf/bert-base-uncased to ./local/models/bert",
            "   - ipfs_fs_bridge_map: Map /ipfs/QmExample to ./local/ipfs/example",
            "",
            "3. Work with content:",
            "   - fs_journal_track: Start tracking operations on ./local/models",
            "   - multi_backend_convert_format: Convert data.json to data.parquet",
            "",
            "4. Search and synchronize:",
            "   - multi_backend_search: Search for 'model' across all backends",
            "   - fs_journal_sync: Synchronize all cached changes to disk",
            "   - multi_backend_sync: Synchronize all backend mappings"
        ]
        
        for example in examples:
            logger.info(example)
    except Exception as e:
        logger.error(f"Error in examples: {e}")
    
    logger.info("\\nFor full documentation, see README_IPFS_FS_INTEGRATION.md")
    return 0

if __name__ == "__main__":
    asyncio.run(main())
""")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        logger.info(f"Created example usage script: {script_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create example usage script: {e}")
        return False

def main():
    """Main function to patch the MCP server"""
    logger.info("Starting MCP integration patch...")
    
    # Patch the MCP server
    if not patch_mcp_server():
        logger.error("Failed to patch MCP server")
        return 1
    
    # Create updated startup script
    if not create_updated_startup_script():
        logger.warning("Failed to create startup script")
    
    # Create example usage script
    if not create_example_usage_script():
        logger.warning("Failed to create example usage script")
    
    logger.info("""
✅ MCP integration patch completed

To use the enhanced MCP server with all tools:
1. Run the new startup script: ./start_ipfs_mcp_complete.sh
2. Try the example: python example_ipfs_fs_usage.py

The integration adds:
- Virtual filesystem operations with history tracking
- IPFS to local filesystem mapping
- Multiple storage backend support (HuggingFace, S3, Filecoin, etc.)
- Content prefetching and search capabilities
- Data format conversion (JSON, Parquet, Arrow)
""")
    return 0

if __name__ == "__main__":
    sys.exit(main())
