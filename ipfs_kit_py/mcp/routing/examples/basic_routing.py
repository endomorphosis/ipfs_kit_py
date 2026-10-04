#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/examples/basic_routing.py

"""
Basic Routing Example

This example demonstrates how to use the Optimized Data Routing system
to intelligently select storage backends for different types of content
and operations.
"""

import os
import time
import logging
from typing import Dict, Any

from ipfs_kit_py.mcp.routing.integration import (
    initialize_mcp_routing, select_backend
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_routing_system():
    """Initialize the routing system with example configuration."""
    # Configuration with custom settings
    config = {
        'default_backend': 'IPFS',
        # Adjust weights to favor different criteria
        'strategy_weights': {
            'content': 0.4,  # Higher weight for content-awareness
            'cost': 0.3,     # Medium weight for cost
            'geo': 0.1,      # Lower weight for geographic factors
            'performance': 0.2  # Medium weight for performance
        },
        # Custom cost models for backends
        'backend_costs': {
            'IPFS': {
                'storage_cost': 0.02,    # $ per GB per month
                'retrieval_cost': 0.01,  # $ per GB
                'operation_cost': 0.0001  # $ per operation
            },
            'S3': {
                'storage_cost': 0.023,   # $ per GB per month
                'retrieval_cost': 0.09,  # $ per GB
                'operation_cost': 0.0005  # $ per operation
            },
            'FILECOIN': {
                'storage_cost': 0.005,   # $ per GB per month (long-term storage)
                'retrieval_cost': 0.02,  # $ per GB
                'operation_cost': 0.001  # $ per operation
            }
        }
    }
    
    # Initialize the routing integration
    routing = initialize_mcp_routing(config)
    
    # Register available backends
    routing.register_backend('IPFS', {'type': 'ipfs', 'version': '0.14.0'})
    routing.register_backend('S3', {'type': 's3', 'bucket': 'example-bucket'})
    routing.register_backend('FILECOIN', {'type': 'filecoin', 'network': 'mainnet'})
    
    return routing


def demonstrate_content_based_routing(routing):
    """Demonstrate content-based routing for different file types."""
    print("\n=== Content-Based Routing ===")
    
    # Example files with different content types and sizes
    files = [
        {
            'name': 'family_photo.jpg',
            'type': 'image',
            'size': 5 * 1024 * 1024  # 5 MB
        },
        {
            'name': 'vacation_video.mp4',
            'type': 'video',
            'size': 500 * 1024 * 1024  # 500 MB
        },
        {
            'name': 'research_paper.pdf',
            'type': 'document',
            'size': 2 * 1024 * 1024  # 2 MB
        },
        {
            'name': 'machine_learning_model.pt',
            'type': 'model',
            'size': 200 * 1024 * 1024  # 200 MB
        },
        {
            'name': 'dataset.csv',
            'type': 'dataset',
            'size': 50 * 1024 * 1024  # 50 MB
        }
    ]
    
    # Select backends for storing (writing) each file
    print("\nSelecting backends for storing different file types:")
    for file in files:
        result = routing.select_backend(
            operation_type='write',
            content_type=file['type'],
            content_size=file['size']
        )
        
        backend = result['backend']
        score = result['score']
        
        print(f"File: {file['name']} ({file['type']}, {file['size'] / (1024*1024):.1f} MB)")
        print(f"  -> Selected backend: {backend} (score: {score:.2f})")
        print(f"  -> Reason: {result['reason']}")
    
    # Select backends for retrieving (reading) each file
    print("\nSelecting backends for retrieving different file types:")
    for file in files:
        result = routing.select_backend(
            operation_type='read',
            content_type=file['type'],
            content_size=file['size']
        )
        
        backend = result['backend']
        score = result['score']
        
        print(f"File: {file['name']} ({file['type']}, {file['size'] / (1024*1024):.1f} MB)")
        print(f"  -> Selected backend: {backend} (score: {score:.2f})")
        print(f"  -> Reason: {result['reason']}")


def demonstrate_cost_based_routing(routing):
    """Demonstrate cost-based routing for different operation types and sizes."""
    print("\n=== Cost-Based Routing ===")
    
    # Define different file sizes
    sizes = [
        ('Small', 1 * 1024 * 1024),       # 1 MB
        ('Medium', 100 * 1024 * 1024),    # 100 MB
        ('Large', 1 * 1024 * 1024 * 1024),  # 1 GB
        ('Very large', 10 * 1024 * 1024 * 1024)  # 10 GB
    ]
    
    # Select backends based on cost optimization
    print("\nSelecting backends for storing files of different sizes (cost optimization):")
    for name, size in sizes:
        result = routing.select_backend(
            operation_type='write',
            content_size=size,
            strategy='cost_based'
        )
        
        backend = result['backend']
        
        print(f"File size: {name} ({size / (1024*1024):.1f} MB)")
        print(f"  -> Selected backend: {backend}")
        print(f"  -> Reason: {result['reason']}")
    
    # Estimate costs for long-term storage
    print("\nEstimating costs for long-term storage (1 year):")
    for name, size in sizes:
        for backend in ['IPFS', 'S3', 'FILECOIN']:
            # Get cost calculator
            cost_calculator = routing.router.metrics_collectors.get('cost')
            if cost_calculator:
                # Estimate storage cost for 12 months
                storage_cost = cost_calculator.estimate_storage_cost(
                    backend=backend,
                    size_bytes=size,
                    months=12.0
                )
                
                # Estimate retrieval cost
                retrieval_cost = cost_calculator.estimate_retrieval_cost(
                    backend=backend,
                    size_bytes=size
                )
                
                print(f"File size: {name} ({size / (1024*1024):.1f} MB), Backend: {backend}")
                print(f"  -> Storage cost (1 year): ${storage_cost:.2f}")
                print(f"  -> Retrieval cost: ${retrieval_cost:.2f}")
                print(f"  -> Total cost: ${storage_cost + retrieval_cost:.2f}")


def demonstrate_performance_based_routing(routing):
    """Demonstrate performance-based routing using metrics."""
    print("\n=== Performance-Based Routing ===")
    
    # Simulate performance metrics for backends
    # In a real application, these would be real measurements
    backends = ['IPFS', 'S3', 'FILECOIN']
    
    print("\nRecording simulated performance metrics:")
    for backend in backends:
        # Simulate different performance characteristics
        if backend == 'IPFS':
            latency = 50.0  # ms
            throughput = 100.0  # Mbps
        elif backend == 'S3':
            latency = 70.0  # ms
            throughput = 80.0  # Mbps
        else:  # FILECOIN
            latency = 200.0  # ms
            throughput = 50.0  # Mbps
        
        # Convert throughput from Mbps to bytes per second for the simulation
        bytes_per_second = (throughput * 1_000_000) / 8
        
        # Simulate a read operation with the given performance
        duration_seconds = 1.0  # 1 second operation
        bytes_received = int(bytes_per_second * duration_seconds)
        
        # Record the performance metrics
        start_time = time.time() - (latency / 1000.0)  # Adjust for latency
        routing.record_operation_performance(
            backend=backend,
            operation_type='read',
            start_time=start_time,
            bytes_received=bytes_received,
            success=True
        )
        
        print(f"Backend: {backend}")
        print(f"  -> Simulated latency: {latency} ms")
        print(f"  -> Simulated throughput: {throughput} Mbps")
    
    # Get performance metrics
    print("\nCollected performance metrics:")
    for backend in backends:
        metrics = routing.get_backend_metrics(backend)
        if 'performance' in metrics:
            perf = metrics['performance']
            print(f"Backend: {backend}")
            print(f"  -> Throughput: {perf.get('throughput_mbps', 'N/A')} Mbps")
            print(f"  -> Latency: {perf.get('latency_ms', 'N/A')} ms")
            print(f"  -> Performance score: {perf.get('performance_score', 'N/A')}")
    
    # Select backend based on performance
    print("\nSelecting backend based on performance for a real-time streaming operation:")
    result = routing.select_backend(
        operation_type='read',
        content_type='video',
        content_size=100 * 1024 * 1024,  # 100 MB
        strategy='performance'
    )
    
    backend = result['backend']
    print(f"Selected backend: {backend}")
    print(f"Reason: {result['reason']}")


def demonstrate_geographic_routing(routing):
    """Demonstrate geographic routing for users in different regions."""
    print("\n=== Geographic Routing ===")
    
    # Simulate users in different regions
    users = [
        {'id': 'user1', 'region': 'us-east', 'residency': 'US'},
        {'id': 'user2', 'region': 'eu-west', 'residency': 'EU'},
        {'id': 'user3', 'region': 'ap-northeast', 'residency': 'APAC'}
    ]
    
    # Select backends based on geographic considerations
    print("\nSelecting backends for users in different regions:")
    for user in users:
        result = routing.select_backend(
            operation_type='read',
            content_size=10 * 1024 * 1024,  # 10 MB
            region=user['region'],
            metadata={'residency_zone': user['residency']},
            strategy='geographic'
        )
        
        backend = result['backend']
        
        print(f"User: {user['id']} (Region: {user['region']}, Residency: {user['residency']})")
        print(f"  -> Selected backend: {backend}")
        print(f"  -> Reason: {result['reason']}")


def demonstrate_composite_routing(routing):
    """Demonstrate composite routing that considers all factors."""
    print("\n=== Composite Routing (All Factors) ===")
    
    # Example scenarios combining different factors
    scenarios = [
        {
            'name': 'Large video for European user',
            'operation': 'write',
            'content_type': 'video',
            'size': 500 * 1024 * 1024,  # 500 MB
            'region': 'eu-west',
            'residency': 'EU'
        },
        {
            'name': 'Critical document with high performance requirements',
            'operation': 'read',
            'content_type': 'document',
            'size': 5 * 1024 * 1024,  # 5 MB
            'priority': 10  # High priority
        },
        {
            'name': 'AI model for long-term archiving',
            'operation': 'archive',
            'content_type': 'model',
            'size': 2 * 1024 * 1024 * 1024,  # 2 GB
            'region': 'us-west'
        },
        {
            'name': 'Small image with cost constraints',
            'operation': 'write',
            'content_type': 'image',
            'size': 500 * 1024,  # 500 KB
            'metadata': {'cost_sensitive': True}
        }
    ]
    
    # Select backends for each scenario
    print("\nSelecting backends for complex scenarios:")
    for scenario in scenarios:
        result = routing.select_backend(
            operation_type=scenario['operation'],
            content_type=scenario.get('content_type'),
            content_size=scenario['size'],
            region=scenario.get('region'),
            metadata={
                'residency_zone': scenario.get('residency'),
                'priority': scenario.get('priority', 0),
                **scenario.get('metadata', {})
            }
        )
        
        backend = result['backend']
        score = result['score']
        
        print(f"Scenario: {scenario['name']}")
        print(f"  -> Selected backend: {backend} (score: {score:.2f})")
        print(f"  -> Reason: {result['reason']}")
        
        # Show alternatives
        print("  -> Alternatives:")
        for alt in result['alternatives']:
            print(f"     * {alt['backend']} (score: {alt['score']:.2f})")


def main():
    """Run the example application."""
    print("Optimized Data Routing Example")
    print("==============================")
    
    # Initialize the routing system
    routing = initialize_routing_system()
    print(f"Initialized routing system with {len(routing.router.available_backends)} backends")
    
    # Demonstrate different routing strategies
    demonstrate_content_based_routing(routing)
    demonstrate_cost_based_routing(routing)
    demonstrate_performance_based_routing(routing)
    demonstrate_geographic_routing(routing)
    demonstrate_composite_routing(routing)
    
    # Print routing history
    history = routing.get_routing_history(limit=5)
    print("\n=== Recent Routing Decisions ===")
    for i, decision in enumerate(history):
        print(f"{i+1}. Backend: {decision['backend']}, Operation: {decision['operation']}")


if __name__ == "__main__":
    main()