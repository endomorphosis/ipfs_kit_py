"""
Example demonstrating the usage of the optimized data routing system
in the ipfs_kit_py package.

This example shows how to initialize the routing system, select the
optimal backend for different content types, and use the routing
dashboard.
"""

import os
import anyio
import logging
from typing import Dict, Any, List
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("routing_example")

# Sample content types and files for demonstration
SAMPLE_CONTENT_TYPES = [
    "application/pdf", 
    "image/jpeg", 
    "video/mp4", 
    "text/plain",
    "application/json"
]

# Mock content data generators
def generate_mock_content(content_type: str, size_kb: int = 100) -> bytes:
    """Generate mock content of specified type and size."""
    # Create random content data
    return os.urandom(size_kb * 1024)

def generate_mock_metadata(content_type: str) -> Dict[str, Any]:
    """Generate mock metadata for content."""
    extensions = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "video/mp4": "mp4",
        "text/plain": "txt",
        "application/json": "json"
    }
    
    # Create filename
    extension = extensions.get(content_type, "bin")
    filename = f"sample-{random.randint(1000, 9999)}.{extension}"
    
    return {
        "content_type": content_type,
        "filename": filename,
        "created": "2025-04-15T20:00:00Z",
        "tags": ["sample", extension, "demo"]
    }

# Mock backend operations
class MockBackendManager:
    """Mock implementation of a backend manager for demonstration."""
    
    def __init__(self):
        """Initialize mock backend manager."""
        self.backends = [
            "ipfs", 
            "filecoin", 
            "s3", 
            "local"
        ]
        self.operations = []
    
    async def list_backends(self) -> List[str]:
        """List available backends."""
        return self.backends
    
    async def store(self, backend_id: str, content: bytes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store content in a backend."""
        # Simulate storage operation
        await anyio.sleep(0.1)
        content_id = f"{backend_id}:{random.randint(100000, 999999)}"
        
        # Record operation
        operation = {
            "type": "store",
            "backend_id": backend_id,
            "content_size": len(content),
            "metadata": metadata,
            "content_id": content_id,
            "success": True
        }
        self.operations.append(operation)
        
        logger.info(f"Stored content in {backend_id}: {content_id}")
        return {"content_id": content_id, "success": True}
    
    async def get_backend_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for each backend."""
        stats = {}
        for backend in self.backends:
            # Count operations for this backend
            backend_ops = [op for op in self.operations if op["backend_id"] == backend]
            total_size = sum(op["content_size"] for op in backend_ops)
            
            # Generate mock stats
            stats[backend] = {
                "operations": len(backend_ops),
                "total_size_bytes": total_size,
                "available_space_gb": random.randint(100, 1000),
                "latency_ms": random.randint(10, 500),
                "cost_per_gb": {
                    "ipfs": 0.0,
                    "filecoin": 0.00002,
                    "s3": 0.023,
                    "local": 0.0
                }.get(backend, 0.01)
            }
        
        return stats

async def run_routing_example():
    """Run the routing example."""
    try:
        from ipfs_kit_py.routing import (
            RoutingManager, 
            RoutingManagerSettings,
            RoutingStrategy,
            RoutingPriority
        )
        
        # Create mock backend manager
        backend_manager = MockBackendManager()
        
        # Initialize routing manager
        settings = RoutingManagerSettings(
            enabled=True,
            backends=await backend_manager.list_backends(),
            default_strategy="hybrid",
            default_priority="balanced",
            collect_metrics_on_startup=True,
            learning_enabled=True,
            optimization_weights={
                "network_quality": 0.25,
                "content_match": 0.2,
                "cost_efficiency": 0.2,
                "geographic_proximity": 0.15,
                "load_balancing": 0.05,
                "reliability": 0.1,
                "historical_success": 0.05
            }
        )
        
        # Create routing manager
        routing_manager = await RoutingManager.create(settings)
        logger.info(f"Initialized routing manager with backends: {settings.backends}")
        
        # Process different content types
        for content_type in SAMPLE_CONTENT_TYPES:
            # Generate content and metadata
            content = generate_mock_content(content_type, random.randint(10, 1000))
            metadata = generate_mock_metadata(content_type)
            
            logger.info(f"Processing {content_type} content: {metadata['filename']}")
            
            # Try different routing strategies
            for strategy_name in ["content_type", "cost", "performance", "hybrid"]:
                # Select backend using the current strategy
                backend_id = await routing_manager.select_backend(
                    content=content,
                    metadata=metadata,
                    strategy=strategy_name
                )
                
                logger.info(f"Strategy '{strategy_name}' selected backend: {backend_id}")
                
                # Store the content
                result = await backend_manager.store(backend_id, content, metadata)
                
                # Record the outcome for learning
                await routing_manager.record_routing_outcome(
                    backend_id=backend_id,
                    content_info={
                        "content_type": content_type,
                        "size_bytes": len(content)
                    },
                    success=result["success"]
                )
        
        # Get routing insights
        insights = await routing_manager.get_routing_insights()
        logger.info(f"Routing insights: {insights}")
        
        # Start dashboard (if requested)
        start_dashboard = input("Start the routing dashboard? (y/n): ").lower() == 'y'
        if start_dashboard:
            from ipfs_kit_py.routing.dashboard import run_dashboard
            
            logger.info("Starting routing dashboard. Press Ctrl+C to stop.")
            run_dashboard({
                "host": "127.0.0.1",
                "port": 8050,
                "theme": "darkly",
                "debug": True
            })
        
    except ImportError as e:
        logger.error(f"Error importing routing components: {e}")
    except Exception as e:
        logger.error(f"Error in routing example: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        anyio.run(run_routing_example)
    except KeyboardInterrupt:
        logger.info("Example stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)