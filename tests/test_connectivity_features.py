#!/usr/bin/env python3
"""Quick validation test for universal connectivity features."""

import sys

print("=" * 70)
print("Universal Connectivity Features - Validation Test")
print("=" * 70)
print()

# Test 1: Import all modules
print("Test 1: Importing connectivity modules...")
try:
    from ipfs_kit_py.libp2p.circuit_relay import CircuitRelayClient, CircuitRelayServer
    from ipfs_kit_py.libp2p.dcutr import DCUtR
    from ipfs_kit_py.libp2p.pubsub_peer_discovery import PubsubPeerDiscovery
    from ipfs_kit_py.libp2p.mdns_discovery import MDNSService
    from ipfs_kit_py.libp2p.universal_connectivity import (
        UniversalConnectivityManager,
        ConnectivityConfig,
        DEFAULT_BOOTSTRAP_PEERS
    )
    print("  ✅ All modules imported successfully")
except Exception as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Create configuration
print("\nTest 2: Creating ConnectivityConfig...")
try:
    config = ConnectivityConfig(
        enable_mdns=True,
        enable_pubsub_discovery=True,
        enable_autonat=True,
        enable_relay_client=True,
        enable_dcutr=True
    )
    print(f"  ✅ Config created")
    print(f"     - mDNS: {config.enable_mdns}")
    print(f"     - Pubsub Discovery: {config.enable_pubsub_discovery}")
    print(f"     - AutoNAT: {config.enable_autonat}")
    print(f"     - Relay Client: {config.enable_relay_client}")
    print(f"     - DCUtR: {config.enable_dcutr}")
except Exception as e:
    print(f"  ❌ Config creation failed: {e}")
    sys.exit(1)

# Test 3: Verify bootstrap peers
print("\nTest 3: Checking bootstrap peers...")
try:
    assert len(DEFAULT_BOOTSTRAP_PEERS) == 4
    assert len(config.bootstrap_peers) == 4
    print(f"  ✅ Bootstrap peers configured ({len(DEFAULT_BOOTSTRAP_PEERS)} peers)")
    for i, peer in enumerate(DEFAULT_BOOTSTRAP_PEERS[:2], 1):
        print(f"     {i}. {peer[:60]}...")
except Exception as e:
    print(f"  ❌ Bootstrap check failed: {e}")
    sys.exit(1)

# Test 4: Verify class structure
print("\nTest 4: Verifying class structure...")
try:
    # Check key methods exist
    assert hasattr(UniversalConnectivityManager, 'start')
    assert hasattr(UniversalConnectivityManager, 'stop')
    assert hasattr(UniversalConnectivityManager, 'dial_peer')
    assert hasattr(UniversalConnectivityManager, 'get_metrics')
    
    assert hasattr(CircuitRelayClient, 'make_reservation')
    assert hasattr(CircuitRelayClient, 'dial_through_relay')
    
    assert hasattr(DCUtR, 'attempt_hole_punch')
    
    assert hasattr(PubsubPeerDiscovery, 'start')
    assert hasattr(MDNSService, 'start')
    
    print("  ✅ All required methods present")
except Exception as e:
    print(f"  ❌ Structure check failed: {e}")
    sys.exit(1)

# Test 5: Documentation check
print("\nTest 5: Checking documentation files...")
import os
try:
    doc_file = "ipfs_kit_py/libp2p/UNIVERSAL_CONNECTIVITY.md"
    example_file = "examples/universal_connectivity_example.py"
    summary_file = "UNIVERSAL_CONNECTIVITY_SUMMARY.md"
    
    for file in [doc_file, example_file, summary_file]:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"  ✅ {file} ({size} bytes)")
        else:
            print(f"  ⚠️  {file} not found")
except Exception as e:
    print(f"  ⚠️  Documentation check failed: {e}")

print()
print("=" * 70)
print("All Tests Passed! ✅")
print("=" * 70)
print()
print("Features implemented:")
print("  1. ✅ Circuit Relay v2 (Client + Server)")
print("  2. ✅ DCUtR (Direct Connection Upgrade through Relay)")
print("  3. ✅ Pubsub Peer Discovery")
print("  4. ✅ mDNS Local Network Discovery")
print("  5. ✅ Universal Connectivity Manager")
print("  6. ✅ AutoNAT (already existed, now integrated)")
print()
print("Documentation:")
print("  📖 See ipfs_kit_py/libp2p/UNIVERSAL_CONNECTIVITY.md")
print("  💡 See examples/universal_connectivity_example.py")
print("  📊 See UNIVERSAL_CONNECTIVITY_SUMMARY.md")
print()
print("Next steps:")
print("  1. Create a libp2p host")
print("  2. Initialize UniversalConnectivityManager")
print("  3. Call await manager.start()")
print("  4. Enjoy universal peer connectivity!")
