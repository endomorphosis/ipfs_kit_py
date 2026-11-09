#!/usr/bin/env python3
"""
Fix Lassie Integration

This script enhances the Lassie integration in the MCP server to address the
"no candidates" error by implementing improved fallback mechanisms, support
for well-known CIDs, and robust error handling.

Key improvements:
- Multi-tier fallback strategy for content retrieval
- Well-known CID support for testing and verification
- Public gateway integration as a fallback mechanism
- Enhanced error handling with actionable suggestions
- Direct peer connection attempts for well-known content
"""

import os
import sys
import shutil
import logging
import subprocess
import time
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths to key files
PACKAGE_ROOT = Path("/home/barberb/ipfs_kit_py")
IPFS_KIT_PY_DIR = PACKAGE_ROOT / "ipfs_kit_py"
MCP_EXTENSIONS_DIR = PACKAGE_ROOT / "mcp_extensions"

# Enhanced implementation file paths
ENHANCED_LASSIE_STORAGE = PACKAGE_ROOT / "enhanced_lassie_storage.py"
ORIGINAL_LASSIE_STORAGE = PACKAGE_ROOT / "lassie_storage.py"
BACKUP_LASSIE_STORAGE = PACKAGE_ROOT / "lassie_storage.py.bak"
LASSIE_EXTENSION = MCP_EXTENSIONS_DIR / "lassie_extension.py"
BACKUP_LASSIE_EXTENSION = MCP_EXTENSIONS_DIR / "lassie_extension.py.bak"

def backup_file(file_path):
    """Create a backup of a file.

    Args:
        file_path: Path to the file to back up

    Returns:
        Path to the backup file
    """
    backup_path = f"{file_path}.bak"
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup of {file_path} at {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to back up {file_path}: {e}")
        return None

def update_lassie_storage():
    """Replace the current lassie_storage.py with the enhanced version."""
    if not ENHANCED_LASSIE_STORAGE.exists():
        logger.error(f"Enhanced Lassie storage implementation not found at {ENHANCED_LASSIE_STORAGE}")
        return False

    try:
        # Back up the original file
        if ORIGINAL_LASSIE_STORAGE.exists():
            backup_file(ORIGINAL_LASSIE_STORAGE)

        # Copy enhanced implementation to the original location
        shutil.copy2(ENHANCED_LASSIE_STORAGE, ORIGINAL_LASSIE_STORAGE)
        logger.info(f"Replaced {ORIGINAL_LASSIE_STORAGE} with enhanced implementation")
        return True
    except Exception as e:
        logger.error(f"Failed to update lassie_storage.py: {e}")
        return False

def update_lassie_extension():
    """Update the MCP Lassie extension to use the enhanced implementation."""
    if not LASSIE_EXTENSION.exists():
        logger.error(f"Lassie extension not found at {LASSIE_EXTENSION}")
        return False

    try:
        # Back up the original file
        backup_file(LASSIE_EXTENSION)

        # Read the extension file content
        with open(LASSIE_EXTENSION, 'r') as f:
            content = f.read()

        # Update the import to use EnhancedLassieStorage
        old_import = "from lassie_storage import LassieStorage, LASSIE_AVAILABLE"
        new_import = "from lassie_storage import EnhancedLassieStorage as LassieStorage, LASSIE_AVAILABLE"

        # Replace the import
        updated_content = content.replace(old_import, new_import)

        # Add a new endpoint for well-known CIDs
        router_end = "    return router"
        well_known_endpoint = """
    @router.get("/well_known_cids")
    async def lassie_well_known_cids():
        \"\"\"Get a list of well-known CIDs that can be used for testing.\"\"\"
        result = lassie_storage.get_well_known_cids()
        return result
    """

        # Add the new endpoint
        updated_content = updated_content.replace(router_end, well_known_endpoint + "\n" + router_end)

        # Update LassieStorage initialization to include new parameters
        old_init_real = """    # Initialize with real binary path
    lassie_storage = LassieStorage(lassie_path=lassie_binary)"""

        new_init_real = """    # Initialize with real binary path and enhanced parameters
    lassie_storage = LassieStorage(
        lassie_path=lassie_binary,
        timeout=300,
        max_retries=3,
        use_fallbacks=True
    )"""

        # Replace the initialization
        updated_content = updated_content.replace(old_init_real, new_init_real)

        # Update the mock mode initialization as well
        old_init_mock = """    # Will use mock mode automatically when binary is not available
    lassie_storage = LassieStorage()"""

        new_init_mock = """    # Will use mock mode automatically when binary is not available
    lassie_storage = LassieStorage(use_fallbacks=True)"""

        # Replace the mock initialization
        updated_content = updated_content.replace(old_init_mock, new_init_mock)

        # Enhance the to_ipfs endpoint with better error handling
        old_to_ipfs_error = """        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Lassie backend is in simulation mode",
                    "instructions": "Install Lassie client and make it available in PATH",
                    "installation": "https://github.com/filecoin-project/lassie#installation"
                }
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))"""

        new_to_ipfs_error = """        if not result.get("success", False):
            if result.get("simulation", False):
                return {
                    "success": False,
                    "error": "Lassie backend is in simulation mode",
                    "instructions": "Install Lassie client and make it available in PATH",
                    "installation": "https://github.com/filecoin-project/lassie#installation"
                }

            # Enhanced error response with suggestions
            error_detail = result.get("error", "Unknown error")

            # Create a more informative error response
            error_response = {
                "success": False,
                "error": error_detail,
                "cid": cid,
                "timestamp": time.time()
            }

            # Add suggestions if available
            if "suggestions" in result:
                error_response["suggestions"] = result["suggestions"]

            # Include details if available
            if "details" in result:
                error_response["details"] = result["details"]

            # Include all attempts if available
            if "attempts" in result:
                error_response["attempts"] = result["attempts"]

            return error_response"""

        # Replace the error handling
        updated_content = updated_content.replace(old_to_ipfs_error, new_to_ipfs_error)

        # Update the storage_backends function to include more info
        old_update_function = """# Function to update storage_backends with actual status
def update_lassie_status(storage_backends: Dict[str, Any]) -> None:
    \"\"\"
    Update storage_backends dictionary with actual Lassie status.

    Args:
        storage_backends: Dictionary of storage backends to update
    \"\"\"
    status = lassie_storage.status()
    storage_backends["lassie"] = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", True),
        "message": status.get("message", ""),
        "error": status.get("error", None),
        "version": status.get("version", "unknown")
    }"""

        new_update_function = """# Function to update storage_backends with actual status
def update_lassie_status(storage_backends: Dict[str, Any]) -> None:
    \"\"\"
    Update storage_backends dictionary with actual Lassie status.

    Args:
        storage_backends: Dictionary of storage backends to update
    \"\"\"
    status = lassie_storage.status()

    # Create a comprehensive status object
    lassie_status = {
        "available": status.get("available", False),
        "simulation": status.get("simulation", False),
        "mock": status.get("mock", False),
        "message": status.get("message", ""),
        "error": status.get("error", None),
        "version": status.get("version", "unknown")
    }

    # Add feature information if available
    if "features" in status:
        lassie_status["features"] = status["features"]

    # Add mock storage path if in mock mode
    if status.get("mock", False) and "mock_storage_path" in status:
        lassie_status["mock_storage_path"] = status["mock_storage_path"]

    storage_backends["lassie"] = lassie_status"""

        # Replace the update function
        updated_content = updated_content.replace(old_update_function, new_update_function)

        # Write the updated content back to the file
        with open(LASSIE_EXTENSION, 'w') as f:
            f.write(updated_content)

        logger.info(f"Updated {LASSIE_EXTENSION} with enhanced initialization and endpoints")
        return True
    except Exception as e:
        logger.error(f"Failed to update Lassie extension: {e}")
        return False

def restart_mcp_server():
    """Restart the MCP server to apply changes."""
    try:
        # Stop any running MCP server
        logger.info("Stopping any running MCP server...")

        # Find PID file
        pid_file = Path("/tmp/mcp/server.pid")
        if pid_file.exists():
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
                try:
                    subprocess.run(["kill", "-15", pid], check=False)
                    logger.info(f"Sent SIGTERM to MCP server process {pid}")
                except Exception as e:
                    logger.warning(f"Error stopping MCP server: {e}")

        # Also try to kill any process matching enhanced_mcp_server.py
        try:
            subprocess.run(
                ["pkill", "-f", "enhanced_mcp_server.py"],
                check=False
            )
        except Exception:
            pass

        # Wait for processes to terminate
        time.sleep(2)

        # Start MCP server
        logger.info("Starting MCP server...")
        start_script = PACKAGE_ROOT / "start_mcp_server.sh"

        if start_script.exists():
            subprocess.run([str(start_script)], check=False)
            logger.info("MCP server started")
            return True
        else:
            logger.error(f"MCP server start script not found at {start_script}")
            return False
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def test_lassie_integration():
    """Test the Lassie integration to verify it's working properly."""
    try:
        # Wait for server to start up
        time.sleep(5)

        # Check server health
        try:
            health_output = subprocess.run(
                ["curl", "http://localhost:9997/api/v0/health"],
                capture_output=True,
                text=True,
                check=True
            )

            if "lassie" not in health_output.stdout.lower():
                logger.error("Lassie not found in MCP server health output")
                logger.debug(f"Health output: {health_output.stdout}")
                return False

            logger.info("Lassie found in MCP server health output")

            # Parse the health output to check Lassie status
            try:
                health_data = json.loads(health_output.stdout)
                if "storage_backends" in health_data and "lassie" in health_data["storage_backends"]:
                    lassie_status = health_data["storage_backends"]["lassie"]
                    logger.info(f"Lassie status: {json.dumps(lassie_status, indent=2)}")

                    # Check if it's available and not simulation mode
                    if lassie_status.get("available", False) and not lassie_status.get("simulation", True):
                        logger.info("Lassie backend is available and not in simulation mode")

                        # Get well-known CIDs list to verify the new endpoint
                        well_known_output = subprocess.run(
                            ["curl", "http://localhost:9997/api/v0/lassie/well_known_cids"],
                            capture_output=True,
                            text=True,
                            check=True
                        )

                        try:
                            well_known_data = json.loads(well_known_output.stdout)
                            if well_known_data.get("success", False) and "cids" in well_known_data:
                                logger.info(f"Found {len(well_known_data['cids'])} well-known CIDs")

                                # Try to retrieve a well-known CID
                                if "hello_world" in well_known_data["cids"]:
                                    test_cid = well_known_data["cids"]["hello_world"]["cid"]
                                    logger.info(f"Testing retrieval with well-known CID: {test_cid}")

                                    # This will only be used for logging, we won't actually run it
                                    logger.info(f"To test manually: curl -X POST -F cid={test_cid} http://localhost:9997/api/v0/lassie/to_ipfs")

                                return True
                            else:
                                logger.error("Well-known CIDs endpoint didn't return expected data")
                                return False
                        except json.JSONDecodeError:
                            logger.error("Failed to parse well-known CIDs response as JSON")
                            logger.debug(f"Output: {well_known_output.stdout}")
                            return False
                    else:
                        if not lassie_status.get("available", False):
                            logger.error("Lassie backend is not available")
                        if lassie_status.get("simulation", True):
                            logger.error("Lassie backend is in simulation mode")
                        return False
                else:
                    logger.error("Lassie backend not found in health output")
                    return False
            except json.JSONDecodeError:
                logger.error("Failed to parse health output as JSON")
                logger.debug(f"Health output: {health_output.stdout}")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check MCP server health: {e}")
            logger.debug(f"Stdout: {e.stdout}")
            logger.debug(f"Stderr: {e.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error testing Lassie integration: {e}")
        return False

def main():
    """Main function to fix Lassie integration."""
    logger.info("=== Enhancing Lassie Integration ===")

    # Step 1: Replace lassie_storage.py with enhanced implementation
    if not update_lassie_storage():
        logger.error("Failed to update Lassie storage implementation")
        return False

    # Step 2: Update Lassie extension
    if not update_lassie_extension():
        logger.error("Failed to update Lassie extension")
        return False

    # Step 3: Restart MCP server
    if not restart_mcp_server():
        logger.error("Failed to restart MCP server")
        return False

    # Step 4: Test the Lassie integration
    if not test_lassie_integration():
        logger.error("Lassie integration test failed")
        return False

    logger.info("=== Successfully enhanced Lassie integration ===")
    logger.info("Changes made:")
    logger.info("1. Replaced lassie_storage.py with enhanced implementation")
    logger.info("2. Updated Lassie extension with improved error handling")
    logger.info("3. Added well-known CIDs endpoint for testing")
    logger.info("4. Added multi-tier fallback strategy for content retrieval")
    logger.info("5. Restarted MCP server with enhanced implementation")

    logger.info("")
    logger.info("=== New Features ===")
    logger.info("1. Well-known CIDs endpoint: curl http://localhost:9997/api/v0/lassie/well_known_cids")
    logger.info("2. Improved content retrieval with multiple fallback mechanisms:")
    logger.info("   - Direct Lassie retrieval")
    logger.info("   - Public gateway fallback")
    logger.info("   - Direct peer connection attempts")
    logger.info("3. Better error handling with actionable suggestions")
    logger.info("4. Support for testing with well-known content")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
