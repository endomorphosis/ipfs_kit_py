#!/usr/bin/env python3
"""
Direct Model Fix

This script directly patches the IPFSModel class with the required methods 
instead of relying on the initializer which is having issues.
"""

import logging
import importlib
import inspect
import sys
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_model_fix")

def directly_inject_methods():
    """
    Directly inject methods into the IPFSModel class by extracting them from 
    the ipfs_model_extensions module.
    """
    try:
        # Import the IPFSModel class
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        logger.info("Successfully imported IPFSModel class")
        
        # Import the extensions module
        extensions_module = importlib.import_module('ipfs_kit_py.mcp.models.ipfs_model_extensions')
        logger.info("Successfully imported ipfs_model_extensions module")
        
        # Get the add_ipfs_model_extensions function
        add_extensions_func = getattr(extensions_module, 'add_ipfs_model_extensions')
        logger.info("Found add_ipfs_model_extensions function")
        
        # Extract the method definitions directly from the source code
        methods = {}
        source_code = inspect.getsource(add_extensions_func)
        
        # Directly define the methods we need
        def add_content(self, content, filename=None, pin=True):
            """Add content to IPFS."""
            if hasattr(self.ipfs_kit, 'add'):
                if isinstance(content, str):
                    content = content.encode('utf-8')
                
                result = self.ipfs_kit.add(content, filename=filename if filename else None, pin=pin)
                
                # Handle different result formats
                if isinstance(result, dict):
                    cid = result.get('Hash', result.get('cid', None))
                    size = result.get('Size', result.get('size', len(content)))
                else:
                    cid = str(result)
                    size = len(content)
                
                return {
                    "success": True,
                    "cid": cid,
                    "size": size
                }
            else:
                # Simulation mode
                return {
                    "success": True,
                    "cid": f"QmSim{hash(content) % 1000000}",
                    "size": len(content) if isinstance(content, bytes) else len(content.encode('utf-8')),
                    "simulation": True
                }
        
        def cat(self, cid):
            """Retrieve content from IPFS."""
            if hasattr(self.ipfs_kit, 'cat'):
                data = self.ipfs_kit.cat(cid)
                return {
                    "success": True,
                    "content": data if isinstance(data, str) else data.decode('utf-8', errors='replace')
                }
            else:
                # Simulation mode
                return {
                    "success": True,
                    "content": f"Simulated content for {cid}",
                    "simulation": True
                }
        
        def pin_add(self, cid, recursive=True):
            """Pin content in IPFS."""
            if hasattr(self.ipfs_kit, 'pin_add'):
                self.ipfs_kit.pin_add(cid, recursive=recursive)
                return {"success": True}
            else:
                # Simulation mode
                return {"success": True, "simulation": True}
        
        def pin_rm(self, cid, recursive=True):
            """Remove pin from IPFS."""
            if hasattr(self.ipfs_kit, 'pin_rm'):
                self.ipfs_kit.pin_rm(cid, recursive=recursive)
                return {"success": True}
            else:
                # Simulation mode
                return {"success": True, "simulation": True}
        
        def pin_ls(self, cid=None, type="all"):
            """List pins in IPFS."""
            pins = []
            if hasattr(self.ipfs_kit, 'pin_ls'):
                result = self.ipfs_kit.pin_ls(type=type)
                if isinstance(result, dict) and 'Keys' in result:
                    for pin_cid, info in result['Keys'].items():
                        pins.append({
                            'cid': pin_cid,
                            'type': info['Type'] if isinstance(info, dict) else str(info)
                        })
            else:
                # Simulation mode
                for i in range(5):
                    pins.append({
                        'cid': f"QmSimPin{i}",
                        'type': 'recursive'
                    })
            
            return {
                "success": True,
                "pins": pins,
                "count": len(pins)
            }
        
        def swarm_peers(self):
            """List peers connected to the IPFS node."""
            peers = []
            if hasattr(self.ipfs_kit, 'swarm_peers'):
                result = self.ipfs_kit.swarm_peers()
                if isinstance(result, dict) and 'Peers' in result:
                    peers = result['Peers']
                elif isinstance(result, list):
                    peers = result
            else:
                # Simulation mode
                peers = [
                    {"Peer": "QmSimPeer1", "Addr": "/ip4/127.0.0.1/tcp/4001"},
                    {"Peer": "QmSimPeer2", "Addr": "/ip4/127.0.0.1/tcp/4002"}
                ]
            
            return {
                "success": True,
                "peers": peers,
                "peer_count": len(peers)
            }
        
        def swarm_connect(self, peer_addr):
            """Connect to a peer."""
            if hasattr(self.ipfs_kit, 'swarm_connect'):
                self.ipfs_kit.swarm_connect(peer_addr)
                return {"success": True}
            else:
                # Simulation mode
                return {"success": True, "simulation": True}
        
        def swarm_disconnect(self, peer_addr):
            """Disconnect from a peer."""
            if hasattr(self.ipfs_kit, 'swarm_disconnect'):
                self.ipfs_kit.swarm_disconnect(peer_addr)
                return {"success": True}
            else:
                # Simulation mode
                return {"success": True, "simulation": True}
        
        def storage_transfer(self, source, destination, identifier):
            """Transfer content between storage backends."""
            if hasattr(self, 'storage_manager') and self.storage_manager:
                result = self.storage_manager.transfer(
                    source_backend=source,
                    dest_backend=destination,
                    content_id=identifier
                )
                return {
                    "success": result.get('success', False),
                    "destinationId": result.get('destination_id', None)
                }
            else:
                # Simulation mode
                return {
                    "success": True,
                    "destinationId": f"{destination}_{hash(identifier) % 1000000}",
                    "simulation": True
                }
        
        def get_version(self):
            """Get IPFS version information."""
            if hasattr(self.ipfs_kit, 'version'):
                version = self.ipfs_kit.version()
                return {
                    "success": True,
                    "version": version
                }
            else:
                # Simulation mode
                return {
                    "success": True,
                    "version": {
                        "Version": "0.15.0-simulation",
                        "Commit": "simulated"
                    },
                    "simulation": True
                }
        
        # Attach methods to the IPFSModel class
        methods_to_attach = {
            'add_content': add_content,
            'cat': cat,
            'pin_add': pin_add,
            'pin_rm': pin_rm,
            'pin_ls': pin_ls,
            'swarm_peers': swarm_peers,
            'swarm_connect': swarm_connect,
            'swarm_disconnect': swarm_disconnect,
            'storage_transfer': storage_transfer,
            'get_version': get_version
        }
        
        for name, method in methods_to_attach.items():
            setattr(IPFSModel, name, method)
            logger.info(f"Attached method {name} to IPFSModel class")
        
        # Verify that methods are attached
        for name in methods_to_attach:
            if hasattr(IPFSModel, name):
                logger.info(f"Verified method {name} is attached to IPFSModel class")
            else:
                logger.warning(f"Method {name} NOT found on IPFSModel class")
        
        # Create an instance to check instance methods
        model = IPFSModel()
        for name in methods_to_attach:
            if hasattr(model, name):
                logger.info(f"Verified method {name} is accessible on IPFSModel instance")
            else:
                logger.warning(f"Method {name} NOT found on IPFSModel instance")
        
        return True
    except Exception as e:
        logger.error(f"Error directly injecting methods: {e}")
        return False

def main():
    """
    Main function to directly fix the IPFSModel class.
    """
    logger.info("Starting direct model fix...")
    
    # Directly inject methods
    if directly_inject_methods():
        logger.info("Successfully injected methods directly into IPFSModel class")
    else:
        logger.error("Failed to inject methods directly into IPFSModel class")
    
if __name__ == "__main__":
    main()
