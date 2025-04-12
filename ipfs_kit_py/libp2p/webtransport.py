"""
WebTransport protocol implementation for libp2p.

This module implements WebTransport as a transport for libp2p, providing a modern
HTTP/3-based alternative to WebRTC for browser-to-node and node-to-node communication.
WebTransport offers lower latency than WebSockets and better API design than WebRTC.

References:
- WebTransport spec: https://w3c.github.io/webtransport/
- HTTP/3 spec: https://quicwg.org/base-drafts/draft-ietf-quic-http.html
- libp2p transport spec: https://github.com/libp2p/specs/tree/master/webtransport

Requirements:
- aioquic: For QUIC and HTTP/3 implementation
"""

import anyio
import json
import logging
import ssl
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union, Callable, Any

try:
    from aioquic.asyncio import QuicConnectionProtocol, serve
    from aioquic.h3.connection import H3Connection
    from aioquic.h3.events import DataReceived, H3Event, HeadersReceived, WebTransportStreamDataReceived
    from aioquic.h3.exceptions import H3Error
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.tls import CipherSuite
    HAS_WEBTRANSPORT = True
except ImportError:
    HAS_WEBTRANSPORT = False
    QuicConnectionProtocol = object
    H3Connection = object
    H3Event = object
    QuicConfiguration = object

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

class WebTransportStream(INetStream):
    """
    Stream implementation based on WebTransport bidirectional stream.
    
    This class adapts a WebTransport stream to the libp2p INetStream interface,
    allowing it to be used as a standard libp2p stream.
    """
    
    def __init__(self, stream_id, protocol_id, connection, peer_id=None):
        """
        Initialize a WebTransport stream.
        
        Args:
            stream_id: WebTransport stream ID
            protocol_id: Protocol ID for this stream
            connection: WebTransportConnection instance
            peer_id: ID of the remote peer
        """
        self.stream_id = stream_id
        self.protocol_id = protocol_id
        self.connection = connection
        self.peer_id = peer_id
        self.logger = logging.getLogger("WebTransportStream")
        
        # Buffer for received data
        self.receive_buffer = bytearray()
        self.message_event = anyio.Event()
        
        # Status tracking
        self.closed = False
        self.open_event = anyio.Event()
        self.open_event.set()  # WebTransport streams are open when created
        
    def add_data(self, data):
        """
        Add received data to the buffer.
        
        Args:
            data: Data received from WebTransport
        """
        self.receive_buffer.extend(data)
        self.message_event.set()
    
    async def read(self, n=-1):
        """
        Read data from the stream.
        
        Args:
            n: Number of bytes to read, or -1 for all available data
            
        Returns:
            Bytes read from the stream
        """
        await self.open_event.wait()
        
        if self.closed and not self.receive_buffer:
            return b""
        
        # If buffer is empty, wait for data
        if not self.receive_buffer:
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
            data: Data to write
            
        Returns:
            Number of bytes written
        """
        await self.open_event.wait()
        
        if self.closed:
            raise ConnectionError("Stream is closed")
            
        # Convert to bytes if necessary
        if isinstance(data, str):
            data_bytes = data.encode()
        else:
            data_bytes = data
            
        # Send data via WebTransport
        await self.connection.send_stream_data(self.stream_id, data_bytes)
        
        return len(data_bytes)
    
    async def close(self):
        """Close the stream."""
        if not self.closed:
            self.closed = True
            self.open_event.clear()
            await self.connection.close_stream(self.stream_id)
            self.message_event.set()  # Wake up any waiting read operations

class WebTransportConnection(IRawConnection):
    """
    Raw connection implementation based on WebTransport.
    
    This class adapts a WebTransport connection to the libp2p IRawConnection interface.
    """
    
    def __init__(self, http_conn, session_id, peer_id=None):
        """
        Initialize a WebTransport connection.
        
        Args:
            http_conn: H3Connection object
            session_id: WebTransport session ID
            peer_id: Optional peer ID of the remote peer
        """
        self.http_conn = http_conn
        self.session_id = session_id
        self.peer_id = peer_id
        self.logger = logging.getLogger("WebTransportConnection")
        
        # Stream tracking
        self.streams = {}
        self.next_stream_id = 0
        
        # Status tracking
        self.closed = False
        self.ready = anyio.Event()
        self.ready.set()  # WebTransport connections are ready when created
    
    async def send_stream_data(self, stream_id, data):
        """
        Send data on a specific stream.
        
        Args:
            stream_id: Stream ID to send on
            data: Data to send
        """
        if self.closed:
            raise ConnectionError("Connection is closed")
            
        # Send data via WebTransport
        self.http_conn.send_stream_data(stream_id, data)
    
    async def close_stream(self, stream_id):
        """
        Close a specific stream.
        
        Args:
            stream_id: Stream ID to close
        """
        if stream_id in self.streams:
            del self.streams[stream_id]
            
        self.http_conn.send_stream_data(stream_id, b"", end_stream=True)
    
    async def open(self):
        """Open the connection."""
        await self.ready.wait()
        return not self.closed
    
    async def close(self):
        """Close the connection."""
        self.closed = True
        self.ready.clear()
        
        # Close all streams
        for stream in list(self.streams.values()):
            await stream.close()
            
        self.streams.clear()

class WebTransportProtocolHandler(QuicConnectionProtocol):
    """
    QUIC protocol handler for WebTransport connections.
    
    This class handles the HTTP/3 and WebTransport protocol details for the server side.
    """
    
    def __init__(self, *args, **kwargs):
        self.transport_handler = kwargs.pop("transport_handler", None)
        super().__init__(*args, **kwargs)
        
        self.h3 = None
        self.peer_id = None
        self.sessions = {}
        self.streams = {}
        self.logger = logging.getLogger("WebTransportProtocolHandler")
    
    def quic_event_received(self, event):
        """
        Handle QUIC protocol events.
        
        Args:
            event: QUIC event
        """
        # Create H3 connection on first event if needed
        if self.h3 is None:
            self.h3 = H3Connection(self._quic)
            
        # Process HTTP/3 events
        for h3_event in self.h3.handle_event(event):
            self.h3_event_received(h3_event)
    
    def h3_event_received(self, event):
        """
        Handle HTTP/3 events.
        
        Args:
            event: HTTP/3 event
        """
        if isinstance(event, HeadersReceived):
            # WebTransport session request
            headers = {}
            for header, value in event.headers:
                headers[header.decode()] = value.decode()
                
            # Check for WebTransport session request
            if (headers.get(":method") == "CONNECT" and 
                headers.get(":protocol") == "webtransport"):
                self._handle_webtransport_request(event.stream_id, headers)
                
        elif isinstance(event, WebTransportStreamDataReceived):
            # Data received on WebTransport stream
            session_id = event.session_id
            if session_id in self.sessions:
                # Find the right stream
                stream_id = event.stream_id
                if stream_id in self.streams:
                    # Add data to stream's buffer
                    stream = self.streams[stream_id]
                    stream.add_data(event.data)
                    
                    # Handle end of stream
                    if event.end_stream:
                        stream.closed = True
                else:
                    # New stream, notify handler
                    self._handle_new_stream(session_id, stream_id, event.data, event.end_stream)
    
    def _handle_webtransport_request(self, stream_id, headers):
        """
        Handle a WebTransport session request.
        
        Args:
            stream_id: HTTP stream ID
            headers: Request headers
        """
        # Check if we have a transport handler
        if not self.transport_handler:
            self.logger.warning("No transport handler registered, rejecting session")
            # Send error response
            response_headers = [
                (b":status", b"400"),
                (b"content-type", b"text/plain"),
            ]
            self.h3.send_headers(stream_id, response_headers, end_stream=True)
            return
            
        # Extract peer ID if available
        self.peer_id = headers.get("peer-id")
        
        # Create session ID
        session_id = stream_id
        
        # Accept the session
        response_headers = [
            (b":status", b"200"),
            (b"sec-webtransport-http3-draft", b"draft02"),
        ]
        self.h3.send_headers(stream_id, response_headers)
        
        # Create and store session
        self.sessions[session_id] = {
            "path": headers.get(":path", "/"),
            "created": time.time(),
            "peer_id": self.peer_id
        }
        
        # Notify transport handler
        if self.transport_handler:
            anyio.create_task(self.transport_handler.handle_session(
                session_id=session_id,
                path=headers.get(":path", "/"),
                peer_id=self.peer_id,
                connection=self
            ))
    
    def _handle_new_stream(self, session_id, stream_id, initial_data, end_stream):
        """
        Handle a new WebTransport stream.
        
        Args:
            session_id: WebTransport session ID
            stream_id: Stream ID
            initial_data: Initial data received on the stream
            end_stream: Whether the stream is already closed
        """
        if not self.transport_handler:
            self.logger.warning("No transport handler for new stream")
            return
            
        # The transport handler will determine the protocol
        # based on initial data or negotiation
        anyio.create_task(self.transport_handler.handle_stream(
            session_id=session_id,
            stream_id=stream_id,
            initial_data=initial_data,
            end_stream=end_stream,
            connection=self
        ))

@dataclass
class WebTransportSessionInfo:
    """Information about a WebTransport session."""
    session_id: int
    path: str
    peer_id: Optional[str] = None
    created: float = 0.0
    connection: Any = None

class WebTransport:
    """
    WebTransport implementation for libp2p.
    
    This class provides WebTransport as a transport for libp2p, enabling 
    browser-to-node and node-to-node communication using HTTP/3.
    """
    
    # Protocol ID for WebTransport in libp2p
    PROTOCOL_ID = "/webtransport/1.0.0"
    
    def __init__(self, host, certificate_path=None, private_key_path=None):
        """
        Initialize WebTransport support.
        
        Args:
            host: The libp2p host
            certificate_path: Path to TLS certificate file
            private_key_path: Path to TLS private key file
        """
        if not HAS_WEBTRANSPORT:
            raise ImportError("WebTransport requires the aioquic package")
            
        self.host = host
        self.certificate_path = certificate_path
        self.private_key_path = private_key_path
        self.logger = logging.getLogger("WebTransport")
        
        # Session tracking
        self.sessions = {}
        self.streams = {}
        
        # Protocol handlers for incoming streams
        self.protocol_handlers = {}
        
        # Server instance
        self.server = None
    
    async def start_server(self, addr="0.0.0.0", port=443):
        """
        Start the WebTransport server.
        
        Args:
            addr: Address to bind to
            port: Port to listen on
            
        Returns:
            Server instance
        """
        # Configure QUIC
        configuration = QuicConfiguration(
            alpn_protocols=["h3"],
            is_client=False,
            max_datagram_frame_size=65536,
        )
        
        # Load certificates
        if self.certificate_path and self.private_key_path:
            configuration.load_cert_chain(self.certificate_path, self.private_key_path)
        else:
            # Generate a self-signed certificate if paths not provided
            self.logger.warning("No certificate provided, generating self-signed certificate")
            import tempfile
            import subprocess
            
            cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            
            cert_path = cert_file.name
            key_path = key_file.name
            
            cert_file.close()
            key_file.close()
            
            # Generate self-signed certificate
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", key_path,
                "-out", cert_path,
                "-days", "365",
                "-nodes",
                "-subj", "/CN=localhost"
            ], check=True)
            
            configuration.load_cert_chain(cert_path, key_path)
            
            # Store paths for cleanup
            self.certificate_path = cert_path
            self.private_key_path = key_path
        
        # Start server
        self.server = await serve(
            addr,
            port,
            configuration=configuration,
            create_protocol=self._create_protocol_handler
        )
        
        self.logger.info(f"WebTransport server started on {addr}:{port}")
        return self.server
    
    def _create_protocol_handler(self):
        """
        Create a protocol handler for a new connection.
        
        Returns:
            WebTransportProtocolHandler instance
        """
        return WebTransportProtocolHandler(
            self._quic_connection_factory(),
            transport_handler=self
        )
    
    def _quic_connection_factory(self):
        """
        Create a new QUIC connection.
        
        Returns:
            QuicConfiguration instance
        """
        configuration = QuicConfiguration(
            alpn_protocols=["h3"],
            is_client=False,
            max_datagram_frame_size=65536,
        )
        
        # Load certificates if available
        if self.certificate_path and self.private_key_path:
            configuration.load_cert_chain(self.certificate_path, self.private_key_path)
            
        return configuration
    
    async def handle_session(self, session_id, path, peer_id, connection):
        """
        Handle a new WebTransport session.
        
        Args:
            session_id: WebTransport session ID
            path: Request path
            peer_id: Peer ID if provided
            connection: WebTransportProtocolHandler instance
        """
        # Store session information
        self.sessions[session_id] = WebTransportSessionInfo(
            session_id=session_id,
            path=path,
            peer_id=peer_id,
            created=time.time(),
            connection=connection
        )
        
        self.logger.info(f"New WebTransport session {session_id} from peer {peer_id}")
        
        # Determine protocols from path
        # Path may have format "/protocols/protocol1,protocol2
        protocols = []
        if path.startswith("/protocols/"):
            protocol_part = path[len("/protocols/"):]
            protocols = protocol_part.split(",")
            
        if not protocols:
            self.logger.warning(f"No protocols specified in path: {path}")
    
    async def handle_stream(self, session_id, stream_id, initial_data, end_stream, connection):
        """
        Handle a new WebTransport stream.
        
        Args:
            session_id: WebTransport session ID
            stream_id: Stream ID
            initial_data: Initial data received on the stream
            end_stream: Whether the stream is already closed
            connection: WebTransportProtocolHandler instance
        """
        if session_id not in self.sessions:
            self.logger.warning(f"Unknown session: {session_id}")
            return
            
        session = self.sessions[session_id]
        
        # Try to determine the protocol from initial data
        protocol_id = None
        if initial_data:
            try:
                # Check for protocol negotiation format
                if initial_data.startswith(b"/"):
                    # Find the newline that terminates the protocol ID
                    newline_pos = initial_data.find(b"\n")
                    if newline_pos != -1:
                        protocol_id = initial_data[:newline_pos].decode()
                        # Remove protocol ID from initial data
                        initial_data = initial_data[newline_pos+1:]
            except Exception as e:
                self.logger.warning(f"Error parsing protocol ID: {e}")
                
        # If no protocol determined, use a default
        if not protocol_id:
            protocol_id = "/libp2p/webtransport/1.0.0"
            
        # Create stream object
        stream = WebTransportStream(
            stream_id=stream_id,
            protocol_id=protocol_id,
            connection=WebTransportConnection(connection.h3, session_id, session.peer_id),
            peer_id=session.peer_id
        )
        
        # Store stream
        self.streams[stream_id] = stream
        connection.streams[stream_id] = stream
        
        # Add initial data to stream buffer
        if initial_data:
            stream.add_data(initial_data)
            
        # Handle end_stream
        if end_stream:
            stream.closed = True
            
        # Check if we have a handler for this protocol
        if protocol_id in self.protocol_handlers:
            # Call the protocol handler
            handler = self.protocol_handlers[protocol_id]
            anyio.create_task(handler(stream))
        else:
            self.logger.warning(f"No handler for protocol: {protocol_id}")
            await stream.close()
    
    def set_protocol_handler(self, protocol_id, handler):
        """
        Set a handler for a specific protocol.
        
        Args:
            protocol_id: Protocol ID to handle
            handler: Function to call with new streams for this protocol
        """
        self.protocol_handlers[protocol_id] = handler
    
    async def dial(self, peer_id, addr, protocols=None):
        """
        Dial a peer using WebTransport.
        
        Args:
            peer_id: Peer ID to dial
            addr: Address to dial (multiaddr)
            protocols: Protocol IDs to negotiate
            
        Returns:
            WebTransportStream for the successfully negotiated protocol
        """
        # This would be a client implementation
        # Not yet implemented
        raise NotImplementedError("WebTransport client support not yet implemented")
    
    async def stop(self):
        """Stop the WebTransport server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            
        # Close all sessions
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)
            
        self.logger.info("WebTransport server stopped")
    
    async def close_session(self, session_id):
        """
        Close a WebTransport session.
        
        Args:
            session_id: Session ID to close
        """
        if session_id in self.sessions:
            # Close all streams for this session
            session_streams = [s for s in self.streams.values() 
                             if s.connection.session_id == session_id]
            for stream in session_streams:
                await stream.close()
                
            # Remove streams from tracking
            self.streams = {sid: s for sid, s in self.streams.items() 
                          if s.connection.session_id != session_id}
                
            # Remove session
            del self.sessions[session_id]

# Utility function to check if WebTransport is available
def is_webtransport_available():
    """Check if WebTransport support is available."""
    return HAS_WEBTRANSPORT