#!/usr/bin/env python
"""
Run MCP server with storage backend integration enabled.

This script initializes and runs the MCP server with all storage backends (S3, Hugging Face, Storacha)
enabled for testing and development.
"""

import logging
import argparse
import uvicorn
from fastapi import FastAPI

from ipfs_kit_py.mcp.server import MCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("run_mcp_with_storage")

def main():
    """Initialize and run the MCP server with storage backends."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run MCP Server with Storage Backends")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=10000, help="Port to run on")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--persistence-path", default=None, help="Path for persistence files")
    parser.add_argument("--api-prefix", default="/api/v0/mcp", help="API endpoint prefix")
    parser.add_argument("--simulation-mode", action="store_true", help="Enable simulation mode for all components")
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server with Storage Backends",
        description="MCP Server with integrated storage backends (S3, Hugging Face, Storacha)",
        version="0.1.0"
    )
    
    # Create MCP server with storage backends
    logger.info("Initializing MCP server with storage backends...")
    
    # Instead of directly modifying MCPServer, we'll monkey patch it to inject our S3 credentials during initialization
    original_init_components = MCPServer._init_components
    
    def patched_init_components(self):
        # Create dummy S3 credentials for testing
        # Note: These are fake credentials, only for testing the status endpoint
        s3_test_config = {
            "accessKey": "test_access_key",
            "secretKey": "test_secret_key",
            "endpoint": "https://test-s3-endpoint.example.com"
        }
        
        # Call the original method
        original_init_components(self)
        
        # Add S3 config to the metadata after IPFS Kit is initialized
        if hasattr(self, 'ipfs_kit') and hasattr(self.ipfs_kit, 'metadata'):
            self.ipfs_kit.metadata["s3_config"] = s3_test_config
            logger.info("Added S3 test configuration to IPFS Kit metadata")
            
        # If S3 model is not available, create a simulated one
        if "s3" not in self.storage_manager.storage_models:
            from ipfs_kit_py.mcp.models.storage.s3_model import S3Model
            from unittest.mock import MagicMock
            
            # Create a mock S3 kit
            mock_s3_kit = MagicMock()
            
            # Create custom get_stats method
            def mock_get_stats():
                return {
                    "operation_stats": {
                        "upload_count": 0,
                        "download_count": 0,
                        "list_count": 0,
                        "delete_count": 0,
                        "total_operations": 0,
                        "success_count": 0,
                        "failure_count": 0,
                        "bytes_uploaded": 0,
                        "bytes_downloaded": 0
                    },
                    "timestamp": time.time()
                }
            
            # Add get_stats method to mock S3 kit
            mock_s3_kit.get_stats = mock_get_stats
            
            # Create a simulated S3 model
            s3_model = S3Model(
                s3_kit_instance=mock_s3_kit,
                ipfs_model=self.models["ipfs"],
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            
            # Register the simulated S3 model
            self.storage_manager.storage_models["s3"] = s3_model
            self.models["storage_s3"] = s3_model
            logger.info("Created simulated S3 model for testing")
            
            # Create and register the S3 controller
            from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
            s3_controller = S3Controller(s3_model)
            self.controllers["storage_s3"] = s3_controller
            logger.info("Created S3 controller for simulated model")
            
            # Register the S3 controller routes
            s3_controller.register_routes(self._create_router())
    
    # Apply the monkey patch
    MCPServer._init_components = patched_init_components
    
    # Create the MCP server
    # Add simulation_mode to the config if enabled
    config = {"simulation_mode": args.simulation_mode} if args.simulation_mode else {}
    logger.info(f"Creating MCP server with simulation_mode={args.simulation_mode}")
    
    mcp_server = MCPServer(
        debug_mode=args.debug,
        log_level=args.log_level,
        persistence_path=args.persistence_path,
        isolation_mode=args.isolation,
        config=config
    )
    
    # Restore the original method
    MCPServer._init_components = original_init_components
    
    # Register MCP server with FastAPI app
    mcp_server.register_with_app(app, prefix=args.api_prefix)
    
    # Log available backends
    try:
        available_backends = mcp_server.storage_manager.get_available_backends()
        logger.info("Available storage backends:")
        for backend, available in available_backends.items():
            status = "Available" if available else "Not available"
            logger.info(f"  - {backend}: {status}")
    except Exception as e:
        logger.error(f"Error retrieving available backends: {e}")
    
    # Start the server
    logger.info(f"Starting MCP server with storage backends at http://{args.host}:{args.port}{args.api_prefix}")
    logger.info(f"Debug mode: {args.debug}, Isolation mode: {args.isolation}")
    
    # Start Uvicorn server
    uvicorn.run(app, host=args.host, port=args.port)
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down MCP server...")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}", exc_info=True)