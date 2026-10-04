"""
WebRTC transport for libp2p offering browser-to-node communication capabilities.

This module implements WebRTC as a transport for libp2p, enabling direct peer-to-peer
connections between browsers and nodes or between nodes. It handles the WebRTC
protocol including offer/answer exchange, ICE candidate negotiation, and data
channel establishment.

Requirements:
- aiortc: WebRTC implementation for Python
- cryptography: For secure communication
"""

import anyio
import json
import logging
import uuid
import time
from typing import Dict, List, Optional, Tuple, Union, Set, Callable

try:
    import aiortc
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
    from aiortc.contrib.signaling import object_from_string, object_to_string
    HAS_WEBRTC = True
except ImportError:
    HAS_WEBRTC = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    RTCConfiguration = None
    RTCIceServer = None

try:
    from libp2p.network.stream.net_stream_interface import INetStream
    from libp2p.network.connection.raw_connection_interface import IRawConnection
    from libp2p.network.connection.net_connection_interface import INetConn
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False
    INetStream = object
    IRawConnection = object
    INetConn = object

class WebRTCStream(INetStream):
    """
    Stream implementation based on WebRTC data channel.
    
    This class adapts a WebRTC data channel to the libp2p INetStream interface,
    allowing it to be used as a standard libp2p stream.
    """
    
    def __init__(self, data_channel, protocol_id, peer_id=None):
        """
        Initialize a WebRTC stream with a data channel.
        
        Args:
            data_channel: aiortc DataChannel object
            protocol_id: Protocol ID for this stream
            peer_id: ID of the remote peer
        """
        self.data_channel = data_channel
        self.protocol_id = protocol_id
        self.peer_id = peer_id
        self.logger = logging.getLogger("WebRTCStream")
        
        # Buffer for received data
        self.receive_buffer = bytearray()
        self.message_event = anyio.Event()
        
        # Set up data channel callbacks
        data_channel.add_listener("message", self._on_message)
        data_channel.add_listener("open", self._on_open)
        data_channel.add_listener("close", self._on_close)
        
        # State tracking
        self.is_open = anyio.Event()
        if data_channel.readyState == "open":
            self.is_open.set()
        
    def _on_message(self, message):
        """Handle incoming message from the data channel."""
        if isinstance(message, str):
            self.receive_buffer.extend(message.encode())
        else:
            self.receive_buffer.extend(message)
        self.message_event.set()
        
    def _on_open(self):
        """Handle data channel open event."""
        self.is_open.set()
        
    def _on_close(self):
        """Handle data channel close event."""
        self.is_open.clear()
        self.message_event.set()  # Wake up any waiting read operations
    
    async def read(self, n=-1):
        """
        Read data from the stream.
        
        Args:
            n: Number of bytes to read, or -1 for all available data
            
        Returns:
            Bytes read from the stream
        """
        await self.is_open.wait()
        
        # If buffer is empty, wait for data
        if not self.receive_buffer and self.data_channel.readyState == "open":
            self.message_event.clear()
            try:
                await anyio.wait_for(self.message_event.wait(), timeout=30)
            except anyio.TimeoutError:
                # Return empty bytes on timeout
                return b""
        
        # Return data from buffer
        if n == -1 or n >= len(self.receive_buffer):
            # Return all data
            data = bytes(self.receive_buffer)
            self.receive_buffer.clear()
            return data
        else:
            # Return requested bytes
            data = bytes(self.receive_buffer[:n])
            self.receive_buffer = self.receive_buffer[n:]
            return data
    
    async def read_until(self, delimiter, max_bytes=None):
        """
        Read from the stream until delimiter is found.
        
        Args:
            delimiter: Bytes delimiter to read until
            max_bytes: Maximum number of bytes to read
            
        Returns:
            Bytes read including the delimiter
        """
        if not isinstance(delimiter, bytes):
            raise ValueError("Delimiter must be bytes")
            
        buffer = bytearray()
        
        while True:
            # Check max bytes limit
            if max_bytes is not None and len(buffer) >= max_bytes:
                break
                
            # Read a chunk of data
            chunk = await self.read(1024)
            
            # End of stream
            if not chunk:
                break
                
            # Add to buffer
            buffer.extend(chunk)
            
            # Check for delimiter
            if delimiter in buffer:
                # Find the complete data up to and including delimiter
                all_data = bytes(buffer)
                delimiter_pos = all_data.find(delimiter) + len(delimiter)
                
                # Put any remaining data back in the receive buffer
                if delimiter_pos < len(all_data):
                    self.receive_buffer[0:0] = all_data[delimiter_pos:]
                    
                return all_data[:delimiter_pos]
        
        # Return all data if delimiter not found
        return bytes(buffer)
    
    async def write(self, data):
        """
        Write data to the stream.
        
        Args:
            data: Data to write (bytes or string)
            
        Returns:
            Number of bytes written
        """
        await self.is_open.wait()
        
        if self.data_channel.readyState != "open":
            raise ConnectionError("Data channel is not open")
            
        # Convert to bytes if necessary
        if isinstance(data, str):
            data_bytes = data.encode()
        else:
            data_bytes = data
            
        # Send data
        self.data_channel.send(data_bytes)
        return len(data_bytes)
    
    async def close(self):
        """Close the stream."""
        self.data_channel.close()
        self.is_open.clear()

class WebRTCRawConnection(IRawConnection):
    """
    Raw connection implementation based on WebRTC.
    
    This class adapts a WebRTC peer connection to the libp2p IRawConnection interface.
    """
    
    def __init__(self, peer_connection, data_channel):
        """
        Initialize a WebRTC raw connection.
        
        Args:
            peer_connection: RTCPeerConnection object
            data_channel: Main data channel for this connection
        """
        self.peer_connection = peer_connection
        self.main_channel = data_channel
        self.logger = logging.getLogger("WebRTCRawConnection")
        
        # Store data channels for different streams
        self.data_channels = {}
        if data_channel:
            self.data_channels[data_channel.label] = data_channel
            
    async def open(self):
        """Open the connection."""
        # Wait for the main data channel to open
        if self.main_channel and self.main_channel.readyState != "open":
            # Create a future to wait for the main channel to open
            future = anyio.Future()
            
            def on_open():
                future.set_result(None)
                
            self.main_channel.add_listener("open", on_open)
            
            try:
                await anyio.wait_for(future, timeout=30)
            except anyio.TimeoutError:
                raise ConnectionError("Timed out waiting for data channel to open")
                
        return True
        
    async def create_data_channel(self, protocol_id):
        """
        Create a new data channel for a specific protocol.
        
        Args:
            protocol_id: Protocol ID for the new data channel
            
        Returns:
            New data channel
        """
        # Use a unique label based on protocol
        label = f"p2p-{uuid.uuid4()}"
        
        # Create the data channel
        channel = self.peer_connection.createDataChannel(label)
        
        # Store the channel
        self.data_channels[label] = channel
        
        # Wait for the channel to open
        future = anyio.Future()
        
        def on_open():
            future.set_result(None)
            
        channel.add_listener("open", on_open)
        
        try:
            await anyio.wait_for(future, timeout=30)
        except anyio.TimeoutError:
            raise ConnectionError("Timed out waiting for data channel to open")
            
        return channel
        
    async def close(self):
        """Close the connection."""
        # Close all data channels
        for channel in self.data_channels.values():
            channel.close()
            
        # Close the peer connection
        await self.peer_connection.close()

class WebRTCConnection(INetConn):
    """
    Network connection implementation based on WebRTC.
    
    This class adapts a WebRTC peer connection to the libp2p INetConn interface.
    """
    
    def __init__(self, raw_conn, peer_id, local_peer, remote_addr=None):
        """
        Initialize a WebRTC network connection.
        
        Args:
            raw_conn: WebRTCRawConnection object
            peer_id: ID of the remote peer
            local_peer: Local peer ID
            remote_addr: Remote multiaddress
        """
        self.raw_conn = raw_conn
        self.peer_id = peer_id
        self.local_peer = local_peer
        self.remote_addr = remote_addr
        self.logger = logging.getLogger("WebRTCConnection")
        
        # Stream tracking
        self.streams = {}
        self.next_stream_id = 0
        
    async def new_stream(self, protocol_id):
        """
        Create a new stream for the given protocol.
        
        Args:
            protocol_id: Protocol ID for the new stream
            
        Returns:
            New WebRTCStream
        """
        try:
            # Create a new data channel for this stream
            channel = await self.raw_conn.create_data_channel(protocol_id)
            
            # Create stream
            stream = WebRTCStream(channel, protocol_id, self.peer_id)
            
            # Store stream
            stream_id = self.next_stream_id
            self.next_stream_id += 1
            self.streams[stream_id] = stream
            
            return stream
            
        except Exception as e:
            self.logger.error(f"Error creating new stream: {e}")
            raise
            
    async def get_streams(self):
        """Get all streams associated with this connection."""
        return list(self.streams.values())
    
    def get_local_peer(self):
        """Get the local peer ID."""
        return self.local_peer
        
    def get_remote_peer(self):
        """Get the remote peer ID."""
        return self.peer_id
        
    def get_remote_public_key(self):
        """Get the remote peer's public key."""
        # Not directly available from WebRTC
        return None
        
    def get_remote_addr(self):
        """Get the remote peer's address."""
        return self.remote_addr
        
    async def close(self):
        """Close the connection."""
        # Close all streams
        for stream in self.streams.values():
            await stream.close()
            
        # Close the raw connection
        await self.raw_conn.close()

class WebRTCTransport:
    """
    WebRTC transport implementation for libp2p.
    
    This class provides a WebRTC transport for libp2p, enabling direct peer-to-peer
    connections between browsers and nodes or between nodes. It handles the WebRTC
    protocol including offer/answer exchange, ICE candidate negotiation, and data
    channel establishment.
    """
    
    def __init__(self, host, signaling_server=None, ice_servers=None, identity=None):
        """
        Initialize WebRTC transport with optional signaling server.
        
        Args:
            host: The libp2p host
            signaling_server: URL of a signaling server for connection establishment
            ice_servers: List of STUN/TURN server URLs
            identity: Optional libp2p identity to use for WebRTC connections
        """
        if not HAS_WEBRTC:
            raise ImportError("WebRTC support requires the aiortc package")
            
        self.host = host
        self.signaling_server = signaling_server
        self.identity = identity
        self.logger = logging.getLogger("WebRTCTransport")
        
        # Set up ICE servers
        self.ice_servers = ice_servers or [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"])
        ]
        
        # Set up peer connections and data channels
        self.peer_connections = {}
        self.raw_connections = {}
        self.net_connections = {}
        
        # Tracking for ICE candidates
        self.pending_ice_candidates = {}
        
        # Signal handlers for protocol negotiation
        self.signal_handlers = {}
        
        # Protocol handlers for incoming streams
        self.protocol_handlers = {}
        
    async def dial(self, peer_id, protocols=None, timeout=30):
        """
        Establish WebRTC connection to a peer.
        
        Args:
            peer_id: ID of the peer to connect to
            protocols: List of protocol IDs to negotiate
            timeout: Timeout in seconds
            
        Returns:
            WebRTCStream for the successfully negotiated protocol
        """
        if not HAS_WEBRTC:
            raise ImportError("WebRTC support requires the aiortc package")
            
        # Check if we already have a connection
        if peer_id in self.net_connections:
            # Use existing connection to create a new stream
            if protocols:
                # Try each protocol until one succeeds
                for protocol_id in protocols:
                    try:
                        return await self.net_connections[peer_id].new_stream(protocol_id)
                    except Exception as e:
                        self.logger.debug(f"Failed to create stream for protocol {protocol_id}: {e}")
                        continue
                
                # None of the protocols succeeded
                raise ValueError(f"None of the provided protocols could be negotiated with peer {peer_id}")
            else:
                raise ValueError("No protocols specified for stream creation")
        
        # Create a new WebRTC connection
        pc = RTCPeerConnection(RTCConfiguration(iceServers=self.ice_servers))
        
        # Create a data channel for the connection
        dc = pc.createDataChannel("libp2p-main")
        
        # Store in our tracking dictionaries
        self.peer_connections[peer_id] = pc
        
        # Create and store raw connection
        raw_conn = WebRTCRawConnection(pc, dc)
        self.raw_connections[peer_id] = raw_conn
        
        # Set up ICE candidate handling
        self.pending_ice_candidates[peer_id] = []
        
        @pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate:
                # Store the candidate for later sending
                self.pending_ice_candidates[peer_id].append(candidate)
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Create signaling message
        offer_dict = {
            "type": "offer",
            "sdp": pc.localDescription.sdp,
            "peer_id": str(self.host.get_id())
        }
        
        # Exchange the offer and receive answer via signaling
        try:
            answer_dict = await self._exchange_signaling(peer_id, offer_dict)
            
            # Process the answer
            answer = RTCSessionDescription(sdp=answer_dict["sdp"], type="answer")
            await pc.setRemoteDescription(answer)
            
            # Process any ICE candidates from the answer
            if "candidates" in answer_dict:
                for candidate in answer_dict["candidates"]:
                    await pc.addIceCandidate(candidate)
            
            # Get remote address from answer if available
            remote_addr = None
            if "addr" in answer_dict:
                from multiaddr import Multiaddr
                remote_addr = Multiaddr(answer_dict["addr"])
            
            # Wait for connection establishment
            try:
                await anyio.wait_for(raw_conn.open(), timeout=timeout)
            except anyio.TimeoutError:
                raise ConnectionError(f"Timed out waiting for WebRTC connection to peer {peer_id}")
                
            # Create network connection
            net_conn = WebRTCConnection(raw_conn, peer_id, self.host.get_id(), remote_addr)
            self.net_connections[peer_id] = net_conn
            
            # Create a stream for the requested protocol
            if protocols:
                # Try each protocol until one succeeds
                for protocol_id in protocols:
                    try:
                        stream = await net_conn.new_stream(protocol_id)
                        # Success
                        return stream
                    except Exception as e:
                        self.logger.debug(f"Failed to create stream for protocol {protocol_id}: {e}")
                        continue
                
                # None of the protocols succeeded
                raise ValueError(f"None of the provided protocols could be negotiated with peer {peer_id}")
            else:
                raise ValueError("No protocols specified for stream creation")
                
        except Exception as e:
            # Clean up on failure
            self.logger.error(f"Error establishing WebRTC connection to peer {peer_id}: {e}")
            
            # Remove tracking entries
            if peer_id in self.peer_connections:
                del self.peer_connections[peer_id]
            if peer_id in self.raw_connections:
                del self.raw_connections[peer_id]
            if peer_id in self.pending_ice_candidates:
                del self.pending_ice_candidates[peer_id]
                
            # Close the peer connection
            await pc.close()
            
            raise
    
    async def listen(self, multiaddr):
        """
        Listen for incoming WebRTC connections.
        
        Args:
            multiaddr: Multiaddress to listen on
            
        Returns:
            True if listening started successfully
        """
        if not HAS_WEBRTC:
            raise ImportError("WebRTC support requires the aiortc package")
            
        # Parse multiaddr to extract relevant information
        from multiaddr import Multiaddr
        addr = multiaddr if isinstance(multiaddr, Multiaddr) else Multiaddr(multiaddr)
        
        # Set up signaling based on the address components
        # WebRTC typically needs some form of signaling to establish connections
        
        # Look for webrtc protocol in the multiaddr
        has_webrtc = False
        for proto in addr.protocols():
            if proto.name == "webrtc":
                has_webrtc = True
                break
                
        if not has_webrtc:
            raise ValueError("Not a WebRTC multiaddress")
            
        # Register a handler for signaling messages
        # This would typically be done via a WebSocket or other channel
        self._register_signal_handler(addr)
        
        return True
    
    def _register_signal_handler(self, addr):
        """
        Register a handler for signaling based on the address.
        
        Args:
            addr: Multiaddress to extract signaling information from
        """
        # This implementation would depend on the specific signaling mechanism
        # For example, a WebSocket server or HTTP endpoint
        signaling_id = str(addr)
        if signaling_id not in self.signal_handlers:
            self.signal_handlers[signaling_id] = self._handle_signaling_message
            
    async def _handle_signaling_message(self, message):
        """
        Handle incoming signaling messages.
        
        Args:
            message: Signaling message to process
            
        Returns:
            Response message if applicable
        """
        try:
            # Extract message type and peer ID
            msg_type = message.get("type")
            peer_id = message.get("peer_id")
            
            if not peer_id:
                raise ValueError("Missing peer_id in signaling message")
                
            if msg_type == "offer":
                # Handle incoming connection offer
                return await self._handle_offer(peer_id, message)
            elif msg_type == "ice-candidate":
                # Handle incoming ICE candidate
                return await self._handle_ice_candidate(peer_id, message)
            else:
                raise ValueError(f"Unknown signaling message type: {msg_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling signaling message: {e}")
            return {"type": "error", "error": str(e)}
    
    async def _handle_offer(self, peer_id, message):
        """
        Handle an incoming WebRTC offer.
        
        Args:
            peer_id: ID of the offering peer
            message: Offer message
            
        Returns:
            Answer message
        """
        # Create a new peer connection
        pc = RTCPeerConnection(RTCConfiguration(iceServers=self.ice_servers))
        
        # Set up ICE candidate handling
        self.pending_ice_candidates[peer_id] = []
        
        @pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate:
                self.pending_ice_candidates[peer_id].append(candidate)
        
        # Handle incoming data channels
        @pc.on("datachannel")
        def on_datachannel(channel):
            self._handle_data_channel(peer_id, pc, channel)
        
        # Store the peer connection
        self.peer_connections[peer_id] = pc
        
        # Set the remote description (the offer)
        offer = RTCSessionDescription(sdp=message["sdp"], type="offer")
        await pc.setRemoteDescription(offer)
        
        # Create an answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        # Prepare the answer message
        answer_dict = {
            "type": "answer",
            "sdp": pc.localDescription.sdp,
            "peer_id": str(self.host.get_id()),
            "candidates": self.pending_ice_candidates[peer_id]
        }
        
        # Add local address if available
        local_addrs = self.host.get_addrs()
        if local_addrs:
            answer_dict["addr"] = str(local_addrs[0])
        
        return answer_dict
    
    async def _handle_ice_candidate(self, peer_id, message):
        """
        Handle an incoming ICE candidate.
        
        Args:
            peer_id: ID of the peer sending the candidate
            message: ICE candidate message
            
        Returns:
            Acknowledgement message
        """
        if peer_id not in self.peer_connections:
            raise ValueError(f"No active connection for peer {peer_id}")
            
        pc = self.peer_connections[peer_id]
        candidate = message["candidate"]
        
        await pc.addIceCandidate(candidate)
        
        return {"type": "ack", "peer_id": str(self.host.get_id())}
    
    def _handle_data_channel(self, peer_id, pc, channel):
        """
        Handle a new data channel from a peer.
        
        Args:
            peer_id: ID of the peer
            pc: RTCPeerConnection object
            channel: Data channel to handle
        """
        # If this is the first data channel for this peer, set up the connection
        if peer_id not in self.raw_connections:
            # Create raw connection
            raw_conn = WebRTCRawConnection(pc, channel)
            self.raw_connections[peer_id] = raw_conn
            
            # Get remote address if available
            remote_addr = None
            
            # Create network connection
            net_conn = WebRTCConnection(raw_conn, peer_id, self.host.get_id(), remote_addr)
            self.net_connections[peer_id] = net_conn
            
            # Store the channel
            raw_conn.data_channels[channel.label] = channel
        else:
            # Add this channel to the existing connection
            self.raw_connections[peer_id].data_channels[channel.label] = channel
        
        # Check if this channel is for a protocol
        if channel.label.startswith("protocol-"):
            protocol_id = channel.label[9:]  # Remove "protocol-" prefix
            
            # Create a stream for this channel
            stream = WebRTCStream(channel, protocol_id, peer_id)
            
            # If we have a handler for this protocol, notify it
            if protocol_id in self.protocol_handlers:
                # Call the handler
                self.protocol_handlers[protocol_id](stream)
    
    async def _exchange_signaling(self, peer_id, offer):
        """
        Exchange signaling information with peer.
        
        This method handles the exchange of WebRTC signaling information
        (offer, answer, ICE candidates) using whatever signaling mechanism
        is available (WebSocket, HTTP, etc.)
        
        Args:
            peer_id: ID of the peer to exchange with
            offer: Offer message to send
            
        Returns:
            Answer message received from peer
        """
        # This implementation would depend on the available signaling mechanism
        # For example, a direct exchange over libp2p, a WebSocket server, or HTTP
        
        # For now, attempt to use a direct libp2p connection if possible
        try:
            # Try to use an existing libp2p connection for signaling
            stream = await self.host.new_stream(peer_id, ["/webrtc/signaling/1.0.0"])
            
            # Send the offer
            await stream.write(json.dumps(offer).encode() + b"\n")
            
            # Wait for the answer
            answer_data = await stream.read_until(b"\n")
            if not answer_data:
                raise ConnectionError("No answer received from peer")
                
            # Parse the answer
            answer = json.loads(answer_data.decode().strip())
            
            # Close the signaling stream
            await stream.close()
            
            return answer
            
        except Exception as e:
            self.logger.warning(f"Failed to use direct libp2p signaling: {e}")
            
            # Fall back to signaling server if configured
            if self.signaling_server:
                try:
                    # Use the signaling server for exchange
                    # This would typically be implemented with WebSocket or HTTP
                    return {"error": "Signaling server not implemented"}
                except Exception as e:
                    self.logger.error(f"Failed to use signaling server: {e}")
                    raise
            else:
                raise ConnectionError("No signaling mechanism available for WebRTC connection")
    
    def set_protocol_handler(self, protocol_id, handler):
        """
        Set a handler for a specific protocol.
        
        Args:
            protocol_id: Protocol ID to handle
            handler: Function to call with new streams for this protocol
        """
        self.protocol_handlers[protocol_id] = handler
    
    async def close(self):
        """Close all connections and stop listening."""
        # Close all connections
        for peer_id, net_conn in list(self.net_connections.items()):
            try:
                await net_conn.close()
            except Exception as e:
                self.logger.warning(f"Error closing connection to peer {peer_id}: {e}")
                
        # Clear dictionaries
        self.peer_connections.clear()
        self.raw_connections.clear()
        self.net_connections.clear()
        self.pending_ice_candidates.clear()

# Utility function to check if WebRTC is available
def is_webrtc_available():
    """Check if WebRTC support is available."""
    return HAS_WEBRTC