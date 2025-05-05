"""
Monkey patch for asyncio issue with 'async' keyword
This applies a patch to fix libraries that use 'async' as a function name.
"""
import sys
import asyncio
import importlib

# Only apply patch if needed
if hasattr(asyncio.tasks, 'async'):
    # Rename the 'async' function to 'ensure_future'
    asyncio.tasks.ensure_future = asyncio.tasks.async
    del asyncio.tasks.async
    
    # Also update the asyncio module itself
    if hasattr(asyncio, 'async'):
        asyncio.ensure_future = asyncio.async
        del asyncio.async
    
    print("Applied monkey patch for asyncio 'async' function")

# Force reload problematic modules
for module_name in ['uvicorn', 'mcp.server.fastmcp']:
    if module_name in sys.modules:
        try:
            importlib.reload(sys.modules[module_name])
            print(f"Reloaded module: {module_name}")
        except:
            print(f"Failed to reload module: {module_name}")
