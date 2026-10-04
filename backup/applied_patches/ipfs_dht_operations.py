"""
Enhanced DHT Operations Module for IPFS Kit.

This module provides advanced Distributed Hash Table (DHT) operations for IPFS,
enabling more sophisticated network participation and content discovery.

Key features:
- DHT record management (get, put)
- Enhanced content routing
- Peer discovery and routing
- Network health diagnostics
- DHT performance metrics
"""

import anyio
import base64
import hashlib
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ipfs_connection_pool import get_connection_pool

# Set up logging
logger = logging.getLogger("ipfs_dht_operations")

class DHTMessageType(Enum):
    """Types of DHT messages for the IPFS DHT network."""
    PUT_VALUE = "PUT_VALUE"
    GET_VALUE = "GET_VALUE"
    ADD_PROVIDER = "ADD_PROVIDER"
    GET_PROVIDERS = "GET_PROVIDERS"
    FIND_NODE = "FIND_NODE"
    PING = "PING"

class DHTRecord:
    """Represents a record in the DHT."""

    def __init__(
        self,
        key: str,
        value: bytes,
        timestamp: Optional[float] = None,
        signature: Optional[bytes] = None,
        publisher: Optional[str] = None,
    ):
        """
        Initialize a DHT record.

        Args:
            key: The record key
            value: The record value
            timestamp: Optional timestamp for the record
            signature: Optional signature for the record
            publisher: Optional publisher PeerID
        """
        self.key = key
        self.value = value
        self.timestamp = timestamp or time.time()
        self.signature = signature
        self.publisher = publisher

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a dictionary."""
        result = {
            "key": self.key,
            "value": base64.b64encode(self.value).decode("utf-8"),
            "timestamp": self.timestamp,
        }

        if self.signature:
            result["signature"] = base64.b64encode(self.signature).decode("utf-8")

        if self.publisher:
            result["publisher"] = self.publisher

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DHTRecord":
        """Create a record from a dictionary."""
        value = base64.b64decode(data["value"])
        signature = base64.b64decode(data["signature"]) if "signature" in data else None

        return cls(
            key=data["key"],
            value=value,
            timestamp=data.get("timestamp"),
            signature=signature,
            publisher=data.get("publisher"),
        )

class DHTOperations:
    """
    Enhanced DHT Operations for IPFS networking.

    This class provides advanced Distributed Hash Table (DHT) operations,
    enabling sophisticated network participation and content discovery in IPFS.
    """

    def __init__(self, connection_pool=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DHT operations with the specified configuration.

        Args:
            connection_pool: Optional connection pool to use
            config: Configuration options for DHT operations
        """
        self.config = config or {}
        self.connection_pool = connection_pool or get_connection_pool()

        # Default timeout for DHT operations
        self.default_timeout = self.config.get("timeout", 30)

        # DHT performance metrics
        self.performance_metrics = {
            "put_value": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "get_value": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "provide": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "find_providers": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "find_peer": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "query": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "routing_table": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
        }

    def _update_metrics(self, operation: str, duration: float, success: bool) -> None:
        """
        Update performance metrics for an operation.

        Args:
            operation: The operation name
            duration: The operation duration in seconds
            success: Whether the operation was successful
        """
        if operation in self.performance_metrics:
            metrics = self.performance_metrics[operation]
            metrics["count"] += 1
            metrics["total_time"] += duration
            metrics["avg_time"] = metrics["total_time"] / metrics["count"]

            # Update success rate using exponential moving average
            alpha = 0.1  # Weight for new observations
            metrics["success_rate"] = (
                (1 - alpha) * metrics["success_rate"] +
                alpha * (1.0 if success else 0.0)
            )

    def put_value(
        self,
        key: str,
        value: Union[str, bytes],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a value in the DHT.

        This creates or updates a record in the IPFS DHT which can be
        retrieved by other peers using the same key.

        Args:
            key: The key to store the value under
            value: The value to store
            options: Additional options for the put operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Ensure value is bytes
        if isinstance(value, str):
            value = value.encode("utf-8")

        # Create the request body
        params = {
            "arg": key,
            "timeout": str(timeout),
        }

        files = {
            "value": ("data", value),
        }

        # Add optional parameters
        if "verify" in options:
            params["verify"] = "true" if options["verify"] else "false"

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/put", params=params, files=files)
            response_json = response.json()

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("put_value", duration, success)

            if success:
                return {
                    "success": True,
                    "key": key,
                    "responses": response_json,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "key": key,
                    "error": "Failed to put value in DHT",
                    "details": response_json,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("put_value", duration, False)

            return {
                "success": False,
                "key": key,
                "error": f"Error putting value in DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def get_value(
        self,
        key: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a value from the DHT.

        This gets a record from the IPFS DHT by its key.

        Args:
            key: The key to retrieve the value for
            options: Additional options for the get operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": key,
            "timeout": str(timeout),
        }

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/get", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("get_value", duration, success)

            if success:
                response_json = response.json()

                # Extract the value from the responses
                value = None
                responses = response_json if isinstance(response_json, list) else [response_json]

                for resp in responses:
                    if resp.get("Type") == 5 and "Extra" in resp:  # Type 5 is VALUE
                        try:
                            value = base64.b64decode(resp["Extra"])
                            break
                        except:
                            pass

                return {
                    "success": True,
                    "key": key,
                    "value": value,
                    "responses": responses,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "key": key,
                    "error": "Failed to get value from DHT",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("get_value", duration, False)

            return {
                "success": False,
                "key": key,
                "error": f"Error getting value from DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def provide(
        self,
        cid: str,
        recursive: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Announce to the network that we are providing the content with the given CID.

        Args:
            cid: The CID to announce as a provider for
            recursive: Whether to recursively provide the entire DAG
            options: Additional options for the provide operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": cid,
            "recursive": "true" if recursive else "false",
            "timeout": str(timeout),
        }

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/provide", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("provide", duration, success)

            if success:
                response_json = response.json()

                return {
                    "success": True,
                    "cid": cid,
                    "responses": response_json,
                    "recursive": recursive,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Failed to provide CID in DHT",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("provide", duration, False)

            return {
                "success": False,
                "cid": cid,
                "error": f"Error providing CID in DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def find_providers(
        self,
        cid: str,
        num_providers: int = 20,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find peers that are providing the content with the given CID.

        Args:
            cid: The CID to find providers for
            num_providers: Maximum number of providers to find
            options: Additional options for the find providers operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": cid,
            "num-providers": str(num_providers),
            "timeout": str(timeout),
        }

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/findprovs", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("find_providers", duration, success)

            if success:
                response_json = response.json()

                # Extract provider information
                providers = []
                responses = response_json if isinstance(response_json, list) else [response_json]

                for resp in responses:
                    if resp.get("Type") == 4 and "Responses" in resp:  # Type 4 is PROVIDER
                        for provider in resp["Responses"]:
                            providers.append({
                                "id": provider.get("ID"),
                                "addresses": provider.get("Addrs", []),
                            })

                return {
                    "success": True,
                    "cid": cid,
                    "providers": providers,
                    "count": len(providers),
                    "responses": responses,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Failed to find providers in DHT",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("find_providers", duration, False)

            return {
                "success": False,
                "cid": cid,
                "error": f"Error finding providers in DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def find_peer(
        self,
        peer_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find information about a peer by its ID.

        Args:
            peer_id: The ID of the peer to find
            options: Additional options for the find peer operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": peer_id,
            "timeout": str(timeout),
        }

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/findpeer", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("find_peer", duration, success)

            if success:
                response_json = response.json()

                # Extract peer information
                addresses = []
                responses = response_json if isinstance(response_json, list) else [response_json]

                for resp in responses:
                    if resp.get("Type") == 2 and "Responses" in resp:  # Type 2 is PEER_RESPONSE
                        for peer in resp["Responses"]:
                            if peer.get("ID") == peer_id:
                                addresses.extend(peer.get("Addrs", []))

                return {
                    "success": True,
                    "peer_id": peer_id,
                    "addresses": addresses,
                    "responses": responses,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "peer_id": peer_id,
                    "error": "Failed to find peer in DHT",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("find_peer", duration, False)

            return {
                "success": False,
                "peer_id": peer_id,
                "error": f"Error finding peer in DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def query(
        self,
        peer_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find the closest peers to a given peer ID in the DHT.

        Args:
            peer_id: The peer ID to query for
            options: Additional options for the query operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        timeout = options.get("timeout", self.default_timeout)
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": peer_id,
            "timeout": str(timeout),
        }

        try:
            # Call the IPFS API
            response = self.connection_pool.post("dht/query", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("query", duration, success)

            if success:
                response_json = response.json()

                return {
                    "success": True,
                    "peer_id": peer_id,
                    "responses": response_json,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "peer_id": peer_id,
                    "error": "Failed to query DHT",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("query", duration, False)

            return {
                "success": False,
                "peer_id": peer_id,
                "error": f"Error querying DHT: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def get_routing_table(
        self,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get the local node's DHT routing table.

        The routing table contains information about the peers that the local node
        knows about and uses for DHT operations.

        Args:
            options: Additional options for the operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        try:
            # Call the IPFS API
            response = self.connection_pool.post("routing/dht/table")

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("routing_table", duration, success)

            if success:
                routing_table = response.json()

                # Process the routing table
                peers_info = []
                if isinstance(routing_table, dict) and "Buckets" in routing_table:
                    for bucket in routing_table["Buckets"]:
                        for peer in bucket.get("Peers", []):
                            peers_info.append({
                                "id": peer.get("ID"),
                                "connected": peer.get("Connected", False),
                                "agent_version": peer.get("AgentVersion"),
                                "last_useful_at": peer.get("LastUsefulAt"),
                            })

                return {
                    "success": True,
                    "peers": peers_info,
                    "count": len(peers_info),
                    "routing_table": routing_table,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to get DHT routing table",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("routing_table", duration, False)

            return {
                "success": False,
                "error": f"Error getting DHT routing table: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    async def discover_peers_async(
        self,
        bootstrap_peers: Optional[List[str]] = None,
        max_peers: int = 100,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Asynchronously discover peers in the IPFS network.

        This performs an iterative peer discovery by:
        1. Starting with bootstrap peers
        2. Finding closest peers to a random ID
        3. Querying each discovered peer to find more peers

        Args:
            bootstrap_peers: Initial peers to start discovery from
            max_peers: Maximum number of peers to discover
            timeout: Maximum time for discovery in seconds

        Returns:
            Dictionary with discovered peers information
        """
        # Get bootstrap peers if not provided
        if not bootstrap_peers:
            try:
                response = self.connection_pool.post("bootstrap/list")
                if response.status_code == 200:
                    bootstrap_data = response.json()
                    bootstrap_peers = bootstrap_data.get("Peers", [])
                else:
                    bootstrap_peers = []
            except Exception:
                bootstrap_peers = []

        # Set of discovered peer IDs
        discovered_peers: Set[str] = set()

        # Details for each discovered peer
        peer_details: Dict[str, Dict[str, Any]] = {}

        # Peers to process
        peers_to_process: List[str] = []

        # Create a random peer ID to query for
        random_bytes = hashlib.sha256(str(time.time()).encode()).digest()
        query_id = base64.b32encode(random_bytes).decode().lower()[:44]

        # Start with a DHT query for a random ID to find initial peers
        result = self.query(query_id)
        if result["success"]:
            responses = result.get("responses", [])
            if isinstance(responses, list):
                for resp in responses:
                    if "Responses" in resp:
                        for peer in resp["Responses"]:
                            peer_id = peer.get("ID")
                            if peer_id and peer_id not in discovered_peers:
                                discovered_peers.add(peer_id)
                                peer_details[peer_id] = {
                                    "id": peer_id,
                                    "addresses": peer.get("Addrs", []),
                                    "source": "initial_query",
                                }
                                peers_to_process.append(peer_id)

        # Add bootstrap peers if we didn't get enough
        if len(peers_to_process) < 5 and bootstrap_peers:
            # Extract peer IDs from bootstrap multiaddresses
            for addr in bootstrap_peers:
                parts = addr.split("/")
                if len(parts) > 2 and parts[-2] == "p2p":
                    peer_id = parts[-1]
                    if peer_id and peer_id not in discovered_peers:
                        discovered_peers.add(peer_id)
                        peer_details[peer_id] = {
                            "id": peer_id,
                            "addresses": [addr],
                            "source": "bootstrap",
                        }
                        peers_to_process.append(peer_id)

        # Start discovery with timeout
        start_time = time.time()

        async def discover_from_peer(peer_id: str):
            """Discover peers from a specific peer."""
            if len(discovered_peers) >= max_peers:
                return

            if time.time() - start_time > timeout:
                return

            # Query for peers close to this peer
            result = self.query(peer_id)
            if not result["success"]:
                return

            responses = result.get("responses", [])
            new_peers = []

            if isinstance(responses, list):
                for resp in responses:
                    if "Responses" in resp:
                        for peer in resp["Responses"]:
                            new_peer_id = peer.get("ID")
                            if new_peer_id and new_peer_id not in discovered_peers:
                                discovered_peers.add(new_peer_id)
                                peer_details[new_peer_id] = {
                                    "id": new_peer_id,
                                    "addresses": peer.get("Addrs", []),
                                    "source": f"from_{peer_id[:8]}",
                                }
                                new_peers.append(new_peer_id)

                                if len(discovered_peers) >= max_peers:
                                    return

            # Process some of the new peers
            for new_peer_id in new_peers[:3]:  # Limit breadth of search
                await discover_from_peer(new_peer_id)

        # Start processing peers
        tasks = peers_to_process[:5]
        if tasks:
            async with anyio.create_task_group() as task_group:
                for peer_id in tasks:  # Start with a few peers
                    task_group.start_soon(discover_from_peer, peer_id)

        # Return results
        return {
            "success": True,
            "discovered_peers": list(discovered_peers),
            "peer_details": peer_details,
            "count": len(discovered_peers),
            "duration": time.time() - start_time,
        }

    def discover_peers(
        self,
        bootstrap_peers: Optional[List[str]] = None,
        max_peers: int = 100,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Discover peers in the IPFS network (synchronous wrapper).

        Args:
            bootstrap_peers: Initial peers to start discovery from
            max_peers: Maximum number of peers to discover
            timeout: Maximum time for discovery in seconds

        Returns:
            Dictionary with discovered peers information
        """
        try:
            # Run the async method in an event loop
            return anyio.run(
                self.discover_peers_async,
                bootstrap_peers,
                max_peers,
                timeout,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Error discovering peers: {str(e)}",
                "exception": str(e),
            }

    def get_network_diagnostics(
        self,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive diagnostics about the local node's DHT networking.

        This collects information about the DHT routing table, peer connections,
        and network performance metrics.

        Args:
            options: Additional options for the diagnostics

        Returns:
            Dictionary with diagnostic information
        """
        options = options or {}
        start_time = time.time()

        diagnostics = {
            "routing_table": None,
            "swarm_peers": None,
            "bootstrap_list": None,
            "dht_performance": self.performance_metrics,
        }

        # Get routing table
        routing_result = self.get_routing_table()
        if routing_result["success"]:
            diagnostics["routing_table"] = {
                "peer_count": routing_result.get("count", 0),
                "peers": routing_result.get("peers", []),
            }

        # Get connected peers
        try:
            response = self.connection_pool.post("swarm/peers")
            if response.status_code == 200:
                swarm_data = response.json()
                peers = swarm_data.get("Peers", [])
                if isinstance(peers, list):
                    diagnostics["swarm_peers"] = {
                        "count": len(peers),
                        "peers": peers,
                    }
                else:
                    peer_list = []
                    for peer_id, info in peers.items():
                        peer_list.append({
                            "id": peer_id,
                            "info": info,
                        })
                    diagnostics["swarm_peers"] = {
                        "count": len(peer_list),
                        "peers": peer_list,
                    }
        except Exception as e:
            diagnostics["swarm_peers_error"] = str(e)

        # Get bootstrap list
        try:
            response = self.connection_pool.post("bootstrap/list")
            if response.status_code == 200:
                bootstrap_data = response.json()
                diagnostics["bootstrap_list"] = {
                    "count": len(bootstrap_data.get("Peers", [])),
                    "peers": bootstrap_data.get("Peers", []),
                }
        except Exception as e:
            diagnostics["bootstrap_list_error"] = str(e)

        return {
            "success": True,
            "diagnostics": diagnostics,
            "duration": time.time() - start_time,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for DHT operations.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "success": True,
            "metrics": self.performance_metrics,
        }

# Global instance
_instance = None

def get_instance(connection_pool=None, config=None) -> DHTOperations:
    """Get or create a singleton instance of the DHT operations."""
    global _instance
    if _instance is None:
        _instance = DHTOperations(connection_pool, config)
    return _instance
