"""
DHT Controller for the MCP server.

This controller provides an interface to the DHT functionality of IPFS through the MCP API.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Body, Path, Query

# Import the DHT operations
import ipfs_dht_operations

# Configure logger
logger = logging.getLogger(__name__)

class DHTController:
    """
    Controller for DHT operations.

    Handles HTTP requests related to DHT operations and delegates
    the business logic to the DHT operations model.
    """

    def __init__(self, dht_operations=None):
        """
        Initialize the DHT controller.

        Args:
            dht_operations: DHT operations model to use for operations
        """
        self.dht_operations = dht_operations or ipfs_dht_operations.get_instance()
        logger.info("DHT Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Add DHT route for putting values
        router.add_api_route(
            "/ipfs/dht/put",
            self.put_value,
            methods=["POST"],
            summary="Store a value in the DHT",
            description="Store a value in the IPFS DHT which can be retrieved by other peers using the same key",
        )

        # Add DHT route for getting values
        router.add_api_route(
            "/ipfs/dht/get/{key:path}",
            self.get_value,
            methods=["GET"],
            summary="Retrieve a value from the DHT",
            description="Get a record from the IPFS DHT by its key",
        )

        # Add DHT route for providing content
        router.add_api_route(
            "/ipfs/dht/provide",
            self.provide_content,
            methods=["POST"],
            summary="Announce providing content",
            description="Announce to the network that we are providing the content with the given CID",
        )

        # Add DHT route for finding providers
        router.add_api_route(
            "/ipfs/dht/findprovs/{cid}",
            self.find_providers,
            methods=["GET"],
            summary="Find providers for a CID",
            description="Find peers that are providing the content with the given CID",
        )

        # Add DHT route for finding a peer
        router.add_api_route(
            "/ipfs/dht/findpeer/{peer_id}",
            self.find_peer,
            methods=["GET"],
            summary="Find information about a peer",
            description="Find information about a peer by its ID",
        )

        # Add DHT route for querying the DHT
        router.add_api_route(
            "/ipfs/dht/query/{peer_id}",
            self.query_dht,
            methods=["GET"],
            summary="Query the DHT for peers",
            description="Find the closest peers to a given peer ID in the DHT",
        )

        # Add DHT route for getting the routing table
        router.add_api_route(
            "/ipfs/dht/routing/table",
            self.get_routing_table,
            methods=["GET"],
            summary="Get the DHT routing table",
            description="Get the local node's DHT routing table",
        )

        # Add DHT route for discovering peers
        router.add_api_route(
            "/ipfs/dht/peers/discover",
            self.discover_peers,
            methods=["GET", "POST"],
            summary="Discover peers in the network",
            description="Discover peers in the IPFS network using the DHT",
        )

        # Add DHT route for network diagnostics
        router.add_api_route(
            "/ipfs/dht/diagnostics",
            self.get_network_diagnostics,
            methods=["GET"],
            summary="Get DHT network diagnostics",
            description="Get comprehensive diagnostics about the local node's DHT networking",
        )

        # Add DHT route for metrics
        router.add_api_route(
            "/ipfs/dht/metrics",
            self.get_metrics,
            methods=["GET"],
            summary="Get DHT metrics",
            description="Get performance metrics for DHT operations",
        )

        logger.info("DHT Controller routes registered")

    async def put_value(self, key: str = Body(...), value: str = Body(...)) -> Dict[str, Any]:
        """
        Store a value in the DHT.

        Args:
            key: The key to store the value under
            value: The value to store

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Putting value in DHT with key: {key}")
        try:
            result = self.dht_operations.put_value(key=key, value=value)
            return result
        except Exception as e:
            logger.error(f"Error putting value in DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error putting value in DHT: {str(e)}"
            )

    async def get_value(self, key: str) -> Dict[str, Any]:
        """
        Retrieve a value from the DHT.

        Args:
            key: The key to retrieve the value for

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Getting value from DHT with key: {key}")
        try:
            result = self.dht_operations.get_value(key=key)
            return result
        except Exception as e:
            logger.error(f"Error getting value from DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting value from DHT: {str(e)}"
            )

    async def provide_content(
        self, cid: str = Body(...), recursive: bool = Body(False)
    ) -> Dict[str, Any]:
        """
        Announce to the network that we are providing the content with the given CID.

        Args:
            cid: The CID to announce as a provider for
            recursive: Whether to recursively provide the entire DAG

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Providing content with CID: {cid}, recursive: {recursive}")
        try:
            result = self.dht_operations.provide(cid=cid, recursive=recursive)
            return result
        except Exception as e:
            logger.error(f"Error providing content in DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error providing content in DHT: {str(e)}"
            )

    async def find_providers(
        self, cid: str, num_providers: int = Query(20, ge=1, le=100)
    ) -> Dict[str, Any]:
        """
        Find peers that are providing the content with the given CID.

        Args:
            cid: The CID to find providers for
            num_providers: Maximum number of providers to find

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Finding providers for CID: {cid}, num_providers: {num_providers}")
        try:
            result = self.dht_operations.find_providers(
                cid=cid, num_providers=num_providers
            )
            return result
        except Exception as e:
            logger.error(f"Error finding providers in DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error finding providers in DHT: {str(e)}"
            )

    async def find_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Find information about a peer by its ID.

        Args:
            peer_id: The ID of the peer to find

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Finding peer in DHT with ID: {peer_id}")
        try:
            result = self.dht_operations.find_peer(peer_id=peer_id)
            return result
        except Exception as e:
            logger.error(f"Error finding peer in DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error finding peer in DHT: {str(e)}"
            )

    async def query_dht(self, peer_id: str) -> Dict[str, Any]:
        """
        Find the closest peers to a given peer ID in the DHT.

        Args:
            peer_id: The peer ID to query for

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Querying DHT for peer ID: {peer_id}")
        try:
            result = self.dht_operations.query(peer_id=peer_id)
            return result
        except Exception as e:
            logger.error(f"Error querying DHT: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error querying DHT: {str(e)}"
            )

    async def get_routing_table(self) -> Dict[str, Any]:
        """
        Get the local node's DHT routing table.

        Returns:
            Dictionary with operation results
        """
        logger.debug("Getting DHT routing table")
        try:
            result = self.dht_operations.get_routing_table()
            return result
        except Exception as e:
            logger.error(f"Error getting DHT routing table: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DHT routing table: {str(e)}"
            )

    async def discover_peers(
        self,
        bootstrap_peers: List[str] = Body(None),
        max_peers: int = Query(100, ge=1, le=1000),
        timeout: int = Query(60, ge=1, le=300),
    ) -> Dict[str, Any]:
        """
        Discover peers in the IPFS network.

        Args:
            bootstrap_peers: Initial peers to start discovery from
            max_peers: Maximum number of peers to discover
            timeout: Maximum time for discovery in seconds

        Returns:
            Dictionary with discovered peers information
        """
        logger.debug(f"Discovering peers, max: {max_peers}, timeout: {timeout}s")
        try:
            result = self.dht_operations.discover_peers(
                bootstrap_peers=bootstrap_peers, max_peers=max_peers, timeout=timeout
            )
            return result
        except Exception as e:
            logger.error(f"Error discovering peers: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error discovering peers: {str(e)}"
            )

    async def get_network_diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive diagnostics about the local node's DHT networking.

        Returns:
            Dictionary with diagnostic information
        """
        logger.debug("Getting DHT network diagnostics")
        try:
            result = self.dht_operations.get_network_diagnostics()
            return result
        except Exception as e:
            logger.error(f"Error getting DHT network diagnostics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DHT network diagnostics: {str(e)}"
            )

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for DHT operations.

        Returns:
            Dictionary with performance metrics
        """
        logger.debug("Getting DHT performance metrics")
        try:
            result = self.dht_operations.get_metrics()
            return result
        except Exception as e:
            logger.error(f"Error getting DHT metrics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DHT metrics: {str(e)}"
            )
