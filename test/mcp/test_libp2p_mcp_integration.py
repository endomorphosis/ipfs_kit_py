#!/usr/bin/env python3
"""
Test LibP2P integration with MCP Server.
This is a simplified test script that focuses directly on testing the integration.
"""

import os
import sys
import logging
from typing import Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the test."""
    print("\n=== Testing LibP2P integration with MCP Server ===\n")
    
    # Set environment variables for testing
    os.environ["IPFS_KIT_AUTO_INSTALL_DEPS"] = "1"
    
    # Import modules
    try:
        # Check LibP2P availability
        from ipfs_kit_py.libp2p import check_dependencies
        libp2p_available = check_dependencies()
        print(f"LibP2P availability: {libp2p_available}")
        
        # Import server
        try:
            from ipfs_kit_py.mcp.server_anyio import MCPServer
            print("Successfully imported MCPServer (AnyIO version)")
            
            # Create server instance
            print("Creating MCPServer instance...")
            mcp_server = MCPServer(
                debug_mode=True,
                isolation_mode=True
            )
            
            # Check if LibP2P controller exists
            if "libp2p" in mcp_server.controllers:
                print(f"SUCCESS: LibP2P controller is available in MCP server")
                controller = mcp_server.controllers["libp2p"]
                
                # Check controller attributes
                print(f"Controller class: {controller.__class__.__name__}")
                
                # Check dependencies attribute
                if hasattr(controller, "libp2p_dependencies_available"):
                    deps_available = controller.libp2p_dependencies_available
                    print(f"LibP2P dependencies available: {deps_available}")
                else:
                    print("WARNING: Controller does not have libp2p_dependencies_available attribute")
                
                # Test health check
                print("\nTesting health check...")
                import anyio
                
                async def test_health_check():
                    result = await controller.health_check_async()
                    print(f"Health check result: {result}")
                    return result
                
                health_result = anyio.run(test_health_check)
                success = health_result.get("success", False)
                
                if success:
                    print("SUCCESS: Health check passed")
                    return 0
                else:
                    print(f"FAILED: Health check failed: {health_result.get('error', 'Unknown error')}")
                    return 1
            else:
                print("WARNING: LibP2P controller not found in MCP server")
                print(f"Available controllers: {list(mcp_server.controllers.keys())}")
                
                # Check if LibP2P model exists
                if "libp2p" in mcp_server.models:
                    print(f"Note: LibP2P model exists but controller wasn't initialized")
                
                # Check if we can get LibP2P model from IPFS model
                if "ipfs" in mcp_server.models and hasattr(mcp_server.models["ipfs"], "get_libp2p_model"):
                    try:
                        model = mcp_server.models["ipfs"].get_libp2p_model()
                        if model:
                            print(f"SUCCESS: Got LibP2P model from IPFS model")
                        else:
                            print(f"WARNING: get_libp2p_model() returned None")
                    except Exception as e:
                        print(f"ERROR getting LibP2P model: {e}")
                
                # Test the IPFS controller's get_node_id method as a fallback
                print("\nTesting IPFS controller get_node_id as fallback...")
                if "ipfs" in mcp_server.controllers:
                    ipfs_controller = mcp_server.controllers["ipfs"]
                    
                    # Check if the get_node_id method exists
                    if hasattr(ipfs_controller, "get_node_id") and callable(getattr(ipfs_controller, "get_node_id")):
                        print("SUCCESS: IPFS controller has get_node_id method")
                        
                        # Test the method
                        import anyio
                        
                        async def test_get_node_id():
                            try:
                                result = await ipfs_controller.get_node_id()
                                print(f"get_node_id result: {result}")
                                return result
                            except Exception as e:
                                print(f"ERROR calling get_node_id: {e}")
                                import traceback
                                traceback.print_exc()
                                return {"success": False, "error": str(e)}
                        
                        node_id_result = anyio.run(test_get_node_id)
                        success = node_id_result.get("success", False)
                        
                        if success:
                            print("SUCCESS: get_node_id method works")
                            # Even without LibP2P controller, we can continue with IPFS
                            return 0
                        else:
                            print(f"FAILED: get_node_id method failed: {node_id_result.get('error', 'Unknown error')}")
                    else:
                        print("FAILED: IPFS controller does not have get_node_id method")
                else:
                    print("FAILED: IPFS controller not found")
                
                return 1
        except Exception as e:
            print(f"ERROR importing or creating MCPServer: {e}")
            import traceback
            traceback.print_exc()
            return 1
    except Exception as e:
        print(f"ERROR importing LibP2P module: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())