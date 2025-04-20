"""
Apache Arrow IPC Example for Optimized Data Routing

This example demonstrates how to use the Apache Arrow IPC interface for 
optimized data routing, which provides a high-performance way to communicate
with the routing system from separate processes.

The example sets up both a server and client, demonstrating the separation
of concerns between core routing functionality and interaction methods.
"""

import os
import sys
import asyncio
import logging
import random
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("arrow_ipc_example")

# Sample content types for demonstration
SAMPLE_CONTENT_TYPES = [
    "application/pdf", 
    "image/jpeg", 
    "video/mp4", 
    "text/plain",
    "application/json"
]

# Mock content generators
def generate_mock_content_info(content_type: str) -> Dict[str, Any]:
    """Generate mock content information."""
    size_kb = random.randint(10, 1000)
    return {
        "content_type": content_type,
        "content_size": size_kb * 1024,
        "content_hash": f"hash-{random.randint(1000, 9999)}",
        "filename": f"sample-{random.randint(1000, 9999)}.{content_type.split('/')[-1]}",
        "metadata": {
            "created": "2025-04-15T20:00:00Z",
            "tags": ["sample", content_type.split('/')[-1], "demo"]
        }
    }

async def run_ipc_server():
    """Run the Apache Arrow IPC server for routing."""
    try:
        # Import necessary components
        from ipfs_kit_py.routing import RoutingManager, RoutingManagerSettings
        from ipfs_kit_py.routing.arrow_ipc import start_ipc_server
        
        # Initialize routing manager
        settings = RoutingManagerSettings(
            enabled=True,
            backends=["ipfs", "filecoin", "s3", "local"],
            default_strategy="hybrid",
            default_priority="balanced",
            collect_metrics_on_startup=True,
            learning_enabled=True
        )
        
        routing_manager = await RoutingManager.create(settings)
        logger.info(f"Initialized routing manager with backends: {settings.backends}")
        
        # Start IPC server
        socket_path = "/tmp/ipfs_kit_routing_example.sock"
        server = await start_ipc_server(socket_path, routing_manager)
        logger.info(f"Started Arrow IPC server on {socket_path}")
        
        # Keep server running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Server task cancelled")
        finally:
            # Cleanup
            await server.stop()
            logger.info("IPC server stopped")
            
    except ImportError as e:
        logger.error(f"Error importing routing components: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in IPC server: {e}", exc_info=True)
        sys.exit(1)

async def run_ipc_client():
    """Run the Apache Arrow IPC client for routing."""
    try:
        # Import necessary components
        from ipfs_kit_py.routing.arrow_ipc import ArrowIPCClient
        
        # Create client
        socket_path = "/tmp/ipfs_kit_routing_example.sock"
        client = ArrowIPCClient(socket_path)
        
        # Connect to server
        await client.connect()
        logger.info(f"Connected to Arrow IPC server on {socket_path}")
        
        # Process different content types
        for content_type in SAMPLE_CONTENT_TYPES:
            # Generate content info
            content_info = generate_mock_content_info(content_type)
            
            logger.info(f"Processing {content_type} content: {content_info['filename']}")
            
            # Try different routing strategies
            for strategy in ["content_type", "cost", "performance", "hybrid"]:
                # Select backend using the current strategy
                backend_id = await client.select_backend(
                    content_type=content_info["content_type"],
                    content_size=content_info["content_size"],
                    content_hash=content_info["content_hash"],
                    metadata=content_info["metadata"],
                    strategy=strategy
                )
                
                logger.info(f"Strategy '{strategy}' selected backend: {backend_id}")
                
                # Simulate storage operation
                success = random.random() > 0.1  # 90% success rate
                
                # Record the outcome
                await client.record_outcome(
                    backend_id=backend_id,
                    content_type=content_info["content_type"],
                    content_size=content_info["content_size"],
                    content_hash=content_info["content_hash"],
                    success=success,
                    duration_ms=random.randint(10, 500)
                )
                
                logger.info(f"Recorded outcome: success={success}")
        
        # Disconnect
        await client.disconnect()
        logger.info("Disconnected from IPC server")
        
    except ImportError as e:
        logger.error(f"Error importing routing components: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in IPC client: {e}", exc_info=True)
        sys.exit(1)

async def run_example():
    """Run the complete Arrow IPC example."""
    # Start server in background task
    server_task = asyncio.create_task(run_ipc_server())
    
    # Wait for server to start
    await asyncio.sleep(2)
    
    try:
        # Run client
        await run_ipc_client()
    finally:
        # Stop server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        logger.info("Example stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)