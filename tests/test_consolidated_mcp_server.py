#!/usr/bin/env python3
"""
Test script for the Consolidated MCP Server.
This script tests all tools exposed by the server to ensure they are properly functioning.
"""

import argparse
import json
import sys
import time
import requests
from typing import Dict, Any, List, Optional

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Default server URL
DEFAULT_URL = "http://127.0.0.1:3000"

def print_header(message: str) -> None:
    """Print a formatted header message."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{message.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

def print_subheader(message: str) -> None:
    """Print a formatted subheader message."""
    print(f"\n{BOLD}{BLUE}{'-' * 50}{RESET}")
    print(f"{BOLD}{BLUE}{message}{RESET}")
    print(f"{BOLD}{BLUE}{'-' * 50}{RESET}")

def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{GREEN}✓ {message}{RESET}")

def print_failure(message: str) -> None:
    """Print a failure message."""
    print(f"{RED}✗ {message}{RESET}")

def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{YELLOW}⚠ {message}{RESET}")

def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{BLUE}ℹ {message}{RESET}")

def print_json(data: Dict[str, Any]) -> None:
    """Print JSON data in a formatted way."""
    print(json.dumps(data, indent=2))

def jsonrpc_request(url: str, method: str, params: Dict[str, Any], request_id: int = 1) -> Dict[str, Any]:
    """Send a JSON-RPC request to the server."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print_failure(f"Error making request: {e}")
        return {"error": {"message": str(e)}}

def test_health_endpoint(base_url: str) -> bool:
    """Test the health endpoint."""
    print_subheader("Testing Health Endpoint")
    try:
        response = requests.get(f"{base_url}/health")
        response.raise_for_status()
        health_data = response.json()
        print_success("Health endpoint responded successfully")
        print_info("Health Status:")
        print_json(health_data)
        return True
    except requests.exceptions.RequestException as e:
        print_failure(f"Health endpoint test failed: {e}")
        return False

def test_initialize_endpoint(base_url: str) -> bool:
    """Test the initialize endpoint."""
    print_subheader("Testing Initialize Endpoint")
    try:
        response = requests.get(f"{base_url}/initialize")
        response.raise_for_status()
        init_data = response.json()
        print_success("Initialize endpoint responded successfully")
        print_info("Initialize Response:")
        print_json(init_data)
        if "models" in init_data and "ipfs" in init_data["models"]:
            print_success("IPFS model is available")
        else:
            print_warning("IPFS model not found in initialize response")
        return True
    except requests.exceptions.RequestException as e:
        print_failure(f"Initialize endpoint test failed: {e}")
        return False

def test_tools_endpoint(base_url: str) -> List[str]:
    """Test the tools endpoint and return list of available tools."""
    print_subheader("Testing Tools Endpoint")
    try:
        response = requests.get(f"{base_url}/tools")
        response.raise_for_status()
        tools_data = response.json()

        # Handle different possible response formats
        if isinstance(tools_data, dict) and "tools" in tools_data:
            # Format: {"tools": [{"name": "tool1"}, {"name": "tool2"}]}
            tools = tools_data.get("tools", [])
            tool_names = [tool["name"] for tool in tools]
        elif isinstance(tools_data, list):
            # Format: [{"name": "tool1"}, {"name": "tool2"}]
            tool_names = [tool["name"] for tool in tools_data if isinstance(tool, dict) and "name" in tool]
        elif isinstance(tools_data, dict):
            # Format: {"tool1": {...}, "tool2": {...}}
            tool_names = list(tools_data.keys())
        elif isinstance(tools_data, str):
            # Format: "tool1, tool2, tool3"
            tool_names = [name.strip() for name in tools_data.split(',')]
        else:
            tool_names = []
            print_warning(f"Unexpected tools response format: {type(tools_data)}")

        tool_count = len(tool_names)
        print_success(f"Tools endpoint responded successfully with {tool_count} tools")
        if tool_names:
            print_info(f"Available tools: {', '.join(tool_names)}")
        return tool_names
    except requests.exceptions.RequestException as e:
        print_failure(f"Tools endpoint test failed: {e}")
        return []
    except (ValueError, TypeError) as e:
        print_failure(f"Error parsing tools response: {e}")
        return []

def test_jsonrpc_endpoint(base_url: str) -> bool:
    """Test the JSON-RPC endpoint."""
    print_subheader("Testing JSON-RPC Endpoint")
    try:
        # Send a simple JSON-RPC request to ping the server
        result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "utility_ping",
                "message": "Testing JSON-RPC endpoint"
            }
        )
        if "result" in result:
            print_success("JSON-RPC endpoint responded successfully")
            print_info("Ping Result:")
            print_json(result["result"])
            return True
        elif "error" in result:
            print_failure(f"JSON-RPC endpoint error: {result['error'].get('message', 'Unknown error')}")
            return False
        else:
            print_failure("JSON-RPC endpoint returned unexpected response")
            return False
    except Exception as e:
        print_failure(f"JSON-RPC endpoint test failed: {e}")
        return False

def test_ipfs_tools(base_url: str) -> bool:
    """Test IPFS tools."""
    print_subheader("Testing IPFS Tools")

    # Test ipfs_add
    print_info("Testing ipfs_add...")
    add_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "ipfs_add",
            "content": "Hello, IPFS from Consolidated MCP Server!",
            "name": "test.txt"
        }
    )

    if "result" in add_result and "Hash" in add_result["result"]:
        cid = add_result["result"]["Hash"]
        print_success(f"Successfully added content to IPFS with CID: {cid}")

        # Test ipfs_cat
        print_info("Testing ipfs_cat...")
        cat_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_cat",
                "cid": cid
            }
        )

        if "result" in cat_result and cat_result["result"].get("data") == "Hello, IPFS from Consolidated MCP Server!":
            print_success("Successfully retrieved content from IPFS")
        else:
            print_failure("Failed to retrieve correct content from IPFS")
            return False

        # Test ipfs_pin_add
        print_info("Testing ipfs_pin_add...")
        pin_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_pin_add",
                "cid": cid
            }
        )

        if "result" in pin_result and pin_result["result"].get("success", False):
            print_success("Successfully pinned content")
        else:
            print_warning("Failed to pin content or already pinned")

        # Test ipfs_pin_ls
        print_info("Testing ipfs_pin_ls...")
        pin_ls_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_pin_ls"
            }
        )

        if "result" in pin_ls_result and "pins" in pin_ls_result["result"]:
            pins = pin_ls_result["result"]["pins"]
            if cid in pins or any(cid in pin for pin in pins):
                print_success("CID found in pins list")
            else:
                print_warning("CID not found in pins list")
        else:
            print_warning("Failed to list pins")

        # Test ipfs_pin_rm
        print_info("Testing ipfs_pin_rm...")
        pin_rm_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_pin_rm",
                "cid": cid
            }
        )

        if "result" in pin_rm_result and pin_rm_result["result"].get("success", False):
            print_success("Successfully unpinned content")
        else:
            print_warning("Failed to unpin content")

        return True
    else:
        error_msg = add_result.get("error", {}).get("message", "Unknown error")
        print_failure(f"Failed to add content to IPFS: {error_msg}")
        return False

def test_vfs_tools(base_url: str) -> bool:
    """Test Virtual Filesystem tools."""
    print_subheader("Testing VFS Tools")

    # Test vfs_mkdir
    print_info("Testing vfs_mkdir...")
    mkdir_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "vfs_mkdir",
            "path": "/test_directory"
        }
    )

    if "result" in mkdir_result and mkdir_result["result"].get("success", False):
        print_success("Successfully created directory")

        # Test vfs_write
        print_info("Testing vfs_write...")
        write_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "vfs_write",
                "path": "/test_directory/test_file.txt",
                "content": "Hello, Virtual Filesystem!"
            }
        )

        if "result" in write_result and write_result["result"].get("success", False):
            print_success("Successfully wrote file")

            # Test vfs_list
            print_info("Testing vfs_list...")
            ls_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_list",
                    "path": "/test_directory"
                }
            )

            if "result" in ls_result and "entries" in ls_result["result"]:
                entries = ls_result["result"]["entries"]
                entry_names = [entry["name"] for entry in entries if isinstance(entry, dict) and "name" in entry]
                if any(name == "test_file.txt" for name in entry_names):
                    print_success("File found in directory listing")
                else:
                    print_failure("File not found in directory listing")
                    return False
            else:
                print_failure("Failed to list directory contents")
                return False

            # Test vfs_read
            print_info("Testing vfs_read...")
            read_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_read",
                    "path": "/test_directory/test_file.txt"
                }
            )

            if "result" in read_result and read_result["result"].get("content") == "Hello, Virtual Filesystem!":
                print_success("Successfully read file with correct content")
            else:
                print_failure("Failed to read file or content mismatch")
                return False

            # Test vfs_stat
            print_info("Testing vfs_stat...")
            stat_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_stat",
                    "path": "/test_directory/test_file.txt"
                }
            )

            if "result" in stat_result and "type" in stat_result["result"] and stat_result["result"]["type"] == "file":
                print_success("Successfully got file stats")
            else:
                print_failure("Failed to get file stats")
                return False

            # Test vfs_rm
            print_info("Testing vfs_rm...")
            rm_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_rm",
                    "path": "/test_directory/test_file.txt"
                }
            )

            if "result" in rm_result and rm_result["result"].get("success", False):
                print_success("Successfully removed file")
            else:
                print_failure("Failed to remove file")
                return False

            # Test removing directory with vfs_rm
            print_info("Testing vfs_rm on directory...")
            rmdir_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_rm",
                    "path": "/test_directory"
                }
            )

            if "result" in rmdir_result and rmdir_result["result"].get("success", False):
                print_success("Successfully removed directory")
            else:
                print_failure("Failed to remove directory")
                return False

            return True
        else:
            print_failure("Failed to write file")
            return False
    else:
        error_msg = mkdir_result.get("error", {}).get("message", "Unknown error")
        print_failure(f"Failed to create directory: {error_msg}")
        return False

def test_bridge_tools(base_url: str) -> bool:
    """Test IPFS-VFS bridge tools."""
    print_subheader("Testing IPFS-VFS Bridge Tools")

    # First, let's create a file in VFS
    print_info("Creating test directory and file in VFS...")
    mkdir_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "vfs_mkdir",
            "path": "/bridge_test"
        }
    )

    if "result" not in mkdir_result or not mkdir_result["result"].get("success", False):
        print_failure("Failed to create test directory")
        return False

    write_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "vfs_write",
            "path": "/bridge_test/bridge_file.txt",
            "content": "Testing IPFS-VFS Bridge!"
        }
    )

    if "result" not in write_result or not write_result["result"].get("success", False):
        print_failure("Failed to write test file")
        return False

    print_success("Created test file in VFS")

    # Test export to IPFS
    print_info("Testing ipfs_fs_export_to_ipfs...")
    export_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "ipfs_fs_export_to_ipfs",
            "path": "/bridge_test/bridge_file.txt"
        }
    )

    if "result" in export_result and "cid" in export_result["result"]:
        cid = export_result["result"]["cid"]
        print_success(f"Successfully exported file to IPFS with CID: {cid}")

        # Verify content in IPFS
        cat_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_cat",
                "cid": cid
            }
        )

        if "result" in cat_result and cat_result["result"].get("data") == "Testing IPFS-VFS Bridge!":
            print_success("Content in IPFS matches the original file")
        else:
            print_failure("Content mismatch or failed to retrieve from IPFS")
            return False

        # Test import from IPFS
        print_info("Testing ipfs_fs_import_from_ipfs...")
        import_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "ipfs_fs_import_from_ipfs",
                "cid": cid,
                "path": "/bridge_test/imported_file.txt"
            }
        )

        if "result" in import_result and import_result["result"].get("success", False):
            print_success("Successfully imported file from IPFS to VFS")

            # Verify content in VFS
            read_result = jsonrpc_request(
                f"{base_url}/jsonrpc",
                "use_tool",
                {
                    "tool_name": "vfs_read",
                    "path": "/bridge_test/imported_file.txt"
                }
            )

            if "result" in read_result and read_result["result"].get("content") == "Testing IPFS-VFS Bridge!":
                print_success("Content in VFS matches the original file")
            else:
                print_failure("Content mismatch or failed to read imported file")
                return False
        else:
            print_failure("Failed to import file from IPFS to VFS")
            return False

        # Clean up
        print_info("Cleaning up test files...")
        jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "vfs_rm",
                "path": "/bridge_test/bridge_file.txt"
            }
        )
        jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "vfs_rm",
                "path": "/bridge_test/imported_file.txt"
            }
        )
        jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "vfs_rm",
                "path": "/bridge_test"
            }
        )

        return True
    else:
        error_msg = export_result.get("error", {}).get("message", "Unknown error")
        print_failure(f"Failed to export file to IPFS: {error_msg}")
        return False

def test_journal_tools(base_url: str) -> bool:
    """Test filesystem journal tools."""
    print_subheader("Testing Filesystem Journal Tools")

    # Test fs_journal_status
    print_info("Testing fs_journal_status...")
    status_result = jsonrpc_request(
        f"{base_url}/jsonrpc",
        "use_tool",
        {
            "tool_name": "fs_journal_status"
        }
    )

    if "result" in status_result and "enabled" in status_result["result"]:
        print_success("Successfully retrieved journal status")
        enabled = status_result["result"]["enabled"]
        print_info(f"Journal is {'enabled' if enabled else 'disabled'}")

        if not enabled:
            print_warning("Journal is disabled, skipping other journal tests")
            return True

        # Test fs_journal_get_history
        print_info("Testing fs_journal_get_history...")
        records_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "fs_journal_get_history",
                "limit": 5
            }
        )

        if "result" in records_result and "entries" in records_result["result"]:
            print_success("Successfully retrieved journal records")
            records = records_result["result"]["entries"]
            print_info(f"Retrieved {len(records)} records")
        else:
            print_warning("Failed to retrieve journal records")

        # Test fs_journal_clear
        print_info("Testing fs_journal_clear...")
        clear_result = jsonrpc_request(
            f"{base_url}/jsonrpc",
            "use_tool",
            {
                "tool_name": "fs_journal_clear"
            }
        )

        if "result" in clear_result and clear_result["result"].get("success", False):
            print_success("Successfully cleared journal")
        else:
            print_warning("Failed to clear journal")

        return True
    else:
        error_msg = status_result.get("error", {}).get("message", "Unknown error")
        print_failure(f"Failed to get journal status: {error_msg}")
        return False

def run_all_tests(base_url: str) -> None:
    """Run all tests for the MCP server."""
    print_header("Consolidated MCP Server Test Suite")
    print_info(f"Testing server at: {base_url}")
    print_info(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Basic server tests
    health_ok = test_health_endpoint(base_url)
    initialize_ok = test_initialize_endpoint(base_url)
    tools = test_tools_endpoint(base_url)
    jsonrpc_ok = test_jsonrpc_endpoint(base_url)

    if not (health_ok and initialize_ok and tools and jsonrpc_ok):
        print_failure("Basic server tests failed. Aborting further tests.")
        sys.exit(1)

    # Tool category tests
    ipfs_ok = test_ipfs_tools(base_url)
    vfs_ok = test_vfs_tools(base_url)
    bridge_ok = test_bridge_tools(base_url)
    journal_ok = test_journal_tools(base_url)

    # Summary
    print_header("Test Summary")
    print(f"{GREEN if health_ok else RED}Health Endpoint: {'PASS' if health_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if initialize_ok else RED}Initialize Endpoint: {'PASS' if initialize_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if tools else RED}Tools Endpoint: {'PASS' if tools else 'FAIL'}{RESET}")
    print(f"{GREEN if jsonrpc_ok else RED}JSON-RPC Endpoint: {'PASS' if jsonrpc_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if ipfs_ok else RED}IPFS Tools: {'PASS' if ipfs_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if vfs_ok else RED}VFS Tools: {'PASS' if vfs_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if bridge_ok else RED}IPFS-VFS Bridge: {'PASS' if bridge_ok else 'FAIL'}{RESET}")
    print(f"{GREEN if journal_ok else RED}Filesystem Journal: {'PASS' if journal_ok else 'FAIL'}{RESET}")

    all_passed = health_ok and initialize_ok and jsonrpc_ok and ipfs_ok and vfs_ok and bridge_ok and journal_ok
    if all_passed:
        print_success("\nAll tests passed! The Consolidated MCP Server is working correctly.")
    else:
        print_failure("\nSome tests failed. Please check the logs above for details.")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test the Consolidated MCP Server")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Server URL (default: {DEFAULT_URL})")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_all_tests(args.url)
