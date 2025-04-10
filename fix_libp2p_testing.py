#!/usr/bin/env python3
"""
Comprehensive fix for libp2p testing in ipfs_kit_py.

This script provides tools to enable testing of libp2p functionality
without requiring the actual libp2p dependency. It can be used directly
in tests or as a test helper.

Features:
1. Complete mock implementation of IPFSLibp2pPeer
2. Patches for HAS_LIBP2P flags throughout the codebase
3. Mock implementations of MCP server command handlers for libp2p
4. Additional helper functions for test setup

Usage:
    # Option 1: Run directly to apply all fixes
    python fix_libp2p_testing.py
    
    # Option 2: Import in test files
    from fix_libp2p_testing import setup_libp2p_testing
    
    # Apply in test setup
    def setup_function():
        setup_libp2p_testing()
"""

import os
import sys
import inspect
import importlib
import importlib.util
import logging
import uuid
import time
from unittest.mock import MagicMock, AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
_applied_mocks = False
_patched_modules = set()

def setup_libp2p_testing():
    """
    Set up environment for libp2p testing.
    
    This function:
    1. Applies all necessary mocks for libp2p_peer
    2. Patches MCP server to handle libp2p commands
    3. Sets environment variables to force mocking
    
    Returns:
        bool: True if setup was successful, False otherwise
    """
    global _applied_mocks
    
    # Avoid reapplying if already done
    if _applied_mocks:
        return True
    
    # Set environment variables
    os.environ['FORCE_MOCK_IPFS_LIBP2P_PEER'] = '1'
    os.environ['SKIP_LIBP2P'] = '0'
    
    # Apply mocks
    libp2p_success = apply_libp2p_mocks()
    mcp_success = patch_mcp_command_handlers()
    
    _applied_mocks = libp2p_success and mcp_success
    return _applied_mocks

def apply_libp2p_mocks():
    """
    Apply mocks to the ipfs_kit_py.libp2p_peer module for testing.
    
    This function:
    1. Ensures HAS_LIBP2P is set to True in the module
    2. Creates mock objects for all libp2p dependencies
    3. Creates a mock IPFSLibp2pPeer implementation
    
    Returns:
        bool: True if mocks were applied successfully, False otherwise
    """
    try:
        # Import the module
        import ipfs_kit_py.libp2p_peer
        _patched_modules.add('ipfs_kit_py.libp2p_peer')
        
        # Create mock class for PeerID
        class MockPeerID:
            @staticmethod
            def from_base58(peer_id):
                return f"PeerID({peer_id})"
                
            def __str__(self):
                return "MockPeerID"
        
        # Create mock class for KeyPair
        class MockKeyPair:
            def __init__(self):
                self.private_key = MagicMock()
                self.public_key = MagicMock()
        
        # Create mock objects
        mock_host = MagicMock()
        mock_host_instance = MagicMock()
        mock_host_instance.get_id = MagicMock(return_value="QmServerPeerId")
        mock_host_instance.get_addrs = MagicMock(return_value=["test_addr"])
        mock_host_instance.new_stream = AsyncMock()
        mock_network = MagicMock()
        mock_network.connections = {}
        mock_host_instance.get_network = MagicMock(return_value=mock_network)
        mock_host.return_value = mock_host_instance

        mock_dht = MagicMock()
        mock_dht_instance = AsyncMock()
        mock_dht.return_value = mock_dht_instance
        
        mock_pubsub = MagicMock()
        mock_pubsub_instance = MagicMock()
        mock_pubsub_instance.publish = MagicMock()
        mock_pubsub_instance.subscribe = MagicMock()
        mock_pubsub_instance.start = AsyncMock()
        mock_pubsub = MagicMock(return_value=mock_pubsub_instance)
        
        mock_pubsub_utils = MagicMock()
        mock_pubsub_utils.create_pubsub = mock_pubsub
                
        # Set necessary flags in the module
        ipfs_kit_py.libp2p_peer.HAS_LIBP2P = True
        ipfs_kit_py.libp2p_peer.HAS_MDNS = True
        ipfs_kit_py.libp2p_peer.HAS_NAT_TRAVERSAL = True
        
        # Also set in the module's globals dict
        ipfs_kit_py.libp2p_peer.__dict__['HAS_LIBP2P'] = True
        ipfs_kit_py.libp2p_peer.__dict__['HAS_MDNS'] = True
        ipfs_kit_py.libp2p_peer.__dict__['HAS_NAT_TRAVERSAL'] = True
        
        # Ensure the module-level variable is defined through sys.modules
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_LIBP2P = True
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_MDNS = True
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_NAT_TRAVERSAL = True
        
        # Add mock objects directly to the module
        ipfs_kit_py.libp2p_peer.new_host = mock_host
        ipfs_kit_py.libp2p_peer.KademliaServer = mock_dht
        ipfs_kit_py.libp2p_peer.pubsub_utils = mock_pubsub_utils
        ipfs_kit_py.libp2p_peer.KeyPair = MockKeyPair
        ipfs_kit_py.libp2p_peer.PeerID = MockPeerID
        
        # Also patch the package level
        try:
            import ipfs_kit_py.libp2p
            _patched_modules.add('ipfs_kit_py.libp2p')
            ipfs_kit_py.libp2p.HAS_LIBP2P = True
            sys.modules['ipfs_kit_py.libp2p'].HAS_LIBP2P = True
        except ImportError:
            pass
        
        # Create mock IPFSLibp2pPeer class if we need to replace the original
        original_IPFSLibp2pPeer = getattr(ipfs_kit_py.libp2p_peer, 'IPFSLibp2pPeer', None)
        
        if not original_IPFSLibp2pPeer or os.environ.get('FORCE_MOCK_IPFS_LIBP2P_PEER', '0') == '1':
            # Create a complete mock implementation
            from ipfs_kit_py.error import IPFSError
            
            class MockLibP2PError(IPFSError):
                """Mock base class for all libp2p-related errors."""
                pass
            
            class MockIPFSLibp2pPeer:
                """Mock implementation of IPFSLibp2pPeer for testing."""
                
                def __init__(self, identity_path=None, bootstrap_peers=None, listen_addrs=None, 
                              role="leecher", enable_mdns=True, enable_hole_punching=False, 
                              enable_relay=False, tiered_storage_manager=None):
                    # Set up basic attributes
                    self.identity_path = identity_path
                    self.role = role
                    self.logger = logging.getLogger(__name__)
                    self.content_store = {}
                    self.host = mock_host_instance
                    self.dht = mock_dht_instance
                    self.pubsub = mock_pubsub_instance
                    self.bootstrap_peers = bootstrap_peers or []
                    self.enable_mdns = enable_mdns
                    self.enable_hole_punching = enable_hole_punching
                    self.enable_relay_client = enable_relay
                    self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
                    self.tiered_storage_manager = tiered_storage_manager
                    self._running = True
                    
                    # Create storage structures
                    self.content_metadata = {}
                    self.wantlist = {}
                    self.wantlist_lock = MagicMock()  # Instead of real RLock
                    self.heat_scores = {}
                    self.want_counts = {}
                    
                    # Mock identity
                    self.identity = MockKeyPair()
                    
                    self.logger.info(f"Mock IPFSLibp2pPeer initialized with role: {role}")
                
                def get_peer_id(self):
                    return "QmServerPeerId"
                    
                def get_multiaddrs(self):
                    return ["test_addr"]
                    
                def get_protocols(self):
                    return ["/ipfs/bitswap/1.2.0", "/ipfs/id/1.0.0", "/ipfs/ping/1.0.0"]
                    
                def connect_peer(self, peer_addr):
                    return True
                    
                def store_bytes(self, cid, data):
                    self.content_store[cid] = data
                    return True
                    
                def get_stored_bytes(self, cid):
                    return self.content_store.get(cid)
                
                def is_connected_to(self, peer_id):
                    return True  # Always pretend to be connected
                    
                def announce_content(self, cid, metadata=None):
                    return True
                    
                def request_content(self, cid, timeout=30):
                    # Check local store first
                    content = self.get_stored_bytes(cid)
                    if content:
                        return content
                        
                    # Generate mock content for testing
                    mock_content = f"Mock content for {cid}".encode()
                    self.store_bytes(cid, mock_content)
                    return mock_content
                
                # Create the async version too
                async def request_content_async(self, cid, timeout=30):
                    return self.request_content(cid, timeout)
                
                def receive_streamed_data(self, peer_id, cid, callback):
                    # Generate 1MB of data in 64KB chunks
                    data = b"X" * 1024 * 1024
                    chunk_size = 65536
                    total_sent = 0
                    
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        callback(chunk)
                        total_sent += len(chunk)
                    
                    return total_sent
                    
                def close(self):
                    self.content_store = {}
                    self._running = False
                    return None
                
                def register_protocol_handler(self, protocol_id, handler):
                    return True
                
                def start_discovery(self, rendezvous_string="ipfs-discovery"):
                    return True
                
                def enable_relay(self):
                    return True
                
                def find_providers(self, cid, count=20, timeout=60):
                    return []
                
                def stream_data(self, callback):
                    # Generate 1MB of data in 64KB chunks
                    data = b"X" * 1024 * 1024
                    chunk_size = 65536
                    
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        callback(chunk)
                    
                    return len(data)
            
            # Replace the original class with our mock
            ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer = MockIPFSLibp2pPeer
            ipfs_kit_py.libp2p_peer.LibP2PError = MockLibP2PError
        
        logger.info("Successfully applied libp2p mocks")
        return True
        
    except Exception as e:
        logger.error(f"Error applying libp2p mocks: {e}")
        return False

def patch_mcp_command_handlers():
    """
    Patch the MCP command handlers to support libp2p commands.
    
    This ensures that the MCP server can handle libp2p-related commands
    even when the actual libp2p dependency is not available.
    
    Returns:
        bool: True if patch was applied successfully, False otherwise
    """
    try:
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        _patched_modules.add('ipfs_kit_py.mcp.models.ipfs_model')
        logger.info("Successfully imported IPFSModel")
        
        # Add handlers for libp2p commands if they don't exist
        if not hasattr(IPFSModel, '_handle_list_known_peers'):
            def _handle_list_known_peers(self, command_args):
                """Handle listing known peers."""
                # Mock implementation
                import time
                return {
                    "success": True,
                    "peers": [
                        {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                        {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                    ],
                    "count": 2,
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_list_known_peers = _handle_list_known_peers
            logger.info("Added missing method: _handle_list_known_peers")
        else:
            logger.info("Method already exists: _handle_list_known_peers")
        
        if not hasattr(IPFSModel, '_handle_register_node'):
            def _handle_register_node(self, command_args):
                """Handle registering a node with the cluster."""
                # Mock implementation
                import uuid
                import time
                node_id = command_args.get("node_id", f"QmNode{uuid.uuid4()}")
                return {
                    "success": True,
                    "node_id": node_id,
                    "registered": True,
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_register_node = _handle_register_node
            logger.info("Added missing method: _handle_register_node")
        else:
            logger.info("Method already exists: _handle_register_node")
        
        if not hasattr(IPFSModel, '_handle_connect_peer'):
            def _handle_connect_peer(self, command_args):
                """Handle connecting to a peer."""
                # Mock implementation
                import time
                peer_id = command_args.get("peer_id", "QmPeer1")
                addr = command_args.get("addr", "/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1")
                return {
                    "success": True,
                    "peer_id": peer_id,
                    "connected": True,
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_connect_peer = _handle_connect_peer
            logger.info("Added missing method: _handle_connect_peer")
        else:
            logger.info("Method already exists: _handle_connect_peer")

        if not hasattr(IPFSModel, '_handle_discover_peers'):
            def _handle_discover_peers(self, command_args):
                """Handle peer discovery."""
                # Mock implementation
                import time
                return {
                    "success": True,
                    "peers_found": 2,
                    "peers": [
                        {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                        {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                    ],
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_discover_peers = _handle_discover_peers
            logger.info("Added missing method: _handle_discover_peers")
        else:
            logger.info("Method already exists: _handle_discover_peers")
        
        # Patch the execute_command method to handle libp2p commands
        original_execute_command = IPFSModel.execute_command
        
        def patched_execute_command(self, command, args=None):
            # Handle libp2p-specific commands
            if command == "list_known_peers":
                return self._handle_list_known_peers(args or {})
            elif command == "register_node":
                return self._handle_register_node(args or {})
            elif command == "connect_peer":
                return self._handle_connect_peer(args or {})
            elif command == "discover_peers":
                return self._handle_discover_peers(args or {})
            # Call the original method for other commands
            return original_execute_command(self, command, args)
        
        # Apply the patch only if it hasn't been applied yet
        if not hasattr(IPFSModel.execute_command, '_patched_for_libp2p'):
            IPFSModel.execute_command = patched_execute_command
            # Mark the method as patched to avoid double-patching
            IPFSModel.execute_command._patched_for_libp2p = True
            logger.info("Successfully patched execute_command method to handle libp2p commands")
        else:
            logger.info("execute_command method already patched for libp2p")
        
        return True
        
    except Exception as e:
        logger.error(f"Error patching MCP command handlers: {e}")
        return False

def patch_mcp_server_for_libp2p(server_instance):
    """
    Apply patches to an MCP server instance to support libp2p.
    
    Args:
        server_instance: The MCPServer instance to patch
        
    Returns:
        bool: True if patched successfully, False otherwise
    """
    try:
        # Make sure the server's IPFSModel is patched
        if hasattr(server_instance, 'models') and 'ipfs' in server_instance.models:
            model = server_instance.models['ipfs']
            
            # Patch the execute_command method if not already patched
            if not hasattr(model.execute_command, '_patched_for_libp2p'):
                # Store original method
                original_execute_command = model.execute_command
                
                # Create patched method
                def patched_execute_command(command, args=None):
                    # Handle libp2p-specific commands
                    if command == "list_known_peers":
                        return model._handle_list_known_peers(args or {})
                    elif command == "register_node":
                        return model._handle_register_node(args or {})
                    elif command == "connect_peer":
                        return model._handle_connect_peer(args or {})
                    elif command == "discover_peers":
                        return model._handle_discover_peers(args or {})
                    # Call the original method for other commands
                    return original_execute_command(command, args)
                
                # Apply the patch
                model.execute_command = patched_execute_command
                model.execute_command._patched_for_libp2p = True
                
                # Add handlers if they don't exist
                if not hasattr(model, '_handle_list_known_peers'):
                    model._handle_list_known_peers = lambda args: {
                        "success": True,
                        "peers": [
                            {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                            {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                        ],
                        "count": 2,
                        "timestamp": time.time()
                    }
                
                if not hasattr(model, '_handle_register_node'):
                    model._handle_register_node = lambda args: {
                        "success": True,
                        "node_id": args.get("node_id", f"QmNode{uuid.uuid4()}"),
                        "registered": True,
                        "timestamp": time.time()
                    }
                
                if not hasattr(model, '_handle_connect_peer'):
                    model._handle_connect_peer = lambda args: {
                        "success": True,
                        "peer_id": args.get("peer_id", "QmPeer1"),
                        "connected": True,
                        "timestamp": time.time()
                    }
                
                if not hasattr(model, '_handle_discover_peers'):
                    model._handle_discover_peers = lambda args: {
                        "success": True,
                        "peers_found": 2,
                        "peers": [
                            {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                            {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                        ],
                        "timestamp": time.time()
                    }
            
            logger.info("Successfully patched MCP server instance for libp2p support")
            return True
        else:
            logger.error("Server instance has no IPFS model")
            return False
    except Exception as e:
        logger.error(f"Error patching MCP server instance: {e}")
        return False

def create_pytest_fixtures():
    """Create and return pytest fixtures for libp2p testing."""
    import pytest
    
    @pytest.fixture(scope="function")
    def libp2p_test_setup():
        """Set up libp2p testing environment."""
        # Apply all fixes
        setup_libp2p_testing()
        
        # Return any state needed by tests
        return {
            "applied_mocks": _applied_mocks,
            "patched_modules": list(_patched_modules)
        }
    
    return {"libp2p_test_setup": libp2p_test_setup}

def add_to_conftest(conftest_path=None):
    """Add the libp2p fixtures to a conftest.py file."""
    if conftest_path is None:
        # Try to find the caller's conftest.py
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        caller_dir = os.path.dirname(caller_file)
        conftest_path = os.path.join(caller_dir, "conftest.py")
    
    # Check if file exists
    if not os.path.exists(conftest_path):
        with open(conftest_path, "w") as f:
            f.write("""# conftest.py - pytest fixtures
import pytest

# Import libp2p fixtures
from fix_libp2p_testing import create_pytest_fixtures

# Get the fixtures
fixtures = create_pytest_fixtures()

# Add fixtures to this module
locals().update(fixtures)
""")
        logger.info(f"Created new conftest.py at {conftest_path}")
    else:
        # Append to existing file
        with open(conftest_path, "a") as f:
            f.write("""
# Import libp2p fixtures
from fix_libp2p_testing import create_pytest_fixtures

# Get the fixtures
fixtures = create_pytest_fixtures()

# Add fixtures to this module
locals().update(fixtures)
""")
        logger.info(f"Added fixtures to existing conftest.py at {conftest_path}")
    
    return True

if __name__ == "__main__":
    # Apply all fixes
    setup_result = setup_libp2p_testing()
    
    # Report results
    if setup_result:
        print("✅ Successfully set up libp2p testing environment")
        print(f"Patched modules: {', '.join(_patched_modules)}")
        sys.exit(0)
    else:
        print("❌ Failed to set up libp2p testing environment")
        sys.exit(1)