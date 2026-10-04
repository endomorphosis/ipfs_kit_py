#!/bin/bash
# start_ipfs_enhanced_mcp.sh
#
# All-in-one script to start the IPFS-enhanced direct MCP server
# This script:
# 1. Fixes the server.py indentation issue
# 2. Loads IPFS MCP tools into the environment
# 3. Patches direct_mcp_server.py to use these tools
# 4. Starts the server with all enhancements
#

set -e  # Exit on any error

echo "📋 Starting IPFS-Enhanced Direct MCP Server..."

# Directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Fix server.py indentation issues
echo "🔧 Step 1: Fixing MCP server.py indentation issues..."
if [ -f "./complete_server_fix.py" ]; then
    chmod +x ./complete_server_fix.py
    ./complete_server_fix.py
else
    echo "❌ complete_server_fix.py not found. Creating it now..."
    
    cat > complete_server_fix.py << 'EOL'
#!/usr/bin/env python3
"""
Complete server.py fix

This script completely rewrites the problematic section of the server.py file
to fix all syntax issues.
"""

import os
import sys

SERVER_PATH = "/home/barberb/ipfs_kit_py/docs/mcp-python-sdk/src/mcp/server/lowlevel/server.py"

def fix_server_file():
    """Fix the server.py file completely."""
    try:
        with open(SERVER_PATH, 'r') as f:
            content = f.read()
        
        # Find the start of the method
        method_start = content.find("async def _handle_request(")
        if method_start == -1:
            print("❌ Could not find the _handle_request method")
            return False
        
        # Find where the method ends (next def or end of file)
        next_def = content.find("\n    async def", method_start + 1)
        if next_def == -1:
            next_def = len(content)
        
        # Extract the method implementation
        method_impl = content[method_start:next_def]
        
        # Identify the section we want to replace
        start_marker = "            finally:"
        end_marker = "\n    async def _handle_notification"
        
        start_pos = method_impl.find(start_marker)
        if start_pos == -1:
            print("❌ Could not find the finally block")
            return False
        
        # Create the corrected implementation
        corrected_section = """            finally:
                # Reset the global state after we are done
                if token is not None:
                    request_ctx.reset(token)

            try:
                await message.respond(response)
            except Exception as e:
                logger.warning(f"Error responding to message: {e}")
        else:
            try:
                await message.respond(
                    types.ErrorData(
                        code=types.METHOD_NOT_FOUND,
                        message="Method not found",
                    )
                )
            except Exception as e:
                logger.warning(f"Error responding to error message: {e}")"""
        
        # Replace in the method implementation
        method_end = method_impl.find(end_marker, start_pos)
        if method_end == -1:
            method_end = len(method_impl)
        
        fixed_method = method_impl[:start_pos] + corrected_section
        
        # Rebuild the file content
        fixed_content = content[:method_start] + fixed_method + content[method_start + method_end:]
        
        # Write the fixed content back to the file
        with open(SERVER_PATH, 'w') as f:
            f.write(fixed_content)
        
        print("✅ Fixed server.py file with proper syntax and indentation")
        return True
    except Exception as e:
        print(f"❌ Error fixing server.py: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists(SERVER_PATH):
        print(f"❌ File not found: {SERVER_PATH}")
        sys.exit(1)
    
    if fix_server_file():
        print("✅ Successfully fixed the server.py file")
        print("Please restart the MCP server for the changes to take effect")
    else:
        print("❌ Failed to fix the server.py file")
        sys.exit(1)
EOL
    
    chmod +x ./complete_server_fix.py
    ./complete_server_fix.py
fi

# Load IPFS MCP tools
echo "🔧 Step 2: Loading IPFS MCP tools..."
if [ -f "./enhance_ipfs_mcp_tools.py" ]; then
    chmod +x ./enhance_ipfs_mcp_tools.py
    ./enhance_ipfs_mcp_tools.py
else
    echo "❌ enhance_ipfs_mcp_tools.py not found. Please make sure this file exists."
    exit 1
fi

if [ -f "./load_ipfs_mcp_tools.py" ]; then
    chmod +x ./load_ipfs_mcp_tools.py
    ./load_ipfs_mcp_tools.py
else
    echo "❌ load_ipfs_mcp_tools.py not found. Please make sure this file exists."
    exit 1
fi

# Patch direct_mcp_server.py
echo "🔧 Step 3: Patching direct_mcp_server.py to use IPFS tools..."
if [ -f "./patch_direct_mcp_server.py" ]; then
    chmod +x ./patch_direct_mcp_server.py
    ./patch_direct_mcp_server.py
else
    echo "❌ patch_direct_mcp_server.py not found. Please make sure this file exists."
    exit 1
fi

# Check if direct_mcp_server.py exists
if [ ! -f "./direct_mcp_server.py" ]; then
    echo "❌ direct_mcp_server.py not found. Please ensure it exists in the current directory."
    exit 1
fi

# Default port and host
PORT=3000
HOST="127.0.0.1"
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --port)
        PORT="$2"
        shift
        shift
        ;;
        --host)
        HOST="$2"
        shift
        shift
        ;;
        --log-level)
        LOG_LEVEL="$2"
        shift
        shift
        ;;
        *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--port PORT] [--host HOST] [--log-level LEVEL]"
        exit 1
        ;;
    esac
done

# Check for existing server
if [ -f "./direct_mcp_server_blue.pid" ]; then
    PID=$(cat ./direct_mcp_server_blue.pid)
    if ps -p $PID > /dev/null; then
        echo "⚠️ Direct MCP Server is already running with PID $PID"
        echo "   Use stop_mcp_server.sh to stop it, or use a different port."
        echo "   Continuing with a new instance..."
    fi
fi

# Start the server
echo "🚀 Step 4: Starting Enhanced IPFS-MCP Server on $HOST:$PORT..."
echo "📋 The server now includes all IPFS tools and file system integration."
echo "📋 Available IPFS tools:"
echo "   - ipfs_files_ls: List files in IPFS MFS"
echo "   - ipfs_files_mkdir: Create directories in IPFS MFS"
echo "   - ipfs_files_write: Write files to IPFS MFS"
echo "   - ipfs_files_read: Read files from IPFS MFS"
echo "   - ipfs_files_rm: Remove files/directories from IPFS MFS"
echo "   - ipfs_files_stat: Get file/directory info from IPFS MFS"
echo "   - ipfs_files_cp: Copy files in IPFS MFS"
echo "   - ipfs_files_mv: Move files in IPFS MFS"
echo "   - ipfs_name_publish: Publish IPNS names"
echo "   - ipfs_name_resolve: Resolve IPNS names"
echo "   - ipfs_dag_put: Add DAG nodes to IPFS"
echo "   - ipfs_dag_get: Get DAG nodes from IPFS"
echo ""

python direct_mcp_server.py --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"

# Note: The server will keep running in the foreground
# Press Ctrl+C to stop it
