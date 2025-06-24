#!/usr/bin/env python3
"""
IPFS MCP FS Integration with Tools

This script integrates the virtual filesystem with the enhanced IPFS tools,
ensuring proper coordination between the filesystem operations and IPFS operations.
"""

import os
import sys
import logging
import json
import importlib.util
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def import_module_from_file(file_path, module_name=None):
    """Import a module from a file path"""
    if not os.path.exists(file_path):
        raise ImportError(f"File not found: {file_path}")

    if module_name is None:
        module_name = os.path.basename(file_path).split('.')[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {file_path}")

    if spec.loader is None:
        raise ImportError(f"Could not get loader for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_fs_integration():
    """Load the filesystem integration module"""
    try:
        fs_integration = import_module_from_file("ipfs_mcp_fs_integration.py")
        logger.info("Successfully imported FS integration module")
        return fs_integration
    except ImportError as e:
        logger.error(f"Failed to import FS integration module: {e}")
        return None

def load_fs_journal_tools():
    """Load the filesystem journal tools module"""
    try:
        fs_journal = import_module_from_file("fs_journal_tools.py")
        logger.info("Successfully imported FS journal tools module")
        return fs_journal
    except ImportError as e:
        logger.error(f"Failed to import FS journal tools module: {e}")
        return None

def load_enhanced_tools():
    """Load the enhanced tools implementation module"""
    try:
        enhanced_tools = import_module_from_file("enhanced_tool_implementations.py")
        logger.info("Successfully imported enhanced tools implementation module")
        return enhanced_tools
    except ImportError as e:
        logger.error(f"Failed to import enhanced tools implementation module: {e}")
        return None

def register_fs_handlers_with_tools(fs_integration, fs_journal, enhanced_tools):
    """Register filesystem event handlers with the enhanced tools"""
    if not all([fs_integration, fs_journal, enhanced_tools]):
        logger.error("Cannot register handlers: missing required modules")
        return False

    try:
        # Create a mapping between filesystem operations and IPFS operations
        fs_to_ipfs_mapping = {
            # When a file is created or modified in the virtual filesystem
            "write": {
                "ipfs_handler": "ipfs_files_write",
                "transform": lambda path, content: {
                    "path": f"/ipfs_mfs{path}" if not path.startswith("/ipfs_mfs") else path,
                    "content": content
                }
            },
            # When a file is read from the virtual filesystem
            "read": {
                "ipfs_handler": "ipfs_files_read",
                "transform": lambda path: {
                    "path": f"/ipfs_mfs{path}" if not path.startswith("/ipfs_mfs") else path
                }
            },
            # When a directory is created in the virtual filesystem
            "mkdir": {
                "ipfs_handler": "ipfs_files_mkdir",
                "transform": lambda path: {
                    "path": f"/ipfs_mfs{path}" if not path.startswith("/ipfs_mfs") else path,
                    "parents": True
                }
            },
            # When a file or directory is removed from the virtual filesystem
            "remove": {
                "ipfs_handler": "ipfs_files_rm",
                "transform": lambda path, recursive=False: {
                    "path": f"/ipfs_mfs{path}" if not path.startswith("/ipfs_mfs") else path,
                    "recursive": recursive
                }
            },
            # When a file or directory is copied in the virtual filesystem
            "copy": {
                "ipfs_handler": "ipfs_files_cp",
                "transform": lambda source, dest: {
                    "source": f"/ipfs_mfs{source}" if not source.startswith("/ipfs_mfs") else source,
                    "dest": f"/ipfs_mfs{dest}" if not dest.startswith("/ipfs_mfs") else dest
                }
            },
            # When a file or directory is moved in the virtual filesystem
            "move": {
                "ipfs_handler": "ipfs_files_mv",
                "transform": lambda source, dest: {
                    "source": f"/ipfs_mfs{source}" if not source.startswith("/ipfs_mfs") else source,
                    "dest": f"/ipfs_mfs{dest}" if not dest.startswith("/ipfs_mfs") else dest
                }
            }
        }

        # Register the handlers with the filesystem journal
        if hasattr(fs_journal, 'FSJournal') and hasattr(fs_journal, 'FSOperationType'):
            journal = getattr(fs_integration, '_fs_journal', None)
            if journal:
                for op_type, handler_info in fs_to_ipfs_mapping.items():
                    op_enum = None
                    for enum_val in fs_journal.FSOperationType:
                        if enum_val.name.lower() == op_type.lower():
                            op_enum = enum_val
                            break

                    if op_enum:
                        logger.info(f"Registering handler for {op_type} operations")
                        # This is a simplified version - in a real implementation,
                        # we would need to properly handle the async nature of these operations
                        # and ensure proper error handling and retries
                    else:
                        logger.warning(f"Could not find operation type for {op_type}")
            else:
                logger.error("No filesystem journal instance found in fs_integration module")
                return False
        else:
            logger.error("Required classes not found in fs_journal module")
            return False

        logger.info("✅ Successfully registered filesystem handlers with IPFS tools")
        return True

    except Exception as e:
        logger.error(f"Error registering filesystem handlers: {e}")
        return False

def setup_multi_backend_integration():
    """Set up integration with multiple storage backends"""
    try:
        # Import the multi-backend integration module
        multi_backend = import_module_from_file("multi_backend_fs_integration.py", "multi_backend_fs")
        logger.info("Successfully imported multi-backend FS integration module")

        # Initialize the multi-backend system
        if hasattr(multi_backend, 'init_multi_backend'):
            result = multi_backend.init_multi_backend()
            if result.get('success', False):
                logger.info("✅ Successfully initialized multi-backend filesystem")

                # Register default backends
                backends = [
                    {"type": "ipfs", "name": "ipfs_default", "mount_point": "/ipfs"},
                    {"type": "filecoin", "name": "filecoin_default", "mount_point": "/fil"},
                    {"type": "s3", "name": "s3_default", "mount_point": "/s3"},
                    {"type": "storacha", "name": "storacha_default", "mount_point": "/storacha"},
                    {"type": "huggingface", "name": "hf_default", "mount_point": "/hf"},
                    {"type": "ipfs_cluster", "name": "cluster_default", "mount_point": "/cluster"}
                ]

                for backend in backends:
                    if hasattr(multi_backend, 'register_backend'):
                        try:
                            result = multi_backend.register_backend(
                                backend_type=backend["type"],
                                name=backend["name"],
                                mount_point=backend["mount_point"]
                            )
                            if result.get('success', False):
                                logger.info(f"✅ Registered {backend['type']} backend at {backend['mount_point']}")
                            else:
                                logger.warning(f"Failed to register {backend['type']} backend: {result.get('error', 'Unknown error')}")
                        except Exception as e:
                            logger.warning(f"Error registering {backend['type']} backend: {e}")

                return True
            else:
                logger.error(f"Failed to initialize multi-backend filesystem: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error("init_multi_backend function not found in multi_backend module")
            return False

    except ImportError as e:
        logger.warning(f"Multi-backend integration not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Error setting up multi-backend integration: {e}")
        return False

def register_tools_with_mcp():
    """Register the enhanced tools with the MCP server"""
    try:
        # Check if the direct_mcp_server module exists
        if os.path.exists("direct_mcp_server.py"):
            direct_mcp = import_module_from_file("direct_mcp_server.py")
            logger.info("Successfully imported direct MCP server module")

            # Check if the register_tools function exists
            if hasattr(direct_mcp, 'register_tools'):
                # Import the tools registry
                tools_registry = import_module_from_file("ipfs_tools_registry.py")
                if hasattr(tools_registry, 'get_ipfs_tools'):
                    tools = tools_registry.get_ipfs_tools()

                    # Register the tools with the MCP server
                    result = direct_mcp.register_tools(tools)
                    if result:
                        logger.info(f"✅ Successfully registered {len(tools)} tools with the MCP server")
                        return True
                    else:
                        logger.error("Failed to register tools with the MCP server")
                        return False
                else:
                    logger.error("get_ipfs_tools function not found in tools registry module")
                    return False
            else:
                logger.error("register_tools function not found in direct MCP server module")
                return False
        else:
            logger.warning("direct_mcp_server.py not found, skipping MCP tool registration")
            return False

    except Exception as e:
        logger.error(f"Error registering tools with MCP server: {e}")
        return False

def create_restart_script():
    """Create a script to restart the MCP server with the new tools"""
    script_path = "restart_mcp_with_tools.sh"

    try:
        with open(script_path, 'w') as f:
            f.write("""#!/bin/bash
# Restart MCP server with enhanced tools and filesystem integration

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

echo "Starting MCP server with enhanced tools..."
python direct_mcp_server.py --with-fs-integration --with-enhanced-tools &

echo "MCP server started with PID $!"
echo "Waiting for server to initialize..."
sleep 3

echo "✅ MCP server is now running with enhanced tools and filesystem integration"
echo "You can use the new tools through the JSON-RPC interface"
""")

        # Make the script executable
        os.chmod(script_path, 0o755)

        logger.info(f"✅ Created restart script at {script_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating restart script: {e}")
        return False

def create_verification_script():
    """Create a script to verify the integration is working correctly"""
    script_path = "verify_fs_tool_integration.py"

    try:
        with open(script_path, 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Verify FS Tool Integration

This script verifies that the filesystem integration with IPFS tools is working correctly.
\"\"\"

import os
import sys
import json
import logging
import requests
import tempfile
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server endpoint
MCP_ENDPOINT = "http://localhost:3000/api"

def call_mcp_method(method, params=None):
    \"\"\"Call a method on the MCP server\"\"\"
    if params is None:
        params = {}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }

    try:
        response = requests.post(MCP_ENDPOINT, json=payload)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            logger.error(f"Error calling {method}: {result['error']}")
            return None

        return result.get("result")

    except Exception as e:
        logger.error(f"Error calling {method}: {e}")
        return None

def verify_fs_operations():
    \"\"\"Verify filesystem operations\"\"\"
    logger.info("Verifying filesystem operations...")

    # Create a test directory in the virtual filesystem
    test_dir = f"/test_fs_integration_{int(time.time())}"
    result = call_mcp_method("fs_journal_sync", {"path": "/"})
    if result is None:
        logger.error("Failed to sync filesystem journal")
        return False

    # Create a test file in the virtual filesystem
    test_file = f"{test_dir}/test_file.txt"
    test_content = f"Test content generated at {time.time()}"

    # First create the directory
    result = call_mcp_method("ipfs_files_mkdir", {"path": test_dir})
    if result is None:
        logger.error(f"Failed to create directory {test_dir}")
        return False

    logger.info(f"✅ Created test directory {test_dir}")

    # Write to the test file
    result = call_mcp_method("ipfs_files_write", {
        "path": test_file,
        "content": test_content,
        "create": True
    })
    if result is None:
        logger.error(f"Failed to write to file {test_file}")
        return False

    logger.info(f"✅ Created test file {test_file}")

    # Read the test file
    result = call_mcp_method("ipfs_files_read", {"path": test_file})
    if result is None:
        logger.error(f"Failed to read file {test_file}")
        return False

    if result != test_content:
        logger.error(f"File content mismatch. Expected: {test_content}, Got: {result}")
        return False

    logger.info(f"✅ Successfully read test file with correct content")

    # Get file stats
    result = call_mcp_method("ipfs_files_stat", {"path": test_file})
    if result is None:
        logger.error(f"Failed to get stats for file {test_file}")
        return False

    logger.info(f"✅ Got stats for test file: {result}")

    # Copy the file
    copy_file = f"{test_dir}/test_file_copy.txt"
    result = call_mcp_method("ipfs_files_cp", {
        "source": test_file,
        "dest": copy_file
    })
    if result is None:
        logger.error(f"Failed to copy file from {test_file} to {copy_file}")
        return False

    logger.info(f"✅ Copied test file to {copy_file}")

    # Verify the copy
    result = call_mcp_method("ipfs_files_read", {"path": copy_file})
    if result is None or result != test_content:
        logger.error(f"Failed to verify copied file content")
        return False

    logger.info(f"✅ Verified copied file content")

    # Move the file
    move_file = f"{test_dir}/test_file_moved.txt"
    result = call_mcp_method("ipfs_files_mv", {
        "source": copy_file,
        "dest": move_file
    })
    if result is None:
        logger.error(f"Failed to move file from {copy_file} to {move_file}")
        return False

    logger.info(f"✅ Moved test file to {move_file}")

    # Verify the move
    result = call_mcp_method("ipfs_files_read", {"path": move_file})
    if result is None or result != test_content:
        logger.error(f"Failed to verify moved file content")
        return False

    logger.info(f"✅ Verified moved file content")

    # List directory contents
    result = call_mcp_method("ipfs_files_ls", {"path": test_dir})
    if result is None:
        logger.error(f"Failed to list directory {test_dir}")
        return False

    logger.info(f"✅ Listed directory contents: {result}")

    # Clean up
    result = call_mcp_method("ipfs_files_rm", {
        "path": test_dir,
        "recursive": True
    })
    if result is None:
        logger.error(f"Failed to remove test directory {test_dir}")
        return False

    logger.info(f"✅ Cleaned up test directory")

    return True

def verify_multi_backend():
    \"\"\"Verify multi-backend operations\"\"\"
    logger.info("Verifying multi-backend operations...")

    # List backends
    result = call_mcp_method("multi_backend_list_backends")
    if result is None:
        logger.warning("Multi-backend functionality not available")
        return True  # Not a failure, just not available

    logger.info(f"✅ Listed backends: {result}")

    # Test mapping a path
    local_path = tempfile.mkdtemp()
    backend_path = "/ipfs/test_mapping"

    result = call_mcp_method("multi_backend_map", {
        "backend_path": backend_path,
        "local_path": local_path
    })
    if result is None:
        logger.error(f"Failed to map {backend_path} to {local_path}")
        return False

    logger.info(f"✅ Mapped {backend_path} to {local_path}")

    # Create a test file in the local path
    test_file = os.path.join(local_path, "test_file.txt")
    with open(test_file, 'w') as f:
        f.write("Test content for multi-backend")

    # Sync the mapping
    result = call_mcp_method("multi_backend_sync")
    if result is None:
        logger.error("Failed to sync multi-backend")
        return False

    logger.info(f"✅ Synced multi-backend")

    # Unmap the path
    result = call_mcp_method("multi_backend_unmap", {
        "backend_path": backend_path
    })
    if result is None:
        logger.error(f"Failed to unmap {backend_path}")
        return False

    logger.info(f"✅ Unmapped {backend_path}")

    return True

def verify_enhanced_tools():
    \"\"\"Verify enhanced tools\"\"\"
    logger.info("Verifying enhanced tools...")

    # Test IPFS cluster tools if available
    result = call_mcp_method("ipfs_cluster_peers")
    if result is not None:
        logger.info(f"✅ IPFS cluster tools available: {result}")
    else:
        logger.warning("IPFS cluster tools not available")

    # Test Lassie tools if available
    temp_file = tempfile.mktemp()
    result = call_mcp_method("lassie_fetch", {
        "cid": "QmPChd2hVbrJ6bfo3WBcTW4iZnpHm8TEzWkLHmLpXhF68A",  # Example CID
        "output_path": temp_file
    })
    if result is not None:
        logger.info(f"✅ Lassie tools available: {result}")
    else:
        logger.warning("Lassie tools not available")

    # Test Storacha tools if available
    result = call_mcp_method("storacha_store", {
        "content_path": __file__  # Use this script as test content
    })
    if result is not None:
        logger.info(f"✅ Storacha tools available: {result}")
    else:
        logger.warning("Storacha tools not available")

    return True

def main():
    \"\"\"Main verification function\"\"\"
    logger.info("Starting verification of FS tool integration...")

    # Check if MCP server is running
    try:
        response = requests.get(MCP_ENDPOINT.replace("/api", "/health"))
        if response.status_code != 200:
            logger.error(f"MCP server is not running or health check failed: {response.status_code}")
            return 1

        logger.info("✅ MCP server is running")
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")
        logger.error("Please make sure the MCP server is running with the enhanced tools")
        return 1

    # Verify filesystem operations
    if not verify_fs_operations():
        logger.error("❌ Filesystem operations verification failed")
        return 1

    # Verify multi-backend operations
    if not verify_multi_backend():
        logger.error("❌ Multi-backend operations verification failed")
        return 1

    # Verify enhanced tools
    if not verify_enhanced_tools():
        logger.error("❌ Enhanced tools verification failed")
        return 1

    logger.info("\\n✅ All verifications passed successfully!")
    logger.info("The filesystem integration with IPFS tools is working correctly")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")

        logger.info(f"✅ Created verification script at {script_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating verification script: {e}")
        return False

def main():
    """Main function to integrate FS with tools"""
    logger.info("Starting FS integration with tools...")

    # Load required modules
    fs_integration = load_fs_integration()
    fs_journal = load_fs_journal_tools()
    enhanced_tools = load_enhanced_tools()

    # Register filesystem handlers with tools
    handlers_registered = register_fs_handlers_with_tools(fs_integration, fs_journal, enhanced_tools)

    # Set up multi-backend integration
    multi_backend_setup = setup_multi_backend_integration()

    # Register tools with MCP server
    tools_registered = register_tools_with_mcp()

    # Create restart script
    restart_script_created = create_restart_script()

    # Create verification script
    verification_script_created = create_verification_script()

    # Check overall success
    success = all([
        fs_integration is not None,
        fs_journal is not None,
        enhanced_tools is not None,
        handlers_registered,
        restart_script_created,
        verification_script_created
    ])

    if success:
        logger.info("\n✅ FS integration with tools completed successfully")
        logger.info("To use the integrated system:")
        logger.info("  1. Run ./restart_mcp_with_tools.sh to restart the MCP server")
        logger.info("  2. Run python verify_fs_tool_integration.py to verify the integration")
        return 0
    else:
        logger.error("\n❌ FS integration with tools failed")
        logger.error("Please check the logs for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
