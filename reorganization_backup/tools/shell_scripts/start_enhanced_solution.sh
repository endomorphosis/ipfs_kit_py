#!/bin/bash
# Start the enhanced MCP solution with improved parameter handling

# Set up logging
LOG_FILE="enhanced_solution_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "===== Starting Enhanced MCP Solution with Improved Parameter Handling ====="
echo "$(date): Starting initialization"

# Stop any running servers
echo "Stopping any existing MCP servers..."
./enhanced_mcp_launcher.py --action stop

# Ensure IPFS daemon is running
if ! pgrep -x "ipfs" > /dev/null; then
    echo "Starting IPFS daemon..."
    ipfs daemon --init &
    IPFS_PID=$!
    echo "IPFS daemon started with PID: $IPFS_PID"
    
    # Wait for IPFS to initialize
    echo "Waiting for IPFS to initialize..."
    sleep 5
else
    echo "IPFS daemon is already running"
fi

# Apply parameter fixes
echo "Applying parameter fixes..."
if [ -f "direct_param_fix.py" ]; then
    python direct_param_fix.py
    echo "Applied direct parameter fixes"
else
    echo "Warning: direct_param_fix.py not found"
fi

# Start the enhanced MCP server
echo "Starting enhanced MCP server..."
./enhanced_mcp_launcher.py --action start

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Check if server is running
if ./enhanced_mcp_launcher.py --action status; then
    echo "Enhanced MCP server is running"
else
    echo "Error: Enhanced MCP server failed to start"
    exit 1
fi

# Register all tools
echo "Registering tools with enhanced parameter handling..."

# Register IPFS tools
if [ -f "direct_param_fix.py" ]; then
    python -c "from direct_param_fix import register_ipfs_tools; from final_mcp_server import server; register_ipfs_tools(server)"
    echo "Registered IPFS tools with enhanced parameter handling"
else
    echo "Warning: direct_param_fix.py not found, IPFS tools may not be registered correctly"
fi

# Register multi-backend tools
if [ -f "register_enhanced_multi_backend_tools.py" ]; then
    python -c "from register_enhanced_multi_backend_tools import register_multi_backend_tools; from final_mcp_server import server; register_multi_backend_tools(server)"
    echo "Registered multi-backend tools with enhanced parameter handling"
else
    echo "Warning: register_enhanced_multi_backend_tools.py not found, multi-backend tools may not be registered correctly"
fi

echo "===== Enhanced MCP Solution Started Successfully ====="
echo "The MCP server is running with enhanced parameter handling for IPFS and multi-backend tools."
echo "Log file: $LOG_FILE"
echo 
echo "To stop the server, run: ./enhanced_mcp_launcher.py --action stop"
echo "To test parameter handling, run: ./test_enhanced_parameters.py"
echo "For more information, see PARAMETER_HANDLING.md"
