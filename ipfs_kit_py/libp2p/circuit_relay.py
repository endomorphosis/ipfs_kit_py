"""
Circuit Relay v2 implementation for libp2p.

This module implements Circuit Relay v2 protocol, which allows peers to relay
connections through intermediate peers when direct connections are not possible.
This is essential for NAT traversal and browser-to-browser connectivity.

Key features:
- Relay client: Make relay reservations and use relayed connections
- Relay server: Act as a relay for other peers
- Reservation management with limits
- Circuit establishment and management
- Integration with DCUtR for connection upgrades

References:
- https://github.com/libp2p/specs/tree/master/relay
"""

import anyio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Callable

try:
    from multiaddr import Multiaddr
    HAS_MULTIADDR = True
except ImportError:
    HAS_MULTIADDR = False
    Multiaddr = object

logger = logging.getLogger(__name__)


class RelayStatus(Enum):
    """Status of relay connections and reservations."""
    UNKNOWN = "unknown"
    RESERVATION_PENDING = "reservation_pending"
    RESERVATION_ACCEPTED = "reservation_accepted"
    RESERVATION_DENIED = "reservation_denied"
    CIRCUIT_PENDING = "circuit_pending"
    CIRCUIT_ESTABLISHED = "circuit_established"
    CIRCUIT_FAILED = "circuit_failed"
    CIRCUIT_CLOSED = "circuit_closed"


@dataclass
class RelayReservation:
    """Represents a relay reservation."""
    relay_peer_id: str
    relay_addr: str
    expiration: float
    renewal: bool = False
    limit: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """Check if the reservation has expired."""
        return time.time() >= self.expiration
    
    def time_until_expiration(self) -> float:
        """Get time in seconds until expiration."""
        return max(0, self.expiration - time.time())


@dataclass
class RelayCircuit:
    """Represents an active relay circuit."""
    circuit_id: str
    relay_peer_id: str
    src_peer_id: str
    dst_peer_id: str
    status: RelayStatus = RelayStatus.CIRCUIT_PENDING
    created_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    bytes_sent: int = 0
    bytes_received: int = 0


class CircuitRelayClient:
    """
    Circuit Relay v2 Client implementation.
    
    The client makes reservations with relay servers and uses them to establish
    circuits when direct connections are not possible.
    """
    
    PROTOCOL_ID_HOP = "/libp2p/circuit/relay/0.2.0/hop"
    PROTOCOL_ID_STOP = "/libp2p/circuit/relay/0.2.0/stop"
    
    def __init__(
        self,
        host,
        max_reservations: int = 3,
        reservation_ttl: int = 3600,
        auto_renew: bool = True
    ):
        """
        Initialize Circuit Relay Client.
        
        Args:
            host: The libp2p host
            max_reservations: Maximum number of concurrent reservations
            reservation_ttl: Time-to-live for reservations in seconds
            auto_renew: Automatically renew expiring reservations
        """
        self.host = host
        self.max_reservations = max_reservations
        self.reservation_ttl = reservation_ttl
        self.auto_renew = auto_renew
        
        self.reservations: Dict[str, RelayReservation] = {}
        self.circuits: Dict[str, RelayCircuit] = {}
        self.pending_reservations: Set[str] = set()
        
        self.logger = logging.getLogger("CircuitRelayClient")
        self._running = False
        self._task_group = None
        
    async def start(self):
        """Start the relay client."""
        if self._running:
            return
            
        self._running = True
        self.logger.info("Circuit Relay Client started")
        
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            if self.auto_renew:
                tg.start_soon(self._reservation_renewal_loop)
    
    async def stop(self):
        """Stop the relay client."""
        self._running = False
        
        # Close all active circuits
        for circuit_id in list(self.circuits.keys()):
            await self.close_circuit(circuit_id)
        
        self.logger.info("Circuit Relay Client stopped")
    
    async def make_reservation(self, relay_peer_id: str, relay_addr: Optional[str] = None) -> bool:
        """
        Make a reservation with a relay peer.
        
        Args:
            relay_peer_id: ID of the relay peer
            relay_addr: Optional multiaddr of the relay peer
            
        Returns:
            True if reservation was successful
        """
        if len(self.reservations) >= self.max_reservations:
            self.logger.warning("Maximum reservations reached")
            return False
        
        if relay_peer_id in self.pending_reservations:
            self.logger.debug(f"Reservation already pending for {relay_peer_id}")
            return False
        
        try:
            self.pending_reservations.add(relay_peer_id)
            
            # Connect to relay if address provided
            if relay_addr and hasattr(self.host, 'connect'):
                await self.host.connect(relay_addr)
            
            # Open stream with HOP protocol
            if hasattr(self.host, 'new_stream'):
                stream = await self.host.new_stream(relay_peer_id, [self.PROTOCOL_ID_HOP])
                
                # Send reservation request
                request = self._create_reservation_request()
                await stream.write(request)
                
                # Read response
                response_data = await stream.read()
                response = self._parse_reservation_response(response_data)
                
                if response.get("status") == "OK":
                    expiration = time.time() + self.reservation_ttl
                    reservation = RelayReservation(
                        relay_peer_id=relay_peer_id,
                        relay_addr=relay_addr or "",
                        expiration=expiration,
                        limit=response.get("limit")
                    )
                    
                    self.reservations[relay_peer_id] = reservation
                    self.logger.info(f"Reservation accepted by {relay_peer_id}")
                    return True
                else:
                    self.logger.warning(f"Reservation denied by {relay_peer_id}: {response.get('message')}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to make reservation with {relay_peer_id}: {e}")
            return False
        finally:
            self.pending_reservations.discard(relay_peer_id)
    
    async def dial_through_relay(
        self,
        relay_peer_id: str,
        dst_peer_id: str,
        dst_addrs: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Establish a circuit through a relay to a destination peer.
        
        Args:
            relay_peer_id: ID of the relay peer
            dst_peer_id: ID of the destination peer
            dst_addrs: Optional multiaddrs of destination
            
        Returns:
            Circuit ID if successful, None otherwise
        """
        # Check if we have a reservation
        if relay_peer_id not in self.reservations:
            self.logger.warning(f"No reservation with relay {relay_peer_id}")
            if not await self.make_reservation(relay_peer_id):
                return None
        
        reservation = self.reservations[relay_peer_id]
        if reservation.is_expired():
            self.logger.warning(f"Reservation with {relay_peer_id} expired")
            if not await self.make_reservation(relay_peer_id):
                return None
        
        try:
            # Open stream with HOP protocol
            if hasattr(self.host, 'new_stream'):
                stream = await self.host.new_stream(relay_peer_id, [self.PROTOCOL_ID_HOP])
                
                # Send circuit request
                request = self._create_circuit_request(dst_peer_id, dst_addrs)
                await stream.write(request)
                
                # Read response
                response_data = await stream.read()
                response = self._parse_circuit_response(response_data)
                
                if response.get("status") == "OK":
                    circuit_id = response.get("circuit_id", f"{relay_peer_id}-{dst_peer_id}")
                    circuit = RelayCircuit(
                        circuit_id=circuit_id,
                        relay_peer_id=relay_peer_id,
                        src_peer_id=str(self.host.get_id()),
                        dst_peer_id=dst_peer_id,
                        status=RelayStatus.CIRCUIT_ESTABLISHED
                    )
                    
                    self.circuits[circuit_id] = circuit
                    self.logger.info(f"Circuit established: {circuit_id}")
                    return circuit_id
                else:
                    self.logger.warning(f"Circuit request denied: {response.get('message')}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Failed to establish circuit through {relay_peer_id}: {e}")
            return None
    
    async def close_circuit(self, circuit_id: str):
        """Close an active circuit."""
        if circuit_id not in self.circuits:
            return
        
        circuit = self.circuits[circuit_id]
        circuit.status = RelayStatus.CIRCUIT_CLOSED
        circuit.closed_at = time.time()
        
        # TODO: Send close message to relay
        
        self.logger.info(f"Circuit closed: {circuit_id}")
        del self.circuits[circuit_id]
    
    async def _reservation_renewal_loop(self):
        """Background task to renew expiring reservations."""
        while self._running:
            try:
                await anyio.sleep(60)  # Check every minute
                
                for relay_peer_id, reservation in list(self.reservations.items()):
                    # Renew if less than 5 minutes remaining
                    if reservation.time_until_expiration() < 300:
                        self.logger.info(f"Renewing reservation with {relay_peer_id}")
                        await self.make_reservation(relay_peer_id, reservation.relay_addr)
                        
            except Exception as e:
                self.logger.error(f"Error in reservation renewal: {e}")
    
    def _create_reservation_request(self) -> bytes:
        """Create a reservation request message."""
        # TODO: Implement proper protobuf encoding
        import json
        request = {
            "type": "RESERVE",
            "ttl": self.reservation_ttl
        }
        return json.dumps(request).encode()
    
    def _parse_reservation_response(self, data: bytes) -> Dict[str, Any]:
        """Parse reservation response."""
        # TODO: Implement proper protobuf decoding
        import json
        try:
            return json.loads(data.decode())
        except:
            return {"status": "ERROR", "message": "Failed to parse response"}
    
    def _create_circuit_request(self, dst_peer_id: str, dst_addrs: Optional[List[str]]) -> bytes:
        """Create a circuit request message."""
        # TODO: Implement proper protobuf encoding
        import json
        request = {
            "type": "CONNECT",
            "peer": dst_peer_id,
            "addrs": dst_addrs or []
        }
        return json.dumps(request).encode()
    
    def _parse_circuit_response(self, data: bytes) -> Dict[str, Any]:
        """Parse circuit response."""
        # TODO: Implement proper protobuf decoding
        import json
        try:
            return json.loads(data.decode())
        except:
            return {"status": "ERROR", "message": "Failed to parse response"}
    
    def get_relay_listen_addrs(self) -> List[str]:
        """Get listen addresses for relay connections."""
        addrs = []
        for reservation in self.reservations.values():
            if not reservation.is_expired():
                # Create p2p-circuit multiaddr
                relay_addr = reservation.relay_addr
                if relay_addr:
                    circuit_addr = f"{relay_addr}/p2p-circuit"
                    addrs.append(circuit_addr)
        return addrs


class CircuitRelayServer:
    """
    Circuit Relay v2 Server implementation.
    
    The server accepts reservation requests and relays circuits between peers.
    """
    
    PROTOCOL_ID_HOP = "/libp2p/circuit/relay/0.2.0/hop"
    
    def __init__(
        self,
        host,
        max_reservations: int = 256,
        max_reservations_per_peer: int = 10,
        max_circuits: int = 256,
        max_circuits_per_peer: int = 10,
        reservation_ttl: int = 3600
    ):
        """
        Initialize Circuit Relay Server.
        
        Args:
            host: The libp2p host
            max_reservations: Maximum total reservations
            max_reservations_per_peer: Maximum reservations per peer
            max_circuits: Maximum total circuits
            max_circuits_per_peer: Maximum circuits per peer
            reservation_ttl: Default reservation time-to-live
        """
        self.host = host
        self.max_reservations = max_reservations
        self.max_reservations_per_peer = max_reservations_per_peer
        self.max_circuits = max_circuits
        self.max_circuits_per_peer = max_circuits_per_peer
        self.reservation_ttl = reservation_ttl
        
        self.reservations: Dict[str, RelayReservation] = {}
        self.circuits: Dict[str, RelayCircuit] = {}
        self.peer_reservation_count: Dict[str, int] = {}
        self.peer_circuit_count: Dict[str, int] = {}
        
        self.logger = logging.getLogger("CircuitRelayServer")
        self._running = False
    
    async def start(self):
        """Start the relay server."""
        if self._running:
            return
        
        self._running = True
        
        # Register protocol handler
        if hasattr(self.host, 'set_stream_handler'):
            self.host.set_stream_handler(self.PROTOCOL_ID_HOP, self._handle_hop_protocol)
        
        self.logger.info(
            f"Circuit Relay Server started "
            f"(max_reservations={self.max_reservations}, "
            f"max_circuits={self.max_circuits})"
        )
    
    async def stop(self):
        """Stop the relay server."""
        self._running = False
        
        # Close all circuits
        for circuit_id in list(self.circuits.keys()):
            circuit = self.circuits[circuit_id]
            circuit.status = RelayStatus.CIRCUIT_CLOSED
            circuit.closed_at = time.time()
        
        self.circuits.clear()
        self.reservations.clear()
        
        self.logger.info("Circuit Relay Server stopped")
    
    async def _handle_hop_protocol(self, stream):
        """Handle incoming HOP protocol stream."""
        try:
            # Read request
            data = await stream.read()
            request = self._parse_request(data)
            
            request_type = request.get("type")
            
            if request_type == "RESERVE":
                await self._handle_reservation_request(stream, request)
            elif request_type == "CONNECT":
                await self._handle_circuit_request(stream, request)
            else:
                self.logger.warning(f"Unknown request type: {request_type}")
                await self._send_error(stream, "Unknown request type")
                
        except Exception as e:
            self.logger.error(f"Error handling HOP protocol: {e}")
            try:
                await self._send_error(stream, str(e))
            except:
                pass
        finally:
            if hasattr(stream, 'close'):
                await stream.close()
    
    async def _handle_reservation_request(self, stream, request):
        """Handle a reservation request."""
        # Get peer ID from stream
        peer_id = str(stream.remote_peer_id) if hasattr(stream, 'remote_peer_id') else "unknown"
        
        # Check limits
        if len(self.reservations) >= self.max_reservations:
            await self._send_response(stream, {
                "status": "ERROR",
                "message": "Maximum reservations reached"
            })
            return
        
        peer_count = self.peer_reservation_count.get(peer_id, 0)
        if peer_count >= self.max_reservations_per_peer:
            await self._send_response(stream, {
                "status": "ERROR",
                "message": "Maximum reservations per peer reached"
            })
            return
        
        # Create reservation
        ttl = min(request.get("ttl", self.reservation_ttl), self.reservation_ttl)
        expiration = time.time() + ttl
        
        reservation = RelayReservation(
            relay_peer_id=str(self.host.get_id()),
            relay_addr="",  # Will be filled by client
            expiration=expiration
        )
        
        self.reservations[peer_id] = reservation
        self.peer_reservation_count[peer_id] = peer_count + 1
        
        self.logger.info(f"Reservation accepted for {peer_id}")
        
        await self._send_response(stream, {
            "status": "OK",
            "expiration": expiration,
            "limit": {
                "duration": ttl,
                "data": 1024 * 1024  # 1MB limit
            }
        })
    
    async def _handle_circuit_request(self, stream, request):
        """Handle a circuit establishment request."""
        src_peer_id = str(stream.remote_peer_id) if hasattr(stream, 'remote_peer_id') else "unknown"
        dst_peer_id = request.get("peer")
        
        # Check if source has a reservation
        if src_peer_id not in self.reservations:
            await self._send_response(stream, {
                "status": "ERROR",
                "message": "No reservation found"
            })
            return
        
        # Check circuit limits
        if len(self.circuits) >= self.max_circuits:
            await self._send_response(stream, {
                "status": "ERROR",
                "message": "Maximum circuits reached"
            })
            return
        
        peer_count = self.peer_circuit_count.get(src_peer_id, 0)
        if peer_count >= self.max_circuits_per_peer:
            await self._send_response(stream, {
                "status": "ERROR",
                "message": "Maximum circuits per peer reached"
            })
            return
        
        # Attempt to connect to destination
        try:
            dst_addrs = request.get("addrs", [])
            # TODO: Actually establish connection to destination
            
            circuit_id = f"{src_peer_id}-{dst_peer_id}"
            circuit = RelayCircuit(
                circuit_id=circuit_id,
                relay_peer_id=str(self.host.get_id()),
                src_peer_id=src_peer_id,
                dst_peer_id=dst_peer_id,
                status=RelayStatus.CIRCUIT_ESTABLISHED
            )
            
            self.circuits[circuit_id] = circuit
            self.peer_circuit_count[src_peer_id] = peer_count + 1
            
            self.logger.info(f"Circuit established: {circuit_id}")
            
            await self._send_response(stream, {
                "status": "OK",
                "circuit_id": circuit_id
            })
            
        except Exception as e:
            self.logger.error(f"Failed to establish circuit: {e}")
            await self._send_response(stream, {
                "status": "ERROR",
                "message": str(e)
            })
    
    def _parse_request(self, data: bytes) -> Dict[str, Any]:
        """Parse incoming request."""
        # TODO: Implement proper protobuf decoding
        import json
        try:
            return json.loads(data.decode())
        except:
            return {}
    
    async def _send_response(self, stream, response: Dict[str, Any]):
        """Send response to client."""
        # TODO: Implement proper protobuf encoding
        import json
        data = json.dumps(response).encode()
        await stream.write(data)
    
    async def _send_error(self, stream, message: str):
        """Send error response."""
        await self._send_response(stream, {
            "status": "ERROR",
            "message": message
        })
