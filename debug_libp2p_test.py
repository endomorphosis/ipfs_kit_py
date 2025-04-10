#!/usr/bin/env python3
"""
Debug script to run the libp2p communication test with detailed error reporting.
"""

import os
import sys
import logging
import unittest
import pytest
import traceback

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_test():
    """Run the libp2p communication test directly."""
    try:
        # First ensure our fix is applied
        from fix_libp2p_mocks import apply_libp2p_mocks, patch_mcp_command_handlers
        logger.info("Applying libp2p mocks...")
        libp2p_success = apply_libp2p_mocks()
        logger.info(f"Applied libp2p mocks: {libp2p_success}")
        
        mcp_success = patch_mcp_command_handlers()
        logger.info(f"Applied MCP command handlers patch: {mcp_success}")
        
        # Ensure HAS_LIBP2P is True in the module
        import ipfs_kit_py.libp2p_peer
        ipfs_kit_py.libp2p_peer.HAS_LIBP2P = True
        if 'ipfs_kit_py.libp2p_peer' in sys.modules:
            sys.modules['ipfs_kit_py.libp2p_peer'].HAS_LIBP2P = True
        
        logger.debug(f"Has libp2p: {ipfs_kit_py.libp2p_peer.HAS_LIBP2P}")
        logger.debug(f"IPFSLibp2pPeer exists: {hasattr(ipfs_kit_py.libp2p_peer, 'IPFSLibp2pPeer')}")
        
        # Create a monkeypatch instance for testing
        import unittest.mock
        monkeypatch = unittest.mock.MagicMock()
        monkeypatch.setattr = unittest.mock.MagicMock()
        
        # Create a complete mock of the libp2p_peer module
        class MockIPFSLibp2pPeer:
            def __init__(self, identity_path=None, bootstrap_peers=None, listen_addrs=None, role="leecher", 
                         enable_mdns=True, enable_hole_punching=False, enable_relay=False, tiered_storage_manager=None):
                self.identity_path = identity_path
                self.role = role
                self.logger = logging.getLogger(__name__)
                self.content_store = {}
                self.host = unittest.mock.MagicMock()
                self.host.get_id.return_value = "QmServerPeerId"
                self.host.get_addrs.return_value = ["test_addr"]
                # Explicitly set HAS_LIBP2P in initialization to avoid UnboundLocalError
                self._has_libp2p = True
            
            def get_peer_id(self):
                return "QmServerPeerId"
                
            def get_multiaddrs(self):
                return ["test_addr"]
                
            def connect_peer(self, peer_addr):
                return True
                
            def store_bytes(self, cid, data):
                self.content_store[cid] = data
                return True
                
            def get_stored_bytes(self, cid):
                return self.content_store.get(cid)
                
            def announce_content(self, cid, metadata=None):
                return True
                
            def request_content(self, cid, timeout=30):
                return self.content_store.get(cid, b"Mock content for " + cid.encode())
                
            def close(self):
                self.content_store = {}
                return None
        
        # Create minimal test components to avoid fixture dependency
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # This function will be called by pytest
        def main():
            # Use pytest to run just the one test
            exit_code = pytest.main([
                "-xvs",  # Verbose, exit on first failure
                "--log-cli-level=DEBUG",  # Show debug logs in console
                "--no-header",  # Skip header
                "--tb=native",  # Use native traceback format
                "test/test_mcp_communication.py::TestMCPServerCommunication::test_libp2p_communication"
            ])
            
            return exit_code
        
        # Run pytest
        return_code = main()
        logger.info(f"Test completed with return code: {return_code}")
        
    except Exception as e:
        logger.error(f"Error setting up test: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    run_test()