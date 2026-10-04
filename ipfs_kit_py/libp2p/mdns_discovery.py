"""
mDNS (Multicast DNS) peer discovery implementation.

This module implements mDNS-based peer discovery for local network environments.
Peers broadcast their presence on the local network using multicast DNS,
allowing automatic discovery without any infrastructure.

Key features:
- Zero-configuration peer discovery
- Works on local networks only
- Fast discovery (typically < 1 second)
- No bootstrap nodes required
- Useful for development and private networks

References:
- https://github.com/libp2p/specs/blob/master/discovery/mdns.md
- RFC 6762: Multicast DNS
"""

import anyio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any, Tuple

logger = logging.getLogger(__name__)


# mDNS constants
MDNS_ADDR = "224.0.0.251"
MDNS_ADDR_V6 = "ff02::fb"
MDNS_PORT = 5353
SERVICE_NAME = "_p2p._udp.local."


@dataclass
class MDNSPeer:
    """Represents a peer discovered via mDNS."""
    peer_id: str
    addresses: List[str] = field(default_factory=list)
    service_name: str = ""
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    def is_stale(self, ttl: float) -> bool:
        """Check if peer info is stale."""
        return (time.time() - self.last_seen) > ttl
    
    def update_seen(self):
        """Update last seen timestamp."""
        self.last_seen = time.time()


class MDNSService:
    """
    mDNS service for local peer discovery.
    
    This class implements mDNS-based peer discovery using multicast DNS
    to announce and discover peers on the local network.
    """
    
    def __init__(
        self,
        host,
        service_name: str = "libp2p",
        query_interval: float = 60.0,
        peer_ttl: float = 300.0,
        on_peer_discovered: Optional[Callable[[MDNSPeer], None]] = None
    ):
        """
        Initialize mDNS service.
        
        Args:
            host: The libp2p host
            service_name: Service name for discovery
            query_interval: Interval in seconds between queries
            peer_ttl: Time-to-live for peer information
            on_peer_discovered: Callback for when new peer is discovered
        """
        self.host = host
        self.service_name = service_name
        self.query_interval = query_interval
        self.peer_ttl = peer_ttl
        self.on_peer_discovered = on_peer_discovered
        
        self.discovered_peers: Dict[str, MDNSPeer] = {}
        self.sock_v4: Optional[socket.socket] = None
        self.sock_v6: Optional[socket.socket] = None
        
        self.logger = logging.getLogger("MDNSService")
        self._running = False
        self._task_group = None
    
    async def start(self):
        """Start the mDNS service."""
        if self._running:
            return
        
        self._running = True
        
        # Setup multicast sockets
        await self._setup_sockets()
        
        # Start service loops
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            tg.start_soon(self._query_loop)
            tg.start_soon(self._listen_loop_v4)
            if self.sock_v6:
                tg.start_soon(self._listen_loop_v6)
            tg.start_soon(self._cleanup_loop)
        
        self.logger.info(f"mDNS service started (service: {self.service_name})")
    
    async def stop(self):
        """Stop the mDNS service."""
        self._running = False
        
        # Close sockets
        if self.sock_v4:
            self.sock_v4.close()
            self.sock_v4 = None
        
        if self.sock_v6:
            self.sock_v6.close()
            self.sock_v6 = None
        
        self.logger.info("mDNS service stopped")
    
    async def _setup_sockets(self):
        """Setup multicast sockets for mDNS."""
        # IPv4 socket
        try:
            self.sock_v4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock_v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Allow multiple listeners
            try:
                self.sock_v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                pass  # SO_REUSEPORT not available on all platforms
            
            # Bind to mDNS port
            self.sock_v4.bind(('', MDNS_PORT))
            
            # Join multicast group
            mreq = struct.pack("4sl", socket.inet_aton(MDNS_ADDR), socket.INADDR_ANY)
            self.sock_v4.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Set TTL
            self.sock_v4.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            
            # Non-blocking
            self.sock_v4.setblocking(False)
            
            self.logger.debug("IPv4 mDNS socket setup complete")
            
        except Exception as e:
            self.logger.error(f"Failed to setup IPv4 socket: {e}")
            self.sock_v4 = None
        
        # IPv6 socket
        try:
            if socket.has_ipv6:
                self.sock_v6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                self.sock_v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                try:
                    self.sock_v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except AttributeError:
                    pass
                
                self.sock_v6.bind(('', MDNS_PORT))
                
                # Join IPv6 multicast group
                mreq = socket.inet_pton(socket.AF_INET6, MDNS_ADDR_V6) + struct.pack('@I', 0)
                self.sock_v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                
                self.sock_v6.setblocking(False)
                
                self.logger.debug("IPv6 mDNS socket setup complete")
        except Exception as e:
            self.logger.debug(f"IPv6 socket not available: {e}")
            self.sock_v6 = None
    
    async def _query_loop(self):
        """Periodically send mDNS queries."""
        while self._running:
            try:
                await self._send_query()
                await anyio.sleep(self.query_interval)
            except Exception as e:
                self.logger.error(f"Error in query loop: {e}")
                await anyio.sleep(self.query_interval)
    
    async def _send_query(self):
        """Send an mDNS query for libp2p peers."""
        query = self._build_query()
        
        # Send on IPv4
        if self.sock_v4:
            try:
                self.sock_v4.sendto(query, (MDNS_ADDR, MDNS_PORT))
                self.logger.debug("Sent mDNS query (IPv4)")
            except Exception as e:
                self.logger.error(f"Failed to send IPv4 query: {e}")
        
        # Send on IPv6
        if self.sock_v6:
            try:
                self.sock_v6.sendto(query, (MDNS_ADDR_V6, MDNS_PORT))
                self.logger.debug("Sent mDNS query (IPv6)")
            except Exception as e:
                self.logger.error(f"Failed to send IPv6 query: {e}")
    
    def _build_query(self) -> bytes:
        """Build an mDNS query packet."""
        # Simple DNS query structure
        # Transaction ID: 0x0000
        # Flags: 0x0000 (standard query)
        # Questions: 1
        # Answer RRs: 0
        # Authority RRs: 0
        # Additional RRs: 0
        
        query = bytearray()
        
        # Header
        query.extend(b'\x00\x00')  # Transaction ID
        query.extend(b'\x00\x00')  # Flags
        query.extend(b'\x00\x01')  # Questions
        query.extend(b'\x00\x00')  # Answer RRs
        query.extend(b'\x00\x00')  # Authority RRs
        query.extend(b'\x00\x00')  # Additional RRs
        
        # Question: _p2p._udp.local PTR
        query.extend(self._encode_name(SERVICE_NAME))
        query.extend(b'\x00\x0c')  # Type: PTR
        query.extend(b'\x00\x01')  # Class: IN
        
        return bytes(query)
    
    def _encode_name(self, name: str) -> bytes:
        """Encode a DNS name."""
        parts = name.rstrip('.').split('.')
        encoded = bytearray()
        
        for part in parts:
            encoded.append(len(part))
            encoded.extend(part.encode('ascii'))
        
        encoded.append(0)  # Null terminator
        return bytes(encoded)
    
    async def _listen_loop_v4(self):
        """Listen for mDNS responses on IPv4."""
        if not self.sock_v4:
            return
        
        while self._running:
            try:
                # Use anyio socket wrapper for async I/O
                data, addr = await anyio.to_thread.run_sync(
                    lambda: self.sock_v4.recvfrom(4096)
                )
                
                await self._handle_packet(data, addr)
                
            except socket.error:
                await anyio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in IPv4 listen loop: {e}")
                await anyio.sleep(1)
    
    async def _listen_loop_v6(self):
        """Listen for mDNS responses on IPv6."""
        if not self.sock_v6:
            return
        
        while self._running:
            try:
                data, addr = await anyio.to_thread.run_sync(
                    lambda: self.sock_v6.recvfrom(4096)
                )
                
                await self._handle_packet(data, addr)
                
            except socket.error:
                await anyio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in IPv6 listen loop: {e}")
                await anyio.sleep(1)
    
    async def _handle_packet(self, data: bytes, addr: Tuple):
        """Handle an incoming mDNS packet."""
        try:
            # Parse DNS packet
            response = self._parse_response(data)
            
            if not response:
                return
            
            # Extract peer information
            peer_id = response.get('peer_id')
            addresses = response.get('addresses', [])
            
            if not peer_id:
                return
            
            # Don't process our own announcements
            our_id = str(self.host.get_id()) if hasattr(self.host, 'get_id') else None
            if peer_id == our_id:
                return
            
            # Check if we already know this peer
            if peer_id in self.discovered_peers:
                peer = self.discovered_peers[peer_id]
                peer.update_seen()
                
                # Update addresses if changed
                if set(addresses) != set(peer.addresses):
                    peer.addresses = addresses
                    self.logger.debug(f"Updated addresses for peer {peer_id}")
            else:
                # New peer discovered
                peer = MDNSPeer(
                    peer_id=peer_id,
                    addresses=addresses,
                    service_name=self.service_name
                )
                
                self.discovered_peers[peer_id] = peer
                self.logger.info(f"Discovered peer via mDNS: {peer_id}")
                
                # Call discovery callback
                if self.on_peer_discovered:
                    try:
                        self.on_peer_discovered(peer)
                    except Exception as e:
                        self.logger.error(f"Error in discovery callback: {e}")
                
                # Optionally auto-connect
                if hasattr(self, 'auto_connect') and self.auto_connect:
                    await self._connect_to_peer(peer)
                    
        except Exception as e:
            self.logger.error(f"Error handling mDNS packet: {e}")
    
    def _parse_response(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse an mDNS response packet."""
        # This is a simplified parser
        # A full implementation would properly parse all DNS records
        
        try:
            if len(data) < 12:
                return None
            
            # Skip header (12 bytes)
            offset = 12
            
            # Parse questions
            num_questions = struct.unpack('!H', data[4:6])[0]
            for _ in range(num_questions):
                # Skip question
                while offset < len(data) and data[offset] != 0:
                    length = data[offset]
                    offset += 1 + length
                offset += 5  # Null terminator + type + class
            
            # Parse answers
            num_answers = struct.unpack('!H', data[6:8])[0]
            
            peer_info = {}
            
            for _ in range(num_answers):
                if offset >= len(data):
                    break
                
                # Parse name (simplified - assumes no compression)
                name_parts = []
                while offset < len(data) and data[offset] != 0:
                    length = data[offset]
                    offset += 1
                    if length > 0 and offset + length <= len(data):
                        name_parts.append(data[offset:offset+length].decode('ascii'))
                        offset += length
                offset += 1  # Null terminator
                
                if offset + 10 > len(data):
                    break
                
                # Type, class, TTL, data length
                rtype = struct.unpack('!H', data[offset:offset+2])[0]
                offset += 2
                rclass = struct.unpack('!H', data[offset:offset+2])[0]
                offset += 2
                ttl = struct.unpack('!I', data[offset:offset+4])[0]
                offset += 4
                data_length = struct.unpack('!H', data[offset:offset+2])[0]
                offset += 2
                
                # Extract record data
                if offset + data_length <= len(data):
                    record_data = data[offset:offset+data_length]
                    offset += data_length
                    
                    # Extract peer information from TXT records
                    if rtype == 16:  # TXT record
                        txt_data = self._parse_txt_record(record_data)
                        peer_info.update(txt_data)
            
            return peer_info if peer_info else None
            
        except Exception as e:
            self.logger.debug(f"Error parsing mDNS response: {e}")
            return None
    
    def _parse_txt_record(self, data: bytes) -> Dict[str, Any]:
        """Parse TXT record data."""
        result = {}
        offset = 0
        
        while offset < len(data):
            length = data[offset]
            offset += 1
            
            if length == 0 or offset + length > len(data):
                break
            
            txt = data[offset:offset+length].decode('utf-8', errors='ignore')
            offset += length
            
            if '=' in txt:
                key, value = txt.split('=', 1)
                result[key] = value
        
        return result
    
    async def _connect_to_peer(self, peer: MDNSPeer):
        """Attempt to connect to a discovered peer."""
        for addr in peer.addresses:
            try:
                if hasattr(self.host, 'connect'):
                    await self.host.connect(addr)
                    self.logger.info(f"Connected to mDNS peer {peer.peer_id}")
                    return
            except Exception as e:
                self.logger.debug(f"Failed to connect to {peer.peer_id} at {addr}: {e}")
    
    async def _cleanup_loop(self):
        """Periodically cleanup stale peer information."""
        while self._running:
            try:
                await anyio.sleep(60)  # Cleanup every minute
                
                stale_peers = [
                    peer_id for peer_id, peer in self.discovered_peers.items()
                    if peer.is_stale(self.peer_ttl)
                ]
                
                for peer_id in stale_peers:
                    del self.discovered_peers[peer_id]
                    self.logger.debug(f"Removed stale mDNS peer: {peer_id}")
                    
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    def get_discovered_peers(self) -> List[MDNSPeer]:
        """Get list of discovered peers."""
        return list(self.discovered_peers.values())
    
    def get_peer_by_id(self, peer_id: str) -> Optional[MDNSPeer]:
        """Get a specific peer by ID."""
        return self.discovered_peers.get(peer_id)


def integrate_mdns_discovery(host, **kwargs):
    """
    Convenience function to integrate mDNS discovery with a libp2p host.
    
    Args:
        host: The libp2p host
        **kwargs: Arguments to pass to MDNSService
        
    Returns:
        MDNSService instance
    """
    service = MDNSService(host, **kwargs)
    
    # Add service as an attribute to the host
    if not hasattr(host, '_mdns_service'):
        host._mdns_service = service
    
    return service
