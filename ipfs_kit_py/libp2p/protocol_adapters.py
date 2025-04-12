"""
LibP2P Protocol Adapters for IPFS Kit and MCP Server.

This module provides protocol adapters that bridge between the IPFS Kit
high-level API and the underlying libp2p protocols. These adapters handle
protocol negotiation, message formatting, and stream management.
"""

import anyio
import json
import logging
import time
import base64
from typing import Dict, List, Any, Optional, Callable, Union, Tuple, Set

# Configure logging
logger = logging.getLogger(__name__)

# Protocol identifiers
BITSWAP_PROTOCOL = "/ipfs/bitswap/1.2.0"
DHT_PROTOCOL = "/ipfs/kad/1.0.0"
IDENTIFY_PROTOCOL = "/ipfs/id/1.0.0"
PING_PROTOCOL = "/ipfs/ping/1.0.0"

# Custom protocols
from ipfs_kit_py.libp2p.protocol_extensions import PROTOCOLS as CUSTOM_PROTOCOLS


class ProtocolAdapter:
    """Base class for protocol adapters."""
    
    def __init__(self, peer, protocol_id: str):
        """
        Initialize the protocol adapter.
        
        Args:
            peer: The libp2p peer instance
            protocol_id: The protocol ID
        """
        self.peer = peer
        self.protocol_id = protocol_id
        self.active_streams = {}  # Map of peer_id -> stream
        
        # Register handler with the peer
        if hasattr(peer, "register_protocol_handler") and callable(peer.register_protocol_handler):
            self.peer.register_protocol_handler(self.protocol_id, self._handle_incoming)
            logger.debug(f"Registered handler for {self.protocol_id}")
    
    async def _handle_incoming(self, stream):
        """
        Handle incoming protocol streams.
        
        Args:
            stream: The incoming protocol stream
        """
        raise NotImplementedError("Subclasses must implement _handle_incoming")
        
    async def open_stream(self, peer_id: str) -> Any:
        """
        Open a protocol stream to a peer.
        
        Args:
            peer_id: The peer ID to connect to
            
        Returns:
            The protocol stream
        """
        if hasattr(self.peer, "open_protocol_stream") and callable(self.peer.open_protocol_stream):
            stream = await self.peer.open_protocol_stream(peer_id, self.protocol_id)
            self.active_streams[peer_id] = stream
            return stream
        else:
            raise RuntimeError(f"Peer does not support open_protocol_stream")
    
    def close_stream(self, peer_id: str):
        """
        Close a protocol stream.
        
        Args:
            peer_id: The peer ID to disconnect from
        """
        if peer_id in self.active_streams:
            try:
                self.active_streams[peer_id].close()
            except Exception as e:
                logger.warning(f"Error closing stream to {peer_id}: {e}")
            finally:
                del self.active_streams[peer_id]


class BitswapAdapter(ProtocolAdapter):
    """Adapter for the Bitswap protocol."""
    
    def __init__(self, peer):
        """
        Initialize the Bitswap adapter.
        
        Args:
            peer: The libp2p peer instance
        """
        super().__init__(peer, BITSWAP_PROTOCOL)
        self.want_list = set()  # CIDs we want
        self.blocks = {}  # Map of CID -> block data
        
        # Message handling
        self.message_handlers = {
            "WANT": self._handle_want_message,
            "HAVE": self._handle_have_message,
            "DONT_HAVE": self._handle_dont_have_message,
            "BLOCK": self._handle_block_message,
        }
    
    async def _handle_incoming(self, stream):
        """
        Handle incoming Bitswap streams.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Get peer ID from stream
            peer_id = stream.conn.remote_peer_id
            
            # Read message
            message_data = await stream.read()
            message = self._parse_message(message_data)
            
            if not message:
                logger.warning(f"Received invalid Bitswap message from {peer_id}")
                return
            
            # Process message
            message_type = message.get("type")
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](message, stream, peer_id)
            else:
                logger.warning(f"Received unknown Bitswap message type {message_type} from {peer_id}")
        except Exception as e:
            logger.error(f"Error handling Bitswap message: {e}")
    
    def _parse_message(self, data: bytes) -> Dict[str, Any]:
        """
        Parse a Bitswap message.
        
        Args:
            data: Raw message data
            
        Returns:
            Parsed message as a dictionary
        """
        try:
            # This is a simplified parser - a real one would handle protobuf
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error parsing Bitswap message: {e}")
            return {}
    
    async def _handle_want_message(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a Bitswap WANT message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        cids = message.get("cids", [])
        
        responses = []
        
        for cid in cids:
            if cid in self.blocks:
                # We have this block
                responses.append({
                    "type": "BLOCK",
                    "cid": cid,
                    "data": base64.b64encode(self.blocks[cid]).decode('utf-8')
                })
            else:
                # We don't have this block
                responses.append({
                    "type": "DONT_HAVE",
                    "cid": cid
                })
        
        # Send responses
        for response in responses:
            response_data = json.dumps(response).encode('utf-8')
            await stream.write(response_data)
    
    async def _handle_have_message(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a Bitswap HAVE message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The sender peer ID
        """
        cid = message.get("cid")
        
        if not cid:
            return
        
        # If we want this block, send a WANT message
        if cid in self.want_list:
            response = {
                "type": "WANT",
                "cids": [cid]
            }
            
            response_data = json.dumps(response).encode('utf-8')
            await stream.write(response_data)
    
    async def _handle_dont_have_message(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a Bitswap DONT_HAVE message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The sender peer ID
        """
        # Nothing to do for this simple implementation
        pass
    
    async def _handle_block_message(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a Bitswap BLOCK message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The sender peer ID
        """
        cid = message.get("cid")
        data_b64 = message.get("data")
        
        if not cid or not data_b64:
            return
        
        # Decode the block data
        try:
            data = base64.b64decode(data_b64)
            
            # Store the block
            self.blocks[cid] = data
            
            # Remove from want list
            if cid in self.want_list:
                self.want_list.remove(cid)
            
            # Notify any listeners
            if hasattr(self.peer, "on_block_received") and callable(self.peer.on_block_received):
                self.peer.on_block_received(cid, data, peer_id)
                
        except Exception as e:
            logger.error(f"Error processing block {cid} from {peer_id}: {e}")
    
    async def want(self, cid: str) -> bool:
        """
        Request a block by CID.
        
        Args:
            cid: The CID to request
            
        Returns:
            True if the request was sent successfully, False otherwise
        """
        # Add to want list
        self.want_list.add(cid)
        
        # Get connected peers
        if hasattr(self.peer, "get_connected_peers") and callable(self.peer.get_connected_peers):
            peers = self.peer.get_connected_peers()
            
            # Create WANT message
            message = {
                "type": "WANT",
                "cids": [cid]
            }
            
            message_data = json.dumps(message).encode('utf-8')
            
            # Send to all peers
            for peer_id in peers:
                try:
                    async with await self.open_stream(peer_id) as stream:
                        await stream.write(message_data)
                except Exception as e:
                    logger.warning(f"Error sending WANT message to {peer_id}: {e}")
            
            return True
        
        return False
    
    async def put(self, cid: str, data: bytes) -> bool:
        """
        Store a block locally and announce to peers.
        
        Args:
            cid: The CID of the block
            data: The block data
            
        Returns:
            True if the block was stored successfully, False otherwise
        """
        # Store the block
        self.blocks[cid] = data
        
        # Get connected peers
        if hasattr(self.peer, "get_connected_peers") and callable(self.peer.get_connected_peers):
            peers = self.peer.get_connected_peers()
            
            # Create HAVE message
            message = {
                "type": "HAVE",
                "cid": cid
            }
            
            message_data = json.dumps(message).encode('utf-8')
            
            # Send to all peers
            for peer_id in peers:
                try:
                    async with await self.open_stream(peer_id) as stream:
                        await stream.write(message_data)
                except Exception as e:
                    logger.warning(f"Error sending HAVE message to {peer_id}: {e}")
            
            return True
        
        return False
    
    async def get_block(self, cid: str) -> Optional[bytes]:
        """
        Get a block by CID.
        
        Args:
            cid: The CID to get
            
        Returns:
            The block data if found, None otherwise
        """
        # Check if we have it locally
        if cid in self.blocks:
            return self.blocks[cid]
        
        # Request it from peers
        success = await self.want(cid)
        if not success:
            return None
        
        # Wait for it to be received
        for _ in range(10):  # Try for up to 10 seconds
            if cid in self.blocks:
                return self.blocks[cid]
            await anyio.sleep(1)
        
        return None


class DHTAdapter(ProtocolAdapter):
    """Adapter for the DHT protocol."""
    
    def __init__(self, peer):
        """
        Initialize the DHT adapter.
        
        Args:
            peer: The libp2p peer instance
        """
        super().__init__(peer, DHT_PROTOCOL)
        self.routing_table = {}  # Map of peer_id -> routing info
        self.providers = {}  # Map of CID -> set of provider peer IDs
        self.values = {}  # Map of key -> value
        
        # Message handling
        self.message_handlers = {
            "FIND_NODE": self._handle_find_node,
            "FIND_VALUE": self._handle_find_value,
            "GET_PROVIDERS": self._handle_get_providers,
            "ADD_PROVIDER": self._handle_add_provider,
            "PUT_VALUE": self._handle_put_value,
        }
    
    async def _handle_incoming(self, stream):
        """
        Handle incoming DHT streams.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Get peer ID from stream
            peer_id = stream.conn.remote_peer_id
            
            # Add to routing table
            self.routing_table[peer_id] = {
                "last_seen": time.time()
            }
            
            # Read message
            message_data = await stream.read()
            message = self._parse_message(message_data)
            
            if not message:
                logger.warning(f"Received invalid DHT message from {peer_id}")
                return
            
            # Process message
            message_type = message.get("type")
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](message, stream, peer_id)
            else:
                logger.warning(f"Received unknown DHT message type {message_type} from {peer_id}")
        except Exception as e:
            logger.error(f"Error handling DHT message: {e}")
    
    def _parse_message(self, data: bytes) -> Dict[str, Any]:
        """
        Parse a DHT message.
        
        Args:
            data: Raw message data
            
        Returns:
            Parsed message as a dictionary
        """
        try:
            # This is a simplified parser - a real one would handle protobuf
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error parsing DHT message: {e}")
            return {}
    
    async def _handle_find_node(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a DHT FIND_NODE message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        target_id = message.get("target")
        
        if not target_id:
            return
        
        # Find closest peers to target
        closest_peers = self._find_closest_peers(target_id)
        
        # Prepare response
        response = {
            "type": "FIND_NODE_RESPONSE",
            "closer_peers": closest_peers
        }
        
        response_data = json.dumps(response).encode('utf-8')
        await stream.write(response_data)
    
    async def _handle_find_value(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a DHT FIND_VALUE message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        key = message.get("key")
        
        if not key:
            return
        
        # Check if we have the value
        if key in self.values:
            # Return the value
            response = {
                "type": "FIND_VALUE_RESPONSE",
                "found": True,
                "value": self.values[key]
            }
        else:
            # Find closest peers to key
            closest_peers = self._find_closest_peers(key)
            
            # Return closest peers
            response = {
                "type": "FIND_VALUE_RESPONSE",
                "found": False,
                "closer_peers": closest_peers
            }
        
        response_data = json.dumps(response).encode('utf-8')
        await stream.write(response_data)
    
    async def _handle_get_providers(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a DHT GET_PROVIDERS message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        cid = message.get("cid")
        
        if not cid:
            return
        
        # Check if we have providers for this CID
        if cid in self.providers:
            # Return providers
            response = {
                "type": "GET_PROVIDERS_RESPONSE",
                "providers": list(self.providers[cid])
            }
        else:
            # Find closest peers to CID
            closest_peers = self._find_closest_peers(cid)
            
            # Return closest peers
            response = {
                "type": "GET_PROVIDERS_RESPONSE",
                "providers": [],
                "closer_peers": closest_peers
            }
        
        response_data = json.dumps(response).encode('utf-8')
        await stream.write(response_data)
    
    async def _handle_add_provider(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a DHT ADD_PROVIDER message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        cid = message.get("cid")
        provider_id = message.get("provider", peer_id)
        
        if not cid:
            return
        
        # Add provider
        if cid not in self.providers:
            self.providers[cid] = set()
        
        self.providers[cid].add(provider_id)
        
        # Acknowledge
        response = {
            "type": "ADD_PROVIDER_RESPONSE",
            "success": True
        }
        
        response_data = json.dumps(response).encode('utf-8')
        await stream.write(response_data)
    
    async def _handle_put_value(self, message: Dict[str, Any], stream: Any, peer_id: str):
        """
        Handle a DHT PUT_VALUE message.
        
        Args:
            message: The parsed message
            stream: The protocol stream
            peer_id: The requesting peer ID
        """
        key = message.get("key")
        value = message.get("value")
        
        if not key or value is None:
            return
        
        # Store the value
        self.values[key] = value
        
        # Acknowledge
        response = {
            "type": "PUT_VALUE_RESPONSE",
            "success": True
        }
        
        response_data = json.dumps(response).encode('utf-8')
        await stream.write(response_data)
    
    def _find_closest_peers(self, target_id: str, limit: int = 20) -> List[str]:
        """
        Find peers closest to a target ID.
        
        Args:
            target_id: The target peer/content ID
            limit: Maximum number of peers to return
            
        Returns:
            List of peer IDs closest to the target
        """
        # This is a simplified implementation - a real one would use XOR distance
        return list(self.routing_table.keys())[:limit]
    
    async def find_providers(self, cid: str, limit: int = 20) -> List[str]:
        """
        Find providers for a CID.
        
        Args:
            cid: The CID to find providers for
            limit: Maximum number of providers to return
            
        Returns:
            List of provider peer IDs
        """
        # Check if we have local providers
        local_providers = list(self.providers.get(cid, set()))
        
        if len(local_providers) >= limit:
            return local_providers[:limit]
        
        # Create query message
        message = {
            "type": "GET_PROVIDERS",
            "cid": cid
        }
        
        message_data = json.dumps(message).encode('utf-8')
        
        # Query closest peers
        closest_peers = self._find_closest_peers(cid)
        all_providers = set(local_providers)
        
        for peer_id in closest_peers:
            try:
                async with await self.open_stream(peer_id) as stream:
                    # Send query
                    await stream.write(message_data)
                    
                    # Read response
                    response_data = await stream.read()
                    response = self._parse_message(response_data)
                    
                    if response.get("type") == "GET_PROVIDERS_RESPONSE":
                        # Add providers to our list
                        remote_providers = response.get("providers", [])
                        all_providers.update(remote_providers)
                        
                        # Add to our local cache
                        for provider_id in remote_providers:
                            if cid not in self.providers:
                                self.providers[cid] = set()
                            self.providers[cid].add(provider_id)
                        
                        # Break if we have enough providers
                        if len(all_providers) >= limit:
                            break
                        
                        # Check if there are closer peers to query
                        closer_peers = response.get("closer_peers", [])
                        for closer_peer in closer_peers:
                            if closer_peer not in closest_peers:
                                closest_peers.append(closer_peer)
                        
            except Exception as e:
                logger.warning(f"Error querying peer {peer_id} for providers: {e}")
        
        return list(all_providers)[:limit]
    
    async def provide(self, cid: str) -> bool:
        """
        Announce that this peer provides a CID.
        
        Args:
            cid: The CID to provide
            
        Returns:
            True if the announcement was successful, False otherwise
        """
        # Add ourselves as a provider
        if cid not in self.providers:
            self.providers[cid] = set()
        
        self.providers[cid].add(self.peer.get_peer_id())
        
        # Create announcement message
        message = {
            "type": "ADD_PROVIDER",
            "cid": cid,
            "provider": self.peer.get_peer_id()
        }
        
        message_data = json.dumps(message).encode('utf-8')
        
        # Announce to closest peers
        closest_peers = self._find_closest_peers(cid)
        success = False
        
        for peer_id in closest_peers:
            try:
                async with await self.open_stream(peer_id) as stream:
                    # Send announcement
                    await stream.write(message_data)
                    
                    # Read acknowledgement
                    response_data = await stream.read()
                    response = self._parse_message(response_data)
                    
                    if response.get("type") == "ADD_PROVIDER_RESPONSE" and response.get("success", False):
                        success = True
                        
            except Exception as e:
                logger.warning(f"Error announcing provider to {peer_id}: {e}")
        
        return success
    
    async def store_value(self, key: str, value: Any) -> bool:
        """
        Store a value in the DHT.
        
        Args:
            key: The key to store under
            value: The value to store
            
        Returns:
            True if the value was stored successfully, False otherwise
        """
        # Store locally
        self.values[key] = value
        
        # Create message
        message = {
            "type": "PUT_VALUE",
            "key": key,
            "value": value
        }
        
        message_data = json.dumps(message).encode('utf-8')
        
        # Announce to closest peers
        closest_peers = self._find_closest_peers(key)
        success = False
        
        for peer_id in closest_peers:
            try:
                async with await self.open_stream(peer_id) as stream:
                    # Send message
                    await stream.write(message_data)
                    
                    # Read acknowledgement
                    response_data = await stream.read()
                    response = self._parse_message(response_data)
                    
                    if response.get("type") == "PUT_VALUE_RESPONSE" and response.get("success", False):
                        success = True
                        
            except Exception as e:
                logger.warning(f"Error storing value to {peer_id}: {e}")
        
        return success
    
    async def get_value(self, key: str) -> Optional[Any]:
        """
        Get a value from the DHT.
        
        Args:
            key: The key to get
            
        Returns:
            The value if found, None otherwise
        """
        # Check if we have it locally
        if key in self.values:
            return self.values[key]
        
        # Create query message
        message = {
            "type": "FIND_VALUE",
            "key": key
        }
        
        message_data = json.dumps(message).encode('utf-8')
        
        # Query closest peers
        closest_peers = self._find_closest_peers(key)
        
        for peer_id in closest_peers:
            try:
                async with await self.open_stream(peer_id) as stream:
                    # Send query
                    await stream.write(message_data)
                    
                    # Read response
                    response_data = await stream.read()
                    response = self._parse_message(response_data)
                    
                    if response.get("type") == "FIND_VALUE_RESPONSE":
                        if response.get("found", False):
                            # Value found
                            value = response.get("value")
                            
                            # Cache locally
                            self.values[key] = value
                            
                            return value
                        else:
                            # Check if there are closer peers to query
                            closer_peers = response.get("closer_peers", [])
                            for closer_peer in closer_peers:
                                if closer_peer not in closest_peers:
                                    closest_peers.append(closer_peer)
                        
            except Exception as e:
                logger.warning(f"Error querying peer {peer_id} for value: {e}")
        
        return None


class IdentifyAdapter(ProtocolAdapter):
    """Adapter for the Identify protocol."""
    
    def __init__(self, peer):
        """
        Initialize the Identify adapter.
        
        Args:
            peer: The libp2p peer instance
        """
        super().__init__(peer, IDENTIFY_PROTOCOL)
        self.peer_info = {}  # Map of peer_id -> peer info
    
    async def _handle_incoming(self, stream):
        """
        Handle incoming Identify streams.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Get peer ID from stream
            peer_id = stream.conn.remote_peer_id
            
            # Send our identity
            identity = self._get_identity()
            identity_data = json.dumps(identity).encode('utf-8')
            
            await stream.write(identity_data)
            
            # Read their identity
            response_data = await stream.read()
            response = json.loads(response_data.decode('utf-8'))
            
            # Store their info
            self.peer_info[peer_id] = response
        except Exception as e:
            logger.error(f"Error handling Identify stream: {e}")
    
    def _get_identity(self) -> Dict[str, Any]:
        """
        Get this peer's identity information.
        
        Returns:
            Identity information as a dictionary
        """
        identity = {
            "peer_id": self.peer.get_peer_id(),
            "agent_version": "ipfs-kit-py/libp2p-adapter/1.0.0",
            "protocols": [],
            "listen_addrs": [],
            "observed_addr": "",
        }
        
        # Add protocols
        if hasattr(self.peer, "protocols") and self.peer.protocols:
            identity["protocols"] = list(self.peer.protocols.keys())
        else:
            # Standard protocols
            identity["protocols"] = [
                BITSWAP_PROTOCOL,
                DHT_PROTOCOL,
                IDENTIFY_PROTOCOL,
                PING_PROTOCOL
            ]
            
            # Add custom protocols
            identity["protocols"].extend(CUSTOM_PROTOCOLS.values())
        
        # Add listen addresses
        if hasattr(self.peer, "listen_addrs") and self.peer.listen_addrs:
            identity["listen_addrs"] = self.peer.listen_addrs
        
        return identity
    
    async def identify(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """
        Identify a peer.
        
        Args:
            peer_id: The peer ID to identify
            
        Returns:
            Peer identity information if successful, None otherwise
        """
        # Check if we already have their info
        if peer_id in self.peer_info:
            return self.peer_info[peer_id]
        
        try:
            # Open stream
            async with await self.open_stream(peer_id) as stream:
                # Send our identity
                identity = self._get_identity()
                identity_data = json.dumps(identity).encode('utf-8')
                
                await stream.write(identity_data)
                
                # Read their identity
                response_data = await stream.read()
                response = json.loads(response_data.decode('utf-8'))
                
                # Store their info
                self.peer_info[peer_id] = response
                
                return response
        except Exception as e:
            logger.error(f"Error identifying peer {peer_id}: {e}")
            return None


class PingAdapter(ProtocolAdapter):
    """Adapter for the Ping protocol."""
    
    def __init__(self, peer):
        """
        Initialize the Ping adapter.
        
        Args:
            peer: The libp2p peer instance
        """
        super().__init__(peer, PING_PROTOCOL)
        self.ping_stats = {}  # Map of peer_id -> {success, failure, latency}
    
    async def _handle_incoming(self, stream):
        """
        Handle incoming Ping streams.
        
        Args:
            stream: The incoming protocol stream
        """
        try:
            # Read ping message
            ping_data = await stream.read()
            
            # Echo it back
            await stream.write(ping_data)
        except Exception as e:
            logger.error(f"Error handling Ping stream: {e}")
    
    async def ping(self, peer_id: str) -> Tuple[bool, float]:
        """
        Ping a peer.
        
        Args:
            peer_id: The peer ID to ping
            
        Returns:
            Tuple of (success, latency) where latency is in seconds
        """
        try:
            # Create ping message
            ping_message = f"PING:{int(time.time() * 1000)}".encode('utf-8')
            
            # Track start time
            start_time = time.time()
            
            # Open stream
            async with await self.open_stream(peer_id) as stream:
                # Send ping
                await stream.write(ping_message)
                
                # Read pong
                pong = await stream.read()
                
                # Calculate latency
                latency = time.time() - start_time
                
                # Verify pong
                success = pong == ping_message
                
                # Update stats
                if peer_id not in self.ping_stats:
                    self.ping_stats[peer_id] = {
                        "success": 0,
                        "failure": 0,
                        "latency": []
                    }
                
                if success:
                    self.ping_stats[peer_id]["success"] += 1
                    self.ping_stats[peer_id]["latency"].append(latency)
                else:
                    self.ping_stats[peer_id]["failure"] += 1
                
                # Keep only the last 10 latency measurements
                if len(self.ping_stats[peer_id]["latency"]) > 10:
                    self.ping_stats[peer_id]["latency"].pop(0)
                
                return success, latency
        except Exception as e:
            logger.error(f"Error pinging peer {peer_id}: {e}")
            
            # Update stats
            if peer_id not in self.ping_stats:
                self.ping_stats[peer_id] = {
                    "success": 0,
                    "failure": 0,
                    "latency": []
                }
            
            self.ping_stats[peer_id]["failure"] += 1
            
            return False, 0


def apply_protocol_adapters(peer):
    """
    Apply all protocol adapters to a libp2p peer.
    
    Args:
        peer: The libp2p peer instance
        
    Returns:
        Dict of protocol adapters that were applied
    """
    # Create and apply protocol adapters
    adapters = {
        "bitswap": BitswapAdapter(peer),
        "dht": DHTAdapter(peer),
        "identify": IdentifyAdapter(peer),
        "ping": PingAdapter(peer),
    }
    
    # Add adapters to peer
    peer.protocol_adapters = adapters
    
    # Add convenience methods
    _add_convenience_methods(peer, adapters)
    
    logger.info(f"Applied protocol adapters to peer: {list(adapters.keys())}")
    return adapters


def _add_convenience_methods(peer, adapters):
    """Add convenience methods to the peer for direct protocol access."""
    # Bitswap methods
    if "bitswap" in adapters:
        peer.get_block = adapters["bitswap"].get_block
        peer.put_block = adapters["bitswap"].put
    
    # DHT methods
    if "dht" in adapters:
        peer.find_providers = adapters["dht"].find_providers
        peer.provide = adapters["dht"].provide
        peer.store_value = adapters["dht"].store_value
        peer.get_value = adapters["dht"].get_value
    
    # Identify methods
    if "identify" in adapters:
        peer.identify_peer = adapters["identify"].identify
    
    # Ping methods
    if "ping" in adapters:
        peer.ping_peer = adapters["ping"].ping
