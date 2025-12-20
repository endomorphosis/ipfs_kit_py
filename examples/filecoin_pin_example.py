#!/usr/bin/env python3
"""
Example: Using the new Filecoin Pin backend and Unified Pin Service.

This example demonstrates the Phase 1 implementation of the Filecoin/IPFS
backend improvements.
"""

import sys
import os
import asyncio

# Add parent directory to path to import modules directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend import FilecoinPinBackend
from ipfs_kit_py.mcp.storage_manager.pinning.unified_pin_service import UnifiedPinService
from ipfs_kit_py.mcp.storage_manager.retrieval.gateway_chain import GatewayChain


def example_filecoin_pin_backend():
    """Example 1: Using Filecoin Pin backend directly."""
    print("=" * 60)
    print("Example 1: Filecoin Pin Backend")
    print("=" * 60)
    
    # Initialize backend (mock mode - no API key needed for testing)
    backend = FilecoinPinBackend(
        resources={},  # No API key = mock mode
        metadata={"default_replication": 3}
    )
    
    print(f"\n✓ Backend initialized: {backend.get_name()}")
    print(f"  Mock mode: {backend.mock_mode}")
    print(f"  Default replication: {backend.default_replication}")
    
    # Pin some content
    content = b"Hello from Filecoin Pin! This is a test of the new backend."
    
    print(f"\n📌 Pinning content ({len(content)} bytes)...")
    result = backend.add_content(
        content=content,
        metadata={
            "name": "example-pin",
            "description": "Test pin from example script",
            "tags": ["example", "test"]
        }
    )
    
    print(f"  Success: {result['success']}")
    print(f"  CID: {result['cid']}")
    print(f"  Status: {result['status']}")
    print(f"  Replication: {result['replication']}")
    
    # Get metadata
    cid = result['cid']
    print(f"\n📊 Getting metadata for CID: {cid[:20]}...")
    metadata = backend.get_metadata(cid)
    
    print(f"  Status: {metadata['status']}")
    print(f"  Size: {metadata['size']} bytes")
    print(f"  Deals: {len(metadata['deals'])}")
    for deal in metadata['deals']:
        print(f"    - Deal ID: {deal['id']}, Provider: {deal['provider']}")
    
    # List all pins
    print(f"\n📋 Listing all pins...")
    pins = backend.list_pins(status="pinned", limit=10)
    
    print(f"  Total pins: {pins['count']}")
    for pin in pins['pins'][:3]:
        print(f"    - CID: {pin['cid'][:20]}..., Size: {pin['size']} bytes")
    
    # Retrieve content
    print(f"\n⬇️  Retrieving content...")
    retrieved = backend.get_content(cid)
    
    print(f"  Success: {retrieved['success']}")
    print(f"  Source: {retrieved['source']}")
    print(f"  Size: {retrieved['size']} bytes")
    print(f"  Content: {retrieved['data'][:50]}...")
    
    # Unpin content
    print(f"\n🗑️  Unpinning content...")
    unpin_result = backend.remove_content(cid)
    
    print(f"  Success: {unpin_result['success']}")
    print(f"  CID: {unpin_result['cid'][:20]}...")


async def example_unified_pin_service():
    """Example 2: Using Unified Pin Service for multi-backend operations."""
    print("\n\n" + "=" * 60)
    print("Example 2: Unified Pin Service")
    print("=" * 60)
    
    # Initialize service
    service = UnifiedPinService()
    
    print(f"\n✓ Service initialized")
    print(f"  Supported backends: {service._supported_backends}")
    
    # Pin to multiple backends
    test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
    
    print(f"\n📌 Pinning to multiple backends...")
    print(f"  CID: {test_cid}")
    
    result = await service.pin(
        cid=test_cid,
        name="multi-backend-example",
        metadata={"description": "Pinned to multiple backends"},
        backends=["ipfs", "filecoin_pin"]
    )
    
    print(f"  Overall success: {result['success']}")
    print(f"  Backends:")
    for backend_name, backend_result in result['backends'].items():
        print(f"    - {backend_name}: {backend_result.get('status', 'N/A')}")
    
    # Check pin status across backends
    print(f"\n📊 Checking pin status across all backends...")
    status = await service.pin_status(test_cid)
    
    print(f"  Overall success: {status['success']}")
    print(f"  Backends:")
    for backend_name, backend_status in status['backends'].items():
        print(f"    - {backend_name}: {backend_status['status']}")
    
    # List pins from all backends
    print(f"\n📋 Listing pins from all backends...")
    pins = await service.list_pins(backend=None, status="pinned", limit=5)
    
    print(f"  Total count: {pins['total_count']}")
    for backend_name, backend_pins in pins['backends'].items():
        print(f"    - {backend_name}: {backend_pins['count']} pins")


async def example_gateway_chain():
    """Example 3: Using Gateway Chain for intelligent content retrieval."""
    print("\n\n" + "=" * 60)
    print("Example 3: Gateway Chain")
    print("=" * 60)
    
    # Initialize gateway chain
    chain = GatewayChain(
        enable_parallel=False,  # Sequential for this example
        cache_duration=3600
    )
    
    print(f"\n✓ Gateway chain initialized")
    print(f"  Gateways: {len(chain.gateways)}")
    for gw in chain.gateways:
        print(f"    - {gw['url']} (priority: {gw['priority']})")
    
    # Test gateway health
    print(f"\n🏥 Testing gateway health...")
    health = await chain.test_all()
    
    print(f"  Results:")
    for gateway_url, status in health.items():
        if status['available']:
            print(f"    ✓ {gateway_url}: {status.get('latency_ms', 'N/A')}ms")
        else:
            print(f"    ✗ {gateway_url}: {status.get('error', 'Failed')}")
    
    # Get metrics
    print(f"\n📊 Gateway metrics:")
    metrics = chain.get_metrics()
    
    for gateway_url, metric in metrics.items():
        if metric['requests'] > 0:
            success_rate = (metric['successes'] / metric['requests']) * 100
            print(f"  {gateway_url}:")
            print(f"    Requests: {metric['requests']}")
            print(f"    Success rate: {success_rate:.1f}%")
            print(f"    Avg time: {metric['avg_time_ms']:.0f}ms")
    
    # Note: Actual fetch would require a real CID and working gateways
    print(f"\n⬇️  Content retrieval would use:")
    print(f"    content = await chain.fetch('bafybeib...')")
    print(f"    content, metrics = await chain.fetch_with_metrics('bafybeib...')")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Filecoin Pin Implementation Examples")
    print("=" * 60)
    print("\nDemonstrating Phase 1 implementation:")
    print("  - Filecoin Pin Backend")
    print("  - Unified Pin Service")
    print("  - Gateway Chain")
    print("\nNote: These examples use mock mode (no API keys required)")
    
    # Example 1: Filecoin Pin Backend
    example_filecoin_pin_backend()
    
    # Example 2: Unified Pin Service (async)
    asyncio.run(example_unified_pin_service())
    
    # Example 3: Gateway Chain (async)
    asyncio.run(example_gateway_chain())
    
    print("\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Set FILECOIN_PIN_API_KEY to use real API")
    print("  2. Configure custom gateways in config.yaml")
    print("  3. Integrate with storage manager")
    print("  4. Add MCP tools for pin operations")
    print("\nSee FILECOIN_PIN_IMPLEMENTATION_SUMMARY.md for details")
    print()


if __name__ == "__main__":
    main()
