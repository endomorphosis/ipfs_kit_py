"""
DAG Exchange protocol implementation for libp2p.

This module implements the DAG exchange protocol (GraphSync) for libp2p, enabling
efficient exchange of IPLD-based content between peers with partial and selective
querying capabilities.

References:
- GraphSync spec: https://github.com/ipfs/specs/blob/master/GRAPHSYNC.md
- IPLD specs: https://github.com/ipld/specs
"""

import anyio
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Union, Any, Callable

try:
    import cbor2
    HAS_CBOR = True
except ImportError:
    HAS_CBOR = False
    
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

# Protocol ID for DAG Exchange
PROTOCOL_ID = "/ipfs/graphsync/1.0.0"

class MessageType(Enum):
    """GraphSync message types."""
    REQUEST = 0
    RESPONSE = 1
    CANCEL = 2
    UPDATE = 3

class ResponseCode(Enum):
    """GraphSync response codes."""
    OK = 10
    PARTIAL = 11
    NOT_FOUND = 20
    REQUEST_FAILED = 21
    INTERNAL_ERROR = 30
    INVALID_REQUEST = 31
    REJECTED = 32
    TIMEOUT = 33
    WOULD_BLOCK = 34

class DAGExchangeError(Exception):
    """Base exception for DAG Exchange errors."""
    pass

class RequestNotFoundError(DAGExchangeError):
    """Request not found error."""
    pass

class InvalidRequestError(DAGExchangeError):
    """Invalid request error."""
    pass

@dataclass
class RequestOptions:
    """Options for a DAG exchange request."""
    max_blocks: Optional[int] = None
    max_depth: Optional[int] = None
    priority: int = 0
    client_timeout: float = 60.0
    server_timeout: float = 60.0
    extensions: Optional[Dict[str, Any]] = None
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        result = {}
        
        if self.max_blocks is not None:
            result['maxBlocks'] = self.max_blocks
            
        if self.max_depth is not None:
            result['maxDepth'] = self.max_depth
            
        if self.priority != 0:
            result['priority'] = self.priority
            
        if self.client_timeout != 60.0:
            result['clientTimeout'] = self.client_timeout
            
        if self.server_timeout != 60.0:
            result['serverTimeout'] = self.server_timeout
            
        if self.extensions:
            result['extensions'] = self.extensions
            
        return result
        
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary after deserialization."""
        return cls(
            max_blocks=data.get('maxBlocks'),
            max_depth=data.get('maxDepth'),
            priority=data.get('priority', 0),
            client_timeout=data.get('clientTimeout', 60.0),
            server_timeout=data.get('serverTimeout', 60.0),
            extensions=data.get('extensions')
        )

@dataclass
class Request:
    """DAG exchange request."""
    request_id: str
    root_cid: str
    selector: Any
    options: RequestOptions
    created_at: float = None
    
    def __post_init__(self):
        """Initialize created_at if not provided."""
        if self.created_at is None:
            self.created_at = time.time()
            
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            'requestId': self.request_id,
            'rootCid': self.root_cid,
            'selector': self.selector,
            'options': self.options.to_dict(),
            'createdAt': self.created_at
        }
        
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary after deserialization."""
        return cls(
            request_id=data['requestId'],
            root_cid=data['rootCid'],
            selector=data['selector'],
            options=RequestOptions.from_dict(data.get('options', {})),
            created_at=data.get('createdAt', time.time())
        )

@dataclass
class Response:
    """DAG exchange response."""
    request_id: str
    status: ResponseCode
    blocks: Dict[str, bytes]
    extensions: Optional[Dict[str, Any]] = None
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        result = {
            'requestId': self.request_id,
            'status': self.status.value,
            'blocks': {cid: block.hex() for cid, block in self.blocks.items()}
        }
        
        if self.extensions:
            result['extensions'] = self.extensions
            
        return result
        
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary after deserialization."""
        # Convert blocks from hex strings to bytes
        blocks = {}
        for cid, block_hex in data.get('blocks', {}).items():
            if isinstance(block_hex, str):
                blocks[cid] = bytes.fromhex(block_hex)
            else:
                blocks[cid] = block_hex
                
        return cls(
            request_id=data['requestId'],
            status=ResponseCode(data['status']),
            blocks=blocks,
            extensions=data.get('extensions')
        )

class DAGExchange:
    """
    DAG Exchange protocol implementation for libp2p.
    
    This class implements the DAG Exchange protocol (GraphSync) for efficient
    exchange of IPLD-based content between peers with partial and selective
    querying capabilities.
    """
    
    def __init__(self, host, blockstore=None):
        """
        Initialize DAG Exchange.
        
        Args:
            host: The libp2p host
            blockstore: Optional blockstore for storing and retrieving blocks
        """
        if not HAS_CBOR:
            raise ImportError("DAG Exchange requires the cbor2 package")
            
        if not HAS_LIBP2P:
            raise ImportError("DAG Exchange requires libp2p to be installed")
            
        self.host = host
        self.blockstore = blockstore
        self.logger = logging.getLogger("DAGExchange")
        
        # Request tracking
        self.outgoing_requests = {}
        self.incoming_requests = {}
        
        # Response callbacks
        self.response_handlers = {}
        
        # Block retrieval function
        self.block_getter = None
        
        # Selector evaluation function
        self.selector_evaluator = None
        
        # Running state
        self.running = False
        
    async def start(self):
        """Start the DAG Exchange protocol."""
        if self.running:
            return
            
        self.running = True
        
        # Register protocol handler
        self.host.set_stream_handler(PROTOCOL_ID, self._handle_incoming_stream)
        
        self.logger.info("DAG Exchange protocol started")
        
    async def stop(self):
        """Stop the DAG Exchange protocol."""
        if not self.running:
            return
            
        self.running = False
        
        # Unregister protocol handler
        self.host.remove_stream_handler(PROTOCOL_ID)
        
        # Cancel all pending requests
        for request_id in list(self.outgoing_requests.keys()):
            await self.cancel_request(request_id)
            
        self.logger.info("DAG Exchange protocol stopped")
        
    def set_block_getter(self, getter_func):
        """
        Set a function to get blocks from the blockstore.
        
        Args:
            getter_func: Function that takes a CID and returns a block
        """
        self.block_getter = getter_func
        
    def set_selector_evaluator(self, evaluator_func):
        """
        Set a function to evaluate selectors and return matching blocks.
        
        Args:
            evaluator_func: Function that takes a root CID and selector and returns matching blocks
        """
        self.selector_evaluator = evaluator_func
        
    async def request(self, peer_id, root_cid, selector, options=None, callback=None):
        """
        Request blocks from a peer.
        
        Args:
            peer_id: ID of the peer to request from
            root_cid: Root CID to start traversal from
            selector: IPLD selector to determine which blocks to retrieve
            options: Request options
            callback: Function to call with response updates
            
        Returns:
            Request ID
        """
        if not self.running:
            raise DAGExchangeError("DAG Exchange protocol not running")
            
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Create request
        request = Request(
            request_id=request_id,
            root_cid=root_cid,
            selector=selector,
            options=options or RequestOptions()
        )
        
        # Store request
        self.outgoing_requests[request_id] = request
        
        # Set up response handler
        if callback:
            self.response_handlers[request_id] = callback
            
        # Send request
        try:
            # Open stream to peer
            stream = await self.host.new_stream(peer_id, [PROTOCOL_ID])
            
            # Serialize and send request
            message = {
                "type": MessageType.REQUEST.value,
                "request": request.to_dict()
            }
            
            # Use CBOR for serialization
            serialized = cbor2.dumps(message)
            await stream.write(len(serialized).to_bytes(4, 'big') + serialized)
            
            # Process responses in the background
            anyio.create_task(self._process_responses(stream, request_id))
            
            return request_id
            
        except Exception as e:
            # Clean up on failure
            if request_id in self.outgoing_requests:
                del self.outgoing_requests[request_id]
                
            if request_id in self.response_handlers:
                del self.response_handlers[request_id]
                
            raise DAGExchangeError(f"Failed to send request: {e}")
            
    async def cancel_request(self, request_id):
        """
        Cancel an ongoing request.
        
        Args:
            request_id: ID of the request to cancel
            
        Returns:
            True if request was cancelled, False if not found
        """
        if request_id not in self.outgoing_requests:
            return False
            
        # Remove request
        request = self.outgoing_requests.pop(request_id)
        
        # Send cancel message if possible
        try:
            # Open stream to peer
            peer_id = request.peer_id if hasattr(request, 'peer_id') else None
            if peer_id:
                stream = await self.host.new_stream(peer_id, [PROTOCOL_ID])
                
                # Serialize and send cancel
                message = {
                    "type": MessageType.CANCEL.value,
                    "requestId": request_id
                }
                
                # Use CBOR for serialization
                serialized = cbor2.dumps(message)
                await stream.write(len(serialized).to_bytes(4, 'big') + serialized)
                await stream.close()
        except Exception as e:
            self.logger.warning(f"Error sending cancel message: {e}")
            
        # Remove response handler
        if request_id in self.response_handlers:
            del self.response_handlers[request_id]
            
        return True
        
    async def _handle_incoming_stream(self, stream):
        """
        Handle an incoming DAG Exchange stream.
        
        Args:
            stream: The incoming stream
        """
        peer_id = stream.get_protocol()
        
        try:
            # Process messages from the stream
            while True:
                # Read message length
                length_bytes = await stream.read(4)
                if not length_bytes or len(length_bytes) < 4:
                    break
                    
                # Decode message length
                message_length = int.from_bytes(length_bytes, 'big')
                
                # Read message
                message_bytes = await stream.read(message_length)
                if not message_bytes or len(message_bytes) < message_length:
                    break
                    
                # Decode message
                message = cbor2.loads(message_bytes)
                
                # Process message based on type
                message_type = MessageType(message.get("type", 0))
                
                if message_type == MessageType.REQUEST:
                    # Handle request
                    await self._handle_request(stream, peer_id, message)
                elif message_type == MessageType.RESPONSE:
                    # Handle response
                    await self._handle_response(message)
                elif message_type == MessageType.CANCEL:
                    # Handle cancel
                    await self._handle_cancel(message)
                elif message_type == MessageType.UPDATE:
                    # Handle update
                    await self._handle_update(message)
                else:
                    # Unknown message type
                    self.logger.warning(f"Unknown message type: {message_type}")
                    
        except Exception as e:
            self.logger.warning(f"Error handling DAG Exchange stream: {e}")
            
        finally:
            # Close the stream
            await stream.close()
            
    async def _handle_request(self, stream, peer_id, message):
        """
        Handle a DAG Exchange request.
        
        Args:
            stream: The stream to respond on
            peer_id: ID of the requesting peer
            message: The request message
        """
        # Extract request
        try:
            request_dict = message.get("request", {})
            request = Request.from_dict(request_dict)
        except (KeyError, ValueError) as e:
            # Send error response
            response = Response(
                request_id=request_dict.get("requestId", "unknown"),
                status=ResponseCode.INVALID_REQUEST,
                blocks={},
                extensions={"error": str(e)}
            )
            
            await self._send_response(stream, response)
            return
            
        # Store request
        self.incoming_requests[request.request_id] = {
            "request": request,
            "peer_id": peer_id,
            "stream": stream,
            "started_at": time.time()
        }
        
        # Process request
        anyio.create_task(self._process_request(request, stream))
        
    async def _process_request(self, request, stream):
        """
        Process a DAG Exchange request.
        
        Args:
            request: The request to process
            stream: The stream to respond on
        """
        # Check if we have a selector evaluator
        if not self.selector_evaluator:
            # Send error response
            response = Response(
                request_id=request.request_id,
                status=ResponseCode.INTERNAL_ERROR,
                blocks={},
                extensions={"error": "No selector evaluator configured"}
            )
            
            await self._send_response(stream, response)
            return
            
        try:
            # Evaluate selector to get matching blocks
            blocks = await self.selector_evaluator(request.root_cid, request.selector)
            
            # Check if we found any blocks
            if not blocks:
                # Send not found response
                response = Response(
                    request_id=request.request_id,
                    status=ResponseCode.NOT_FOUND,
                    blocks={}
                )
                
                await self._send_response(stream, response)
                return
                
            # Apply max blocks limit if specified
            if request.options.max_blocks and len(blocks) > request.options.max_blocks:
                # Trim blocks and send partial response
                limited_blocks = dict(list(blocks.items())[:request.options.max_blocks])
                response = Response(
                    request_id=request.request_id,
                    status=ResponseCode.PARTIAL,
                    blocks=limited_blocks,
                    extensions={"remainingBlocks": len(blocks) - len(limited_blocks)}
                )
            else:
                # Send complete response
                response = Response(
                    request_id=request.request_id,
                    status=ResponseCode.OK,
                    blocks=blocks
                )
                
            await self._send_response(stream, response)
            
        except Exception as e:
            # Send error response
            response = Response(
                request_id=request.request_id,
                status=ResponseCode.REQUEST_FAILED,
                blocks={},
                extensions={"error": str(e)}
            )
            
            await self._send_response(stream, response)
            
        finally:
            # Clean up request
            if request.request_id in self.incoming_requests:
                del self.incoming_requests[request.request_id]
                
    async def _send_response(self, stream, response):
        """
        Send a DAG Exchange response.
        
        Args:
            stream: The stream to send on
            response: The response to send
        """
        try:
            # Serialize response
            message = {
                "type": MessageType.RESPONSE.value,
                "response": response.to_dict()
            }
            
            # Use CBOR for serialization
            serialized = cbor2.dumps(message)
            await stream.write(len(serialized).to_bytes(4, 'big') + serialized)
            
        except Exception as e:
            self.logger.warning(f"Error sending response: {e}")
            
    async def _process_responses(self, stream, request_id):
        """
        Process responses for a request.
        
        Args:
            stream: The stream to read from
            request_id: ID of the request
        """
        try:
            while request_id in self.outgoing_requests:
                # Read message length
                length_bytes = await stream.read(4)
                if not length_bytes or len(length_bytes) < 4:
                    break
                    
                # Decode message length
                message_length = int.from_bytes(length_bytes, 'big')
                
                # Read message
                message_bytes = await stream.read(message_length)
                if not message_bytes or len(message_bytes) < message_length:
                    break
                    
                # Decode message
                message = cbor2.loads(message_bytes)
                
                # Handle response
                await self._handle_response(message)
                
        except Exception as e:
            self.logger.warning(f"Error processing responses: {e}")
            
        finally:
            # Clean up request on stream close
            if request_id in self.outgoing_requests:
                del self.outgoing_requests[request_id]
                
            if request_id in self.response_handlers:
                del self.response_handlers[request_id]
                
    async def _handle_response(self, message):
        """
        Handle a DAG Exchange response.
        
        Args:
            message: The response message
        """
        # Extract response
        try:
            response_dict = message.get("response", {})
            response = Response.from_dict(response_dict)
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Invalid response: {e}")
            return
            
        # Get request ID
        request_id = response.request_id
        
        # Check if we have a handler for this request
        if request_id in self.response_handlers:
            # Call handler
            handler = self.response_handlers[request_id]
            try:
                handler(response)
            except Exception as e:
                self.logger.warning(f"Error in response handler: {e}")
                
        # Check if request is complete
        if response.status in (ResponseCode.OK, ResponseCode.NOT_FOUND, ResponseCode.REQUEST_FAILED):
            # Clean up request
            if request_id in self.outgoing_requests:
                del self.outgoing_requests[request_id]
                
            if request_id in self.response_handlers:
                del self.response_handlers[request_id]
                
    async def _handle_cancel(self, message):
        """
        Handle a DAG Exchange cancel message.
        
        Args:
            message: The cancel message
        """
        # Extract request ID
        request_id = message.get("requestId")
        if not request_id:
            return
            
        # Check if we have this request
        if request_id in self.incoming_requests:
            # Remove request
            del self.incoming_requests[request_id]
            
    async def _handle_update(self, message):
        """
        Handle a DAG Exchange update message.
        
        Args:
            message: The update message
        """
        # Extract request ID and updates
        request_id = message.get("requestId")
        updates = message.get("updates", {})
        
        if not request_id or not updates:
            return
            
        # Check if we have this request
        if request_id in self.outgoing_requests:
            # Apply updates to request
            request = self.outgoing_requests[request_id]
            
            # Update options
            if "options" in updates:
                new_options = RequestOptions.from_dict(updates["options"])
                request.options = new_options
                
            # Other updates could be added here

# Utility functions for selectors

def make_simple_selector():
    """Create a simple selector that selects only the root block."""
    return {
        "type": "selector",
        "kind": "simple"
    }

def make_all_selector():
    """Create a selector that recursively selects all blocks."""
    return {
        "type": "selector",
        "kind": "all"
    }

def make_path_selector(path_segments):
    """
    Create a selector that follows a specific path.
    
    Args:
        path_segments: List of path segments to follow
        
    Returns:
        Path selector
    """
    return {
        "type": "selector",
        "kind": "path",
        "path": path_segments
    }

def make_field_selector(field_name):
    """
    Create a selector that selects a specific field.
    
    Args:
        field_name: Field name to select
        
    Returns:
        Field selector
    """
    return {
        "type": "selector",
        "kind": "field",
        "field": field_name
    }

def make_limit_depth_selector(selector, max_depth):
    """
    Create a selector that limits recursion depth.
    
    Args:
        selector: Base selector
        max_depth: Maximum recursion depth
        
    Returns:
        Depth-limited selector
    """
    return {
        "type": "selector",
        "kind": "depth",
        "selector": selector,
        "maxDepth": max_depth
    }

# Utility function to check if DAG Exchange is available
def is_dag_exchange_available():
    """Check if DAG Exchange support is available."""
    return HAS_CBOR and HAS_LIBP2P