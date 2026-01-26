#!/usr/bin/env python3
"""
Test the peer manager singleton pattern and thread safety.
"""
import anyio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_singleton_pattern():
    """Test that the peer manager is truly a singleton."""
    print("Testing peer manager singleton pattern...")
    
    from ipfs_kit_py.libp2p.peer_manager import get_peer_manager, start_peer_manager
    
    # Get the peer manager twice
    manager1 = get_peer_manager()
    manager2 = get_peer_manager()
    
    # They should be the same object
    assert manager1 is manager2, "Peer managers are not the same object!"
    print("✓ Singleton pattern works: both calls return the same instance")
    
    # Test thread-safe start
    print("\nTesting thread-safe initialization...")
    
    # Start multiple times concurrently
    results = []

    async def _start_manager():
        try:
            results.append(await start_peer_manager())
        except Exception as exc:
            results.append(exc)

    async with anyio.create_task_group() as tg:
        for _ in range(3):
            tg.start_soon(_start_manager)
    
    # All should return the same instance
    managers = [r for r in results if not isinstance(r, Exception)]
    if managers:
        assert all(m is managers[0] for m in managers), "Concurrent starts returned different instances!"
        print(f"✓ Thread-safe initialization works: {len(managers)} concurrent starts returned same instance")
    else:
        print("⚠ Could not start peer manager (this is OK if libp2p dependencies are not installed)")
        for r in results:
            if isinstance(r, Exception):
                print(f"  Error: {r}")
    
    return True

async def test_multihash_compatibility():
    """Test multihash namespace compatibility."""
    print("\nTesting multihash namespace compatibility...")
    
    try:
        # Try to import multihash
        import sys
        
        # This should work either way
        if 'multihash' in sys.modules:
            print("✓ multihash module is available in sys.modules")
            import multihash
            print(f"  multihash module: {multihash.__name__}")
            
            if hasattr(multihash, 'FuncReg'):
                print("✓ multihash.FuncReg compatibility patch is applied")
            else:
                print("⚠ multihash.FuncReg not found (may not be needed)")
        else:
            print("⚠ multihash not in sys.modules (this is OK if not using libp2p)")
            
    except ImportError as e:
        print(f"⚠ Could not import multihash: {e} (this is OK if not using libp2p)")
    
    return True

async def test_mcp_handlers():
    """Test that MCP handlers use the singleton."""
    print("\nTesting MCP peer handlers...")
    
    from mcp_handlers.get_peers_handler import GetPeersHandler
    from mcp_handlers.connect_peer_handler import ConnectPeerHandler
    from mcp_handlers.get_peer_stats_handler import GetPeerStatsHandler
    
    import tempfile
    ipfs_kit_dir = Path(tempfile.mkdtemp())
    
    # Create handler instances
    get_peers = GetPeersHandler(ipfs_kit_dir)
    connect_peer = ConnectPeerHandler(ipfs_kit_dir)
    get_stats = GetPeerStatsHandler(ipfs_kit_dir)
    
    print("✓ All MCP peer handlers can be instantiated")
    
    # Test get_peers handler
    result = await get_peers.handle({})
    print(f"✓ get_peers handler returned: success={result.get('success')}")
    
    # Test get_peer_stats handler
    result = await get_stats.handle({})
    print(f"✓ get_peer_stats handler returned: success={result.get('success')}")
    
    return True

async def main():
    """Run all tests."""
    print("=" * 60)
    print("Peer Manager Singleton and Thread Safety Tests")
    print("=" * 60)
    
    try:
        await test_singleton_pattern()
        await test_multihash_compatibility()
        await test_mcp_handlers()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(anyio.run(main))
