#!/bin/bash
echo "🚀 Restarting MCP server with VFS tools adapter..."

# Kill existing MCP server processes
echo "Stopping existing MCP server processes..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Update the server code to use our adapter
echo "Updating direct_mcp_server.py to use VFS adapter..."
python3 - << EOF
import os
import sys
import traceback

try:
    # Read the server code
    with open('direct_mcp_server.py', 'r') as f:
        server_code = f.read()

    # Backup the original file
    backup_path = 'direct_mcp_server.py.bak.vfs_adapter'
    with open(backup_path, 'w') as f:
        f.write(server_code)
    print(f"Backed up original server code to {backup_path}")
    
    # Add import for vfs_tools_adapter
    if "import vfs_tools_adapter" not in server_code:
        imports_end = server_code.find("# Configure logging")
        if imports_end == -1:
            imports_end = server_code.find("logging.basicConfig")
        
        server_code = server_code[:imports_end] + "import vfs_tools_adapter\n" + server_code[imports_end:]
        print("Added import for vfs_tools_adapter")
    
    # Find the register_all_tools function
    if "def register_all_tools(server):" in server_code:
        # Modify the register_all_tools function to use our adapter
        register_func_start = server_code.find("def register_all_tools(server):")
        register_func_end = server_code.find("def", register_func_start + 1)
        if register_func_end == -1:
            register_func_end = len(server_code)
        
        # Get the original function code
        register_func_code = server_code[register_func_start:register_func_end]
        
        # Check if VFS adapter is already integrated
        if "vfs_tools_adapter.register_all_vfs_tools" in register_func_code:
            print("VFS adapter already integrated in register_all_tools function")
        else:
            # Add VFS adapter tool registration
            register_vfs_code = """    # Register VFS tools via adapter
    try:
        logger.info("Registering VFS tools via adapter...")
        if vfs_tools_adapter.register_all_vfs_tools(server):
            logger.info("✅ Successfully registered VFS tools via adapter")
        else:
            logger.warning("⚠️ Failed to register VFS tools via adapter")
    except Exception as e:
        logger.error(f"❌ Error registering VFS tools via adapter: {e}")
        logger.error(traceback.format_exc())
    
"""
            # Find the appropriate position to insert our code
            # Look for a line that starts with logger.info or return
            insertion_point = register_func_code.find("    return")
            if insertion_point == -1:
                # If no return statement, add our code at the end
                register_func_code = register_func_code + register_vfs_code
            else:
                # Add our code before the return statement
                register_func_code = register_func_code[:insertion_point] + register_vfs_code + register_func_code[insertion_point:]
            
            # Replace the original function code with our modified code
            server_code = server_code[:register_func_start] + register_func_code + server_code[register_func_end:]
            print("Modified register_all_tools function to use VFS adapter")
    else:
        print("Could not find register_all_tools function in server code")
        sys.exit(1)
    
    # Write the modified code back
    with open('direct_mcp_server.py', 'w') as f:
        f.write(server_code)
    
    print("✅ Updated server code with VFS adapter integration")
except Exception as e:
    print(f"Error updating server with VFS adapter: {e}")
    print(traceback.format_exc())
    sys.exit(1)
EOF

# Start the server in the background
echo "Starting MCP server with VFS tools..."
cd /home/barberb/ipfs_kit_py
python3 direct_mcp_server.py > mcp_server_vfs_adapter.log 2>&1 &
echo $! > mcp_server_vfs_adapter.pid
echo "Server started with PID $(cat mcp_server_vfs_adapter.pid)"

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 5

# Verify server is running
echo "Verifying server is running..."
curl -s http://localhost:3000/ || echo "Could not connect to server"

echo "Verifying tool registration..."
python3 verify_vfs_tools.py
if [ $? -eq 0 ]; then
    echo "✅ VFS tools successfully registered and verified!"
else
    echo "❌ Error: VFS tools not properly registered. Check mcp_server_vfs_adapter.log for details."
    echo "Last 30 lines of log:"
    tail -n 30 mcp_server_vfs_adapter.log
fi
