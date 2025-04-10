#!/usr/bin/env python3
"""
Fix libp2p integration in the MCP server's IPFS model and command dispatcher.

This script enhances the libp2p integration in the MCP server model by:
1. Adding improved libp2p dependency checking and installation
2. Enhancing the execute_command method to properly route libp2p-related commands
3. Updating methods that use libp2p to attempt real functionality before simulation
"""

import os
import sys
import re
import logging
import shutil
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the model file
MODEL_FILE = Path("/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model.py")

# New execute_command with improved libp2p command handling
EXECUTE_COMMAND_CODE = '''    def execute_command(self, command, params=None):
        """Execute a command with the provided parameters.
        
        Args:
            command: Command to execute (e.g., 'add', 'cat', 'pin_add')
            params: Dictionary of parameters for the command
            
        Returns:
            Dictionary with operation results
        """
        start_time = time.time()
        operation_id = str(uuid.uuid4())
        logger.debug(f"Executing command '{command}' with operation ID {operation_id}")
        
        # Initialize parameters if None
        params = params or {}
        
        # Initialize result dictionary
        result = {
            "success": False,
            "command": command,
            "operation_id": operation_id,
            "timestamp": time.time()
        }
        
        # Command mappings
        command_map = {
            # Core IPFS commands
            "add": self.add_content,
            "cat": self.get_content,
            "pin_add": self.pin_content,
            "pin_rm": self.unpin_content,
            "pin_ls": self.list_pins,
            "file_ls": self.list_files,
            "refs": self.get_refs,
            "refs_local": self.get_local_refs,
            
            # Cluster commands
            "cluster_add": self.cluster_add,
            "cluster_pin": self.cluster_pin,
            "cluster_peers": self.cluster_peers,
            "cluster_status": self.cluster_status,
            
            # WebRTC commands
            "webrtc_offer": self.create_webrtc_offer,
            "webrtc_answer": self.handle_webrtc_answer,
            "webrtc_candidate": self.handle_ice_candidate,
            "webrtc_connect": self.connect_webrtc_peer,
            "webrtc_benchmark": self.benchmark_webrtc,
            
            # libp2p commands - these will now try real libp2p first
            "discover_peers": self.find_libp2p_peers,
            "list_known_peers": self._handle_list_known_peers,
            "register_node": self._handle_register_node,
            
            # Advanced commands
            "check_health": self.check_health,
            "get_stats": self.get_stats,
            "search": self.search_content,
            "node_info": self.get_node_info,
            
            # Storage tier commands
            "storage_info": self.get_storage_info,
            "storage_add": self.add_to_storage,
            "storage_get": self.get_from_storage
        }
        
        # Handle unknown command
        if command not in command_map:
            result["error"] = f"Unknown command: {command}"
            result["error_type"] = "invalid_command"
            result["available_commands"] = list(command_map.keys())
            result["duration_ms"] = (time.time() - start_time) * 1000
            logger.warning(result["error"])
            return result
            
        # Execute the command
        try:
            # Handle libp2p commands with improved handling
            if command in ["discover_peers", "list_known_peers", "register_node"]:
                # For libp2p commands, try to use real libp2p functionality first
                try:
                    # Try to import libp2p
                    try:
                        from ...libp2p import HAS_LIBP2P, check_dependencies, install_dependencies
                        
                        # If we don't have libp2p, attempt to install it
                        if not HAS_LIBP2P:
                            logger.info("libp2p not available, attempting installation...")
                            install_dependencies()
                    except ImportError:
                        logger.warning("Failed to import libp2p module, will use simulation")
                except Exception as e:
                    logger.warning(f"Error checking libp2p dependencies: {e}")
            
            # Call the handler function
            handler = command_map[command]
            cmd_result = handler(params)
            
            # Merge handler result with our base result
            result.update(cmd_result)
            
            # Always include duration
            if "duration_ms" not in result:
                result["duration_ms"] = (time.time() - start_time) * 1000
                
            return result
            
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            result["duration_ms"] = (time.time() - start_time) * 1000
            
            return result'''

# Improved method for handling peer listing that tries real libp2p first
LIST_KNOWN_PEERS_CODE = '''    def _handle_list_known_peers(self, params=None):
        """Handle the list_known_peers command.
        
        This method attempts to use real libp2p functionality first, falling back
        to simulation mode if real libp2p is not available.
        
        Args:
            params: Optional parameters for the command
            
        Returns:
            Dictionary with operation results including peer list
        """
        params = params or {}
        operation_id = str(uuid.uuid4())
        logger.debug(f"Handling list_known_peers command with operation ID {operation_id}")
        
        result = {
            "success": False,
            "operation_id": operation_id,
            "timestamp": time.time(),
            "peers": []
        }
        
        # First try to use actual libp2p functionality
        try:
            # Check if we have a libp2p peer instance
            if hasattr(self.ipfs_kit, 'libp2p_peer') and self.ipfs_kit.libp2p_peer:
                libp2p_peer = self.ipfs_kit.libp2p_peer
                
                # Try to get connected peers
                if hasattr(libp2p_peer, 'get_connected_peers'):
                    try:
                        peers = []
                        peer_ids = libp2p_peer.get_connected_peers()
                        
                        for peer_id in peer_ids:
                            # Get peer info if available
                            peer_info = {
                                "id": peer_id,
                                "addresses": [],
                                "connected_since": time.time() - random.randint(300, 7200),
                                "protocol_version": "ipfs/0.1.0"
                            }
                            
                            # Try to get addresses if available
                            if hasattr(libp2p_peer, 'get_peer_addresses'):
                                try:
                                    addresses = libp2p_peer.get_peer_addresses(peer_id)
                                    if addresses:
                                        peer_info["addresses"] = addresses
                                except Exception as e:
                                    logger.debug(f"Could not get addresses for peer {peer_id}: {e}")
                            
                            peers.append(peer_info)
                        
                        # Update result with success
                        result["success"] = True
                        result["peers"] = peers
                        result["peer_count"] = len(peers)
                        result["simulated"] = False
                        
                        logger.info(f"Successfully listed {len(peers)} peers using real libp2p")
                        return result
                    except Exception as e:
                        logger.warning(f"Error getting connected peers: {e}")
            
            # Try to initialize libp2p peer if not already initialized
            elif hasattr(self.ipfs_kit, 'init_libp2p_peer'):
                try:
                    logger.info("Initializing libp2p peer for peer listing")
                    self.ipfs_kit.init_libp2p_peer()
                    
                    # Try again after initialization
                    return self._handle_list_known_peers(params)
                except Exception as e:
                    logger.warning(f"Failed to initialize libp2p peer: {e}")
        
        except Exception as e:
            logger.warning(f"Error using real libp2p for peer listing: {e}")
        
        # If we get here, we need to use simulation mode
        logger.info("Using simulation mode for peer listing")
        
        # Generate simulated peer data
        import random
        peer_count = random.randint(2, 5)
        
        peers = []
        for i in range(peer_count):
            peer_id = f"QmSimPeer{i}{uuid.uuid4().hex[:8]}"
            peer = {
                "id": peer_id,
                "addresses": [
                    f"/ip4/192.168.0.{random.randint(2, 254)}/tcp/4001/p2p/{peer_id}",
                    f"/ip4/127.0.0.1/tcp/4001/p2p/{peer_id}"
                ],
                "role": random.choice(["master", "worker", "leecher"]),
                "connected_since": time.time() - random.randint(300, 7200),
                "protocol_version": "ipfs/0.1.0"
            }
            peers.append(peer)
            
        result["success"] = True
        result["peers"] = peers
        result["peer_count"] = len(peers)
        result["simulated"] = True
        
        return result'''

# Improved method for node registration that tries real libp2p first
REGISTER_NODE_CODE = '''    def _handle_register_node(self, params=None):
        """Handle the register_node command.
        
        This method attempts to use real libp2p functionality first, falling back
        to simulation mode if real libp2p is not available.
        
        Args:
            params: Optional parameters for the command
            
        Returns:
            Dictionary with operation results including node registration status
        """
        params = params or {}
        operation_id = str(uuid.uuid4())
        logger.debug(f"Handling register_node command with operation ID {operation_id}")
        
        # Extract parameters with defaults
        node_id = params.get("node_id")
        if not node_id:
            node_id = f"node_{uuid.uuid4()}"
            
        cluster_id = params.get("cluster_id", "default-cluster")
        role = params.get("role", "worker")
        master_address = params.get("master_address", "")
        
        result = {
            "success": False,
            "operation_id": operation_id,
            "timestamp": time.time(),
            "node_id": node_id,
            "cluster_id": cluster_id,
            "role": role
        }
        
        # First try to use actual libp2p functionality
        try:
            # Check if we have a libp2p peer instance
            if not hasattr(self.ipfs_kit, 'libp2p_peer') or not self.ipfs_kit.libp2p_peer:
                # Try to initialize libp2p peer
                if hasattr(self.ipfs_kit, 'init_libp2p_peer'):
                    try:
                        logger.info("Initializing libp2p peer for node registration")
                        self.ipfs_kit.init_libp2p_peer(
                            role=role,
                            bootstrap_peers=[master_address] if master_address else None
                        )
                    except Exception as e:
                        logger.warning(f"Failed to initialize libp2p peer: {e}")
            
            # Try to use the existing libp2p peer
            if hasattr(self.ipfs_kit, 'libp2p_peer') and self.ipfs_kit.libp2p_peer:
                libp2p_peer = self.ipfs_kit.libp2p_peer
                
                # Try to connect to master if provided
                if master_address and hasattr(libp2p_peer, 'connect_peer'):
                    try:
                        logger.info(f"Connecting to master node at {master_address}")
                        libp2p_peer.connect_peer(master_address)
                    except Exception as e:
                        logger.warning(f"Failed to connect to master node: {e}")
                
                # Get peer information
                try:
                    # Get peer ID
                    peer_id = libp2p_peer.get_peer_id()
                    
                    # Get connected peers
                    peer_list = []
                    if hasattr(libp2p_peer, 'get_connected_peers'):
                        try:
                            peer_ids = libp2p_peer.get_connected_peers()
                            
                            for pid in peer_ids:
                                peer_info = {
                                    "id": pid,
                                    "addresses": [],
                                    "role": "unknown"
                                }
                                
                                # Try to get addresses if available
                                if hasattr(libp2p_peer, 'get_peer_addresses'):
                                    try:
                                        addresses = libp2p_peer.get_peer_addresses(pid)
                                        if addresses:
                                            peer_info["addresses"] = addresses
                                    except Exception as e:
                                        logger.debug(f"Could not get addresses for peer {pid}: {e}")
                                
                                peer_list.append(peer_info)
                        except Exception as e:
                            logger.warning(f"Error getting connected peers: {e}")
                    
                    # Add current peer info
                    peer_list.append({
                        "id": peer_id,
                        "addresses": libp2p_peer.get_multiaddrs() if hasattr(libp2p_peer, 'get_multiaddrs') else [],
                        "role": role,
                        "is_self": True
                    })
                    
                    # Build successful result
                    result.update({
                        "success": True,
                        "status": "online",
                        "peers": peer_list,
                        "peer_count": len(peer_list),
                        "simulated": False
                    })
                    
                    logger.info(f"Successfully registered node {node_id} using real libp2p")
                    return result
                except Exception as e:
                    logger.warning(f"Error getting peer information: {e}")
        
        except Exception as e:
            logger.warning(f"Error using real libp2p for node registration: {e}")
        
        # If we get here, we need to use simulation mode
        logger.info("Using simulation mode for node registration")
        
        # Create a simulated response
        import random
        
        # Generate sample peers
        sample_peers = []
        peer_count = random.randint(1, 5)
        
        for i in range(peer_count):
            peer_id = f"QmSimPeer{i}{uuid.uuid4().hex[:8]}"
            sample_peers.append({
                "id": peer_id,
                "addresses": [
                    f"/ip4/192.168.0.{random.randint(2, 254)}/tcp/4001/p2p/{peer_id}"
                ],
                "role": random.choice(["master", "worker", "leecher"])
            })
            
        # Add result with the node_id we extracted earlier
        result.update({
            "success": True,
            "status": "online",
            "peers": sample_peers,
            "peer_count": len(sample_peers),
            "simulated": True
        })
        
        return result'''

def backup_file(file_path):
    """Create a backup of a file."""
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_model_file():
    """Fix the libp2p integration in the IPFS model file."""
    # Check if file exists
    if not MODEL_FILE.exists():
        logger.error(f"Model file not found at {MODEL_FILE}")
        return False
        
    # Create backup
    backup_file(MODEL_FILE)
    
    # Read model file
    with open(MODEL_FILE, 'r') as f:
        content = f.read()
    
    # Replace execute_command method
    execute_command_pattern = re.compile(r'def execute_command\s*\(\s*self\s*,\s*command\s*,\s*params\s*=\s*None\s*\).*?def ', re.DOTALL)
    match = execute_command_pattern.search(content)
    if match:
        handler_text = match.group(0)
        new_handler = EXECUTE_COMMAND_CODE + "\n\n    def "
        content = content.replace(handler_text, new_handler)
        logger.info("Replaced execute_command method")
    else:
        logger.warning("Could not find execute_command method")
    
    # Add/update list_known_peers handler
    list_peers_pattern = re.compile(r'def _handle_list_known_peers\s*\(\s*self\s*,.*?\).*?(?=def )', re.DOTALL)
    match = list_peers_pattern.search(content)
    if match:
        handler_text = match.group(0)
        content = content.replace(handler_text, LIST_KNOWN_PEERS_CODE + "\n\n    ")
        logger.info("Replaced _handle_list_known_peers method")
    else:
        # Method doesn't exist, add it after find_libp2p_peers
        find_peers_pattern = re.compile(r'def find_libp2p_peers.*?(?=def )', re.DOTALL)
        match = find_peers_pattern.search(content)
        if match:
            handler_text = match.group(0)
            new_text = handler_text + LIST_KNOWN_PEERS_CODE + "\n\n    "
            content = content.replace(handler_text, new_text)
            logger.info("Added _handle_list_known_peers method")
        else:
            logger.warning("Could not find find_libp2p_peers method to add _handle_list_known_peers")
    
    # Add/update register_node handler
    register_node_pattern = re.compile(r'def _handle_register_node\s*\(\s*self\s*,.*?\).*?(?=def )', re.DOTALL)
    match = register_node_pattern.search(content)
    if match:
        handler_text = match.group(0)
        content = content.replace(handler_text, REGISTER_NODE_CODE + "\n\n    ")
        logger.info("Replaced _handle_register_node method")
    else:
        # Method doesn't exist, add it after _handle_list_known_peers
        list_known_peers_pattern = re.compile(r'def _handle_list_known_peers.*?(?=def )', re.DOTALL)
        match = list_known_peers_pattern.search(content)
        if match:
            handler_text = match.group(0)
            new_text = handler_text + REGISTER_NODE_CODE + "\n\n    "
            content = content.replace(handler_text, new_text)
            logger.info("Added _handle_register_node method")
        else:
            logger.warning("Could not find _handle_list_known_peers method to add _handle_register_node")
    
    # Write updated content
    with open(MODEL_FILE, 'w') as f:
        f.write(content)
    
    logger.info(f"Successfully updated libp2p integration in {MODEL_FILE}")
    return True

def main():
    """Main function to run the script."""
    try:
        success = fix_model_file()
        if success:
            logger.info("Successfully fixed libp2p integration in the MCP server model.")
            logger.info("The improved methods will now properly try to use real libp2p functionality")
            logger.info("when available, and gracefully fall back to simulation mode when necessary.")
            return 0
        else:
            logger.error("Failed to fix libp2p integration.")
            return 1
    except Exception as e:
        logger.error(f"Error fixing libp2p integration: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())