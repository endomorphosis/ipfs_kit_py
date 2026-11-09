#!/usr/bin/env python3
"""
Test script to verify that the MCP Server can be started with the WebRTC controller AnyIO version
and test basic WebRTC operations through the AnyIO controller.
"""

import logging
import os
import json
import time
import anyio
import anyio
from fastapi import FastAPI
from ipfs_kit_py.mcp.server_anyio import MCPServer
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample CID for testing (a small file)
TEST_CID = "QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB"  # IPFS Hello World file

# Model for WebRTC stream request (matching the controller's model)
class StreamRequest(BaseModel):
    cid: str
    address: str = "127.0.0.1"
    port: int = 8889
    quality: str = "medium"
    ice_servers: Optional[List[Dict[str, Any]]] = None
    benchmark: bool = False
    buffer_size: Optional[int] = None
    prefetch_threshold: Optional[float] = None
    use_progressive_loading: bool = True

async def run_test():
    """Run the test to verify WebRTC controller integration and operations."""
    logger.info("Starting MCP Server with WebRTC controller AnyIO test")
    
    # Create FastAPI app
    app = FastAPI(title="IPFS MCP Server Test")
    
    # Create MCP server with debug mode
    mcp_server = MCPServer(
        debug_mode=True,
        log_level="INFO",
        isolation_mode=True  # Use isolation mode to avoid affecting system
    )
    
    # Register MCP server with app
    mcp_server.register_with_app(app, prefix="/api/v0/mcp")
    
    # Track test status
    test_results = {
        "webrtc_controller_loaded": False,
        "is_anyio_compatible": False,
        "operations_tested": {},
        "errors": []
    }
    
    try:
        # STEP 1: Verify the WebRTC controller is loaded
        if "webrtc" in mcp_server.controllers:
            controller = mcp_server.controllers["webrtc"]
            test_results["webrtc_controller_loaded"] = True
            logger.info(f"WebRTC controller loaded: {type(controller).__name__}")
            
            # Check if it's the AnyIO version
            if hasattr(controller, 'shutdown') and hasattr(controller.shutdown, '__await__'):
                test_results["is_anyio_compatible"] = True
                logger.info("✅ WebRTC controller is AnyIO-compatible (has async shutdown method)")
            else:
                logger.error("❌ WebRTC controller is NOT AnyIO-compatible")
                test_results["errors"].append("WebRTC controller is not AnyIO-compatible")
        else:
            logger.error("❌ WebRTC controller not loaded")
            test_results["errors"].append("WebRTC controller not loaded")
            raise RuntimeError("WebRTC controller not loaded, cannot continue tests")
        
        # If we've confirmed the WebRTC controller is loaded and AnyIO-compatible, test operations
        if test_results["webrtc_controller_loaded"] and test_results["is_anyio_compatible"]:
            logger.info("Testing WebRTC controller operations...")
            
            # STEP 2: Check dependencies
            try:
                logger.info("Checking WebRTC dependencies...")
                deps_response = await controller.check_dependencies()
                
                test_results["operations_tested"]["check_dependencies"] = {
                    "success": deps_response.get("success", False),
                    "available": deps_response.get("available", False)
                }
                
                if deps_response.get("available", False):
                    logger.info("✅ WebRTC dependencies available")
                else:
                    logger.warning("⚠️ WebRTC dependencies not available, skipping streaming tests")
                    test_results["errors"].append("WebRTC dependencies not available")
            except Exception as e:
                logger.error(f"❌ Error checking WebRTC dependencies: {e}")
                test_results["operations_tested"]["check_dependencies"] = {
                    "success": False,
                    "error": str(e)
                }
                test_results["errors"].append(f"Dependencies check error: {str(e)}")
            
            # STEP 3: Get resource stats (should work even without WebRTC dependencies)
            try:
                logger.info("Getting WebRTC resource stats...")
                stats_response = await controller.get_resources_endpoint()
                
                test_results["operations_tested"]["get_resources"] = {
                    "success": stats_response.get("success", False),
                    "server_count": stats_response.get("servers", {}).get("count", 0),
                    "connection_count": stats_response.get("connections", {}).get("count", 0)
                }
                
                logger.info(f"✅ Resource stats: {stats_response.get('servers', {}).get('count', 0)} servers, "
                           f"{stats_response.get('connections', {}).get('count', 0)} connections")
            except Exception as e:
                logger.error(f"❌ Error getting resource stats: {e}")
                test_results["operations_tested"]["get_resources"] = {
                    "success": False,
                    "error": str(e)
                }
                test_results["errors"].append(f"Resource stats error: {str(e)}")
            
            # STEP 4: Try streaming content if WebRTC dependencies are available
            if deps_response.get("available", False):
                try:
                    logger.info(f"Starting WebRTC stream for CID: {TEST_CID}...")
                    stream_request = StreamRequest(
                        cid=TEST_CID,
                        address="127.0.0.1",
                        port=8889,
                        quality="low",  # Use low quality for faster testing
                        benchmark=False,
                        use_progressive_loading=True
                    )
                    
                    stream_response = await controller.stream_content(stream_request)
                    
                    test_results["operations_tested"]["stream_content"] = {
                        "success": stream_response.get("success", False),
                        "server_id": stream_response.get("server_id"),
                        "url": stream_response.get("url")
                    }
                    
                    if stream_response.get("success", False):
                        logger.info(f"✅ Streaming started for {TEST_CID}: {stream_response.get('url')}")
                        server_id = stream_response.get("server_id")
                        
                        # STEP 5: List connections (there shouldn't be any yet, but test the API)
                        try:
                            logger.info("Listing WebRTC connections...")
                            connections_response = await controller.list_connections()
                            
                            test_results["operations_tested"]["list_connections"] = {
                                "success": connections_response.get("success", False),
                                "count": len(connections_response.get("connections", []))
                            }
                            
                            logger.info(f"✅ Listed {len(connections_response.get('connections', []))} connections")
                        except Exception as e:
                            logger.error(f"❌ Error listing connections: {e}")
                            test_results["operations_tested"]["list_connections"] = {
                                "success": False,
                                "error": str(e)
                            }
                            test_results["errors"].append(f"List connections error: {str(e)}")
                        
                        # STEP 6: Stop streaming
                        try:
                            logger.info(f"Stopping WebRTC stream {server_id}...")
                            stop_response = await controller.stop_streaming(server_id)
                            
                            test_results["operations_tested"]["stop_streaming"] = {
                                "success": stop_response.get("success", False)
                            }
                            
                            if stop_response.get("success", False):
                                logger.info(f"✅ Stream {server_id} stopped successfully")
                            else:
                                logger.error(f"❌ Failed to stop stream: {stop_response.get('error')}")
                                test_results["errors"].append(f"Stop streaming error: {stop_response.get('error')}")
                        except Exception as e:
                            logger.error(f"❌ Error stopping stream: {e}")
                            test_results["operations_tested"]["stop_streaming"] = {
                                "success": False,
                                "error": str(e)
                            }
                            test_results["errors"].append(f"Stop streaming error: {str(e)}")
                    else:
                        logger.error(f"❌ Failed to start streaming: {stream_response.get('error')}")
                        test_results["errors"].append(f"Stream content error: {stream_response.get('error')}")
                except Exception as e:
                    logger.error(f"❌ Error starting stream: {e}")
                    test_results["operations_tested"]["stream_content"] = {
                        "success": False,
                        "error": str(e)
                    }
                    test_results["errors"].append(f"Stream content error: {str(e)}")
            
            # STEP 7: Test close_all_connections
            try:
                logger.info("Testing close_all_connections...")
                close_all_response = await controller.close_all_connections()
                
                test_results["operations_tested"]["close_all_connections"] = {
                    "success": close_all_response.get("success", False)
                }
                
                if close_all_response.get("success", False):
                    logger.info("✅ All connections closed successfully")
                else:
                    logger.error(f"❌ Failed to close all connections: {close_all_response.get('error')}")
                    test_results["errors"].append(f"Close all connections error: {close_all_response.get('error')}")
            except Exception as e:
                logger.error(f"❌ Error closing all connections: {e}")
                test_results["operations_tested"]["close_all_connections"] = {
                    "success": False,
                    "error": str(e)
                }
                test_results["errors"].append(f"Close all connections error: {str(e)}")
    except Exception as e:
        logger.error(f"Test error: {e}")
        test_results["errors"].append(f"General test error: {str(e)}")
    finally:
        # STEP 8: Cleanup - test the async shutdown method
        try:
            logger.info("Testing async shutdown method...")
            shutdown_start = time.time()
            await mcp_server.shutdown()
            shutdown_duration = time.time() - shutdown_start
            
            test_results["operations_tested"]["async_shutdown"] = {
                "success": True,
                "duration_seconds": shutdown_duration
            }
            
            logger.info(f"✅ Server shutdown completed in {shutdown_duration:.2f} seconds")
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
            test_results["operations_tested"]["async_shutdown"] = {
                "success": False,
                "error": str(e)
            }
            test_results["errors"].append(f"Shutdown error: {str(e)}")
    
    # Display test summary
    logger.info("\n" + "="*50)
    logger.info("WebRTC AnyIO Controller Test Summary:")
    logger.info(f"- WebRTC Controller Loaded: {test_results['webrtc_controller_loaded']}")
    logger.info(f"- AnyIO Compatible: {test_results['is_anyio_compatible']}")
    logger.info(f"- Operations Tested: {len(test_results['operations_tested'])}")
    logger.info(f"- Errors: {len(test_results['errors'])}")
    
    # Log details of operations
    logger.info("\nOperations Results:")
    for op_name, op_result in test_results['operations_tested'].items():
        success = op_result.get('success', False)
        status = "✅ Success" if success else "❌ Failed"
        logger.info(f"- {op_name}: {status}")
    
    # Log errors if any
    if test_results['errors']:
        logger.info("\nErrors:")
        for i, error in enumerate(test_results['errors'], 1):
            logger.info(f"{i}. {error}")
    
    logger.info("="*50)
    
    # Save test results to file
    with open("webrtc_anyio_test_results.json", "w") as f:
        json.dump(test_results, f, indent=2)
    
    logger.info(f"Test results saved to webrtc_anyio_test_results.json")
    return test_results
    
if __name__ == "__main__":
    # Run the test with AnyIO
    anyio.run(run_test, backend=("async" "io"))