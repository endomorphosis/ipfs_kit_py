"""
gRPC Routing Client Example

This example demonstrates how to use the gRPC client for optimized data routing,
enabling high-performance, language-independent access to routing functionality.

This example covers:
1. Starting a gRPC routing server
2. Connecting a gRPC client
3. Performing routing operations (select_backend, record_outcome)
4. Getting routing insights
5. Streaming metrics updates
"""

import os
import sys
import json
import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("grpc_routing_example")

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

async def run_server():
    """Run a gRPC server instance for routing."""
    try:
        # Import gRPC server
        from ipfs_kit_py.routing.grpc_server import run_server
        
        # Start server
        port = 50051
        address = "127.0.0.1"
        server = await run_server(
            host=address,
            port=port,
            max_workers=10
        )
        
        logger.info(f"Started gRPC server on {address}:{port}")
        return server
        
    except ImportError as e:
        logger.error(f"Error importing gRPC server: {e}")
        logger.error("Make sure to install gRPC dependencies: pip install grpcio grpcio-tools")
        logger.error("And generate gRPC code: python bin/generate_grpc_code.py")
        return None
    except Exception as e:
        logger.error(f"Error starting gRPC server: {e}", exc_info=True)
        return None

async def run_client_example():
    """Run the gRPC client example."""
    try:
        # Import gRPC client
        from ipfs_kit_py.routing.grpc_client import create_client
        
        # Create client
        client = await create_client(
            host="127.0.0.1",
            port=50051,
            timeout=10.0
        )
        
        logger.info("Connected to gRPC routing server")
        
        # Process different content types
        for content_type in SAMPLE_CONTENT_TYPES:
            # Generate test content info
            content_info = generate_mock_content_info(content_type)
            
            logger.info(f"Processing {content_type} content: {content_info['filename']}")
            
            # Try different routing strategies
            for strategy in ["content_type", "cost", "performance", "hybrid"]:
                # Select backend for content
                backend_result = await client.select_backend(
                    content_type=content_info["content_type"],
                    content_size=content_info["content_size"],
                    content_hash=content_info["content_hash"],
                    metadata=content_info["metadata"],
                    strategy=strategy
                )
                
                backend_id = backend_result["backend_id"]
                logger.info(f"Strategy '{strategy}' selected backend: {backend_id} with score {backend_result['score']:.2f}")
                
                # Simulate content operation (success 80% of the time)
                success = random.random() < 0.8
                
                # Record outcome
                outcome_result = await client.record_outcome(
                    backend_id=backend_id,
                    success=success,
                    content_type=content_info["content_type"],
                    content_size=content_info["content_size"],
                    content_hash=content_info["content_hash"],
                    duration_ms=random.randint(10, 500)
                )
                
                logger.info(f"Recorded outcome: {outcome_result['message']}")
        
        # Get routing insights
        insights = await client.get_insights()
        logger.info("Routing Insights:")
        logger.info(f"  Factor weights: {insights['factor_weights']}")
        logger.info(f"  Backend scores: {insights['backend_scores']}")
        
        # Define metrics callback
        def metrics_callback(update):
            status_str = "NORMAL"
            if update["status"] == 1:
                status_str = "WARNING"
            elif update["status"] == 2:
                status_str = "CRITICAL"
                
            logger.info(f"Metrics update ({status_str}) at {update['timestamp']}:")
            for metric_type, value in update["metrics"].items():
                if isinstance(value, dict) and len(value) <= 5:  # Show only if dict is small
                    logger.info(f"  {metric_type}: {value}")
                else:
                    logger.info(f"  {metric_type}: (data available)")
        
        # Stream metrics for a short time
        logger.info("Starting metrics streaming (5 seconds)...")
        await client.start_metrics_streaming(
            callback=metrics_callback,
            update_interval_seconds=1,
            include_backends=True
        )
        
        # Wait for a few updates
        await asyncio.sleep(5)
        
        # Stop metrics streaming
        await client.stop_metrics_streaming()
        logger.info("Stopped metrics streaming")
        
        # Disconnect client
        await client.disconnect()
        logger.info("Disconnected from routing gRPC server")
        
    except ImportError as e:
        logger.error(f"Error importing gRPC client: {e}")
        logger.error("Make sure to install gRPC dependencies: pip install grpcio grpcio-tools")
        logger.error("And generate gRPC code: python bin/generate_grpc_code.py")
    except Exception as e:
        logger.error(f"Error in client example: {e}", exc_info=True)

async def run_example():
    """Run the complete gRPC routing example."""
    # Start server in background
    server = await run_server()
    if not server:
        return
    
    try:
        # Wait for server to initialize
        await asyncio.sleep(1)
        
        # Run client example
        await run_client_example()
        
    finally:
        # Stop server
        await server.stop()
        logger.info("Stopped gRPC server")

if __name__ == "__main__":
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        logger.info("Example stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)