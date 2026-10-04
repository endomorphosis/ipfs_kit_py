"""
AutoNAT protocol implementation for automatic NAT detection and traversal.

This module implements the AutoNAT protocol from libp2p, which helps peers
determine if they are behind a NAT and discover their public IP address.
It does this by periodically asking other peers to dial back and confirm
connectivity.

References:
- https://github.com/libp2p/specs/blob/master/autonat/README.md
"""

import anyio
import json
import logging
import random
import time
from typing import Dict, List, Optional, Set, Tuple, Any, Union

try:
    from multiaddr import Multiaddr
    HAS_MULTIADDR = True
except ImportError:
    HAS_MULTIADDR = False
    Multiaddr = object

try:
    import libp2p
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

class AutoNATError(Exception):
    """Base exception for AutoNAT errors."""
    pass

class AutoNAT:
    """
    AutoNAT protocol implementation for automatic NAT detection and traversal.
    
    This class implements the AutoNAT protocol to detect the type of NAT a peer
    is behind and determine reachability from the public internet. It does this
    by periodically asking other peers to dial back and confirm connectivity.
    """
    
    # Protocol ID for AutoNAT
    PROTOCOL_ID = "/libp2p/autonat/1.0.0"
    
    # Message types
    DIAL_BACK = 0x00
    DIAL_RESPONSE = 0x01
    
    # NAT status constants
    STATUS_UNKNOWN = "unknown"
    STATUS_PUBLIC = "public"
    STATUS_PRIVATE = "private"
    
    def __init__(self, host, max_peers_to_query=4, query_interval=300, throttle_interval=60):
        """
        Initialize the AutoNAT service.
        
        Args:
            host: The libp2p host
            max_peers_to_query: Maximum number of peers to query for each check
            query_interval: Interval in seconds between NAT checks
            throttle_interval: Minimum time between serving dial-back requests
        """
        if not HAS_LIBP2P:
            raise ImportError("AutoNAT requires libp2p to be installed")
            
        if not HAS_MULTIADDR:
            raise ImportError("AutoNAT requires multiaddr to be installed")
            
        self.host = host
        self.max_peers_to_query = max_peers_to_query
        self.query_interval = query_interval
        self.throttle_interval = throttle_interval
        self.logger = logging.getLogger("AutoNAT")
        
        # NAT status and public addresses
        self.nat_status = self.STATUS_UNKNOWN
        self.public_addresses = set()
        self.last_check_time = 0
        
        # Tracking peers that have helped with NAT detection
        self.peers_queried = set()
        self.peers_responded = set()
        
        # Request throttling
        self.last_request_time = {}
        
        # Task for periodic checking
        self.periodic_task = None
        self.running = False
        
    async def start(self):
        """Start the AutoNAT service."""
        if self.running:
            return
            
        self.running = True
        
        # Register protocol handler
        self.host.set_stream_handler(self.PROTOCOL_ID, self._handle_dial_back)
        
        # Start periodic checking
        self.periodic_task = anyio.create_task(self._periodic_check())
        self.logger.info("AutoNAT service started")
        
    async def stop(self):
        """Stop the AutoNAT service."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel periodic task
        if self.periodic_task:
            self.periodic_task.cancel()
            try:
                await self.periodic_task
            except anyio.CancelledError:
                pass
            self.periodic_task = None
            
        # Remove protocol handler
        self.host.remove_stream_handler(self.PROTOCOL_ID)
        self.logger.info("AutoNAT service stopped")
        
    async def _periodic_check(self):
        """Periodically check NAT status."""
        while self.running:
            try:
                await self.check_nat_status()
            except Exception as e:
                self.logger.error(f"Error checking NAT status: {e}")
                
            # Wait for next check
            await anyio.sleep(self.query_interval)
            
    async def check_nat_status(self):
        """
        Check the NAT status by requesting dial backs from remote peers.
        
        Returns:
            Dictionary with NAT status information
        """
        # Skip if too soon since last check
        if time.time() - self.last_check_time < self.query_interval / 2:
            return {
                "status": self.nat_status,
                "addresses": list(self.public_addresses),
                "time_since_last_check": time.time() - self.last_check_time
            }
        
        # Find peers to query
        peers = await self._get_peers_to_query()
        if not peers:
            self.logger.warning("No peers available to query for NAT status")
            return {
                "status": self.STATUS_UNKNOWN,
                "error": "No peers available to query"
            }
            
        # Query selected peers
        successful_responses = 0
        new_public_addresses = set()
        
        for peer_id in peers:
            try:
                result = await self._query_peer(peer_id)
                if result["reachable"]:
                    successful_responses += 1
                    if "address" in result:
                        new_public_addresses.add(result["address"])
                        
                self.peers_queried.add(peer_id)
                if result["responded"]:
                    self.peers_responded.add(peer_id)
                    
            except Exception as e:
                self.logger.warning(f"Error querying peer {peer_id}: {e}")
                
        # Update public addresses if any successful responses
        if successful_responses > 0:
            self.public_addresses = new_public_addresses
                
        # Determine NAT status based on responses
        if successful_responses > 0:
            self.nat_status = self.STATUS_PUBLIC
            self.logger.info(f"NAT status: public, addresses: {self.public_addresses}")
        else:
            self.nat_status = self.STATUS_PRIVATE
            self.logger.info("NAT status: private (not directly reachable)")
            
        self.last_check_time = time.time()
        
        return {
            "status": self.nat_status,
            "addresses": list(self.public_addresses),
            "successful_queries": successful_responses,
            "total_queries": len(peers)
        }
            
    async def _get_peers_to_query(self):
        """
        Get a list of peers to query for NAT status.
        
        Returns:
            List of peer IDs to query
        """
        # Get connected peers
        peers = self.host.get_network().get_peers()
        
        # Filter out peers we've recently queried
        available_peers = [p for p in peers if p not in self.peers_queried]
        
        # Prioritize peers that have successfully responded in the past
        prioritized_peers = [p for p in available_peers if p in self.peers_responded]
        
        # Select peers to query (prioritizing responsive peers)
        selected_peers = []
        if len(prioritized_peers) >= self.max_peers_to_query:
            selected_peers = random.sample(prioritized_peers, self.max_peers_to_query)
        else:
            selected_peers = prioritized_peers.copy()
            remaining = self.max_peers_to_query - len(selected_peers)
            if remaining > 0 and len(available_peers) > len(prioritized_peers):
                remaining_peers = [p for p in available_peers if p not in prioritized_peers]
                selected_peers.extend(random.sample(remaining_peers, min(remaining, len(remaining_peers))))
                
        return selected_peers
        
    async def _query_peer(self, peer_id):
        """
        Query a peer to dial back and check reachability.
        
        Args:
            peer_id: ID of the peer to query
            
        Returns:
            Dictionary with query results
        """
        result = {
            "peer_id": peer_id,
            "reachable": False,
            "responded": False,
            "address": None
        }
        
        try:
            # Open a stream to the peer
            stream = await self.host.new_stream(peer_id, [self.PROTOCOL_ID])
            
            # Get our own addresses to send
            observation_addrs = []
            for addr in self.host.get_addrs():
                # Skip local and loopback addresses
                if "/ip4/127.0.0.1/" in str(addr) or "/ip4/192.168." in str(addr) or "/ip4/10." in str(addr):
                    continue
                observation_addrs.append(str(addr))
                
            if not observation_addrs:
                self.logger.warning("No suitable addresses to send for dial-back")
                return result
                
            # Create dial-back request
            request = {
                "type": self.DIAL_BACK,
                "addresses": observation_addrs,
                "peer_id": str(self.host.get_id())
            }
            
            # Send request
            await stream.write(json.dumps(request).encode() + b"\n")
            
            # Wait for response
            response_data = await stream.read(1024)
            if not response_data:
                return result
                
            # Parse response
            response = json.loads(response_data.decode())
            result["responded"] = True
            
            if response.get("status") == "success":
                result["reachable"] = True
                if "address" in response:
                    result["address"] = response["address"]
                    
            await stream.close()
            
        except Exception as e:
            self.logger.warning(f"Error during dial-back query to {peer_id}: {e}")
            
        return result
        
    async def _handle_dial_back(self, stream):
        """
        Handle a dial-back request from another peer.
        
        This method is called when a remote peer wants us to attempt to dial them
        to determine if they are publicly reachable.
        """
        peer_id = stream.get_protocol()
        
        # Check if we're throttling requests from this peer
        current_time = time.time()
        if peer_id in self.last_request_time:
            time_since_last = current_time - self.last_request_time[peer_id]
            if time_since_last < self.throttle_interval:
                self.logger.debug(f"Throttling dial-back request from {peer_id}: too frequent")
                response = {
                    "status": "error",
                    "error": "too_frequent",
                    "retry_after": self.throttle_interval - time_since_last
                }
                await stream.write(json.dumps(response).encode() + b"\n")
                await stream.close()
                return
                
        # Update last request time
        self.last_request_time[peer_id] = current_time
        
        try:
            # Read request
            request_data = await stream.read(1024)
            if not request_data:
                await stream.close()
                return
                
            request = json.loads(request_data.decode())
            
            # Validate request
            if request.get("type") != self.DIAL_BACK or "addresses" not in request:
                response = {
                    "status": "error",
                    "error": "invalid_request"
                }
                await stream.write(json.dumps(response).encode() + b"\n")
                await stream.close()
                return
                
            # Try to dial back to the peer on each provided address
            success = False
            used_address = None
            
            for addr_str in request["addresses"]:
                try:
                    # Parse the address
                    addr = Multiaddr(addr_str)
                    
                    # Try to dial this address
                    dial_result = await self._try_dial(addr)
                    if dial_result:
                        success = True
                        used_address = addr_str
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Error dialing back to {addr_str}: {e}")
                    
            # Send response
            response = {
                "type": self.DIAL_RESPONSE,
                "status": "success" if success else "error",
                "error": None if success else "not_reachable"
            }
            if success and used_address:
                response["address"] = used_address
                
            await stream.write(json.dumps(response).encode() + b"\n")
            await stream.close()
            
        except Exception as e:
            self.logger.warning(f"Error handling dial-back request: {e}")
            try:
                response = {
                    "status": "error",
                    "error": str(e)
                }
                await stream.write(json.dumps(response).encode() + b"\n")
                await stream.close()
            except:
                pass
                
    async def _try_dial(self, addr):
        """
        Try to dial an address to check reachability.
        
        Args:
            addr: Multiaddress to dial
            
        Returns:
            True if dial was successful, False otherwise
        """
        try:
            # Extract peer ID from the address
            peer_id = None
            addr_str = str(addr)
            
            # Get the peer ID from the address if it's available
            for proto in addr.protocols():
                if proto.name == 'p2p' or proto.name == 'ipfs':
                    peer_id = addr.value_for_protocol(proto.name)
                    break
                    
            if not peer_id:
                self.logger.debug(f"No peer ID in address {addr_str}")
                return False
                
            # Create a temporary stream to test connectivity
            # Try with a simple protocol like ping
            ping_protocol = "/ipfs/ping/1.0.0"
            dial_timeout = 5  # seconds
            
            try:
                # Try to open a stream with timeout
                stream = await anyio.wait_for(
                    self.host.new_stream(peer_id, [ping_protocol], [addr]),
                    timeout=dial_timeout
                )
                
                if stream:
                    await stream.close()
                    return True
                
            except anyio.TimeoutError:
                self.logger.debug(f"Timeout dialing {addr_str}")
                return False
                
            return False
            
        except Exception as e:
            self.logger.debug(f"Dial-back failed: {e}")
            return False
    
    def get_nat_status(self):
        """
        Get the current NAT status.
        
        Returns:
            Dictionary with NAT status information
        """
        return {
            "status": self.nat_status,
            "addresses": list(self.public_addresses),
            "last_check_time": self.last_check_time,
            "time_since_check": time.time() - self.last_check_time
        }

# Utility function to check if AutoNAT is available
def is_autonat_available():
    """Check if AutoNAT support is available."""
    return HAS_LIBP2P and HAS_MULTIADDR