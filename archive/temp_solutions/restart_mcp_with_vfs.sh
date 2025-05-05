#!/bin/bash
echo "🚀 Restarting MCP server with VFS tools..."

# Kill existing MCP server processes
echo "Stopping existing MCP server processes..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Start the server in the background
echo "Starting MCP server with VFS tools..."
cd /home/barberb/ipfs_kit_py
python3 direct_mcp_server.py > mcp_server_vfs.log 2>&1 &
echo $! > mcp_server_vfs.pid
echo "Server started with PID $(cat mcp_server_vfs.pid)"

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Verify server is running
echo "Verifying server is running..."
curl -s http://localhost:3000/ || echo "Could not connect to server"

# Modify the server code to include VFS tools
echo "Updating server code with VFS integration..."
python3 - << EOF
import os
import sys
import traceback

try:
    # Read the server code
    with open('direct_mcp_server.py', 'r') as f:
        server_code = f.read()

    # Check if VFS integration is already included
    if "register_all_fs_tools" in server_code:
        print("VFS integration already present in server code")
    else:
        # Backup the original file
        backup_path = 'direct_mcp_server.py.bak.vfs'
        with open(backup_path, 'w') as f:
            f.write(server_code)
        print(f"Backed up original server code to {backup_path}")
        
        # Modify the server code to import and register VFS tools
        if "def register_all_tools(server):" in server_code:
            # Find the register_all_tools function
            import_line = "import integrate_vfs_to_final_mcp"
            
            # Add the import at the top if not already there
            if import_line not in server_code:
                imports_end = server_code.find("# Configure logging")
                if imports_end == -1:
                    imports_end = server_code.find("logging.basicConfig")
                
                server_code = server_code[:imports_end] + import_line + "\n" + server_code[imports_end:]
            
            # Add VFS tool registration inside the register_all_tools function
            register_func_pos = server_code.find("def register_all_tools(server):")
            register_func_body_pos = server_code.find("    ", register_func_pos)
            register_vfs_code = """    # Register VFS tools
    try:
        integrate_vfs_to_final_mcp.register_all_fs_tools(server)
        logger.info("✅ VFS tools registered successfully")
    except Exception as e:
        logger.error(f"❌ Error registering VFS tools: {e}")
        logger.error(traceback.format_exc())
    
"""
            server_code = server_code[:register_func_body_pos] + register_vfs_code + server_code[register_func_body_pos:]
            
            # Write the modified code back
            with open('direct_mcp_server.py', 'w') as f:
                f.write(server_code)
            
            print("✅ Updated server code with VFS integration")
        else:
            print("Could not find the register_all_tools function in server code")
except Exception as e:
    print(f"Error updating server with VFS tools: {e}")
    print(traceback.format_exc())
EOF

# Restart the server again with the updated code
echo "Restarting MCP server with VFS tools..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Start the server in the background
echo "Starting MCP server with VFS tools..."
cd /home/barberb/ipfs_kit_py
python3 direct_mcp_server.py > mcp_server_vfs.log 2>&1 &
echo $! > mcp_server_vfs.pid
echo "Server started with PID $(cat mcp_server_vfs.pid)"

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 5

# Verify tool registration
echo "Verifying server is running..."
curl -s http://localhost:3000/ || echo "Could not connect to server"

echo "Verifying tool registration..."
python3 verify_vfs_tools.py
if [ $? -eq 0 ]; then
    echo "✅ VFS tools successfully registered and verified!"
else
    echo "❌ Error: VFS tools not properly registered. Check mcp_server_vfs.log for details."
    echo "Last 20 lines of log:"
    tail -n 20 mcp_server_vfs.log
fi
