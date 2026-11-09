"""
Example script demonstrating how to use the Optimized Data Routing system.

This example shows:
1. Setting up the routing system
2. Using it to select optimal backends for different content types
3. Recording routing outcomes to improve future decisions
4. Accessing routing insights and metrics
"""

import os
import sys
import anyio
import json
from typing import Dict, Any, List

# Add the parent directory to the path so we can import the packages
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required components
from ipfs_kit_py.mcp.routing.routing_manager import (
    RoutingManagerSettings, 
    RoutingManager,
    initialize_routing_manager
)
from ipfs_kit_py.mcp.optimized_routing import RoutingIntegration
from fastapi import FastAPI

# Create sample content for testing
def create_sample_content():
    """Create sample content of different types for testing."""
    return {
        "document": {
            "content": b"This is a sample document content." * 100,
            "metadata": {
                "content_type": "application/pdf",
                "filename": "sample.pdf"
            }
        },
        "image": {
            "content": os.urandom(1024 * 200),  # 200KB random data
            "metadata": {
                "content_type": "image/jpeg",
                "filename": "sample.jpg"
            }
        },
        "video": {
            "content": os.urandom(1024 * 1024),  # 1MB random data
            "metadata": {
                "content_type": "video/mp4",
                "filename": "sample.mp4"
            }
        },
        "code": {
            "content": b"function helloWorld() { return 'Hello, World!'; }" * 20,
            "metadata": {
                "content_type": "text/javascript",
                "filename": "sample.js"
            }
        }
    }

class MockBackendManager:
    """Mock backend manager for testing."""
    
    def __init__(self):
        """Initialize with sample backends."""
        self.backends = ["ipfs", "filecoin", "s3", "storacha", "huggingface"]
        self.storage = {}
    
    async def list_backends(self):
        """Return list of available backends."""
        return self.backends
    
    async def store(self, backend_id, content, metadata=None):
        """Store content in a backend."""
        content_id = f"{hash(content)}"
        if backend_id not in self.storage:
            self.storage[backend_id] = {}
        
        self.storage[backend_id][content_id] = {
            "content": content,
            "metadata": metadata or {}
        }
        
        print(f"Stored content in {backend_id} with ID: {content_id}")
        
        # Simulate success/failure based on backend and content size
        success = True
        if backend_id == "ipfs" and len(content) > 1024 * 500:
            # Simulate IPFS having issues with large content
            success = False
        
        return MockResult(
            success=success,
            content_id=content_id,
            backend_id=backend_id
        )
    
    async def retrieve(self, backend_id, content_id):
        """Retrieve content from a backend."""
        if backend_id not in self.storage or content_id not in self.storage[backend_id]:
            return MockResult(success=False, error="Content not found")
        
        return MockResult(
            success=True,
            content=self.storage[backend_id][content_id]["content"],
            metadata=self.storage[backend_id][content_id]["metadata"]
        )

class MockResult:
    """Mock result for backend operations."""
    
    def __init__(self, success=True, content_id=None, content=None, metadata=None, backend_id=None, error=None):
        """Initialize with result data."""
        self.success = success
        self.content_id = content_id
        self.content = content
        self.metadata = metadata
        self.backend_id = backend_id
        self.error = error

async def setup_routing():
    """Set up the routing system."""
    # Create a FastAPI app for the integration
    app = FastAPI()
    
    # Create a mock backend manager
    backend_manager = MockBackendManager()
    
    # Create routing integration
    routing_integration = RoutingIntegration(
        app=app,
        config={
            "routing_enabled": True,
            "routing_strategy": "hybrid",
            "collect_metrics_on_startup": True,
            "learning_enabled": True
        },
        storage_backend_manager=backend_manager
    )
    
    # Initialize the routing integration
    await routing_integration.initialize()
    
    return routing_integration, backend_manager

async def demo_routing():
    """Demonstrate optimized routing functionality."""
    print("Setting up optimized routing system...")
    routing_integration, backend_manager = await setup_routing()
    
    print("\nCreating sample content...")
    content_samples = create_sample_content()
    
    # Try different routing strategies
    strategies = ["adaptive", "content_type", "cost", "performance", "geographic", "hybrid"]
    
    print("\n=== Testing different routing strategies ===")
    for strategy in strategies:
        print(f"\nUsing strategy: {strategy}")
        content_type = "document"
        sample = content_samples[content_type]
        
        # Select backend using the current strategy
        backend_id = await routing_integration.select_backend(
            content=sample["content"],
            metadata=sample["metadata"],
            strategy=strategy
        )
        
        print(f"Selected backend for {content_type}: {backend_id}")
    
    print("\n=== Testing different content types with hybrid strategy ===")
    for content_type, sample in content_samples.items():
        # Select backend using the hybrid strategy
        backend_id = await routing_integration.select_backend(
            content=sample["content"],
            metadata=sample["metadata"],
            strategy="hybrid"
        )
        
        print(f"Selected backend for {content_type}: {backend_id}")
        
        # Store the content
        result = await backend_manager.store(backend_id, sample["content"], sample["metadata"])
        
        # Record the outcome
        await routing_integration.record_outcome(
            backend_id=backend_id,
            content_info={
                "content_type": sample["metadata"]["content_type"],
                "size_bytes": len(sample["content"])
            },
            success=result.success
        )
        
        print(f"Storage {'succeeded' if result.success else 'failed'}")
    
    print("\n=== Testing different routing priorities ===")
    priorities = ["balanced", "performance", "cost", "reliability", "geographic"]
    content_type = "image"
    sample = content_samples[content_type]
    
    for priority in priorities:
        # Select backend using the current priority
        backend_id = await routing_integration.select_backend(
            content=sample["content"],
            metadata=sample["metadata"],
            priority=priority
        )
        
        print(f"Selected backend for {content_type} with {priority} priority: {backend_id}")
    
    print("\n=== Getting routing insights ===")
    insights = await routing_integration.get_insights()
    
    # Print some interesting insights
    if "backend_distribution" in insights:
        print("\nBackend Distribution:")
        for backend, percentage in insights["backend_distribution"].items():
            print(f"  {backend}: {percentage:.1%}")
    
    if "optimization_weights" in insights:
        print("\nOptimization Weights:")
        for factor, weight in insights["optimization_weights"].items():
            print(f"  {factor}: {weight:.2f}")
    
    print("\n=== Simulating learning effects ===")
    # Store and retrieve content multiple times, recording outcomes
    print("Running 20 operations with varying success/failure...")
    
    content_type = "document"
    sample = content_samples[content_type]
    
    for i in range(20):
        # Select backend 
        backend_id = await routing_integration.select_backend(
            content=sample["content"],
            metadata=sample["metadata"]
        )
        
        # Force different backends for testing
        if i % 4 == 0:
            backend_id = "ipfs"
        elif i % 4 == 1:
            backend_id = "s3"
        elif i % 4 == 2:
            backend_id = "filecoin"
        else:
            backend_id = "storacha"
        
        # Simulate success/failure pattern
        success = True
        if backend_id == "filecoin" and i % 3 == 0:
            success = False
        elif backend_id == "ipfs" and i % 5 == 0:
            success = False
        
        # Record outcome
        await routing_integration.record_outcome(
            backend_id=backend_id,
            content_info={
                "content_type": sample["metadata"]["content_type"],
                "size_bytes": len(sample["content"])
            },
            success=success
        )
        
        print(f"Operation {i+1}: {backend_id} - {'SUCCESS' if success else 'FAILURE'}")
    
    print("\nGetting insights after learning...")
    insights = await routing_integration.get_insights()
    
    if "optimization_weights" in insights:
        print("\nUpdated Optimization Weights:")
        for factor, weight in insights["optimization_weights"].items():
            print(f"  {factor}: {weight:.2f}")
    
    print("\n=== Final backend selection after learning ===")
    for content_type, sample in content_samples.items():
        backend_id = await routing_integration.select_backend(
            content=sample["content"],
            metadata=sample["metadata"]
        )
        
        print(f"Selected backend for {content_type}: {backend_id}")

    print("\nOptimized Data Routing demonstration completed.")

if __name__ == "__main__":
    anyio.run(demo_routing)