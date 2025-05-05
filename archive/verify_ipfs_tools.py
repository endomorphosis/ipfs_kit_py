#!/usr/bin/env python3
"""
Verify IPFS tools registered with MCP server.

This script checks if the IPFS tools have been properly registered with the MCP server
and verifies that they can be called successfully.
"""

import os
import sys
import logging
import importlib
import json
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ipfs_tools_verification.log')
    ]
)
logger = logging.getLogger('ipfs_tools_verification')

def verify_direct_mcp_tools():
    """
    Verify IPFS tools registered with direct_mcp_server.
    
    Returns:
        Dict with verification results.
    """
    results = {
        "server_found": False,
        "tools_available": False,
        "ipfs_tools_count": 0,
        "fs_tools_count": 0,
        "verification_results": {}
    }
    
    try:
        # Try to import the direct_mcp_server module
        import direct_mcp_server
        results["server_found"] = True
        
        # Check if the server instance exists
        if hasattr(direct_mcp_server, 'server'):
            server = direct_mcp_server.server
            
            # Check if tools are available
            tools_dict = None
            
            # Try to access tools attribute
            if hasattr(server, 'tools'):
                tools_dict = server.tools
                results["tools_available"] = True
            
            # Try to access get_tools method
            elif hasattr(server, 'get_tools'):
                tools_dict = server.get_tools()
                results["tools_available"] = True
            
            if tools_dict:
                # Count IPFS tools
                ipfs_tool_categories = [
                    "list_files", "stat_file", "make_directory", "read_file", "write_file", "remove_file",
                    "swarm_", "get_content", "add_content", "pin_content", "unpin_content", "list_pins",
                    "publish_name", "resolve_name", "dag_", "block_", "dht_", "get_node_id", "get_version",
                    "get_stats", "check_daemon"
                ]
                
                # Count FS integration tools
                fs_tool_categories = [
                    "map_ipfs_to_fs", "unmap_ipfs_from_fs", "sync_fs_to_ipfs", "sync_ipfs_to_fs",
                    "list_fs_ipfs_mappings", "mount_ipfs", "unmount_ipfs"
                ]
                
                # Verify each type of tool
                for tool_name in tools_dict:
                    # Check if this is an IPFS tool
                    is_ipfs_tool = any(category in tool_name for category in ipfs_tool_categories)
                    is_fs_tool = any(category in tool_name for category in fs_tool_categories)
                    
                    if is_ipfs_tool:
                        results["ipfs_tools_count"] += 1
                    
                    if is_fs_tool:
                        results["fs_tools_count"] += 1
                    
                    # Store the tool details
                    tool = tools_dict[tool_name]
                    if tool:
                        tool_details = {
                            "name": tool_name,
                            "description": tool.get("description", "No description available"),
                            "parameters": len(tool.get("parameters", [])),
                            "type": "IPFS" if is_ipfs_tool else ("FS Integration" if is_fs_tool else "Other")
                        }
                        results["verification_results"][tool_name] = tool_details
        
    except ImportError:
        logger.warning("Could not import direct_mcp_server")
    except Exception as e:
        logger.error(f"Error verifying tools: {e}")
    
    return results

def verify_tool_registry_file():
    """
    Verify IPFS tools in registry file.
    
    Returns:
        Dict with verification results.
    """
    results = {
        "registry_found": False,
        "tools_count": 0,
        "verification_results": {}
    }
    
    try:
        # Check if ipfs_tools_registry.py exists
        if os.path.exists('ipfs_tools_registry.py'):
            results["registry_found"] = True
            
            # Try to import the registry module
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import ipfs_tools_registry
            
            # Check if TOOLS_REGISTRY is defined
            if hasattr(ipfs_tools_registry, 'TOOLS_REGISTRY'):
                tools_registry = ipfs_tools_registry.TOOLS_REGISTRY
                results["tools_count"] = len(tools_registry)
                
                # Get the details of each tool
                for tool_name in tools_registry:
                    results["verification_results"][tool_name] = {
                        "name": tool_name,
                        "registered": True
                    }
    except ImportError:
        logger.warning("Could not import ipfs_tools_registry")
    except Exception as e:
        logger.error(f"Error verifying registry file: {e}")
    
    return results

def try_sample_tool_calls():
    """
    Try calling a few sample tools to verify they work.
    
    Returns:
        Dict with call results.
    """
    results = {
        "calls_attempted": 0,
        "calls_succeeded": 0,
        "call_results": {}
    }
    
    try:
        # Try to import direct_mcp_server
        import direct_mcp_server
        
        # Check if server has handle_tool method
        if hasattr(direct_mcp_server.server, 'handle_tool'):
            handle_tool = direct_mcp_server.server.handle_tool
            
            # List of sample tools to try
            sample_tools = [
                # Basic IPFS tools
                {"name": "get_version", "args": {}},
                {"name": "list_files", "args": {"path": "/"}},
                {"name": "stat_file", "args": {"path": "/"}},
                
                # Filesystem integration tools
                {"name": "list_fs_ipfs_mappings", "args": {}},
            ]
            
            # Try each sample tool
            for tool in sample_tools:
                results["calls_attempted"] += 1
                
                try:
                    # Call the tool
                    result = handle_tool(tool["name"], tool["args"])
                    
                    # Record the result
                    if result and not (isinstance(result, dict) and "error" in result):
                        results["calls_succeeded"] += 1
                        results["call_results"][tool["name"]] = {
                            "success": True,
                            "result": result
                        }
                    else:
                        results["call_results"][tool["name"]] = {
                            "success": False,
                            "error": result.get("error", "Unknown error") if isinstance(result, dict) else "Invalid result"
                        }
                except Exception as e:
                    results["call_results"][tool["name"]] = {
                        "success": False,
                        "error": str(e)
                    }
    except ImportError:
        logger.warning("Could not import direct_mcp_server")
    except Exception as e:
        logger.error(f"Error trying sample tool calls: {e}")
    
    return results

def main():
    """Verify IPFS tools."""
    logger.info("Starting IPFS tools verification...")
    
    # Verify tools in direct_mcp_server
    direct_mcp_results = verify_direct_mcp_tools()
    logger.info(f"Direct MCP server check: Found {direct_mcp_results['ipfs_tools_count']} IPFS tools and {direct_mcp_results['fs_tools_count']} FS integration tools")
    
    # Verify tools in registry file
    registry_results = verify_tool_registry_file()
    if registry_results["registry_found"]:
        logger.info(f"Registry file check: Found {registry_results['tools_count']} registered tools")
    else:
        logger.warning("Registry file check: No registry file found")
    
    # Try sample tool calls
    call_results = try_sample_tool_calls()
    logger.info(f"Tool call check: {call_results['calls_succeeded']}/{call_results['calls_attempted']} sample calls succeeded")
    
    # Output overall results
    if direct_mcp_results["tools_available"] and direct_mcp_results["ipfs_tools_count"] > 0:
        logger.info(f"VERIFICATION SUCCESSFUL: Found {direct_mcp_results['ipfs_tools_count']} IPFS tools in MCP server")
        print(f"✅ IPFS tools verification successful - {direct_mcp_results['ipfs_tools_count']} tools available")
        
        # Show some tool categories
        categories = {}
        for tool_name, details in direct_mcp_results["verification_results"].items():
            category = details["type"]
            categories[category] = categories.get(category, 0) + 1
        
        for category, count in categories.items():
            print(f"  - {category}: {count} tools")
            
        return 0
    else:
        logger.warning("VERIFICATION FAILED: No IPFS tools found in MCP server")
        print("❌ IPFS tools verification failed - No tools available")
        return 1

if __name__ == "__main__":
    sys.exit(main())
