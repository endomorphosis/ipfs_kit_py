#!/bin/bash
# Startup script for the final MCP server with all models
# This script handles all compatibility issues and properly starts the server

echo "Starting Final MCP Server with all 53 models..."

# Create a Python patching script for asyncio compatibility
cat > asyncio_patch_runtime.py << 'EOPYP'
import asyncio
import sys

# Safe patch for asyncio that avoids using 'async' as an attribute name
def patch_asyncio():
    # Check if we need to patch
    if hasattr(asyncio, 'events'):
        events = asyncio.events
        
        # Save the original attribute if it exists using getattr to avoid syntax errors
        if hasattr(events, '_orig_async'):
            return False  # Already patched
            
        # Store original value safely using getattr
        if hasattr(events, 'async'):
            orig_async = getattr(events, 'async')
            # Save the original value safely
            setattr(events, '_orig_async', orig_async)
            # Delete the problematic attribute
            delattr(events, 'async')
            
            # Add our safe version
            setattr(events, 'async_', orig_async)
            return True
    return False

# Apply the patch
patch_result = patch_asyncio()
if patch_result:
    print("Successfully applied asyncio compatibility patch")
else:
    print("Asyncio compatibility patch not needed or already applied")
EOPYP

# Apply the patch first
python3 -c "import asyncio_patch_runtime; asyncio_patch_runtime.patch_asyncio()"

# Run the server with the main() function
python3 -c "
import asyncio_patch_runtime
import sys
import importlib.util
import os

# Setup path
current_dir = os.getcwd()
sys.path.insert(0, current_dir)

# Make sure exception path exists for multiaddr
try:
    import multiaddr
    if not hasattr(multiaddr, 'exceptions'):
        class Exceptions:
            class Error(Exception):
                pass
        multiaddr.exceptions = Exceptions
        print('Added mock exceptions to multiaddr module')
except ImportError:
    print('multiaddr module not found, continuing without it')

# Load the module using importlib
spec = importlib.util.find_spec('final_mcp_server')
if spec is None:
    print('Could not find final_mcp_server.py')
    sys.exit(1)

# Create the module
module = importlib.util.module_from_spec(spec)
sys.modules['final_mcp_server'] = module
spec.loader.exec_module(module)

# Run the main function with proper arguments
if hasattr(module, 'main'):
    print('Starting server via main() function')
    sys.argv = ['final_mcp_server.py', '--port', '3000']
    module.main()
else:
    print('Error: No main() function found in final_mcp_server.py')
    sys.exit(1)
"
