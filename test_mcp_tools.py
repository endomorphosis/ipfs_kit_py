#!/usr/bin/env python3
"""
MCP Tools Test Script

This script tests the IPFS model extensions and MCP server tools
to ensure they are working correctly.
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_tools_test")

def test_ipfs_model_extensions():
    """
    Test IPFS model extensions directly.
    
    This function imports and initializes the IPFS model with extensions,
    then tests each of the model methods to ensure they work correctly.
    
    Returns:
        bool: Whether all tests passed
    """
    logger.info("Testing IPFS model extensions...")
    
    try:
        # Import and initialize the IPFS model
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
        
        # Initialize the IPFS model extensions
        if not initialize_ipfs_model():
            logger.error("Failed to initialize IPFS model extensions")
            return False
        
        # Create an instance of IPFSModel
        ipfs_model = IPFSModel()
        logger.info("Created IPFSModel instance")
        
        # Test add_content method
        test_content = "This is a test content for MCP tools"
        add_result = ipfs_model.add_content(test_content)
        if not add_result.get("success", False):
            logger.error(f"Failed to add content: {add_result.get('error', 'Unknown error')}")
            return False
        
        test_cid = add_result.get("cid")
        logger.info(f"Successfully added content with CID: {test_cid}")
        
        # Test cat method
        if hasattr(ipfs_model, "cat"):
            cat_result = ipfs_model.cat(test_cid)
            if not cat_result.get("success", False):
                logger.error(f"Failed to retrieve content: {cat_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"Successfully retrieved content for CID: {test_cid}")
        else:
            logger.warning("IPFSModel does not have cat method")
        
        # Test pin_add method
        if hasattr(ipfs_model, "pin_add"):
            pin_result = ipfs_model.pin_add(test_cid)
            if not pin_result.get("success", False):
                logger.error(f"Failed to pin content: {pin_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"Successfully pinned content for CID: {test_cid}")
        else:
            logger.warning("IPFSModel does not have pin_add method")
        
        # Test pin_ls method
        if hasattr(ipfs_model, "pin_ls"):
            pins_result = ipfs_model.pin_ls()
            if not pins_result.get("success", False):
                logger.error(f"Failed to list pins: {pins_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"Successfully listed pins: {pins_result.get('count', 0)} pins found")
        else:
            logger.warning("IPFSModel does not have pin_ls method")
        
        # Test swarm_peers method
        if hasattr(ipfs_model, "swarm_peers"):
            peers_result = ipfs_model.swarm_peers()
            if not peers_result.get("success", False):
                logger.error(f"Failed to list peers: {peers_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"Successfully listed peers: {peers_result.get('peer_count', 0)} peers found")
        else:
            logger.warning("IPFSModel does not have swarm_peers method")
        
        # Test get_version method
        if hasattr(ipfs_model, "get_version"):
            version_result = ipfs_model.get_version()
            if not version_result.get("success", False):
                logger.error(f"Failed to get version: {version_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"Successfully got version information")
        else:
            logger.warning("IPFSModel does not have get_version method")
        
        logger.info("All IPFS model extension tests completed successfully")
        return True
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    except Exception as e:
        logger.error(f"Error testing IPFS model extensions: {e}")
        return False

def test_mcp_server_api(base_url: str = "http://localhost:9994/api/v0"):
    """
    Test MCP server API endpoints.
    
    This function tests the MCP server API endpoints to ensure they work correctly.
    
    Args:
        base_url: Base URL of the MCP server API
        
    Returns:
        bool: Whether all tests passed
    """
    logger.info(f"Testing MCP server API at {base_url}...")
    
    try:
        # Test health endpoint
        try:
            health_url = f"{base_url}/health"
            health_response = requests.get(health_url)
            health_response.raise_for_status()
            logger.info(f"Health endpoint responded with status {health_response.status_code}")
        except Exception as e:
            logger.error(f"Health endpoint failed: {e}")
            return False
        
        # Test add content endpoint
        try:
            add_url = f"{base_url}/ipfs/add"
            test_content = "This is a test content for MCP API"
            add_response = requests.post(
                add_url,
                json={"content": test_content}
            )
            add_response.raise_for_status()
            add_result = add_response.json()
            
            test_cid = add_result.get("cid")
            logger.info(f"Successfully added content with CID: {test_cid}")
        except Exception as e:
            logger.error(f"Add content endpoint failed: {e}")
            return False
        
        # Test cat endpoint
        try:
            cat_url = f"{base_url}/ipfs/cat/{test_cid}"
            cat_response = requests.get(cat_url)
            cat_response.raise_for_status()
            logger.info(f"Successfully retrieved content for CID: {test_cid}")
        except Exception as e:
            logger.error(f"Cat endpoint failed: {e}")
            return False
        
        # Test pin endpoint
        try:
            pin_url = f"{base_url}/ipfs/pin"
            pin_response = requests.post(
                pin_url,
                json={"cid": test_cid}
            )
            pin_response.raise_for_status()
            logger.info(f"Successfully pinned content for CID: {test_cid}")
        except Exception as e:
            logger.error(f"Pin endpoint failed: {e}")
            return False
        
        # Test pins endpoint
        try:
            pins_url = f"{base_url}/ipfs/pins"
            pins_response = requests.get(pins_url)
            pins_response.raise_for_status()
            pins_result = pins_response.json()
            logger.info(f"Successfully listed pins: {pins_result.get('count', 0)} pins found")
        except Exception as e:
            logger.error(f"Pins endpoint failed: {e}")
            return False
        
        # Test swarm peers endpoint
        try:
            peers_url = f"{base_url}/ipfs/swarm/peers"
            peers_response = requests.get(peers_url)
            peers_response.raise_for_status()
            peers_result = peers_response.json()
            logger.info(f"Successfully listed peers: {peers_result.get('peer_count', 0)} peers found")
        except Exception as e:
            logger.error(f"Swarm peers endpoint failed: {e}")
            return False
        
        # Test version endpoint
        try:
            version_url = f"{base_url}/ipfs/version"
            version_response = requests.get(version_url)
            version_response.raise_for_status()
            logger.info(f"Successfully got version information")
        except Exception as e:
            logger.error(f"Version endpoint failed: {e}")
            return False
        
        logger.info("All MCP server API tests completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error testing MCP server API: {e}")
        return False

def test_mcp_cline_integration():
    """
    Test Cline MCP integration.
    
    This function tests the Cline MCP integration to ensure it works correctly.
    
    Returns:
        bool: Whether all tests passed
    """
    logger.info("Testing Cline MCP integration...")
    
    try:
        # Check if the MCP settings file exists
        settings_path = os.path.expanduser("~/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
        if not os.path.exists(settings_path):
            logger.warning(f"MCP settings file not found: {settings_path}")
            return False
        
        # Read the settings file
        with open(settings_path, "r") as f:
            settings = json.load(f)
        
        # Check if the settings file has the required structure
        if "mcpServers" not in settings:
            logger.warning("MCP settings file missing mcpServers key")
            return False
        
        # Check if at least one server is defined
        if not settings["mcpServers"]:
            logger.warning("MCP settings file has no servers defined")
            return False
        
        # Check if the server has the required tools
        server = settings["mcpServers"][0]
        if "tools" not in server:
            logger.warning("MCP server missing tools key")
            return False
        
        # Check if all required tools are defined
        required_tools = ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"]
        for tool_name in required_tools:
            tool_found = False
            for tool in server["tools"]:
                if tool.get("name") == tool_name:
                    tool_found = True
                    break
            
            if not tool_found:
                logger.warning(f"MCP server missing required tool: {tool_name}")
                return False
        
        logger.info("Cline MCP integration verified successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error testing Cline MCP integration: {e}")
        return False

def main():
    """
    Main function to run all tests.
    """
    logger.info("Starting MCP tools tests...")
    
    all_tests_passed = True
    
    # Test IPFS model extensions
    if test_ipfs_model_extensions():
        logger.info("IPFS model extensions tests passed")
    else:
        logger.warning("IPFS model extensions tests failed")
        all_tests_passed = False
    
    # Check if an MCP server is running
    logger.info("Checking if MCP server is running...")
    server_running = False
    mcp_port = os.environ.get("MCP_PORT", "9994")
    api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0")
    base_url = f"http://localhost:{mcp_port}{api_prefix}"
    
    try:
        health_url = f"{base_url}/health"
        health_response = requests.get(health_url, timeout=3)
        health_response.raise_for_status()
        server_running = True
    except:
        logger.warning("MCP server does not appear to be running")
    
    # Test MCP server API if server is running
    if server_running:
        if test_mcp_server_api(base_url):
            logger.info("MCP server API tests passed")
        else:
            logger.warning("MCP server API tests failed")
            all_tests_passed = False
    else:
        logger.warning("Skipping MCP server API tests as server is not running")
    
    # Test Cline MCP integration
    if test_mcp_cline_integration():
        logger.info("Cline MCP integration tests passed")
    else:
        logger.warning("Cline MCP integration tests failed")
        all_tests_passed = False
    
    # Print summary
    if all_tests_passed:
        logger.info("All tests passed! MCP tools are working properly")
    else:
        logger.warning("Some tests failed. Check the logs for details")
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
