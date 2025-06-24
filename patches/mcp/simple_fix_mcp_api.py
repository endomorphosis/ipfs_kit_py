#!/usr/bin/env python3
"""
Simple fix script for MCP API issues.
"""

import os
import sys
import shutil
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("simple_fix_mcp_api")

# Paths to files we'll modify
WEBRTC_CONTROLLER_PATH = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller_anyio.py"
IPFS_CONTROLLER_PATH = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller_anyio.py"
SERVER_PATH = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/server_anyio.py"

# Make backups of files
def backup_file(file_path):
    if os.path.exists(file_path):
        backup_path = f"{file_path}.bak.{int(time.time())}"
        logger.info(f"Creating backup of {file_path} to {backup_path}")
        shutil.copy2(file_path, backup_path)
        return True
    else:
        logger.error(f"File not found: {file_path}")
        return False

# Fix WebRTC controller's check_dependencies method
def fix_webrtc_controller():
    logger.info("Fixing WebRTC controller dependency check...")
    if not backup_file(WEBRTC_CONTROLLER_PATH):
        return False

    try:
        # Read the file
        with open(WEBRTC_CONTROLLER_PATH, 'r') as f:
            content = f.read()

        # Look for the check_dependencies method
        if "async def check_dependencies" in content:
            # Replace the method with a more robust implementation
            new_method = '''async def check_dependencies(self) -> Dict[str, Any]:
        """Check if WebRTC dependencies are available."""
        logger.debug("Checking WebRTC dependencies")

        # Run the dependency check in a background thread using anyio
        try:
            # Try to use the anyio-compatible version first
            if hasattr(self.ipfs_model, 'check_webrtc_dependencies_anyio'):
                return await self.ipfs_model.check_webrtc_dependencies_anyio()

            # Fall back to the sync version
            elif hasattr(self.ipfs_model, 'check_webrtc_dependencies'):
                return await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies)

            # Create a basic response if no method is available
            else:
                return {
                    "success": False,
                    "webrtc_available": False,
                    "error": "No WebRTC dependency check method available",
                    "dependencies": {
                        "numpy": False,
                        "opencv": False,
                        "av": False,
                        "aiortc": False,
                        "websockets": False,
                        "notifications": False
                    }
                }
        except Exception as e:
            logger.error(f"Error checking WebRTC dependencies: {e}")
            return {
                "success": False,
                "webrtc_available": False,
                "error": f"Error checking dependencies: {str(e)}",
                "error_type": type(e).__name__
            }'''

            # Just use a simple string replacement for now without regex
            new_content = content
            if "async def check_dependencies" in content:
                # Split at the method definition
                parts = content.split("async def check_dependencies")
                if len(parts) >= 2:
                    # Find the end of the method by looking for the next method definition
                    method_body = parts[1]
                    next_method_idx = method_body.find("async def")
                    if next_method_idx == -1:  # No next method found, try finding a class definition
                        next_method_idx = method_body.find("class ")

                    if next_method_idx != -1:
                        # Replace just this method
                        new_content = parts[0] + new_method + method_body[next_method_idx:]
                    else:
                        # If we can't find the end, just append the new method to the first part
                        new_content = parts[0] + new_method

            # Write the updated content
            with open(WEBRTC_CONTROLLER_PATH, 'w') as f:
                f.write(new_content)

            logger.info("✅ Successfully fixed WebRTC controller")
            return True
        else:
            logger.warning("Could not find check_dependencies method in WebRTC controller")
            return False
    except Exception as e:
        logger.error(f"Error fixing WebRTC controller: {e}")
        return False

# Create a script for starting the fixed MCP server
def create_fixed_server_script():
    logger.info("Creating run script for fixed MCP server...")
    script_path = "/home/barberb/ipfs_kit_py/run_fixed_mcp_server.py"

    script_content = '''#!/usr/bin/env python3
"""
Run MCP server with all fixes applied.
"""
import sys
import logging
import uvicorn
import anyio
from fastapi import FastAPI
from ipfs_kit_py.mcp.server_anyio import MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_fixed_mcp_server")

# Create FastAPI app
app = FastAPI(
    title="Fixed MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="1.0.0"
)

# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint for the server."""
    import time
    return {
        "name": "IPFS Kit MCP Server",
        "version": "1.0.0",
        "description": "Fixed API server for IPFS Kit operations",
        "timestamp": time.time(),
        "endpoints": ["/", "/health", "/docs", "/api/v0/mcp/"]
    }

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    import time
    return {
        "status": "ok",
        "timestamp": time.time()
    }

# Create MCP server with debug mode
mcp_server = MCPServer(debug_mode=True)

# Register MCP server with FastAPI app
mcp_server.register_with_app(app, prefix="/mcp")

# Also register at /api/v0/mcp for test compatibility
mcp_server.register_with_app(app, prefix="/api/v0/mcp")

if __name__ == "__main__":
    logger.info("Starting fixed MCP server on port 9991")
    uvicorn.run(app, host="127.0.0.1", port=9991)
'''

    with open(script_path, 'w') as f:
        f.write(script_content)

    # Make it executable
    os.chmod(script_path, 0o755)

    logger.info(f"✅ Successfully created {script_path}")
    return True

def main():
    logger.info("Starting simple MCP API fixes...")

    # Fix WebRTC controller
    webrtc_fixed = fix_webrtc_controller()

    # Create run script
    script_created = create_fixed_server_script()

    # Report status
    logger.info("\n" + "="*50)
    logger.info("MCP API FIX SUMMARY")
    logger.info("="*50)
    logger.info(f"WebRTC controller: {'✅ Fixed' if webrtc_fixed else '❌ Failed'}")
    logger.info(f"Fixed server script: {'✅ Created' if script_created else '❌ Failed'}")
    logger.info("="*50)

    if script_created:
        logger.info("\nTo run the fixed MCP server:")
        logger.info("  python run_fixed_mcp_server.py")
        logger.info("  (This will start the server on port 9991)")

    logger.info("\nTo test MCP API endpoints:")
    logger.info("  python test_mcp_api.py --url http://localhost:9991")

    return 0 if webrtc_fixed and script_created else 1

if __name__ == "__main__":
    sys.exit(main())
