#!/usr/bin/env python3
"""
Direct approach to start an MCP server with IPFS daemon integration.

This script:
1. Directly patches the IPFSModelAnyIO class with an add_content method
2. Starts an MCP server that can communicate with the IPFS daemon
3. Tests that the integration works by adding content to IPFS
"""

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def patch_ipfs_model():
    """Directly patch the IPFSModelAnyIO class with an add_content method."""
    # Import the module that needs patching
    from ipfs_kit_py.mcp.models.ipfs_model_anyio import IPFSModelAnyIO

    # Check if the method already exists
    if hasattr(IPFSModelAnyIO, 'add_content'):
        logger.info("IPFSModelAnyIO already has add_content method")
        return True

    # Define the add_content method
    async def add_content(self, content=None, **kwargs):
        """
        Add content to IPFS and return the CID.
        This is a compatibility method added at runtime.
        """
        logger.info("Using patched add_content method")

        # Handle args/kwargs
        if content is None and 'content' in kwargs:
            content = kwargs.pop('content')

        if content is None:
            raise ValueError("Content must be provided")

        # Add string content to IPFS
        if isinstance(content, str):
            # Try to find a suitable string method
            if hasattr(self, 'add_str'):
                return await self.add_str(content, **kwargs)
            elif hasattr(self, 'add_string'):
                return await self.add_string(content, **kwargs)
            elif hasattr(self.ipfs, 'add_str'):
                return await self.ipfs.add_str(content, **kwargs)
            elif hasattr(self.ipfs, 'add_string'):
                return await self.ipfs.add_string(content, **kwargs)
            else:
                # Fallback: convert to bytes and use add_bytes
                content_bytes = content.encode('utf-8')
                if hasattr(self, 'add_bytes'):
                    return await self.add_bytes(content_bytes, **kwargs)
                elif hasattr(self.ipfs, 'add_bytes'):
                    return await self.ipfs.add_bytes(content_bytes, **kwargs)
                else:
                    # Last resort: use command directly
                    result = await self.ipfs.command('add', stdin=content)
                    return result

        # Add bytes content to IPFS
        elif isinstance(content, bytes):
            if hasattr(self, 'add_bytes'):
                return await self.add_bytes(content, **kwargs)
            elif hasattr(self.ipfs, 'add_bytes'):
                return await self.ipfs.add_bytes(content, **kwargs)
            else:
                # Last resort: use command directly
                result = await self.ipfs.command('add', stdin=content)
                return result

        # Unknown content type
        else:
            raise TypeError(f"Unsupported content type: {type(content)}")

    # Add the method to the class
    IPFSModelAnyIO.add_content = add_content
    logger.info("Successfully patched IPFSModelAnyIO.add_content")
    return True

def check_ipfs_daemon():
    """Check if the IPFS daemon is running and responsive."""
    try:
        # Check if we can get the node ID
        result = subprocess.run(
            ["ipfs", "id", "--format=<id>"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0 and result.stdout.strip()
    except Exception as e:
        logger.error(f"Error checking IPFS daemon: {e}")
        return False

def get_free_port(start=8080, max_attempts=100):
    """Find a free port starting from the given port."""
    import socket

    for port in range(start, start + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue

    # Fallback to a random port
    return 0

def start_mcp_server():
    """Start a new MCP server with IPFS daemon integration."""
    # Apply our patch first
    if not patch_ipfs_model():
        logger.error("Failed to patch IPFSModelAnyIO")
        return False

    # Find a suitable port
    port = get_free_port(8080)

    # Find an MCP server script to use
    script_candidates = [
        "run_mcp_server_anyio.py",
        "run_mcp_server_fixed.py",
        "run_mcp_server.py"
    ]

    server_script = None
    for script in script_candidates:
        if os.path.exists(script):
            server_script = script
            break

    if not server_script:
        logger.error("Could not find an MCP server script to use")
        return False

    logger.info(f"Starting MCP server using {server_script} on port {port}")

    # Start the server in a subprocess
    cmd = [
        sys.executable,  # Use the same Python interpreter
        "-c",
        f"""
import os
import sys
import importlib.util

# Add the current directory to sys.path
sys.path.insert(0, os.getcwd())

# First, patch the IPFSModelAnyIO class
from mcp_direct_fix import patch_ipfs_model
patch_ipfs_model()

# Then import and run the server script
spec = importlib.util.spec_from_file_location("server_module", "{server_script}")
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

# If the module has a main function, call it with appropriate args
if hasattr(server_module, "main"):
    sys.argv = ["{server_script}", "--debug", "--port", "{port}", "--host", "localhost"]
    server_module.main()
else:
    print("Could not find main function in server script")
    sys.exit(1)
        """
    ]

    # Start the server and detach it
    try:
        with open("mcp_direct_server.log", "w") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True  # Detach from parent process
            )

        # Give it time to start
        logger.info(f"MCP server starting on port {port}, waiting for it to become responsive...")
        time.sleep(5)

        # Poll the health endpoint to see if it's running
        for i in range(30):  # Wait up to 30 seconds
            try:
                health_check = subprocess.run(
                    ["curl", "-s", f"http://localhost:{port}/api/v0/mcp/health"],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if health_check.returncode == 0 and "success" in health_check.stdout:
                    logger.info(f"MCP server is running on port {port}")
                    return {"port": port, "pid": process.pid}
            except Exception:
                pass

            # Wait before trying again
            time.sleep(1)

        logger.error(f"MCP server did not become responsive after 30 seconds")
        return False
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False

def test_ipfs_api(port):
    """Test the IPFS API via the MCP server."""
    try:
        # Create a test string
        test_content = f"Test content {time.time()}"

        # Try to add the content via the API
        add_command = [
            "curl", "-s",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"content": test_content}),
            f"http://localhost:{port}/api/v0/mcp/ipfs/add/json"
        ]

        logger.info(f"Testing IPFS API with content: {test_content}")
        result = subprocess.run(add_command, capture_output=True, text=True, check=False)

        # Check if the result was successful
        if result.returncode == 0 and "success" in result.stdout:
            try:
                response = json.loads(result.stdout)
                if response.get("success", False) and "cid" in response:
                    cid = response["cid"]
                    logger.info(f"Successfully added content to IPFS with CID: {cid}")

                    # Now try to retrieve the content
                    cat_command = [
                        "curl", "-s",
                        f"http://localhost:{port}/api/v0/mcp/ipfs/cat/{cid}"
                    ]

                    cat_result = subprocess.run(cat_command, capture_output=True, text=True, check=False)

                    if cat_result.returncode == 0 and cat_result.stdout.strip() == test_content:
                        logger.info(f"Successfully retrieved content from IPFS: {cat_result.stdout.strip()}")
                        return {"success": True, "cid": cid, "content": cat_result.stdout.strip()}
                    else:
                        logger.error(f"Failed to retrieve content: {cat_result.stdout}")
                        return False
                else:
                    logger.error(f"Failed to add content: {response}")
                    return False
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {result.stdout}")
                return False
        else:
            logger.error(f"Failed to add content: {result.stdout}")
            return False
    except Exception as e:
        logger.error(f"Error testing IPFS API: {e}")
        return False

def main():
    """Main function to fix and test the MCP server with IPFS daemon integration."""
    # Save this script for the subprocess to import
    script_path = os.path.abspath(__file__)
    module_name = "mcp_direct_fix"
    if not os.path.exists(f"{module_name}.py"):
        with open(f"{module_name}.py", "w") as f:
            with open(script_path, "r") as source:
                f.write(source.read())
        logger.info(f"Created {module_name}.py for subprocess to import")

    # Check if IPFS daemon is running
    if not check_ipfs_daemon():
        logger.error("IPFS daemon is not running. Please start it first with: ipfs daemon")
        return 1

    # Start the MCP server
    server_info = start_mcp_server()
    if not server_info:
        logger.error("Failed to start MCP server")
        return 1

    # Test the IPFS API
    test_result = test_ipfs_api(server_info["port"])
    if not test_result:
        logger.error("IPFS integration test failed")

        # Try again with a small delay
        logger.info("Retrying IPFS integration test after a delay...")
        time.sleep(5)
        test_result = test_ipfs_api(server_info["port"])

        if not test_result:
            logger.error("IPFS integration test failed again")
            print("\nMCP server is running but the IPFS integration test failed.")
            print("The server might be running with a different daemon configuration.")
            print(f"MCP server URL: http://localhost:{server_info['port']}/api/v0/mcp")
            print(f"Documentation: http://localhost:{server_info['port']}/docs")
            print(f"Server PID: {server_info['pid']}")
            print(f"Log file: {os.path.abspath('mcp_direct_server.log')}")
            print("\nTo stop this server: kill", server_info["pid"])
            return 1

    # Success!
    print("\n=== SUCCESS! ===")
    print("MCP server is running with IPFS daemon integration")
    print(f"API URL: http://localhost:{server_info['port']}/api/v0/mcp")
    print(f"Documentation: http://localhost:{server_info['port']}/docs")
    print(f"Server PID: {server_info['pid']}")
    print(f"Log file: {os.path.abspath('mcp_direct_server.log')}")
    print("\nIPFS integration test:")
    print(f"Added content to IPFS with CID: {test_result['cid']}")
    print(f"Retrieved content from IPFS: {test_result['content']}")
    print("\nTo stop this server: kill", server_info["pid"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
