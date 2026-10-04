"""
Protocol Extensions for libp2p Integration with MCP Server.

This module provides advanced protocol extensions for libp2p, including:
1. Enhanced content discovery mechanisms
2. Direct file transfer protocols
3. Custom MCP-specific protocols for efficient communication
4. Metrics collection for protocol usage
"""

import os
import sys
import time
import anyio
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Protocol identifiers
PROTOCOLS = {
    "MCP_SYNC": "/ipfs-kit/mcp/sync/1.0.0",
    "MCP_QUERY": "/ipfs-kit/mcp/query/1.0.0",
    "MCP_EXCHANGE": "/ipfs-kit/mcp/exchange/1.0.0",
    "MCP_STATUS": "/ipfs-kit/mcp/status/1.0.0",
    "MCP_METRICS": "/ipfs-kit/mcp/metrics/1.0.0",
    "DIRECT_TRANSFER": "/ipfs-kit/transfer/1.0.0",
    "ENHANCED_DISCOVERY": "/ipfs-kit/discovery/1.0.0",
    "CONTENT_ATTESTATION": "/ipfs-kit/content/attest/1.0.0",
}

class ProtocolMetrics:
    """Track metrics for protocol usage."""
    
    def __init__(self):
        """Initialize the protocol metrics."""
        self.metrics = {
            "requests_sent": 0,
            "requests_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "successful_exchanges": 0,
            "failed_exchanges": 0,
            "protocol_errors": 0,
            "avg_response_time_ms": 0,
            "start_time": time.time(),
            "protocols": {},
            "peers": {},
        }
        
        # Initialize per-protocol metrics
        for protocol_id in PROTOCOLS.values():
            self.metrics["protocols"][protocol_id] = {
                "requests_sent": 0,
                "requests_received": 0,
                "bytes_sent": 0,
                "bytes_received": 0,
                "successful_exchanges": 0,
                "failed_exchanges": 0,
            }
    
    def record_request_sent(self, protocol_id: str, peer_id: str, size_bytes: int = 0):
        """
        Record a request sent using a protocol.
        
        Args:
            protocol_id: The protocol identifier
            peer_id: The peer ID that received the request
            size_bytes: The size of the request in bytes
        """
        self.metrics["requests_sent"] += 1
        self.metrics["bytes_sent"] += size_bytes
        
        # Update protocol-specific metrics
        if protocol_id in self.metrics["protocols"]:
            self.metrics["protocols"][protocol_id]["requests_sent"] += 1
            self.metrics["protocols"][protocol_id]["bytes_sent"] += size_bytes
        
        # Update peer-specific metrics
        if peer_id not in self.metrics["peers"]:
            self.metrics["peers"][peer_id] = {
                "requests_sent": 0,
                "requests_received": 0,
                "bytes_sent": 0,
                "bytes_received": 0,
                "successful_exchanges": 0,
                "failed_exchanges": 0,
                "last_seen": time.time(),
            }
        
        self.metrics["peers"][peer_id]["requests_sent"] += 1
        self.metrics["peers"][peer_id]["bytes_sent"] += size_bytes
        self.metrics["peers"][peer_id]["last_seen"] = time.time()
    
    def record_request_received(self, protocol_id: str, peer_id: str, size_bytes: int = 0):
        """
        Record a request received using a protocol.
        
        Args:
            protocol_id: The protocol identifier
            peer_id: The peer ID that sent the request
            size_bytes: The size of the request in bytes
        """
        self.metrics["requests_received"] += 1
        self.metrics["bytes_received"] += size_bytes
        
        # Update protocol-specific metrics
        if protocol_id in self.metrics["protocols"]:
            self.metrics["protocols"][protocol_id]["requests_received"] += 1
            self.metrics["protocols"][protocol_id]["bytes_received"] += size_bytes
        
        # Update peer-specific metrics
        if peer_id not in self.metrics["peers"]:
            self.metrics["peers"][peer_id] = {
                "requests_sent": 0,
                "requests_received": 0,
                "bytes_sent": 0,
                "bytes_received": 0,
                "successful_exchanges": 0,
                "failed_exchanges": 0,
                "last_seen": time.time(),
            }
        
        self.metrics["peers"][peer_id]["requests_received"] += 1
        self.metrics["peers"][peer_id]["bytes_received"] += size_bytes
        self.metrics["peers"][peer_id]["last_seen"] = time.time()
    
    def record_successful_exchange(self, protocol_id: str, peer_id: str, response_time_ms: float = 0):
        """
        Record a successful exchange using a protocol.
        
        Args:
            protocol_id: The protocol identifier
            peer_id: The peer ID involved in the exchange
            response_time_ms: The response time in milliseconds
        """
        self.metrics["successful_exchanges"] += 1
        
        # Update average response time
        current_avg = self.metrics["avg_response_time_ms"]
        current_count = self.metrics["successful_exchanges"]
        
        if current_count > 1:
            # Use exponential moving average
            self.metrics["avg_response_time_ms"] = (0.9 * current_avg) + (0.1 * response_time_ms)
        else:
            self.metrics["avg_response_time_ms"] = response_time_ms
        
        # Update protocol-specific metrics
        if protocol_id in self.metrics["protocols"]:
            self.metrics["protocols"][protocol_id]["successful_exchanges"] += 1
        
        # Update peer-specific metrics
        if peer_id in self.metrics["peers"]:
            self.metrics["peers"][peer_id]["successful_exchanges"] += 1
            self.metrics["peers"][peer_id]["last_seen"] = time.time()
    
    def record_failed_exchange(self, protocol_id: str, peer_id: str, error_type: str = "unknown"):
        """
        Record a failed exchange using a protocol.
        
        Args:
            protocol_id: The protocol identifier
            peer_id: The peer ID involved in the exchange
            error_type: Type of error that occurred
        """
        self.metrics["failed_exchanges"] += 1
        
        # Update protocol-specific metrics
        if protocol_id in self.metrics["protocols"]:
            self.metrics["protocols"][protocol_id]["failed_exchanges"] += 1
        
        # Update peer-specific metrics
        if peer_id in self.metrics["peers"]:
            self.metrics["peers"][peer_id]["failed_exchanges"] += 1
            self.metrics["peers"][peer_id]["last_seen"] = time.time()
        
        # Track protocol errors
        if error_type == "protocol":
            self.metrics["protocol_errors"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get the current metrics.
        
        Returns:
            Dict containing all metrics
        """
        metrics_copy = self.metrics.copy()
        metrics_copy["uptime"] = time.time() - self.metrics["start_time"]
        return metrics_copy
    
    def reset_metrics(self):
        """Reset all metrics to their initial values."""
        start_time = self.metrics["start_time"]  # Preserve start time
        self.__init__()
        self.metrics["start_time"] = start_time


class MCPSyncProtocolHandler:
    """
    Handler for the MCP Sync protocol.
    
    This protocol enables MCP servers to synchronize their state,
    including content availability, peer lists, and configuration.
    """
    
    def __init__(self, peer, metrics=None):
        """
        Initialize the MCP Sync protocol handler.
        
        Args:
            peer: The libp2p peer instance
            metrics: Optional ProtocolMetrics instance for tracking metrics
        """
        self.peer = peer
        self.protocol_id = PROTOCOLS["MCP_SYNC"]
        self.metrics = metrics or ProtocolMetrics()
        
        # State tracking
        self.last_sync = {}  # Map of peer_id to last sync time
        
        # Register protocol handler with the peer
        if hasattr(peer, "register_protocol_handler") and callable(peer.register_protocol_handler):
            self.peer.register_protocol_handler(self.protocol_id, self._handle_sync_request)
            logger.debug(f"Registered handler for {self.protocol_id}")
    
    async def _handle_sync_request(self, stream):
        """
        Handle incoming sync requests.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Read request data
            data = await stream.read()
            request = json.loads(data.decode('utf-8'))
            
            # Record metrics
            peer_id = request.get("peer_id", "unknown")
            self.metrics.record_request_received(self.protocol_id, peer_id, len(data))
            
            # Process the sync request
            sync_type = request.get("type", "full")
            response = await self._process_sync_request(request, sync_type)
            
            # Send response
            response_data = json.dumps(response).encode('utf-8')
            await stream.write(response_data)
            
            # Record successful exchange
            self.metrics.record_successful_exchange(
                self.protocol_id,
                peer_id,
                (time.time() - request.get("timestamp", time.time())) * 1000  # ms
            )
            
            # Update last sync time
            self.last_sync[peer_id] = time.time()
            
        except Exception as e:
            logger.error(f"Error handling sync request: {e}")
            self.metrics.record_failed_exchange(self.protocol_id, "unknown", "protocol")
            
            # Try to send error response
            try:
                error_response = json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time()
                }).encode('utf-8')
                await stream.write(error_response)
            except Exception:
                pass
    
    async def _process_sync_request(self, request, sync_type):
        """
        Process a sync request and generate a response.
        
        Args:
            request: The sync request data
            sync_type: Type of sync ('full', 'diff', or 'config')
            
        Returns:
            Dict containing the sync response
        """
        response = {
            "success": True,
            "type": sync_type,
            "timestamp": time.time(),
            "peer_id": self.peer.get_peer_id()
        }
        
        if sync_type == "full":
            # Full sync includes everything
            response.update({
                "content_available": await self._get_available_content(),
                "connected_peers": self._get_connected_peers(),
                "config": self._get_config()
            })
        elif sync_type == "diff":
            # Differential sync includes only changes since last sync
            last_sync_time = request.get("last_sync_time", 0)
            response.update({
                "content_changes": await self._get_content_changes(last_sync_time),
                "peer_changes": self._get_peer_changes(last_sync_time)
            })
        elif sync_type == "config":
            # Config sync includes only configuration
            response["config"] = self._get_config()
        
        return response
    
    async def _get_available_content(self):
        """Get list of available content CIDs."""
        if hasattr(self.peer, "get_stored_content"):
            return await self.peer.get_stored_content()
        return []
    
    async def _get_content_changes(self, since_time):
        """Get content changes since a specific time."""
        if hasattr(self.peer, "get_content_changes"):
            return await self.peer.get_content_changes(since_time)
        return []
    
    def _get_connected_peers(self):
        """Get list of connected peers."""
        if hasattr(self.peer, "get_connected_peers"):
            return self.peer.get_connected_peers()
        return []
    
    def _get_peer_changes(self, since_time):
        """Get peer connection changes since a specific time."""
        if hasattr(self.peer, "get_peer_changes"):
            return self.peer.get_peer_changes(since_time)
        return []
    
    def _get_config(self):
        """Get shareable configuration information."""
        config = {}
        
        # Only include safe configuration items
        if hasattr(self.peer, "role"):
            config["role"] = self.peer.role
        
        if hasattr(self.peer, "protocols"):
            config["supported_protocols"] = list(
                p for p in self.peer.protocols if not p.startswith("_")
            )
        
        return config
    
    async def sync_with_peer(self, peer_id, sync_type="full"):
        """
        Sync with a specific peer.
        
        Args:
            peer_id: The peer to sync with
            sync_type: Type of sync to perform
            
        Returns:
            Dict with sync results
        """
        try:
            # Create sync request
            request = {
                "type": sync_type,
                "timestamp": time.time(),
                "peer_id": self.peer.get_peer_id()
            }
            
            # Add last sync time for differential syncs
            if sync_type == "diff" and peer_id in self.last_sync:
                request["last_sync_time"] = self.last_sync[peer_id]
            
            # Serialize request
            request_data = json.dumps(request).encode('utf-8')
            
            # Record request metrics
            self.metrics.record_request_sent(self.protocol_id, peer_id, len(request_data))
            
            # Open stream and send request
            if hasattr(self.peer, "open_protocol_stream") and callable(self.peer.open_protocol_stream):
                async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                    # Send request
                    await stream.write(request_data)
                    
                    # Receive response
                    response_data = await stream.read()
                    response = json.loads(response_data.decode('utf-8'))
                    
                    # Record metrics
                    self.metrics.record_request_received(
                        self.protocol_id, 
                        peer_id, 
                        len(response_data)
                    )
                    
                    if response.get("success", False):
                        self.metrics.record_successful_exchange(
                            self.protocol_id,
                            peer_id,
                            (time.time() - request["timestamp"]) * 1000  # ms
                        )
                        # Update last sync time
                        self.last_sync[peer_id] = time.time()
                    else:
                        self.metrics.record_failed_exchange(
                            self.protocol_id,
                            peer_id,
                            "protocol"
                        )
                    
                    return response
            else:
                logger.warning("Peer does not support opening protocol streams")
                return {"success": False, "error": "Protocol stream not supported"}
                
        except Exception as e:
            logger.error(f"Error syncing with peer {peer_id}: {e}")
            self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
            return {"success": False, "error": str(e)}


class DirectTransferProtocolHandler:
    """
    Handler for the Direct Transfer protocol.
    
    This protocol enables direct file transfer between peers without
    requiring the full IPFS stack or bitswap protocol.
    """
    
    def __init__(self, peer, metrics=None):
        """
        Initialize the Direct Transfer protocol handler.
        
        Args:
            peer: The libp2p peer instance
            metrics: Optional ProtocolMetrics instance for tracking metrics
        """
        self.peer = peer
        self.protocol_id = PROTOCOLS["DIRECT_TRANSFER"]
        self.metrics = metrics or ProtocolMetrics()
        
        # Register protocol handler with the peer
        if hasattr(peer, "register_protocol_handler") and callable(peer.register_protocol_handler):
            self.peer.register_protocol_handler(self.protocol_id, self._handle_transfer_request)
            logger.debug(f"Registered handler for {self.protocol_id}")
        
        # Transfer tracking
        self.active_transfers = {}
        self.completed_transfers = {}
    
    async def _handle_transfer_request(self, stream):
        """
        Handle incoming transfer requests.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Read request header
            header_data = await stream.read(1024)  # Read first 1KB for header
            header = json.loads(header_data.decode('utf-8'))
            
            # Extract request info
            request_id = header.get("request_id", f"req_{time.time()}")
            peer_id = header.get("peer_id", "unknown")
            cid = header.get("cid")
            transfer_type = header.get("type", "request")
            
            # Record metrics
            self.metrics.record_request_received(self.protocol_id, peer_id, len(header_data))
            
            # Process based on transfer type
            if transfer_type == "request":
                # Handle content request
                await self._handle_content_request(stream, header, request_id, peer_id)
            elif transfer_type == "data":
                # Handle incoming data (should not happen with this protocol design)
                logger.warning(f"Received unexpected data transfer type from {peer_id}")
                await stream.close()
            else:
                logger.warning(f"Unknown transfer type: {transfer_type} from {peer_id}")
                await stream.close()
                
        except Exception as e:
            logger.error(f"Error handling transfer request: {e}")
            self.metrics.record_failed_exchange(self.protocol_id, "unknown", "protocol")
            
            # Try to send error response
            try:
                error_response = json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time()
                }).encode('utf-8')
                await stream.write(error_response)
            except Exception:
                pass
    
    async def _handle_content_request(self, stream, header, request_id, peer_id):
        """
        Handle a request for content.
        
        Args:
            stream: The protocol stream
            header: The request header data
            request_id: The request ID
            peer_id: The requesting peer ID
        """
        cid = header.get("cid")
        offset = header.get("offset", 0)
        length = header.get("length", -1)  # -1 means all content
        
        if not cid:
            # Send error response for missing CID
            error_response = json.dumps({
                "success": False,
                "error": "Missing CID in request",
                "request_id": request_id,
                "timestamp": time.time()
            }).encode('utf-8')
            await stream.write(error_response)
            return
        
        # Register the active transfer
        self.active_transfers[request_id] = {
            "peer_id": peer_id,
            "cid": cid,
            "start_time": time.time(),
            "bytes_sent": 0,
            "status": "processing"
        }
        
        # Try to get the content
        try:
            # Get content from local storage
            if hasattr(self.peer, "get_content_data") and callable(self.peer.get_content_data):
                content = await self.peer.get_content_data(cid)
            elif hasattr(self.peer, "retrieve_content") and callable(self.peer.retrieve_content):
                # Fallback to synchronous method if async not available
                content = self.peer.retrieve_content(cid)
            else:
                content = None
                
            if not content:
                # Content not available
                error_response = json.dumps({
                    "success": False,
                    "error": f"Content not available: {cid}",
                    "request_id": request_id,
                    "timestamp": time.time()
                }).encode('utf-8')
                await stream.write(error_response)
                
                self.active_transfers[request_id]["status"] = "failed"
                self.metrics.record_failed_exchange(self.protocol_id, peer_id, "content_unavailable")
                return
            
            # Apply offset and length if specified
            if offset > 0:
                content = content[offset:]
            if length > 0 and length < len(content):
                content = content[:length]
            
            # Send header response
            header_response = json.dumps({
                "success": True,
                "request_id": request_id,
                "cid": cid,
                "size": len(content),
                "timestamp": time.time()
            }).encode('utf-8')
            await stream.write(header_response)
            
            # Send content data
            chunk_size = 65536  # 64KB chunks
            total_sent = 0
            
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                await stream.write(chunk)
                total_sent += len(chunk)
                
                # Update transfer status
                self.active_transfers[request_id]["bytes_sent"] = total_sent
                
            # Record successful exchange
            self.metrics.record_successful_exchange(
                self.protocol_id,
                peer_id,
                (time.time() - self.active_transfers[request_id]["start_time"]) * 1000
            )
            
            # Move to completed transfers
            self.active_transfers[request_id]["status"] = "completed"
            self.active_transfers[request_id]["end_time"] = time.time()
            self.completed_transfers[request_id] = self.active_transfers[request_id]
            del self.active_transfers[request_id]
            
        except Exception as e:
            logger.error(f"Error handling content request for {cid}: {e}")
            
            # Send error response
            try:
                error_response = json.dumps({
                    "success": False,
                    "error": str(e),
                    "request_id": request_id,
                    "timestamp": time.time()
                }).encode('utf-8')
                await stream.write(error_response)
            except Exception:
                pass
            
            # Update transfer status
            if request_id in self.active_transfers:
                self.active_transfers[request_id]["status"] = "failed"
                self.active_transfers[request_id]["error"] = str(e)
                self.completed_transfers[request_id] = self.active_transfers[request_id]
                del self.active_transfers[request_id]
            
            # Record failed exchange
            self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
    
    async def request_content(self, peer_id: str, cid: str, offset: int = 0, length: int = -1) -> Optional[bytes]:
        """
        Request content from a specific peer.
        
        Args:
            peer_id: The peer ID to request content from
            cid: The content ID to request
            offset: Byte offset to start from (0 means beginning)
            length: Number of bytes to request (-1 means all)
            
        Returns:
            The content bytes if successful, None otherwise
        """
        request_id = f"req_{int(time.time()*1000)}_{id(self)}"
        
        try:
            # Create request header
            header = {
                "type": "request",
                "request_id": request_id,
                "peer_id": self.peer.get_peer_id(),
                "cid": cid,
                "offset": offset,
                "length": length,
                "timestamp": time.time()
            }
            
            # Serialize header
            header_data = json.dumps(header).encode('utf-8')
            
            # Record request metrics
            self.metrics.record_request_sent(self.protocol_id, peer_id, len(header_data))
            
            # Open stream and send request
            if hasattr(self.peer, "open_protocol_stream") and callable(self.peer.open_protocol_stream):
                async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                    # Send header
                    await stream.write(header_data)
                    
                    # Read header response
                    response_header_data = await stream.read(1024)  # Read first 1KB for header
                    response_header = json.loads(response_header_data.decode('utf-8'))
                    
                    # Check if request was successful
                    if not response_header.get("success", False):
                        logger.warning(
                            f"Content request failed: {response_header.get('error', 'Unknown error')}"
                        )
                        self.metrics.record_failed_exchange(self.protocol_id, peer_id, "request_failed")
                        return None
                    
                    # Get expected content size
                    content_size = response_header.get("size", 0)
                    
                    if content_size == 0:
                        # No content to receive
                        self.metrics.record_successful_exchange(
                            self.protocol_id,
                            peer_id,
                            (time.time() - header["timestamp"]) * 1000
                        )
                        return b""
                    
                    # Read content data
                    content_parts = []
                    bytes_received = 0
                    
                    while bytes_received < content_size:
                        chunk = await stream.read(65536)  # Read in 64KB chunks
                        if not chunk:
                            logger.warning(f"Connection closed before receiving all data")
                            break
                        
                        content_parts.append(chunk)
                        bytes_received += len(chunk)
                    
                    # Combine all parts
                    content = b"".join(content_parts)
                    
                    # Record metrics
                    self.metrics.record_request_received(
                        self.protocol_id,
                        peer_id,
                        bytes_received
                    )
                    
                    self.metrics.record_successful_exchange(
                        self.protocol_id,
                        peer_id,
                        (time.time() - header["timestamp"]) * 1000
                    )
                    
                    return content
            else:
                logger.warning("Peer does not support opening protocol streams")
                return None
        
        except Exception as e:
            logger.error(f"Error requesting content {cid} from {peer_id}: {e}")
            self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
            return None


class EnhancedDiscoveryProtocolHandler:
    """
    Handler for the Enhanced Discovery protocol.
    
    This protocol provides advanced peer and content discovery mechanisms
    beyond the basic DHT-based approaches.
    """
    
    def __init__(self, peer, metrics=None):
        """
        Initialize the Enhanced Discovery protocol handler.
        
        Args:
            peer: The libp2p peer instance
            metrics: Optional ProtocolMetrics instance for tracking metrics
        """
        self.peer = peer
        self.protocol_id = PROTOCOLS["ENHANCED_DISCOVERY"]
        self.metrics = metrics or ProtocolMetrics()
        
        # Register protocol handler with the peer
        if hasattr(peer, "register_protocol_handler") and callable(peer.register_protocol_handler):
            self.peer.register_protocol_handler(self.protocol_id, self._handle_discovery_request)
            logger.debug(f"Registered handler for {self.protocol_id}")
        
        # Discovery tracking
        self.recent_discoveries = {}  # Map of query hash to results
        self.discovery_cache_ttl = 300  # 5 minutes
        
        # Content provider index
        self.content_provider_index = {}  # Map of CID to list of provider peer IDs
    
    async def _handle_discovery_request(self, stream):
        """
        Handle incoming discovery requests.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Read request data
            data = await stream.read()
            request = json.loads(data.decode('utf-8'))
            
            # Record metrics
            peer_id = request.get("peer_id", "unknown")
            self.metrics.record_request_received(self.protocol_id, peer_id, len(data))
            
            # Process the discovery request
            discovery_type = request.get("type", "peer")
            response = await self._process_discovery_request(request, discovery_type)
            
            # Send response
            response_data = json.dumps(response).encode('utf-8')
            await stream.write(response_data)
            
            # Record successful exchange
            self.metrics.record_successful_exchange(
                self.protocol_id,
                peer_id,
                (time.time() - request.get("timestamp", time.time())) * 1000
            )
            
        except Exception as e:
            logger.error(f"Error handling discovery request: {e}")
            self.metrics.record_failed_exchange(self.protocol_id, "unknown", "protocol")
            
            # Try to send error response
            try:
                error_response = json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time()
                }).encode('utf-8')
                await stream.write(error_response)
            except Exception:
                pass
    
    async def _process_discovery_request(self, request, discovery_type):
        """
        Process a discovery request and generate a response.
        
        Args:
            request: The discovery request data
            discovery_type: Type of discovery ('peer', 'content', or 'mesh')
            
        Returns:
            Dict containing the discovery response
        """
        response = {
            "success": True,
            "type": discovery_type,
            "timestamp": time.time(),
            "peer_id": self.peer.get_peer_id()
        }
        
        if discovery_type == "peer":
            # Peer discovery request
            limit = request.get("limit", 10)
            role_filter = request.get("role_filter")
            response["peers"] = await self._discover_peers(limit, role_filter)
        elif discovery_type == "content":
            # Content discovery request
            cid = request.get("cid")
            if not cid:
                response["success"] = False
                response["error"] = "Missing CID in content discovery request"
            else:
                response["providers"] = await self._discover_content_providers(cid)
        elif discovery_type == "mesh":
            # Mesh discovery request (provides network topology information)
            depth = request.get("depth", 1)
            response["mesh"] = await self._discover_mesh_topology(depth)
        else:
            response["success"] = False
            response["error"] = f"Unknown discovery type: {discovery_type}"
        
        return response
    
    async def _discover_peers(self, limit=10, role_filter=None):
        """
        Discover peers that match criteria.
        
        Args:
            limit: Maximum number of peers to discover
            role_filter: Optional role to filter by
            
        Returns:
            List of peer information
        """
        peers = []
        
        # First get connected peers
        if hasattr(self.peer, "get_connected_peers"):
            connected_peer_ids = self.peer.get_connected_peers()
            
            # Get detailed info for each peer
            for peer_id in connected_peer_ids[:limit*2]:  # Get extra for filtering
                if hasattr(self.peer, "get_peer_info"):
                    info = self.peer.get_peer_info(peer_id)
                    
                    # Apply role filter if specified
                    if role_filter is not None:
                        peer_role = info.get("role")
                        if peer_role != role_filter:
                            continue
                    
                    peers.append({
                        "peer_id": peer_id,
                        "info": info
                    })
                else:
                    peers.append({"peer_id": peer_id})
                
                # Stop if we have enough peers
                if len(peers) >= limit:
                    break
        
        # If we don't have enough peers yet, try DHT discovery
        if len(peers) < limit and hasattr(self.peer, "discover_peers_dht"):
            try:
                dht_peers = self.peer.discover_peers_dht(limit=(limit - len(peers)))
                
                for peer_id in dht_peers:
                    if peer_id not in [p.get("peer_id") for p in peers]:
                        if hasattr(self.peer, "get_peer_info"):
                            info = self.peer.get_peer_info(peer_id)
                            
                            # Apply role filter if specified
                            if role_filter is not None:
                                peer_role = info.get("role")
                                if peer_role != role_filter:
                                    continue
                                
                            peers.append({
                                "peer_id": peer_id,
                                "info": info
                            })
                        else:
                            peers.append({"peer_id": peer_id})
                
                        # Stop if we have enough peers
                        if len(peers) >= limit:
                            break
            except Exception as e:
                logger.error(f"Error discovering peers from DHT: {e}")
        
        return peers[:limit]
    
    async def _discover_content_providers(self, cid):
        """
        Discover providers for a specific content ID.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider information
        """
        providers = []
        
        # First check our local content provider index
        if cid in self.content_provider_index:
            local_providers = self.content_provider_index[cid]
            
            # Get additional info for each provider
            for peer_id in local_providers:
                if hasattr(self.peer, "get_peer_info"):
                    info = self.peer.get_peer_info(peer_id)
                    providers.append({
                        "peer_id": peer_id,
                        "info": info,
                        "source": "local_index"
                    })
                else:
                    providers.append({
                        "peer_id": peer_id,
                        "source": "local_index"
                    })
        
        # Then try to find providers through DHT
        if hasattr(self.peer, "find_providers"):
            try:
                dht_providers = self.peer.find_providers(cid)
                
                for provider in dht_providers:
                    # Handle different provider formats
                    if isinstance(provider, str):
                        peer_id = provider
                    elif isinstance(provider, dict) and "id" in provider:
                        peer_id = provider["id"]
                    else:
                        continue
                    
                    # Skip if we already have this provider
                    if peer_id in [p.get("peer_id") for p in providers]:
                        continue
                    
                    # Add provider info
                    if hasattr(self.peer, "get_peer_info"):
                        info = self.peer.get_peer_info(peer_id)
                        providers.append({
                            "peer_id": peer_id,
                            "info": info,
                            "source": "dht"
                        })
                    else:
                        providers.append({
                            "peer_id": peer_id,
                            "source": "dht"
                        })
                    
                    # Add to our local index
                    if cid not in self.content_provider_index:
                        self.content_provider_index[cid] = []
                    if peer_id not in self.content_provider_index[cid]:
                        self.content_provider_index[cid].append(peer_id)
                    
            except Exception as e:
                logger.error(f"Error finding providers from DHT for {cid}: {e}")
        
        return providers
    
    async def _discover_mesh_topology(self, depth=1):
        """
        Discover the mesh topology around this peer.
        
        Args:
            depth: How many layers of connections to traverse
            
        Returns:
            Dict containing mesh topology information
        """
        # Get our connected peers
        mesh = {
            "center": self.peer.get_peer_id(),
            "connections": {},
            "depth": depth
        }
        
        if depth < 1:
            return mesh
        
        # Get our direct connections
        if hasattr(self.peer, "get_connected_peers"):
            direct_peers = self.peer.get_connected_peers()
            
            # Add direct connections
            for peer_id in direct_peers:
                mesh["connections"][peer_id] = {
                    "distance": 1,
                    "connections": []
                }
                
                # Get peer info if available
                if hasattr(self.peer, "get_peer_info"):
                    mesh["connections"][peer_id]["info"] = self.peer.get_peer_info(peer_id)
        
        # If depth > 1, recursively get connections of connections
        if depth > 1 and hasattr(self.peer, "open_protocol_stream"):
            for peer_id in list(mesh["connections"].keys()):
                try:
                    # Send mesh discovery request with reduced depth
                    request = {
                        "type": "mesh",
                        "depth": depth - 1,
                        "timestamp": time.time(),
                        "peer_id": self.peer.get_peer_id()
                    }
                    
                    # Serialize request
                    request_data = json.dumps(request).encode('utf-8')
                    
                    # Record request metrics
                    self.metrics.record_request_sent(self.protocol_id, peer_id, len(request_data))
                    
                    # Open stream and send request
                    async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                        # Send request
                        await stream.write(request_data)
                        
                        # Receive response
                        response_data = await stream.read()
                        response = json.loads(response_data.decode('utf-8'))
                        
                        # Record metrics
                        self.metrics.record_request_received(
                            self.protocol_id, 
                            peer_id, 
                            len(response_data)
                        )
                        
                        if response.get("success", False):
                            # Update mesh with peer's connections
                            remote_connections = response.get("mesh", {}).get("connections", {})
                            mesh["connections"][peer_id]["connections"] = list(remote_connections.keys())
                            
                            self.metrics.record_successful_exchange(
                                self.protocol_id,
                                peer_id,
                                (time.time() - request["timestamp"]) * 1000
                            )
                        else:
                            self.metrics.record_failed_exchange(
                                self.protocol_id,
                                peer_id,
                                "protocol"
                            )
                except Exception as e:
                    logger.error(f"Error getting mesh from peer {peer_id}: {e}")
                    self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
        
        return mesh
    
    async def discover_peers_in_role(self, role, limit=10):
        """
        Discover peers that have a specific role.
        
        Args:
            role: The role to look for
            limit: Maximum number of peers to discover
            
        Returns:
            List of peer information for peers with the specified role
        """
        # Create discovery request
        request = {
            "type": "peer",
            "role_filter": role,
            "limit": limit,
            "timestamp": time.time(),
            "peer_id": self.peer.get_peer_id()
        }
        
        # First try local discovery
        local_results = await self._discover_peers(limit, role)
        if len(local_results) >= limit:
            return local_results
        
        # If we need more peers, query our connected peers
        if hasattr(self.peer, "get_connected_peers") and hasattr(self.peer, "open_protocol_stream"):
            connected_peers = self.peer.get_connected_peers()
            remaining_slots = limit - len(local_results)
            
            for peer_id in connected_peers:
                try:
                    # Serialize request
                    request_data = json.dumps(request).encode('utf-8')
                    
                    # Record request metrics
                    self.metrics.record_request_sent(self.protocol_id, peer_id, len(request_data))
                    
                    # Open stream and send request
                    async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                        # Send request
                        await stream.write(request_data)
                        
                        # Receive response
                        response_data = await stream.read()
                        response = json.loads(response_data.decode('utf-8'))
                        
                        # Record metrics
                        self.metrics.record_request_received(
                            self.protocol_id, 
                            peer_id, 
                            len(response_data)
                        )
                        
                        if response.get("success", False):
                            # Add new peers to our results
                            remote_peers = response.get("peers", [])
                            
                            for peer in remote_peers:
                                remote_peer_id = peer.get("peer_id")
                                if remote_peer_id not in [p.get("peer_id") for p in local_results]:
                                    local_results.append(peer)
                                    remaining_slots -= 1
                            
                            self.metrics.record_successful_exchange(
                                self.protocol_id,
                                peer_id,
                                (time.time() - request["timestamp"]) * 1000
                            )
                        else:
                            self.metrics.record_failed_exchange(
                                self.protocol_id,
                                peer_id,
                                "protocol"
                            )
                        
                        # Stop if we have enough peers
                        if remaining_slots <= 0:
                            break
                except Exception as e:
                    logger.error(f"Error discovering peers from {peer_id}: {e}")
                    self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
        
        return local_results[:limit]
    
    async def discover_content_recursive(self, cid, depth=2):
        """
        Recursively discover content providers through multiple peers.
        
        Args:
            cid: The content ID to find providers for
            depth: How many layers of peers to query
            
        Returns:
            List of provider information
        """
        # Create discovery request
        request = {
            "type": "content",
            "cid": cid,
            "timestamp": time.time(),
            "peer_id": self.peer.get_peer_id()
        }
        
        # First get direct providers
        all_providers = await self._discover_content_providers(cid)
        provider_ids = set(p.get("peer_id") for p in all_providers)
        
        # If depth > 0, query other peers
        if depth > 0 and hasattr(self.peer, "get_connected_peers") and hasattr(self.peer, "open_protocol_stream"):
            connected_peers = self.peer.get_connected_peers()
            
            for peer_id in connected_peers:
                try:
                    # Serialize request
                    request_data = json.dumps(request).encode('utf-8')
                    
                    # Record request metrics
                    self.metrics.record_request_sent(self.protocol_id, peer_id, len(request_data))
                    
                    # Open stream and send request
                    async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                        # Send request
                        await stream.write(request_data)
                        
                        # Receive response
                        response_data = await stream.read()
                        response = json.loads(response_data.decode('utf-8'))
                        
                        # Record metrics
                        self.metrics.record_request_received(
                            self.protocol_id, 
                            peer_id, 
                            len(response_data)
                        )
                        
                        if response.get("success", False):
                            # Add new providers to our results
                            remote_providers = response.get("providers", [])
                            
                            for provider in remote_providers:
                                remote_peer_id = provider.get("peer_id")
                                if remote_peer_id and remote_peer_id not in provider_ids:
                                    all_providers.append(provider)
                                    provider_ids.add(remote_peer_id)
                                    
                                    # Update our local index
                                    if cid not in self.content_provider_index:
                                        self.content_provider_index[cid] = []
                                    if remote_peer_id not in self.content_provider_index[cid]:
                                        self.content_provider_index[cid].append(remote_peer_id)
                            
                            self.metrics.record_successful_exchange(
                                self.protocol_id,
                                peer_id,
                                (time.time() - request["timestamp"]) * 1000
                            )
                        else:
                            self.metrics.record_failed_exchange(
                                self.protocol_id,
                                peer_id,
                                "protocol"
                            )
                except Exception as e:
                    logger.error(f"Error discovering content from {peer_id}: {e}")
                    self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
            
            # If depth > 1, and we've discovered new peers, recursively query them
            if depth > 1:
                # Get newly discovered peers that aren't in our initial connected_peers list
                new_peers = [
                    p.get("peer_id") for p in all_providers 
                    if p.get("peer_id") not in connected_peers and p.get("peer_id") != self.peer.get_peer_id()
                ]
                
                # Create a new request with decremented depth
                recursive_request = {
                    "type": "content",
                    "cid": cid,
                    "timestamp": time.time(),
                    "peer_id": self.peer.get_peer_id()
                }
                
                # Query each new peer
                for peer_id in new_peers:
                    try:
                        # Try to connect to the peer first
                        if hasattr(self.peer, "connect_peer") and callable(self.peer.connect_peer):
                            connected = self.peer.connect_peer(peer_id)
                            if not connected:
                                continue
                        
                        # Serialize request
                        request_data = json.dumps(recursive_request).encode('utf-8')
                        
                        # Record request metrics
                        self.metrics.record_request_sent(self.protocol_id, peer_id, len(request_data))
                        
                        # Open stream and send request
                        async with await self.peer.open_protocol_stream(peer_id, self.protocol_id) as stream:
                            # Send request
                            await stream.write(request_data)
                            
                            # Receive response
                            response_data = await stream.read()
                            response = json.loads(response_data.decode('utf-8'))
                            
                            # Record metrics
                            self.metrics.record_request_received(
                                self.protocol_id, 
                                peer_id, 
                                len(response_data)
                            )
                            
                            if response.get("success", False):
                                # Add new providers to our results
                                remote_providers = response.get("providers", [])
                                
                                for provider in remote_providers:
                                    remote_peer_id = provider.get("peer_id")
                                    if remote_peer_id and remote_peer_id not in provider_ids:
                                        all_providers.append(provider)
                                        provider_ids.add(remote_peer_id)
                                        
                                        # Update our local index
                                        if cid not in self.content_provider_index:
                                            self.content_provider_index[cid] = []
                                        if remote_peer_id not in self.content_provider_index[cid]:
                                            self.content_provider_index[cid].append(remote_peer_id)
                                
                                self.metrics.record_successful_exchange(
                                    self.protocol_id,
                                    peer_id,
                                    (time.time() - recursive_request["timestamp"]) * 1000
                                )
                            else:
                                self.metrics.record_failed_exchange(
                                    self.protocol_id,
                                    peer_id,
                                    "protocol"
                                )
                    except Exception as e:
                        logger.error(f"Error recursively discovering content from {peer_id}: {e}")
                        self.metrics.record_failed_exchange(self.protocol_id, peer_id, str(type(e).__name__))
        
        return all_providers


def apply_protocol_extensions(peer):
    """
    Apply all protocol extensions to a libp2p peer.
    
    Args:
        peer: The libp2p peer instance to extend
        
    Returns:
        Dict of protocol handlers that were applied
    """
    # Create metrics collector
    metrics = ProtocolMetrics()
    
    # Create and apply protocol handlers
    handlers = {
        "mcp_sync": MCPSyncProtocolHandler(peer, metrics),
        "direct_transfer": DirectTransferProtocolHandler(peer, metrics),
        "enhanced_discovery": EnhancedDiscoveryProtocolHandler(peer, metrics),
    }
    
    # Add protocol list to peer if not present
    if not hasattr(peer, "protocols"):
        peer.protocols = {}
    
    # Add protocol IDs to peer's protocol list
    for protocol_id in PROTOCOLS.values():
        peer.protocols[protocol_id] = True
    
    # Add metrics collector to peer
    peer.protocol_metrics = metrics
    
    # Create convenience methods on the peer for direct access
    _add_convenience_methods(peer, handlers)
    
    logger.info(f"Applied protocol extensions to peer: {list(handlers.keys())}")
    return handlers


def _add_convenience_methods(peer, handlers):
    """Add convenience methods to the peer for direct protocol access."""
    # Direct Transfer protocol methods
    if "direct_transfer" in handlers:
        peer.request_content_direct = handlers["direct_transfer"].request_content
    
    # Enhanced Discovery protocol methods
    if "enhanced_discovery" in handlers:
        peer.discover_peers_in_role = handlers["enhanced_discovery"].discover_peers_in_role
        peer.discover_content_recursive = handlers["enhanced_discovery"].discover_content_recursive
    
    # MCP Sync protocol methods
    if "mcp_sync" in handlers:
        peer.sync_with_peer = handlers["mcp_sync"].sync_with_peer


def get_protocol_metrics(peer):
    """
    Get protocol metrics from a peer.
    
    Args:
        peer: The libp2p peer instance
        
    Returns:
        Dict of metrics or None if metrics are not available
    """
    if hasattr(peer, "protocol_metrics"):
        return peer.protocol_metrics.get_metrics()
    return None


def reset_protocol_metrics(peer):
    """
    Reset protocol metrics on a peer.
    
    Args:
        peer: The libp2p peer instance
        
    Returns:
        True if metrics were reset, False otherwise
    """
    if hasattr(peer, "protocol_metrics"):
        peer.protocol_metrics.reset_metrics()
        return True
    return False
