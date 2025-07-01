#!/usr/bin/env python3

import os
import sys
import logging
import time
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fix_mcp_api')

def fix_root_endpoint():
    """Add root, health, and version endpoints to the MCP server."""

    mcp_server_file = "ipfs_kit_py/mcp/server.py"
    backup_file = f"{mcp_server_file}.bak.{int(time.time())}"

    # Backup the file
    if os.path.exists(mcp_server_file):
        shutil.copy2(mcp_server_file, backup_file)
        logger.info(f"Created backup at {backup_file}")
    else:
        logger.error(f"Server file not found: {mcp_server_file}")
        return False

    try:
        # Read the file content
        with open(mcp_server_file, 'r') as f:
            content = f.read()

        # Check if the root endpoint already exists
        if "def read_root" in content:
            logger.info("Root endpoint already exists, skipping...")
            return True

        # Add root endpoint by finding the place to insert it
        register_pattern = "def register_with_app(self, app: FastAPI, prefix: str = \"/api/v0\"):"
        if register_pattern in content:
            # Find the end of the register_with_app method
            register_start = content.find(register_pattern)
            next_def = content.find("def ", register_start + len(register_pattern))
            if next_def > 0:
                # Insert before the next method definition
                root_endpoint_code = '''
        # Add root endpoint
        @app.get("/")
        def read_root():
            # Root endpoint for the server
            return {
                "name": "IPFS Kit MCP Server",
                "version": "1.0.0",
                "description": "API server for IPFS Kit operations",
                "endpoints": ["/", "/health", "/docs", "/api/v0/mcp/"]
            }

        # Health check endpoint
        @app.get("/health")
        def health_check():
            # Health check endpoint
            import time
            return {
                "status": "ok",
                "timestamp": time.time(),
                "uptime": time.time() - self.start_time,
                "controllers": list(self.controllers.keys()),
                "models": list(self.models.keys())
            }
                '''
                # Insert after the register_with_app section, before the next method
                insert_pos = next_def
                new_content = content[:insert_pos] + root_endpoint_code + content[insert_pos:]

                # Write the updated content
                with open(mcp_server_file, 'w') as f:
                    f.write(new_content)

                logger.info("Added root and health endpoints to MCP server")
                return True
            else:
                logger.error("Could not find end of register_with_app method")
                return False
        else:
            logger.error("Could not find register_with_app method")
            return False

    except Exception as e:
        logger.error(f"Error adding root endpoint: {e}")
        # Restore backup
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, mcp_server_file)
            logger.info(f"Restored from backup due to error")
        return False

def fix_ipfs_cat_endpoint():
    """Fix the IPFS cat endpoint parameter handling."""

    ipfs_controller_file = "ipfs_kit_py/mcp/controllers/ipfs_controller.py"
    backup_file = f"{ipfs_controller_file}.bak.{int(time.time())}"

    # Backup the file
    if os.path.exists(ipfs_controller_file):
        shutil.copy2(ipfs_controller_file, backup_file)
        logger.info(f"Created backup at {backup_file}")
    else:
        logger.error(f"Controller file not found: {ipfs_controller_file}")
        return False

    try:
        # Read the file content
        with open(ipfs_controller_file, 'r') as f:
            content = f.read()

        # Check if the fix is already applied
        if "# Handle various possible CID formats" in content:
            logger.info("IPFS cat endpoint already fixed, skipping...")
            return True

        # Find the get_content method
        get_content_pattern = "async def get_content(self, cid: str)"
        if get_content_pattern in content:
            get_content_start = content.find(get_content_pattern)
            # Find the line after the method signature
            method_body_start = content.find('\n', get_content_start) + 1

            # Insert parameter handling code
            param_code = '''        # Handle various possible CID formats
        # Strip out 'ipfs://' prefix if present
        if cid.startswith("ipfs://"):
            cid = cid.replace("ipfs://", "")

        # Strip leading slashes if present
        while cid.startswith("/"):
            cid = cid[1:]

        # Remove ipfs/ prefix if present
        if cid.startswith("ipfs/"):
            cid = cid[5:]

        logger.debug(f"Normalized CID for get_content: {cid}")

'''
            # Insert at the beginning of the method body
            new_content = content[:method_body_start] + param_code + content[method_body_start:]

            # Write the updated content
            with open(ipfs_controller_file, 'w') as f:
                f.write(new_content)

            logger.info("Fixed IPFS cat endpoint parameter handling")
            return True
        else:
            logger.error("Could not find get_content method")
            return False

    except Exception as e:
        logger.error(f"Error fixing IPFS cat endpoint: {e}")
        # Restore backup
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, ipfs_controller_file)
            logger.info(f"Restored from backup due to error")
        return False

def add_webrtc_check_method():
    """Add WebRTC dependency check method to the server."""

    mcp_server_file = "ipfs_kit_py/mcp/server.py"
    backup_file = f"{mcp_server_file}.bak.webrtc.{int(time.time())}"

    # Backup the file
    if os.path.exists(mcp_server_file):
        shutil.copy2(mcp_server_file, backup_file)
        logger.info(f"Created backup at {backup_file}")
    else:
        logger.error(f"Server file not found: {mcp_server_file}")
        return False

    try:
        # Read the file content
        with open(mcp_server_file, 'r') as f:
            content = f.read()

        # Check if the method already exists
        if "def _is_webrtc_available" in content:
            logger.info("WebRTC check method already exists, skipping...")
            return True

        # Add the method at the end of the class
        class_end = content.rfind("}")
        if class_end > 0:
            webrtc_method = '''
    def _is_webrtc_available(self) -> bool:
        # Check if WebRTC dependencies are available
        try:
            # Try to import the key WebRTC dependencies
            import numpy
            import cv2

            # Check for aiortc and PyAV which are required for WebRTC
            # These will raise ImportError if not available
            try:
                import aiortc
                import av
                return True
            except ImportError:
                return False
        except ImportError:
            return False

'''
            # Insert before the class end
            new_content = content[:class_end] + webrtc_method + content[class_end:]

            # Write the updated content
            with open(mcp_server_file, 'w') as f:
                f.write(new_content)

            logger.info("Added WebRTC dependency check method")
            return True
        else:
            logger.error("Could not find end of class")
            return False

    except Exception as e:
        logger.error(f"Error adding WebRTC check method: {e}")
        # Restore backup
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, mcp_server_file)
            logger.info(f"Restored from backup due to error")
        return False

def fix_all_mcp_api_issues():
    """Fix all MCP API issues."""
    success_count = 0
    total_fixes = 3

    # Fix 1: Add root endpoint
    if fix_root_endpoint():
        success_count += 1

    # Fix 2: Fix IPFS cat endpoint
    if fix_ipfs_cat_endpoint():
        success_count += 1

    # Fix 3: Add WebRTC check method
    if add_webrtc_check_method():
        success_count += 1

    # Report results
    if success_count == total_fixes:
        logger.info("✅ All MCP API issues fixed successfully!")
        return True
    else:
        logger.warning(f"⚠️ Fixed {success_count}/{total_fixes} issues")
        return success_count > 0

if __name__ == "__main__":
    logger.info("Starting MCP API fix script...")
    success = fix_all_mcp_api_issues()
    if success:
        logger.info("MCP API fixes completed successfully")
        sys.exit(0)
    else:
        logger.error("Some MCP API fixes failed")
        sys.exit(1)
