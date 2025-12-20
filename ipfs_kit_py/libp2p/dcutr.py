"""
DCUtR (Direct Connection Upgrade through Relay) protocol implementation.

This module implements the DCUtR protocol which allows peers to upgrade
relayed connections to direct connections through synchronized hole punching.

DCUtR is critical for:
- Browser-to-browser connectivity
- NAT traversal without relay overhead
- Reducing load on relay servers
- Improving connection quality and latency

References:
- https://github.com/libp2p/specs/blob/master/relay/DCUtR.md
"""

import anyio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    from multiaddr import Multiaddr
    HAS_MULTIADDR = True
except ImportError:
    HAS_MULTIADDR = False
    Multiaddr = object

logger = logging.getLogger(__name__)


class DCUtRStatus(Enum):
    """Status of DCUtR hole punching attempts."""
    IDLE = "idle"
    INITIATING = "initiating"
    COORDINATING = "coordinating"
    PUNCHING = "punching"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class HolePunchAttempt:
    """Represents a hole punching attempt."""
    attempt_id: str
    remote_peer_id: str
    relay_peer_id: str
    local_addrs: List[str] = field(default_factory=list)
    remote_addrs: List[str] = field(default_factory=list)
    status: DCUtRStatus = DCUtRStatus.IDLE
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if the attempt is complete."""
        return self.status in (DCUtRStatus.SUCCESS, DCUtRStatus.FAILED, DCUtRStatus.TIMEOUT)
    
    def duration(self) -> float:
        """Get duration of the attempt in seconds."""
        end_time = self.completed_at or time.time()
        return end_time - self.started_at


class DCUtR:
    """
    DCUtR protocol implementation for upgrading relayed connections.
    
    This class implements the DCUtR protocol which coordinates simultaneous
    connection attempts from both sides to establish direct connectivity
    through NAT hole punching.
    """
    
    PROTOCOL_ID = "/libp2p/dcutr"
    
    # Message types
    MSG_CONNECT = 100
    MSG_SYNC = 300
    
    # Timeouts
    HOLE_PUNCH_TIMEOUT = 5.0  # seconds
    SYNC_TIMEOUT = 5.0  # seconds
    
    def __init__(
        self,
        host,
        max_concurrent_attempts: int = 10,
        enable_metrics: bool = True
    ):
        """
        Initialize DCUtR.
        
        Args:
            host: The libp2p host
            max_concurrent_attempts: Maximum concurrent hole punch attempts
            enable_metrics: Enable metrics collection
        """
        self.host = host
        self.max_concurrent_attempts = max_concurrent_attempts
        self.enable_metrics = enable_metrics
        
        self.active_attempts: Dict[str, HolePunchAttempt] = {}
        self.completed_attempts: List[HolePunchAttempt] = []
        
        self.logger = logging.getLogger("DCUtR")
        self._running = False
        
        # Metrics
        self.metrics = {
            "attempts_total": 0,
            "attempts_success": 0,
            "attempts_failed": 0,
            "attempts_timeout": 0,
            "avg_duration": 0.0
        }
    
    async def start(self):
        """Start the DCUtR service."""
        if self._running:
            return
        
        self._running = True
        
        # Register protocol handler
        if hasattr(self.host, 'set_stream_handler'):
            self.host.set_stream_handler(self.PROTOCOL_ID, self._handle_dcutr_protocol)
        
        self.logger.info("DCUtR started")
    
    async def stop(self):
        """Stop the DCUtR service."""
        self._running = False
        
        # Cancel all active attempts
        for attempt_id in list(self.active_attempts.keys()):
            attempt = self.active_attempts[attempt_id]
            attempt.status = DCUtRStatus.FAILED
            attempt.error = "DCUtR stopped"
            attempt.completed_at = time.time()
            self._record_completed_attempt(attempt)
        
        self.active_attempts.clear()
        self.logger.info("DCUtR stopped")
    
    async def attempt_hole_punch(
        self,
        remote_peer_id: str,
        relay_peer_id: str,
        local_addrs: Optional[List[str]] = None
    ) -> bool:
        """
        Attempt to upgrade a relayed connection to a direct connection.
        
        Args:
            remote_peer_id: ID of the remote peer
            relay_peer_id: ID of the relay peer
            local_addrs: Optional list of local addresses to use
            
        Returns:
            True if hole punch was successful
        """
        # Check concurrent attempts limit
        if len(self.active_attempts) >= self.max_concurrent_attempts:
            self.logger.warning("Maximum concurrent hole punch attempts reached")
            return False
        
        # Create attempt
        attempt_id = f"{remote_peer_id}-{time.time()}"
        attempt = HolePunchAttempt(
            attempt_id=attempt_id,
            remote_peer_id=remote_peer_id,
            relay_peer_id=relay_peer_id,
            local_addrs=local_addrs or self._get_local_addrs(),
            status=DCUtRStatus.INITIATING
        )
        
        self.active_attempts[attempt_id] = attempt
        self.metrics["attempts_total"] += 1
        
        try:
            # Phase 1: Exchange addresses via relay
            self.logger.debug(f"Starting DCUtR with {remote_peer_id} via {relay_peer_id}")
            attempt.status = DCUtRStatus.COORDINATING
            
            remote_addrs = await self._coordinate_via_relay(attempt)
            if not remote_addrs:
                raise Exception("Failed to coordinate via relay")
            
            attempt.remote_addrs = remote_addrs
            
            # Phase 2: Synchronize for simultaneous connection attempts
            self.logger.debug(f"Synchronizing with {remote_peer_id}")
            sync_time = await self._synchronize(attempt)
            if sync_time is None:
                raise Exception("Failed to synchronize")
            
            # Phase 3: Simultaneous hole punching
            self.logger.debug(f"Attempting hole punch to {remote_peer_id}")
            attempt.status = DCUtRStatus.PUNCHING
            
            success = await self._perform_hole_punch(attempt, sync_time)
            
            if success:
                attempt.status = DCUtRStatus.SUCCESS
                attempt.completed_at = time.time()
                self.metrics["attempts_success"] += 1
                self.logger.info(f"DCUtR successful with {remote_peer_id} in {attempt.duration():.2f}s")
                return True
            else:
                raise Exception("Hole punch failed")
                
        except anyio.get_cancelled_exc_class():
            attempt.status = DCUtRStatus.FAILED
            attempt.error = "Cancelled"
            self.logger.debug(f"DCUtR attempt cancelled for {remote_peer_id}")
            return False
            
        except Exception as e:
            attempt.status = DCUtRStatus.FAILED
            attempt.error = str(e)
            attempt.completed_at = time.time()
            self.metrics["attempts_failed"] += 1
            self.logger.warning(f"DCUtR failed with {remote_peer_id}: {e}")
            return False
            
        finally:
            self._record_completed_attempt(attempt)
            del self.active_attempts[attempt_id]
    
    async def _coordinate_via_relay(self, attempt: HolePunchAttempt) -> Optional[List[str]]:
        """
        Coordinate address exchange via relay.
        
        Args:
            attempt: The hole punch attempt
            
        Returns:
            List of remote addresses if successful
        """
        try:
            # Open stream to remote peer via relay
            if hasattr(self.host, 'new_stream'):
                stream = await self.host.new_stream(
                    attempt.remote_peer_id,
                    [self.PROTOCOL_ID]
                )
                
                # Send CONNECT message with our addresses
                connect_msg = self._create_connect_message(attempt.local_addrs)
                await stream.write(connect_msg)
                
                # Read response with remote addresses
                response_data = await stream.read()
                response = self._parse_connect_response(response_data)
                
                if response.get("status") == "OK":
                    return response.get("addrs", [])
                else:
                    self.logger.warning(f"Coordination failed: {response.get('message')}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error coordinating via relay: {e}")
            return None
    
    async def _synchronize(self, attempt: HolePunchAttempt) -> Optional[float]:
        """
        Synchronize with remote peer for simultaneous connection attempts.
        
        Args:
            attempt: The hole punch attempt
            
        Returns:
            Synchronized time for connection attempts
        """
        try:
            # Open stream for sync
            if hasattr(self.host, 'new_stream'):
                stream = await self.host.new_stream(
                    attempt.remote_peer_id,
                    [self.PROTOCOL_ID]
                )
                
                # Send SYNC message
                our_time = time.time()
                sync_msg = self._create_sync_message(our_time)
                await stream.write(sync_msg)
                
                # Read sync response
                with anyio.fail_after(self.SYNC_TIMEOUT):
                    response_data = await stream.read()
                    response = self._parse_sync_response(response_data)
                
                if response.get("status") == "OK":
                    their_time = response.get("time", our_time)
                    # Calculate synchronized time (average + small delay)
                    sync_time = (our_time + their_time) / 2 + 0.1
                    return sync_time
                else:
                    return None
                    
        except TimeoutError:
            self.logger.warning("Sync timeout")
            return None
        except Exception as e:
            self.logger.error(f"Error synchronizing: {e}")
            return None
    
    async def _perform_hole_punch(self, attempt: HolePunchAttempt, sync_time: float) -> bool:
        """
        Perform the actual hole punching.
        
        Args:
            attempt: The hole punch attempt
            sync_time: Time to start connection attempts
            
        Returns:
            True if successful
        """
        try:
            # Wait until sync time
            wait_time = sync_time - time.time()
            if wait_time > 0:
                await anyio.sleep(wait_time)
            
            # Attempt connections to all remote addresses simultaneously
            async with anyio.create_task_group() as tg:
                for addr in attempt.remote_addrs:
                    tg.start_soon(self._try_connect, addr, attempt.remote_peer_id)
            
            # Check if any connection succeeded
            if hasattr(self.host, 'get_network'):
                network = self.host.get_network()
                conns = network.connections.get(attempt.remote_peer_id, [])
                
                # Filter for direct (non-relayed) connections
                direct_conns = [c for c in conns if not self._is_relayed_connection(c)]
                
                if direct_conns:
                    self.logger.info(f"Direct connection established to {attempt.remote_peer_id}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error during hole punch: {e}")
            return False
    
    async def _try_connect(self, addr: str, peer_id: str):
        """Try to connect to a specific address."""
        try:
            with anyio.fail_after(self.HOLE_PUNCH_TIMEOUT):
                if hasattr(self.host, 'connect'):
                    await self.host.connect(addr)
                    self.logger.debug(f"Connected to {peer_id} at {addr}")
        except Exception as e:
            self.logger.debug(f"Connection attempt failed for {addr}: {e}")
    
    async def _handle_dcutr_protocol(self, stream):
        """Handle incoming DCUtR protocol stream."""
        try:
            # Read message
            data = await stream.read()
            message = self._parse_message(data)
            
            msg_type = message.get("type")
            
            if msg_type == self.MSG_CONNECT:
                await self._handle_connect_message(stream, message)
            elif msg_type == self.MSG_SYNC:
                await self._handle_sync_message(stream, message)
            else:
                self.logger.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling DCUtR protocol: {e}")
        finally:
            if hasattr(stream, 'close'):
                await stream.close()
    
    async def _handle_connect_message(self, stream, message):
        """Handle incoming CONNECT message."""
        remote_addrs = message.get("addrs", [])
        
        # Send our addresses in response
        response = self._create_connect_response(self._get_local_addrs())
        await stream.write(response)
        
        # Initiate hole punch from our side
        remote_peer_id = str(stream.remote_peer_id) if hasattr(stream, 'remote_peer_id') else None
        if remote_peer_id:
            # Start hole punch in background
            anyio.from_thread.run_sync(
                self.attempt_hole_punch,
                remote_peer_id,
                "",  # relay not needed here
                None
            )
    
    async def _handle_sync_message(self, stream, message):
        """Handle incoming SYNC message."""
        their_time = message.get("time", time.time())
        our_time = time.time()
        
        # Send sync response
        response = self._create_sync_response(our_time)
        await stream.write(response)
    
    def _get_local_addrs(self) -> List[str]:
        """Get local addresses for hole punching."""
        addrs = []
        if hasattr(self.host, 'get_addrs'):
            for addr in self.host.get_addrs():
                addr_str = str(addr)
                # Filter out relay addresses
                if "p2p-circuit" not in addr_str:
                    addrs.append(addr_str)
        return addrs
    
    def _is_relayed_connection(self, conn) -> bool:
        """Check if a connection is relayed."""
        if hasattr(conn, 'remote_multiaddr'):
            addr_str = str(conn.remote_multiaddr)
            return "p2p-circuit" in addr_str
        return False
    
    def _create_connect_message(self, addrs: List[str]) -> bytes:
        """Create a CONNECT message."""
        import json
        message = {
            "type": self.MSG_CONNECT,
            "addrs": addrs
        }
        return json.dumps(message).encode()
    
    def _parse_connect_response(self, data: bytes) -> Dict[str, Any]:
        """Parse CONNECT response."""
        import json
        try:
            return json.loads(data.decode())
        except:
            return {"status": "ERROR", "message": "Failed to parse"}
    
    def _create_connect_response(self, addrs: List[str]) -> bytes:
        """Create a CONNECT response."""
        import json
        response = {
            "status": "OK",
            "addrs": addrs
        }
        return json.dumps(response).encode()
    
    def _create_sync_message(self, timestamp: float) -> bytes:
        """Create a SYNC message."""
        import json
        message = {
            "type": self.MSG_SYNC,
            "time": timestamp
        }
        return json.dumps(message).encode()
    
    def _parse_sync_response(self, data: bytes) -> Dict[str, Any]:
        """Parse SYNC response."""
        import json
        try:
            return json.loads(data.decode())
        except:
            return {"status": "ERROR"}
    
    def _create_sync_response(self, timestamp: float) -> bytes:
        """Create a SYNC response."""
        import json
        response = {
            "status": "OK",
            "time": timestamp
        }
        return json.dumps(response).encode()
    
    def _parse_message(self, data: bytes) -> Dict[str, Any]:
        """Parse incoming message."""
        import json
        try:
            return json.loads(data.decode())
        except:
            return {}
    
    def _record_completed_attempt(self, attempt: HolePunchAttempt):
        """Record a completed attempt for metrics."""
        self.completed_attempts.append(attempt)
        
        # Keep only recent attempts
        if len(self.completed_attempts) > 100:
            self.completed_attempts = self.completed_attempts[-100:]
        
        # Update metrics
        if self.enable_metrics and attempt.completed_at:
            durations = [a.duration() for a in self.completed_attempts if a.completed_at]
            if durations:
                self.metrics["avg_duration"] = sum(durations) / len(durations)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get DCUtR metrics."""
        return {
            **self.metrics,
            "active_attempts": len(self.active_attempts),
            "success_rate": (
                self.metrics["attempts_success"] / self.metrics["attempts_total"]
                if self.metrics["attempts_total"] > 0 else 0.0
            )
        }
