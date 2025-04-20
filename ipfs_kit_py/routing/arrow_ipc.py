"""
Apache Arrow IPC Implementation for Optimized Data Routing

This module provides integration between the optimized data routing system
and Apache Arrow for high-performance, language-independent data exchange.
"""

import os
import io
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
from pathlib import Path

try:
    import pyarrow as pa
    import pyarrow.ipc as ipc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


class ArrowRoutingInterface:
    """
    Apache Arrow interface for optimized data routing.
    
    This class provides methods for encoding and decoding routing requests
    and responses using Apache Arrow, enabling efficient interprocess communication.
    """
    
    def __init__(self):
        """Initialize the Arrow routing interface."""
        if not ARROW_AVAILABLE:
            logger.warning("pyarrow not available. Install with 'pip install pyarrow'.")
        
        # Define schemas for different message types
        self._define_schemas()
    
    def _define_schemas(self):
        """Define Apache Arrow schemas for routing messages."""
        if not ARROW_AVAILABLE:
            return
        
        # Schema for routing request
        self.routing_request_schema = pa.schema([
            pa.field('request_id', pa.string()),
            pa.field('content_hash', pa.string()),
            pa.field('content_type', pa.string()),
            pa.field('content_size', pa.int64()),
            pa.field('metadata', pa.string()),  # JSON encoded
            pa.field('strategy', pa.string()),
            pa.field('priority', pa.string()),
            pa.field('available_backends', pa.list_(pa.string())),
            pa.field('client_location', pa.string()),  # JSON encoded
            pa.field('timestamp', pa.int64())
        ])
        
        # Schema for routing response
        self.routing_response_schema = pa.schema([
            pa.field('request_id', pa.string()),
            pa.field('selected_backend', pa.string()),
            pa.field('score', pa.float64()),
            pa.field('factors', pa.string()),  # JSON encoded
            pa.field('alternatives', pa.list_(
                pa.struct([
                    pa.field('backend', pa.string()),
                    pa.field('score', pa.float64())
                ])
            )),
            pa.field('timestamp', pa.int64())
        ])
        
        # Schema for routing outcome
        self.routing_outcome_schema = pa.schema([
            pa.field('backend_id', pa.string()),
            pa.field('content_hash', pa.string()),
            pa.field('content_type', pa.string()),
            pa.field('content_size', pa.int64()),
            pa.field('success', pa.bool_()),
            pa.field('duration_ms', pa.int64()),
            pa.field('error', pa.string()),
            pa.field('timestamp', pa.int64())
        ])
    
    def encode_routing_request(
        self,
        request_id: str,
        content_hash: str,
        content_type: str,
        content_size: int,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        available_backends: Optional[List[str]] = None,
        client_location: Optional[Dict[str, float]] = None,
        timestamp: Optional[int] = None
    ) -> bytes:
        """
        Encode a routing request as Arrow IPC message.
        
        Args:
            request_id: Unique request identifier
            content_hash: Content hash (if available)
            content_type: Content MIME type
            content_size: Content size in bytes
            metadata: Optional content metadata
            strategy: Optional routing strategy
            priority: Optional routing priority
            available_backends: Optional list of available backends
            client_location: Optional client geographic location
            timestamp: Optional timestamp (default: current time)
            
        Returns:
            Arrow IPC message as bytes
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Use current time if timestamp not provided
        if timestamp is None:
            timestamp = int(asyncio.get_event_loop().time() * 1000)
        
        # Convert dictionaries to JSON strings
        metadata_json = json.dumps(metadata or {})
        client_location_json = json.dumps(client_location or {})
        
        # Create record batch
        batch_data = [
            [request_id],
            [content_hash],
            [content_type],
            [content_size],
            [metadata_json],
            [strategy or ""],
            [priority or ""],
            [available_backends or []],
            [client_location_json],
            [timestamp]
        ]
        
        arrays = [pa.array(data) for data in batch_data]
        batch = pa.RecordBatch.from_arrays(arrays, schema=self.routing_request_schema)
        
        # Serialize to IPC message
        sink = pa.BufferOutputStream()
        writer = ipc.new_stream(sink, self.routing_request_schema)
        writer.write_batch(batch)
        writer.close()
        
        return sink.getvalue().to_pybytes()
    
    def decode_routing_request(self, data: bytes) -> Dict[str, Any]:
        """
        Decode an Arrow IPC routing request.
        
        Args:
            data: Arrow IPC message bytes
            
        Returns:
            Dictionary with request fields
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Read the record batch
        reader = ipc.open_stream(pa.BufferReader(data))
        batch = reader.read_next_batch()
        
        # Convert to Python dictionary
        result = {
            "request_id": batch["request_id"][0].as_py(),
            "content_hash": batch["content_hash"][0].as_py(),
            "content_type": batch["content_type"][0].as_py(),
            "content_size": batch["content_size"][0].as_py(),
            "metadata": json.loads(batch["metadata"][0].as_py()),
            "strategy": batch["strategy"][0].as_py() or None,
            "priority": batch["priority"][0].as_py() or None,
            "available_backends": [b.as_py() for b in batch["available_backends"][0]],
            "client_location": json.loads(batch["client_location"][0].as_py()),
            "timestamp": batch["timestamp"][0].as_py()
        }
        
        return result
    
    def encode_routing_response(
        self,
        request_id: str,
        selected_backend: str,
        score: float,
        factors: Optional[Dict[str, float]] = None,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[int] = None
    ) -> bytes:
        """
        Encode a routing response as Arrow IPC message.
        
        Args:
            request_id: Original request identifier
            selected_backend: Selected backend ID
            score: Score of the selected backend
            factors: Optional dictionary of factor scores
            alternatives: Optional list of alternative backends and scores
            timestamp: Optional timestamp (default: current time)
            
        Returns:
            Arrow IPC message as bytes
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Use current time if timestamp not provided
        if timestamp is None:
            timestamp = int(asyncio.get_event_loop().time() * 1000)
        
        # Convert dictionaries to JSON strings
        factors_json = json.dumps(factors or {})
        
        # Prepare alternatives
        if alternatives:
            alt_backends = [a["backend"] for a in alternatives]
            alt_scores = [a["score"] for a in alternatives]
            alt_structs = [{"backend": b, "score": s} for b, s in zip(alt_backends, alt_scores)]
        else:
            alt_structs = []
        
        # Create record batch
        batch_data = [
            [request_id],
            [selected_backend],
            [score],
            [factors_json],
            [alt_structs],
            [timestamp]
        ]
        
        arrays = [pa.array(data) for data in batch_data]
        batch = pa.RecordBatch.from_arrays(arrays, schema=self.routing_response_schema)
        
        # Serialize to IPC message
        sink = pa.BufferOutputStream()
        writer = ipc.new_stream(sink, self.routing_response_schema)
        writer.write_batch(batch)
        writer.close()
        
        return sink.getvalue().to_pybytes()
    
    def decode_routing_response(self, data: bytes) -> Dict[str, Any]:
        """
        Decode an Arrow IPC routing response.
        
        Args:
            data: Arrow IPC message bytes
            
        Returns:
            Dictionary with response fields
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Read the record batch
        reader = ipc.open_stream(pa.BufferReader(data))
        batch = reader.read_next_batch()
        
        # Convert to Python dictionary
        result = {
            "request_id": batch["request_id"][0].as_py(),
            "selected_backend": batch["selected_backend"][0].as_py(),
            "score": batch["score"][0].as_py(),
            "factors": json.loads(batch["factors"][0].as_py()),
            "alternatives": [
                {"backend": alt["backend"].as_py(), "score": alt["score"].as_py()}
                for alt in batch["alternatives"][0]
            ],
            "timestamp": batch["timestamp"][0].as_py()
        }
        
        return result
    
    def encode_routing_outcome(
        self,
        backend_id: str,
        content_hash: str,
        content_type: str,
        content_size: int,
        success: bool,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        timestamp: Optional[int] = None
    ) -> bytes:
        """
        Encode a routing outcome as Arrow IPC message.
        
        Args:
            backend_id: Backend that was used
            content_hash: Content hash
            content_type: Content MIME type
            content_size: Content size in bytes
            success: Whether the operation was successful
            duration_ms: Optional operation duration in milliseconds
            error: Optional error message
            timestamp: Optional timestamp (default: current time)
            
        Returns:
            Arrow IPC message as bytes
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Use current time if timestamp not provided
        if timestamp is None:
            timestamp = int(asyncio.get_event_loop().time() * 1000)
        
        # Create record batch
        batch_data = [
            [backend_id],
            [content_hash],
            [content_type],
            [content_size],
            [success],
            [duration_ms or 0],
            [error or ""],
            [timestamp]
        ]
        
        arrays = [pa.array(data) for data in batch_data]
        batch = pa.RecordBatch.from_arrays(arrays, schema=self.routing_outcome_schema)
        
        # Serialize to IPC message
        sink = pa.BufferOutputStream()
        writer = ipc.new_stream(sink, self.routing_outcome_schema)
        writer.write_batch(batch)
        writer.close()
        
        return sink.getvalue().to_pybytes()
    
    def decode_routing_outcome(self, data: bytes) -> Dict[str, Any]:
        """
        Decode an Arrow IPC routing outcome.
        
        Args:
            data: Arrow IPC message bytes
            
        Returns:
            Dictionary with outcome fields
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Read the record batch
        reader = ipc.open_stream(pa.BufferReader(data))
        batch = reader.read_next_batch()
        
        # Convert to Python dictionary
        result = {
            "backend_id": batch["backend_id"][0].as_py(),
            "content_hash": batch["content_hash"][0].as_py(),
            "content_type": batch["content_type"][0].as_py(),
            "content_size": batch["content_size"][0].as_py(),
            "success": batch["success"][0].as_py(),
            "duration_ms": batch["duration_ms"][0].as_py(),
            "error": batch["error"][0].as_py() or None,
            "timestamp": batch["timestamp"][0].as_py()
        }
        
        return result


class ArrowIPCServer:
    """
    Apache Arrow IPC server for routing functionality.
    
    This server allows other processes to make routing decisions through
    a high-performance IPC channel.
    """
    
    def __init__(
        self,
        socket_path: Optional[str] = None,
        routing_manager = None
    ):
        """
        Initialize the Arrow IPC server.
        
        Args:
            socket_path: Path to Unix domain socket or named pipe
            routing_manager: Optional routing manager instance
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available. Install with 'pip install pyarrow'.")
        
        self.socket_path = socket_path or self._default_socket_path()
        self.routing_manager = routing_manager
        self.arrow_interface = ArrowRoutingInterface()
        self.server = None
        self.running = False
        
        logger.info(f"Arrow IPC server initialized with socket path: {self.socket_path}")
    
    def _default_socket_path(self) -> str:
        """Get the default socket path."""
        if os.name == "posix":
            # Unix domain socket
            socket_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
            return os.path.join(socket_dir, "ipfs_kit_routing.sock")
        else:
            # Named pipe on Windows
            return r"\\.\pipe\ipfs_kit_routing"
    
    async def start(self) -> None:
        """Start the Arrow IPC server."""
        if self.running:
            return
        
        # Get routing manager if not provided
        if self.routing_manager is None:
            from .routing_manager import get_routing_manager
            self.routing_manager = get_routing_manager()
            
            if self.routing_manager is None:
                raise RuntimeError("No routing manager available")
        
        # Create socket dir if needed
        socket_dir = os.path.dirname(self.socket_path)
        os.makedirs(socket_dir, exist_ok=True)
        
        # Remove socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Start server
        self.server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path
        )
        self.running = True
        
        # Set socket permissions
        if os.name == "posix":
            os.chmod(self.socket_path, 0o770)
        
        logger.info(f"Arrow IPC server started on {self.socket_path}")
    
    async def stop(self) -> None:
        """Stop the Arrow IPC server."""
        if not self.running:
            return
        
        # Close server
        self.server.close()
        await self.server.wait_closed()
        
        # Remove socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.running = False
        logger.info("Arrow IPC server stopped")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle a client connection.
        
        Args:
            reader: Stream reader
            writer: Stream writer
        """
        client_info = writer.get_extra_info("peername")
        logger.debug(f"New client connection from {client_info}")
        
        try:
            # Read message length (4 bytes)
            length_bytes = await reader.readexactly(4)
            message_length = int.from_bytes(length_bytes, byteorder="little")
            
            # Read message data
            message_data = await reader.readexactly(message_length)
            
            # Parse message type (first byte)
            message_type = message_data[0]
            message_content = message_data[1:]
            
            # Process message
            if message_type == 1:  # Routing request
                response = await self._handle_routing_request(message_content)
            elif message_type == 3:  # Routing outcome
                response = await self._handle_routing_outcome(message_content)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                response = b"ERROR: Unknown message type"
            
            # Send response
            writer.write(len(response).to_bytes(4, byteorder="little"))
            writer.write(response)
            await writer.drain()
            
        except asyncio.IncompleteReadError:
            logger.debug("Client disconnected")
        except Exception as e:
            logger.error(f"Error handling client: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _handle_routing_request(self, data: bytes) -> bytes:
        """
        Handle a routing request.
        
        Args:
            data: Arrow IPC message data
            
        Returns:
            Response as Arrow IPC message
        """
        try:
            # Decode request
            request = self.arrow_interface.decode_routing_request(data)
            
            # Select backend
            metadata = request.get("metadata", {})
            metadata["content_hash"] = request.get("content_hash")
            
            selected_backend = await self.routing_manager.select_backend(
                content_type=request.get("content_type"),
                content_size=request.get("content_size"),
                metadata=metadata,
                available_backends=request.get("available_backends"),
                strategy=request.get("strategy"),
                priority=request.get("priority"),
                client_location=request.get("client_location")
            )
            
            # Get additional information
            insights = await self.routing_manager.get_routing_insights()
            factors = insights.get("factor_weights", {})
            score = 1.0  # Default score
            
            # Build alternatives list
            alternatives = []
            backend_scores = insights.get("backend_scores", {})
            for backend, backend_score in backend_scores.items():
                if backend != selected_backend:
                    alternatives.append({
                        "backend": backend,
                        "score": backend_score
                    })
            
            # Encode response
            response_data = self.arrow_interface.encode_routing_response(
                request_id=request.get("request_id"),
                selected_backend=selected_backend,
                score=score,
                factors=factors,
                alternatives=alternatives
            )
            
            # Add message type (2 = response)
            return b"\x02" + response_data
            
        except Exception as e:
            logger.error(f"Error handling routing request: {e}", exc_info=True)
            return b"\x00Error: " + str(e).encode()
    
    async def _handle_routing_outcome(self, data: bytes) -> bytes:
        """
        Handle a routing outcome.
        
        Args:
            data: Arrow IPC message data
            
        Returns:
            Response as bytes
        """
        try:
            # Decode outcome
            outcome = self.arrow_interface.decode_routing_outcome(data)
            
            # Record outcome
            await self.routing_manager.record_routing_outcome(
                backend_id=outcome.get("backend_id"),
                content_info={
                    "content_hash": outcome.get("content_hash"),
                    "content_type": outcome.get("content_type"),
                    "size_bytes": outcome.get("content_size")
                },
                success=outcome.get("success")
            )
            
            # Return success response
            return b"\x04OK"
            
        except Exception as e:
            logger.error(f"Error handling routing outcome: {e}", exc_info=True)
            return b"\x00Error: " + str(e).encode()


class ArrowIPCClient:
    """
    Apache Arrow IPC client for routing functionality.
    
    This client allows processes to make routing decisions through
    a high-performance IPC channel to the routing server.
    """
    
    def __init__(
        self,
        socket_path: Optional[str] = None
    ):
        """
        Initialize the Arrow IPC client.
        
        Args:
            socket_path: Path to Unix domain socket or named pipe
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available. Install with 'pip install pyarrow'.")
        
        self.socket_path = socket_path or self._default_socket_path()
        self.arrow_interface = ArrowRoutingInterface()
        self.reader = None
        self.writer = None
        
        logger.debug(f"Arrow IPC client initialized with socket path: {self.socket_path}")
    
    def _default_socket_path(self) -> str:
        """Get the default socket path."""
        if os.name == "posix":
            # Unix domain socket
            socket_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
            return os.path.join(socket_dir, "ipfs_kit_routing.sock")
        else:
            # Named pipe on Windows
            return r"\\.\pipe\ipfs_kit_routing"
    
    async def connect(self) -> None:
        """Connect to the Arrow IPC server."""
        if self.reader is not None:
            return
        
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            logger.debug(f"Connected to Arrow IPC server at {self.socket_path}")
        except Exception as e:
            logger.error(f"Error connecting to Arrow IPC server: {e}", exc_info=True)
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from the Arrow IPC server."""
        if self.writer is None:
            return
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
            self.reader = None
            self.writer = None
            logger.debug("Disconnected from Arrow IPC server")
        except Exception as e:
            logger.warning(f"Error disconnecting from Arrow IPC server: {e}")
    
    async def select_backend(
        self,
        content_type: str,
        content_size: int,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        client_location: Optional[Dict[str, float]] = None,
        request_id: Optional[str] = None
    ) -> str:
        """
        Select the optimal backend for content through IPC.
        
        Args:
            content_type: Content MIME type
            content_size: Content size in bytes
            content_hash: Optional content hash
            metadata: Optional content metadata
            available_backends: Optional list of available backends
            strategy: Optional routing strategy
            priority: Optional routing priority
            client_location: Optional client geographic location
            request_id: Optional request ID (default: generated UUID)
            
        Returns:
            ID of the selected backend
        """
        # Ensure connected
        if self.reader is None:
            await self.connect()
        
        # Generate request ID if not provided
        if request_id is None:
            import uuid
            request_id = str(uuid.uuid4())
        
        # Encode request
        request_data = self.arrow_interface.encode_routing_request(
            request_id=request_id,
            content_hash=content_hash or "",
            content_type=content_type,
            content_size=content_size,
            metadata=metadata,
            strategy=strategy,
            priority=priority,
            available_backends=available_backends,
            client_location=client_location
        )
        
        # Add message type (1 = request)
        message = b"\x01" + request_data
        
        # Send request
        self.writer.write(len(message).to_bytes(4, byteorder="little"))
        self.writer.write(message)
        await self.writer.drain()
        
        # Read response length
        length_bytes = await self.reader.readexactly(4)
        response_length = int.from_bytes(length_bytes, byteorder="little")
        
        # Read response
        response_data = await self.reader.readexactly(response_length)
        
        # Check response type
        response_type = response_data[0]
        response_content = response_data[1:]
        
        if response_type == 0:  # Error
            error_message = response_content.decode()
            raise RuntimeError(f"IPC error: {error_message}")
        elif response_type == 2:  # Routing response
            response = self.arrow_interface.decode_routing_response(response_content)
            return response["selected_backend"]
        else:
            raise RuntimeError(f"Unexpected response type: {response_type}")
    
    async def record_outcome(
        self,
        backend_id: str,
        content_type: str,
        content_size: int,
        success: bool,
        content_hash: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Record a routing outcome through IPC.
        
        Args:
            backend_id: Backend that was used
            content_type: Content MIME type
            content_size: Content size in bytes
            success: Whether the operation was successful
            content_hash: Optional content hash
            duration_ms: Optional operation duration in milliseconds
            error: Optional error message
        """
        # Ensure connected
        if self.reader is None:
            await self.connect()
        
        # Encode outcome
        outcome_data = self.arrow_interface.encode_routing_outcome(
            backend_id=backend_id,
            content_hash=content_hash or "",
            content_type=content_type,
            content_size=content_size,
            success=success,
            duration_ms=duration_ms,
            error=error
        )
        
        # Add message type (3 = outcome)
        message = b"\x03" + outcome_data
        
        # Send outcome
        self.writer.write(len(message).to_bytes(4, byteorder="little"))
        self.writer.write(message)
        await self.writer.drain()
        
        # Read response length
        length_bytes = await self.reader.readexactly(4)
        response_length = int.from_bytes(length_bytes, byteorder="little")
        
        # Read response
        response_data = await self.reader.readexactly(response_length)
        
        # Check response type
        response_type = response_data[0]
        response_content = response_data[1:]
        
        if response_type == 0:  # Error
            error_message = response_content.decode()
            raise RuntimeError(f"IPC error: {error_message}")
        elif response_type != 4:  # Not an OK response
            raise RuntimeError(f"Unexpected response type: {response_type}")


async def start_ipc_server(
    socket_path: Optional[str] = None,
    routing_manager = None
) -> ArrowIPCServer:
    """
    Start the Arrow IPC server.
    
    Args:
        socket_path: Optional socket path
        routing_manager: Optional routing manager instance
        
    Returns:
        ArrowIPCServer instance
    """
    server = ArrowIPCServer(socket_path, routing_manager)
    await server.start()
    return server