#!/usr/bin/env python3
"""
Comprehensive libp2p compatibility test for updated dependencies.

This script tests all libp2p functionality to identify any compatibility issues
with the current dependency versions, particularly protobuf.
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_imports():
    """Test basic libp2p imports and dependencies."""
    print("=" * 60)
    print("TESTING BASIC LIBP2P IMPORTS")
    print("=" * 60)
    
    results = {}
    
    # Test protobuf version first
    try:
        import google.protobuf
        protobuf_version = google.protobuf.__version__
        print(f"✓ Protobuf version: {protobuf_version}")
        results["protobuf_version"] = protobuf_version
    except Exception as e:
        print(f"✗ Protobuf import failed: {e}")
        results["protobuf_error"] = str(e)
        return results
    
    # Test our libp2p package
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies
        print(f"✓ ipfs_kit_py.libp2p imported successfully")
        print(f"✓ HAS_LIBP2P: {HAS_LIBP2P}")
        
        deps_available = check_dependencies()
        print(f"✓ Dependencies check: {deps_available}")
        results["has_libp2p"] = HAS_LIBP2P
        results["deps_check"] = deps_available
    except Exception as e:
        print(f"✗ ipfs_kit_py.libp2p import failed: {e}")
        results["libp2p_import_error"] = str(e)
        return results
    
    # Test core libp2p imports
    core_imports = [
        "libp2p",
        "multiaddr", 
        "base58",
        "cryptography"
    ]
    
    for module in core_imports:
        try:
            import importlib
            mod = importlib.import_module(module)
            version = getattr(mod, "__version__", "unknown")
            print(f"✓ {module}: {version}")
            results[f"{module}_version"] = version
        except Exception as e:
            print(f"✗ {module}: {e}")
            results[f"{module}_error"] = str(e)
    
    # Test specific libp2p components that might have protobuf dependencies
    libp2p_components = [
        "libp2p.crypto.keys",
        "libp2p.peer.id", 
        "libp2p.network.stream.net_stream_interface",
        "libp2p.pubsub.pubsub_router_interface"
    ]
    
    for component in libp2p_components:
        try:
            mod = importlib.import_module(component)
            print(f"✓ {component}")
            results[f"{component.replace('.', '_')}_import"] = True
        except Exception as e:
            print(f"✗ {component}: {e}")
            results[f"{component.replace('.', '_')}_error"] = str(e)
    
    return results

def test_libp2p_host_creation():
    """Test creating a libp2p host."""
    print("=" * 60)
    print("TESTING LIBP2P HOST CREATION")
    print("=" * 60)
    
    results = {}
    
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P
        if not HAS_LIBP2P:
            print("✗ libp2p not available, skipping host creation test")
            results["skipped"] = "libp2p not available"
            return results
        
        from libp2p import new_host
        from libp2p.crypto.keys import KeyPair
        from ipfs_kit_py.libp2p.crypto_compat import generate_key_pair
        
        print("✓ Successfully imported host creation modules")
        results["imports_success"] = True
        
        # Generate a key pair
        keypair = generate_key_pair("ed25519")
        print(f"✓ Generated keypair: {type(keypair)}")
        results["keypair_generation"] = True
        
        # Try to create a host (this would test protobuf serialization)
        async def create_test_host():
            try:
                host = new_host(key_pair=keypair)
                print(f"✓ Created libp2p host: {host}")
                
                # Get peer ID (tests protobuf serialization)
                peer_id = host.get_id()
                print(f"✓ Got peer ID: {peer_id}")
                results["peer_id"] = str(peer_id)
                
                # Get listen addresses
                listen_addrs = host.get_addrs()
                print(f"✓ Listen addresses: {[str(addr) for addr in listen_addrs]}")
                results["listen_addrs"] = [str(addr) for addr in listen_addrs]
                
                await host.close()
                print("✓ Host closed successfully")
                results["host_lifecycle"] = True
                
                return True
            except Exception as e:
                print(f"✗ Host creation failed: {e}")
                results["host_creation_error"] = str(e)
                results["host_creation_traceback"] = traceback.format_exc()
                return False
        
        # Run the async test
        success = asyncio.run(create_test_host())
        results["host_creation_success"] = success
        
    except Exception as e:
        print(f"✗ Host creation test setup failed: {e}")
        results["setup_error"] = str(e)
        results["setup_traceback"] = traceback.format_exc()
    
    return results

def test_ipfs_libp2p_peer():
    """Test our IPFSLibp2pPeer implementation."""
    print("=" * 60)
    print("TESTING IPFS LIBP2P PEER")
    print("=" * 60)
    
    results = {}
    
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P
        if not HAS_LIBP2P:
            print("✗ libp2p not available, skipping peer test")
            results["skipped"] = "libp2p not available"
            return results
        
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        print("✓ Successfully imported IPFSLibp2pPeer")
        results["import_success"] = True
        
        # Test peer initialization
        async def test_peer_init():
            try:
                peer = IPFSLibp2pPeer(
                    role="leecher",
                    enable_mdns=False,  # Disable to avoid network issues
                    enable_hole_punching=False,
                    enable_relay=False
                )
                print("✓ IPFSLibp2pPeer created successfully")
                results["peer_creation"] = True
                
                # Test basic methods
                if hasattr(peer, 'get_peer_id'):
                    peer_id = peer.get_peer_id()
                    print(f"✓ Peer ID: {peer_id}")
                    results["peer_id"] = str(peer_id)
                
                if hasattr(peer, 'get_listen_addresses'):
                    listen_addrs = peer.get_listen_addresses()
                    print(f"✓ Listen addresses: {listen_addrs}")
                    results["listen_addresses"] = listen_addrs
                
                # Test cleanup
                if hasattr(peer, 'stop'):
                    await peer.stop()
                    print("✓ Peer stopped successfully")
                    results["peer_cleanup"] = True
                
                return True
            except Exception as e:
                print(f"✗ Peer test failed: {e}")
                results["peer_test_error"] = str(e)
                results["peer_test_traceback"] = traceback.format_exc()
                return False
        
        success = asyncio.run(test_peer_init())
        results["peer_test_success"] = success
        
    except Exception as e:
        print(f"✗ Peer test setup failed: {e}")
        results["setup_error"] = str(e)
        results["setup_traceback"] = traceback.format_exc()
    
    return results

def test_protocol_negotiation():
    """Test protocol negotiation functionality."""
    print("=" * 60)
    print("TESTING PROTOCOL NEGOTIATION")
    print("=" * 60)
    
    results = {}
    
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P
        if not HAS_LIBP2P:
            print("✗ libp2p not available, skipping protocol test")
            results["skipped"] = "libp2p not available"
            return results
        
        # Test protocol constants and imports
        from ipfs_kit_py.libp2p_peer import PROTOCOLS
        print(f"✓ Protocol constants: {PROTOCOLS}")
        results["protocols"] = PROTOCOLS
        
        # Test typing imports
        try:
            from ipfs_kit_py.libp2p.typing import TProtocol
            print("✓ TProtocol type imported")
            results["tprotocol_import"] = True
        except Exception as e:
            print(f"✗ TProtocol import failed: {e}")
            results["tprotocol_error"] = str(e)
        
        # Test constants
        try:
            from ipfs_kit_py.libp2p.tools.constants import ALPHA_VALUE
            print(f"✓ ALPHA_VALUE: {ALPHA_VALUE}")
            results["alpha_value"] = ALPHA_VALUE
        except Exception as e:
            print(f"✗ Constants import failed: {e}")
            results["constants_error"] = str(e)
        
        results["protocol_test_success"] = True
        
    except Exception as e:
        print(f"✗ Protocol test failed: {e}")
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()
    
    return results

def test_cluster_management():
    """Test cluster management with libp2p integration."""
    print("=" * 60)
    print("TESTING CLUSTER MANAGEMENT")
    print("=" * 60)
    
    results = {}
    
    try:
        from ipfs_kit_py.cluster_management import ClusterManager
        print("✓ ClusterManager imported successfully")
        results["import_success"] = True
        
        # Test creating cluster manager without libp2p (should work)
        try:
            cluster_mgr = ClusterManager(
                enable_libp2p=False,
                ipfs_path="/tmp/test_ipfs"
            )
            print("✓ ClusterManager created without libp2p")
            results["without_libp2p"] = True
        except Exception as e:
            print(f"✗ ClusterManager creation without libp2p failed: {e}")
            results["without_libp2p_error"] = str(e)
        
        # Test creating cluster manager with libp2p (might fail due to dependencies)
        try:
            cluster_mgr_libp2p = ClusterManager(
                enable_libp2p=True,
                ipfs_path="/tmp/test_ipfs_libp2p"
            )
            print("✓ ClusterManager created with libp2p")
            results["with_libp2p"] = True
        except Exception as e:
            print(f"✗ ClusterManager creation with libp2p failed: {e}")
            results["with_libp2p_error"] = str(e)
        
    except Exception as e:
        print(f"✗ Cluster management test failed: {e}")
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()
    
    return results

def test_compatibility_modules():
    """Test our compatibility modules."""
    print("=" * 60)
    print("TESTING COMPATIBILITY MODULES")
    print("=" * 60)
    
    results = {}
    
    # Test crypto compatibility
    try:
        from ipfs_kit_py.libp2p.crypto_compat import (
            generate_key_pair, 
            serialize_private_key, 
            load_private_key,
            create_key_pair
        )
        print("✓ Crypto compatibility module imported")
        
        # Test key generation
        keypair = generate_key_pair("ed25519")
        print(f"✓ Generated keypair: {type(keypair)}")
        
        # Test serialization
        serialized = serialize_private_key(keypair.private_key)
        print(f"✓ Serialized key length: {len(serialized)}")
        
        results["crypto_compat"] = True
        
    except Exception as e:
        print(f"✗ Crypto compatibility test failed: {e}")
        results["crypto_compat_error"] = str(e)
    
    # Test anyio compatibility
    try:
        from ipfs_kit_py.libp2p.anyio_compat import create_task_group, sleep
        print("✓ AnyIO compatibility module imported")
        results["anyio_compat"] = True
    except Exception as e:
        print(f"✗ AnyIO compatibility test failed: {e}")
        results["anyio_compat_error"] = str(e)
    
    return results

def test_mcp_libp2p_integration():
    """Test MCP server integration with libp2p features."""
    print("=" * 60)
    print("TESTING MCP LIBP2P INTEGRATION")
    print("=" * 60)
    
    results = {}
    
    try:
        # Test that libp2p features are properly disabled/enabled in the MCP server
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        server = EnhancedMCPServerWithDaemonMgmt()
        print("✓ MCP server created successfully")
        
        # Check if libp2p features are available
        tools = server.tools
        libp2p_related_tools = [
            "ipfs_swarm_peers", 
            "ipfs_dht_findpeer", 
            "ipfs_pubsub_publish"
        ]
        
        for tool in libp2p_related_tools:
            if tool in tools:
                print(f"✓ Tool '{tool}' available")
                results[f"tool_{tool}"] = True
            else:
                print(f"✗ Tool '{tool}' not available")
                results[f"tool_{tool}"] = False
        
        results["mcp_integration"] = True
        
    except Exception as e:
        print(f"✗ MCP integration test failed: {e}")
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()
    
    return results

def run_all_tests():
    """Run all compatibility tests."""
    print("🧪 LIBP2P COMPATIBILITY TEST SUITE")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print("")
    
    all_results = {}
    
    # Run all tests
    test_functions = [
        ("basic_imports", test_basic_imports),
        ("host_creation", test_libp2p_host_creation),
        ("ipfs_peer", test_ipfs_libp2p_peer),
        ("protocol_negotiation", test_protocol_negotiation),
        ("cluster_management", test_cluster_management),
        ("compatibility_modules", test_compatibility_modules),
        ("mcp_integration", test_mcp_libp2p_integration)
    ]
    
    for test_name, test_func in test_functions:
        try:
            print(f"\n⏱️  Running {test_name}...")
            start_time = time.time()
            result = test_func()
            end_time = time.time()
            
            result["duration"] = end_time - start_time
            all_results[test_name] = result
            
            print(f"✅ {test_name} completed in {result['duration']:.2f}s")
            
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            all_results[test_name] = {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    # Generate summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(test_functions)
    passed_tests = 0
    failed_tests = 0
    
    for test_name, result in all_results.items():
        if "error" in result or any("error" in str(v) for v in result.values()):
            print(f"❌ {test_name}: FAILED")
            failed_tests += 1
        else:
            print(f"✅ {test_name}: PASSED")
            passed_tests += 1
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if failed_tests > 0:
        print(f"⚠️  {failed_tests} tests failed - see details above")
    else:
        print("🎉 All tests passed! libp2p compatibility looks good.")
    
    # Save detailed results
    results_file = "libp2p_compatibility_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    return all_results

if __name__ == "__main__":
    results = run_all_tests()
    
    # Exit with non-zero if any tests failed
    if any("error" in result or any("error" in str(v) for v in result.values()) 
           for result in results.values()):
        sys.exit(1)
    else:
        sys.exit(0)
