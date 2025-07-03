#!/usr/bin/env python3
"""
Simple test to check libp2p API and fix compatibility issues.
"""

def test_libp2p_api():
    """Test libp2p API availability."""
    try:
        import libp2p
        print(f"✓ libp2p {libp2p.__version__}")
        
        # Test basic host creation
        from libp2p import new_host
        from libp2p.crypto.keys import KeyPair
        print("✓ Basic imports work")
        
        # Test what pubsub modules are actually available
        try:
            from libp2p.pubsub.gossipsub import GossipSub
            print("✓ GossipSub available")
        except ImportError:
            print("✗ GossipSub not available")
            
        try:
            from libp2p.pubsub.floodsub import FloodSub
            print("✓ FloodSub available")
        except ImportError:
            print("✗ FloodSub not available")
            
        # Test network modules
        try:
            from libp2p.network.stream.net_stream import NetStream
            print("✓ NetStream available")
        except ImportError:
            print("✗ NetStream not available")
            
        # Test what constants are available
        try:
            from libp2p.tools.constants import PROTOCOL_PREFIX
            print(f"✓ PROTOCOL_PREFIX: {PROTOCOL_PREFIX}")
        except ImportError:
            print("✗ PROTOCOL_PREFIX not available")
            
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_libp2p_api()
